"""Requires real network + a running Ollama instance — run explicitly with:
pytest -m 'network and llm'

Regression test for a real bug found via manual UI testing: a domain that
fetched zero pages (bad/unresolvable input) still had its empty profile
passed into synthesis, and the LLM filled in a plausible-sounding SWOT for
it using background knowledge of the real company — a direct violation of
"grounded only in the provided profile" for any well-known brand name."""
import pytest

from radar.pipeline import run_market_scan


@pytest.mark.network
@pytest.mark.llm
@pytest.mark.asyncio
async def test_domain_with_zero_pages_fetched_is_excluded_from_the_brief():
    brief, statuses = await run_market_scan("pepsi.com", ["this-domain-should-not-exist-abc123xyz.com"])

    failed_status = next(s for s in statuses if not s.success)
    assert failed_status.pages_fetched == 0

    # The failed domain must never reach the synthesized brief, regardless
    # of whether its resolved name happens to look like a real company.
    assert brief is not None
    assert failed_status.resolved_domain not in brief.companies
    assert "pepsi.com" in brief.companies
