"""Orchestrates the stages in TRD §4. Plain function composition, no agent
framework — see TRD for why that's a deliberate choice, not an oversight."""
from __future__ import annotations

import asyncio
import logging

from .agents import diff_profiles, extract_company_profile, synthesize_market_brief
from .alerts.slack import notify_material_change
from .crawler import crawl_domain, normalize_company_input
from .llm import get_llm_client
from .schemas import CrawlSnapshot, DiffResult, DomainScanStatus, MarketBrief
from .storage import get_latest_snapshot, make_snapshot_id, save_snapshot

logger = logging.getLogger(__name__)


async def scan_one_domain(raw_input: str, max_pages: int = 4) -> tuple[CrawlSnapshot, DomainScanStatus]:
    """Crawl + extract + persist a single input. The unit every other
    operation (a full market scan, or a single watch-cycle re-check) builds
    on. Never raises for a bad/unreachable input — that's a normal, expected
    outcome here, reported via the returned status rather than an exception,
    so one bad domain in a batch doesn't need special-case handling by callers."""
    llm = get_llm_client()
    resolved_domain = normalize_company_input(raw_input)
    pages, error = await crawl_domain(resolved_domain, max_pages=max_pages)
    profile = extract_company_profile(resolved_domain, pages, llm)
    snapshot = CrawlSnapshot(id=make_snapshot_id(resolved_domain), profile=profile, raw_pages=pages)
    save_snapshot(snapshot)

    status = DomainScanStatus(
        input_value=raw_input,
        resolved_domain=resolved_domain,
        success=bool(pages),
        pages_fetched=len(pages),
        extraction_confidence=profile.extraction_confidence,
        missing_fields=profile.missing_fields,
        error=error,
    )
    return snapshot, status


async def run_market_scan(
    own_domain: str, competitor_domains: list[str], max_pages: int = 4
) -> tuple[MarketBrief | None, list[DomainScanStatus]]:
    """PRD FR-1..FR-7: the v1 MVP flow — a full parity matrix + brief across
    the own company and its competitors.

    Returns (brief, statuses). `brief` is None only if every single input
    failed to crawl — callers must check this before rendering results.
    `statuses` always has one entry per input, in the same order, so the UI
    can show exactly what happened for each domain regardless of overall
    success.

    Domains are scanned concurrently (not one at a time) — each is an
    independent headless-browser crawl with no shared state, so there's no
    reason to pay the full latency of N sequential crawls for a 4-6 domain
    scan.
    """
    llm = get_llm_client()
    all_inputs = [own_domain, *competitor_domains]

    results = await asyncio.gather(
        *(scan_one_domain(raw_input, max_pages=max_pages) for raw_input in all_inputs),
        return_exceptions=True,
    )

    snapshots: list[CrawlSnapshot] = []
    statuses: list[DomainScanStatus] = []
    for raw_input, result in zip(all_inputs, results):
        if isinstance(result, BaseException):
            logger.warning("Skipping %s after unexpected failure: %s", raw_input, result)
            statuses.append(
                DomainScanStatus(
                    input_value=raw_input,
                    resolved_domain=normalize_company_input(raw_input),
                    success=False,
                    error=str(result),
                )
            )
            continue
        snapshot, status = result
        statuses.append(status)
        if status.success:
            snapshots.append(snapshot)
        else:
            # A domain that fetched zero pages has an empty CompanyProfile —
            # passing that into synthesis was a real bug found in testing:
            # given "cococola.com" (unresolvable, 0 pages) alongside a real
            # pepsi.com profile, the synthesis LLM filled in a full SWOT for
            # "cococola.com" anyway, using its own background knowledge of
            # the real Coca-Cola brand — a direct violation of "grounded
            # only in the provided profiles." A domain with nothing fetched
            # must never reach the synthesis prompt at all.
            logger.info("Excluding %s from synthesis — nothing was fetched for it.", status.resolved_domain)

    if not snapshots:
        return None, statuses

    profiles = [s.profile for s in snapshots]
    resolved_own_domain = normalize_company_input(own_domain)
    brief = synthesize_market_brief(resolved_own_domain, profiles, llm)
    return brief, statuses


async def run_watch_cycle(domain: str, max_pages: int = 4) -> DiffResult | None:
    """PRD FR-8..FR-10: re-crawl one watchlisted domain, diff against its
    previous snapshot, and fire an alert if the change is material.
    Returns None on the very first run for a domain (no baseline to diff against)."""
    llm = get_llm_client()
    previous = get_latest_snapshot(domain)

    new_snapshot, status = await scan_one_domain(domain, max_pages=max_pages)
    if not status.success:
        logger.warning("Watch cycle for %s could not fetch anything: %s", domain, status.error)

    if previous is None:
        logger.info("No prior snapshot for %s — this run establishes the baseline.", domain)
        return None

    result = diff_profiles(previous.id, new_snapshot.id, previous.profile, new_snapshot.profile, llm)

    if result.has_material_change:
        notify_material_change(domain, result)

    return result
