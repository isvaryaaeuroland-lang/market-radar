"""Crawl4AI wrapper: given a domain, fetch the homepage plus a handful of
likely pricing/features/product pages, and return raw markdown per URL.

Deliberately conservative: a handful of pages per domain, not a full-site
crawl, and any single page failing does not fail the whole domain (PRD FR-11).
"""
from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler

logger = logging.getLogger(__name__)


def normalize_company_input(raw: str) -> str:
    """Best-effort turn whatever the user typed into something fetchable.

    Handles three cases:
    - Already a URL ("https://acme.com/pricing") -> used as-is (path kept,
      _normalize_domain below only adds a scheme, it doesn't strip paths).
    - Already a bare domain ("acme.com") -> used as-is.
    - A plain company name ("Coco Cola", "coco cola") -> collapsed to a
      slug and given a ".com" TLD as a guess: "cococola.com".

    This is deliberately NOT a real company-name-to-domain resolver — that
    would need a search API, which the PRD explicitly defers (see PRD §4.3,
    "Market Discovery Agent") because third-party search quality made it the
    least reliable part of the whole concept. This is a much smaller,
    honest convenience for the common case of typing a brand name with
    spaces and no TLD. It WILL guess wrong for names that don't match their
    literal domain (e.g. "Coca Cola" -> "cocacola.com", not the real
    coca-cola.com) — callers must always show the resolved value back to
    the user rather than trusting the guess silently.
    """
    value = raw.strip()
    if not value:
        return value

    if value.startswith(("http://", "https://")):
        return value.rstrip("/")

    candidate = value.split("/")[0].strip()
    if "." in candidate and " " not in candidate:
        return candidate  # already looks like a real domain

    slug = re.sub(r"[^a-z0-9]", "", candidate.lower())
    return f"{slug}.com" if slug else candidate

# Link text/href keywords that suggest a page worth crawling for competitive
# intel, roughly in priority order.
_CANDIDATE_KEYWORDS = [
    "pricing",
    "plans",
    "price",
    "features",
    "product",
    "solutions",
    "platform",
    "about",
]


def _normalize_domain(domain: str) -> str:
    domain = domain.strip()
    if not domain.startswith(("http://", "https://")):
        domain = f"https://{domain}"
    return domain.rstrip("/")


def _clean_error_message(raw: str) -> str:
    """Crawl4AI's error_message / exception text can be a multi-line
    traceback with source-code context — fine for logs, not for showing a
    user in the UI. Map the common cases to a plain sentence and otherwise
    fall back to just the first line."""
    text = raw or "unknown error"
    if "ERR_NAME_NOT_RESOLVED" in text or "NAME_NOT_RESOLVED" in text:
        return "This domain doesn't exist or can't be resolved (DNS lookup failed)."
    if "ERR_CONNECTION_REFUSED" in text:
        return "Connection refused — the server isn't accepting requests on this domain."
    if "Timeout" in text or "timeout" in text:
        return "The site took too long to respond and the crawl timed out."
    if "ERR_CERT" in text or "SSL" in text:
        return "The site's SSL certificate could not be verified."
    return text.strip().splitlines()[0][:200]


def _score_link(link: dict) -> int:
    href = (link.get("href") or "").lower()
    text = (link.get("text") or "").lower()
    for rank, keyword in enumerate(_CANDIDATE_KEYWORDS):
        if keyword in href or keyword in text:
            return len(_CANDIDATE_KEYWORDS) - rank
    return 0


async def crawl_domain(domain: str, max_pages: int = 4) -> tuple[dict[str, str], str | None]:
    """Returns ({url: markdown}, error). `error` is set only when the
    homepage itself couldn't be fetched at all (bad domain, DNS failure,
    connection refused, etc.) — the one case where the caller has zero
    pages and needs to know *why*, rather than silently getting an empty
    profile later. Individual candidate pages failing after a working
    homepage is not treated as a domain-level error (PRD FR-11: partial
    results, not a hard failure)."""
    base_url = _normalize_domain(domain)
    base_host = urlparse(base_url).netloc
    pages: dict[str, str] = {}

    try:
        async with AsyncWebCrawler() as crawler:
            home_result = await crawler.arun(url=base_url)
            if not home_result.success:
                error = _clean_error_message(home_result.error_message or "homepage could not be fetched")
                logger.warning("Homepage crawl failed for %s: %s", base_url, home_result.error_message)
                return pages, error

            pages[base_url] = str(home_result.markdown)

            internal_links = home_result.links.get("internal", []) if home_result.links else []
            scored = sorted(internal_links, key=_score_link, reverse=True)

            seen = {base_url}
            candidates: list[str] = []
            for link in scored:
                href = link.get("href")
                if not href:
                    continue
                full_url = urljoin(base_url + "/", href)
                if urlparse(full_url).netloc != base_host:
                    continue  # stay on-domain
                if full_url in seen:
                    continue
                if _score_link(link) == 0:
                    continue  # no keyword match — stop taking low-signal links
                seen.add(full_url)
                candidates.append(full_url)
                if len(candidates) >= max_pages - 1:
                    break

            for url in candidates:
                try:
                    result = await crawler.arun(url=url)
                    if result.success:
                        pages[url] = str(result.markdown)
                    else:
                        logger.warning("Skipping %s: %s", url, result.error_message)
                except Exception as exc:  # noqa: BLE001 — one bad page must not kill the domain
                    logger.warning("Skipping %s after exception: %s", url, exc)
    except Exception as exc:  # noqa: BLE001 — e.g. DNS failure raised instead of returned as .success=False
        logger.warning("Crawl raised for %s: %s", base_url, exc)
        return pages, _clean_error_message(str(exc))

    return pages, None


def crawl_domain_sync(domain: str, max_pages: int = 4) -> tuple[dict[str, str], str | None]:
    """Sync wrapper for callers (e.g. Streamlit) that aren't already in an
    event loop."""
    return asyncio.run(crawl_domain(domain, max_pages=max_pages))
