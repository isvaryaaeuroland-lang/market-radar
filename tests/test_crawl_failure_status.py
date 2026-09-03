"""Requires real network access — run explicitly with: pytest -m network

Verifies the actual bug report: a domain that can't be resolved must come
back with a clear error, not silently succeed with zero pages."""
import pytest

from radar.crawler import crawl_domain


@pytest.mark.network
@pytest.mark.asyncio
async def test_unresolvable_domain_returns_pages_empty_and_error_set():
    pages, error = await crawl_domain("this-domain-should-not-exist-abc123xyz.com")
    assert pages == {}
    assert error is not None
