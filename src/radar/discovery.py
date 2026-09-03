"""Free-source competitor discovery (BRD/VISION.md's FR-2, scoped down and
made honest — see PRD.md's note on this).

Why this doesn't call a paid SERP API: none is used anywhere in this
project (see .env.example — no search API key exists), so discovery is
built on what's actually free:

1. DuckDuckGo text search via `ddgs` (no API key, no cost) — but its
   results are almost always review-aggregator listicles (G2, Zapier,
   Capterra "X alternatives" posts), not the competitors themselves.
2. So one real listicle page gets crawled with the project's existing
   Crawl4AI wrapper (already free, already built).
3. The LLM (already local/free via Ollama) reads that real article and
   extracts the actual named competitors from it.

If the search returns nothing usable, this falls back to asking the LLM
directly from its own general knowledge — clearly weaker grounding, and
labeled as such in the returned suggestions' reasoning.

Every suggestion is exactly that — a suggestion. Nothing here is added to
a scan automatically; the UI always shows these for the user to edit or
confirm first (BRD's FR-3, Competitor Validation Workflow)."""
from __future__ import annotations

import logging

from ddgs import DDGS
from pydantic import BaseModel, Field

from .crawler import crawl_domain
from .llm import LLMClient
from .schemas import CompetitorSuggestion

logger = logging.getLogger(__name__)

_MAX_ARTICLE_CHARS = 8000
_LISTICLE_DOMAIN_BLOCKLIST = {
    # Common review/aggregator sites: good sources of listicle content to
    # crawl, but never valid competitor domains themselves.
    "g2.com",
    "capterra.com",
    "producthunt.com",
    "reddit.com",
    "youtube.com",
    "wikipedia.org",
    "medium.com",
    "quora.com",
}


class _ExtractedCompetitors(BaseModel):
    competitors: list[CompetitorSuggestion] = Field(default_factory=list)


_SYSTEM_PROMPT = """You are extracting real competitor company names from an
article that discusses alternatives/competitors to a specific company.

Rules:
- Only list real, distinct companies or products actually named in the
  article text below.
- Do NOT include the company the article is about, or the publisher of the
  article itself (e.g. if this is a G2 or Zapier article, do not list
  "G2" or "Zapier" as a competitor).
- Give a one-line `reasoning` per suggestion grounded in what the article
  actually says about it (not general knowledge).
- Only set `domain` when you're confident of the real domain; leave it
  null otherwise — never guess a domain that might be wrong.
- List at most 8, most-discussed first.
"""


def _host_of(url: str) -> str:
    host = url.split("/")[2] if "//" in url else url.split("/")[0]
    return host.replace("www.", "")


def _find_listicle_url(search_results: list[dict], own_domain: str) -> str | None:
    """Two passes over the results: prefer a non-aggregator page first, but
    the own-domain exclusion is never relaxed in either pass — the user's
    own site is never a valid "competitor listicle" to crawl, unlike a
    blocklisted aggregator, which is still real (if lower-quality) content."""
    own_host = _host_of(own_domain) if "//" in own_domain or "." in own_domain else own_domain

    non_own = [r for r in search_results if r.get("href") and own_host not in _host_of(r["href"])]
    if not non_own:
        return None

    for result in non_own:
        if not any(blocked in _host_of(result["href"]) for blocked in _LISTICLE_DOMAIN_BLOCKLIST):
            return result["href"]

    # everything remaining is blocklisted — still real content, just deprioritized
    return non_own[0]["href"]


async def discover_competitors(
    own_domain: str, own_company_name: str | None, llm: LLMClient
) -> list[CompetitorSuggestion]:
    query_name = own_company_name or own_domain

    try:
        search_results = list(DDGS().text(f"{query_name} alternatives competitors", max_results=6))
    except Exception as exc:  # noqa: BLE001 — free search has no uptime guarantee
        logger.warning("Free web search failed, falling back to LLM knowledge only: %s", exc)
        search_results = []

    if not search_results:
        return _llm_knowledge_fallback(query_name, llm)

    listicle_url = _find_listicle_url(search_results, own_domain)
    if not listicle_url:
        return _llm_knowledge_fallback(query_name, llm)

    pages, error = await crawl_domain(listicle_url, max_pages=1)
    if not pages:
        logger.warning("Could not crawl candidate listicle %s: %s", listicle_url, error)
        return _llm_knowledge_fallback(query_name, llm)

    article_text = next(iter(pages.values()))[:_MAX_ARTICLE_CHARS]
    prompt = (
        f"Company: {query_name}\nSource article: {listicle_url}\n\n"
        f"Article text:\n{article_text}\n\n"
        "Extract the real named competitors from this article."
    )
    result = llm.complete(system=_SYSTEM_PROMPT, prompt=prompt, schema=_ExtractedCompetitors)

    if not result.competitors:
        return _llm_knowledge_fallback(query_name, llm)

    return result.competitors


def _llm_knowledge_fallback(query_name: str, llm: LLMClient) -> list[CompetitorSuggestion]:
    """Used only when free search/crawl produced nothing usable. Weaker
    grounding than the article-based path — every suggestion says so."""
    prompt = (
        f"Company: {query_name}\n\n"
        "No search results or articles were available. Based only on your own general "
        "knowledge, suggest real, well-known competitors of this company. If you don't "
        "recognize this company at all, return an empty list rather than guessing."
    )
    result = llm.complete(system=_SYSTEM_PROMPT, prompt=prompt, schema=_ExtractedCompetitors)
    for suggestion in result.competitors:
        suggestion.reasoning = f"[from general knowledge, not a live source] {suggestion.reasoning}"
    return result.competitors
