# Autonomous Competitor & Market Radar

Give a product manager, founder, or strategy lead a live, structured view of their competitive landscape, built from nothing but a starting list of URLs — refreshed automatically, and only surfacing an alert when something *actually* changed.

**Docs:** [PRD](docs/PRD.md) · [TRD](docs/TRD.md) · [SOP](docs/SOP.md)

## Status

- ✅ Crawl → structured extraction → parity matrix + SWOT brief → Markdown export (v1 MVP) — built, tested, and verified end-to-end through the UI
- ✅ Snapshot persistence (JSON + SQLite index)
- ✅ Semantic diff (deterministic field-level diff + LLM material/cosmetic classification) — unit-tested and verified against a running Ollama instance
- ✅ Scheduling + Slack alerting (v1.5) — implemented, not yet exercised against a live multi-week watch cycle
- ⏳ PDF export — implemented but optional (`weasyprint`), not yet verified on this machine
- ⏳ Real competitor demo run — pending a chosen public SaaS niche + URLs (see SOP §7)

**v1.1 — real-world testing found and fixed real bugs.** A user test typing "coco cola" / "pepsi" instead of domains produced a matrix of "Not stated" everywhere with zero explanation. Digging into that surfaced two more serious issues underneath it. Full writeup: [TRD §11](docs/TRD.md#11-findings-from-real-world-testing-v11).

1. **Bad input, no feedback.** Plain company names (with spaces, no TLD) produced invalid URLs that silently failed to crawl. Fixed with `normalize_company_input()` (best-effort guess, not a real resolver) plus a `DomainScanStatus` shown for every input — success/failure, pages fetched, and a plain-English error, never silent.
2. **Extraction was unreliable even when the crawl worked.** Given Basecamp's pricing page — unambiguous, 5 tiers, clear prices — extraction once returned a completely empty profile while self-reporting "high" confidence. Root cause: `missing_fields` and `extraction_confidence` were LLM-generated fields the model couldn't actually judge reliably; once, `missing_fields` degenerated into one valid value repeated ~70 times, burning the output budget and truncating the response mid-JSON. Fix: the LLM is no longer asked to grade itself at all — it only fills in the 5 substantive fields it can judge, and confidence/missing-fields are always computed in code from what actually came back. Verified: Basecamp's 5 tiers now extract correctly (right prices, right inclusions) in ~33s with an honestly-reported "medium" confidence for the 2 fields that page genuinely didn't cover.
3. **Crawling was sequential; now concurrent** via `asyncio.gather` — a 4-6 domain scan is bounded by the slowest single domain, not the sum of all of them.
4. **A failed domain's empty profile still reached synthesis — and the LLM filled in a real SWOT from memory.** With "cococola.com" (0 pages fetched) alongside a real pepsi.com profile, the brief confidently listed Coca-Cola's "brand recognition and loyalty" and competition with PepsiCo — the model recognized the name and used background knowledge instead of the (empty) data it was given. Fixed by excluding any domain with zero pages fetched from synthesis entirely (`pipeline.py`), plus a strengthened synthesis prompt that explicitly calls out "even for companies you recognize by name." Re-verified in the live UI: the failed domain now never appears in the brief at all, and PepsiCo's own data gaps are honestly labeled "insufficient data extracted to assess" rather than guessed.

All 27 fast tests pass; every fix above was verified against real captured page content and, for the last two, a real live run through the actual Streamlit UI — not just unit-tested in isolation.

**v1.2 — free-source competitor discovery.** A large BRD/PRD (saved as [VISION.md](docs/VISION.md), not built) specced a full autonomous "Market Discovery Agent" assuming a paid search API. Built a scoped-down, entirely free version instead: DuckDuckGo web search (`ddgs`, no API key) → crawl one real "alternatives to X" article → LLM extracts the actual named competitors from that real text, same grounding discipline as extraction elsewhere in this project. Falls back to the LLM's own general knowledge (clearly labeled as such) if search/crawl comes up empty. Every suggestion shows its reasoning and must be confirmed/edited before a scan runs — never auto-added. One real bug caught live in the UI: setting `st.session_state` for a widget's key after that widget had already rendered in the same script run raised a `StreamlitAPIException` — fixed by moving the discovery-and-rerun logic before the text area's instantiation. Verified end-to-end against `notion.so`: correctly surfaced Trello, Asana, Monday.com, Coda, Confluence, Evernote, Google Workspace, and Microsoft 365, each with a reasoning grounded in the actual crawled article, and domains filled in only when the model was confident of them. Details: [PRD.md §4.3](docs/PRD.md).

## Quickstart

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
crawl4ai-setup   # one-time Playwright browser install
cp .env.example .env
streamlit run src/app.py
```

Full setup, running, testing, and demo procedures: [SOP.md](docs/SOP.md).

## Architecture at a glance

```
[optional] own domain → free web search (ddgs) → crawl one real listicle
                       → LLM extracts named competitors → user confirms/edits

domains → Crawl4AI → per-company markdown
        → Extraction Agent (LLM, schema-constrained) → CompanyProfile
        → Synthesis Agent (LLM) → parity matrix + SWOT + narrative
        → Storage (JSON snapshot + SQLite index)
        → [scheduled] Diff Agent → material vs cosmetic changes → Slack alert
```

Runs entirely on local Ollama by default (`qwen2.5:14b-instruct-q4_K_M`), with an OpenAI-compatible hosted backend as a drop-in swap for a polished demo run. See [TRD.md](docs/TRD.md) for the full design and the reasoning behind each choice (why no agent framework, why SQLite + JSON instead of a full DB, etc.).

## Why this exists

Part of a 10-project AI portfolio built to demonstrate product + technical range for a Product Analyst → PM/Technical PM transition. See `../../AI Portfolio Roadmap.md` for the full plan.
