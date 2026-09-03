import pytest

from radar.discovery import _find_listicle_url, discover_competitors
from radar.llm import get_llm_client

FAKE_RESULTS = [
    {"href": "https://www.g2.com/products/notion/competitors/alternatives", "title": "G2 listicle"},
    {"href": "https://notion.so/some-page", "title": "Notion's own site"},
    {"href": "https://zapier.com/blog/best-notion-alternatives/", "title": "Zapier listicle"},
    {"href": "https://www.reddit.com/r/notion/comments/xyz", "title": "Reddit thread"},
]


def test_own_domain_is_excluded():
    url = _find_listicle_url(FAKE_RESULTS, "notion.so")
    assert "notion.so" not in url


def test_blocklisted_aggregators_are_deprioritized():
    url = _find_listicle_url(FAKE_RESULTS, "notion.so")
    assert url == "https://zapier.com/blog/best-notion-alternatives/"


def test_falls_back_to_first_result_when_everything_is_blocklisted_or_own_domain():
    only_bad = [
        {"href": "https://notion.so/x", "title": "own"},
        {"href": "https://www.g2.com/x", "title": "g2"},
    ]
    url = _find_listicle_url(only_bad, "notion.so")
    assert url == "https://www.g2.com/x"


def test_empty_results_returns_none():
    assert _find_listicle_url([], "notion.so") is None


@pytest.mark.network
@pytest.mark.llm
def test_discover_competitors_finds_real_named_competitors():
    """Requires internet + Ollama — run explicitly with: pytest -m 'network and llm'"""
    import asyncio

    llm = get_llm_client()
    suggestions = asyncio.run(discover_competitors("notion.so", "Notion", llm))

    assert suggestions, "expected at least one suggestion from a real search + crawl"
    names = {s.name.lower() for s in suggestions}
    # Not asserting an exact name (search results vary run to run) — asserting
    # the suggestions are real known productivity tools, not the article's own
    # publisher (g2, zapier, etc.) or Notion itself.
    assert "notion" not in names
    assert not ({"g2", "zapier", "capterra"} & names)
    assert all(s.reasoning for s in suggestions)
