# TRD — Autonomous Competitor & Market Radar

**Status:** v1.1, revised after real-world testing (see §11)
**Companion to:** `PRD.md`

---

## 1. Environment (confirmed on this machine)

| | |
|---|---|
| Python (project venv) | 3.12.9 (`/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12`) — chosen over the system 3.14 because Crawl4AI/Playwright's dependency chain is more reliably prebuilt for 3.12 |
| LLM runtime | Ollama, already running locally at `http://localhost:11434`, models already pulled: `qwen2.5:14b-instruct-q4_K_M` (primary, instruction-tuned, used for structured extraction/synthesis), `qwen3:14b` (alternate/fallback), `nomic-embed-text` / `bge-m3` (embeddings, reserved for the RAG mini-project) |
| Crawling | Crawl4AI (open-source, self-hosted, needs a one-time Playwright browser install) |
| UI | Streamlit |
| Network | Confirmed outbound access (pypi reachable) |

## 2. LLM abstraction layer

Two backends behind one interface, so the rest of the codebase never calls Ollama or an API directly:

```
LLMClient (protocol)
 ├── complete(system, prompt, schema: type[BaseModel]) -> BaseModel   # schema-constrained JSON output
 └── embed(texts: list[str]) -> list[list[float]]
```

- **`OllamaClient`** (default) — talks to `localhost:11434`, uses Ollama's structured-output mode (JSON schema passed via the `format` parameter) against `qwen2.5:14b-instruct-q4_K_M`. No API key, fully local.
- **`OpenAICompatClient`** — talks to any OpenAI-compatible chat-completions endpoint (Groq, Together, Fireworks, OpenRouter, etc.) serving an open-source model (Qwen/Llama/Gemma family), selected via `.env`. Same schema-constrained interface (uses tool-calling or `response_format` depending on provider support), for when you want faster/higher-throughput runs than local inference gives you.
- **`factory.get_llm_client()`** reads `LLM_PROVIDER` from `.env` (`ollama` default, or `openai_compat`) and returns the matching client. Every agent module depends only on the `LLMClient` protocol — swapping providers never touches agent code, which is the whole point of building it this way (and a good interview talking point: providers are a config concern, not an architecture concern).

Both clients validate their output against a Pydantic model before returning it — if the model returns malformed JSON, the client retries once with the validation error fed back into the prompt, then raises a typed `ExtractionError` rather than silently passing bad data downstream.

## 3. Data model (`schemas.py`)

```python
class PricingTier(BaseModel):
    name: str
    price: str | None          # kept as string: "$29/mo", "Custom", "Free" — normalizing currency is a non-goal
    billing_period: str | None
    key_inclusions: list[str]

class CompanyProfile(BaseModel):
    domain: str
    company_name: str | None
    value_proposition: str | None
    target_icp: str | None
    pricing_tiers: list[PricingTier]
    features: list[str]
    extracted_at: datetime
    source_pages: list[str]     # URLs actually used, for traceability
    extraction_confidence: Literal["high", "medium", "low"]
    missing_fields: list[str]   # explicit, not silently blank

class CrawlSnapshot(BaseModel):
    id: str                     # {domain}_{timestamp}
    profile: CompanyProfile
    raw_pages: dict[str, str]   # url -> markdown, cached for re-extraction/debugging

class DiffResult(BaseModel):
    domain: str
    previous_snapshot_id: str
    current_snapshot_id: str
    changes: list[ChangeItem]
    has_material_change: bool

class ChangeItem(BaseModel):
    field: str                  # e.g. "pricing_tiers[1].price"
    before: str
    after: str
    classification: Literal["material", "cosmetic"]
    reasoning: str
```

## 4. Pipeline architecture

```
                ┌─────────────┐
 domain list →  │ Crawl Agent │  Crawl4AI: fetch pricing/features/homepage pages → markdown
                └──────┬──────┘
                       ▼
                ┌──────────────────┐
                │ Extraction Agent │  LLM(schema=CompanyProfile) per company
                └──────┬───────────┘
                       ▼
                ┌───────────────────┐
                │  Synthesis Agent  │  N CompanyProfiles → parity matrix + SWOT brief
                └──────┬────────────┘
                       ▼
              ┌─────────────────────┐
              │ Storage (snapshot)  │  JSON file + SQLite index row
              └──────┬──────────────┘
                      │  (v1.5, on scheduled re-run)
                      ▼
                ┌─────────────┐
                │ Diff Agent  │  previous vs current snapshot → DiffResult
                └──────┬──────┘
                       ▼
                ┌───────────────┐
                │ Alert Dispatch │  Slack webhook, only if has_material_change
                └────────────────┘
```

This is deliberately **not** built on a heavyweight agent framework (LangGraph, CrewAI, etc.) — it's plain Python functions chained by a `pipeline.py` orchestrator. For a 3–5 stage linear pipeline, a framework adds indirection without adding capability, and "I can explain exactly what happens at every step" is worth more in an interview than "I used the trendy framework." If a genuinely branching/looping agent workflow shows up later (the PRD Copilot's planner/writer/critic loop does), that's a more legitimate case for one — worth revisiting there, not here.

## 5. Storage

- `data/snapshots/{domain}/{timestamp}.json` — full `CrawlSnapshot` (profile + raw pages), one file per crawl. Human-inspectable, easy to demo ("here's literally what the system saw").
- `data/radar.db` — a two-table SQLite index: `snapshots(domain, timestamp, snapshot_path)` and `watchlist(domain, is_own_company, added_at)`. Used only to answer "what's the latest/previous snapshot for domain X" — not a general-purpose database, kept intentionally thin.

## 6. Scheduling & alerting

- `scheduler.py` wraps APScheduler's `BackgroundScheduler`, one job per watchlist, interval configurable (default weekly, overridable to minutes for demo purposes).
- `scheduler_daemon.py` is a standalone script (`python -m radar.scheduler_daemon`) that runs the scheduler continuously — this is the "Continuous Monitoring Daemon" from the original concept, runnable independently of the Streamlit UI.
- Alerts: a small `alerts/` module with a `Notifier` protocol and a `SlackNotifier` implementation (incoming webhook URL from `.env`). Email is documented as a drop-in second implementation, not built in v1 unless needed for the demo.

## 7. Export

`export.py` renders the parity matrix + SWOT brief to Markdown directly (Python string templating over the Pydantic models — no templating engine needed for this shape of content), then optionally to PDF via a Markdown→PDF pass (`markdown` + `weasyprint`, or `reportlab` if `weasyprint`'s system dependencies prove troublesome on this machine — decided at implementation time based on what installs cleanly).

## 8. Testing strategy

- `tests/fixtures/*.html` — 2–3 saved real pricing-page HTML snapshots (captured once, checked in) so extraction and diff logic can be unit-tested **without hitting the network or an LLM** on every run.
- `tests/test_schemas.py` — Pydantic validation edge cases (missing fields, malformed pricing).
- `tests/test_diff_agent.py` — given two known snapshots, assert the classification (material/cosmetic) matches expectation. This is the one component worth the most test rigor per the PRD's risk register.
- `tests/test_storage.py` — snapshot write/read round-trip, "latest previous snapshot" lookup logic.
- LLM-calling code paths (extraction, synthesis, diff classification) get integration-style tests that are **skipped by default** (marked `@pytest.mark.llm`) and only run explicitly, since they're slow and depend on Ollama being up.

## 9. Project structure

```
01-competitor-market-radar/
├── docs/
│   ├── PRD.md
│   ├── TRD.md
│   └── SOP.md
├── src/
│   └── radar/
│       ├── __init__.py
│       ├── config.py
│       ├── schemas.py
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── ollama_client.py
│       │   ├── openai_compat_client.py
│       │   └── factory.py
│       ├── crawler.py
│       ├── agents/
│       │   ├── extraction_agent.py
│       │   ├── synthesis_agent.py
│       │   └── diff_agent.py
│       ├── storage.py
│       ├── pipeline.py
│       ├── scheduler.py
│       ├── scheduler_daemon.py
│       ├── alerts/
│       │   └── slack.py
│       └── export.py
│   └── app.py
├── tests/
│   ├── fixtures/
│   ├── test_schemas.py
│   ├── test_diff_agent.py
│   └── test_storage.py
├── data/                  (gitignored — snapshots + sqlite db)
├── .env.example
├── requirements.txt
└── README.md
```

## 10. Open items resolved

| Decision | Resolution |
|---|---|
| LLM provider | Ollama local (default) + OpenAI-compatible hosted open-source fallback, behind one interface |
| Crawling | Crawl4AI |
| UI | Streamlit |
| Test domain | User-supplied (public SaaS niche, 3–5 competitor URLs) — supplied when we reach the crawl-testing milestone |
| Agent framework | None — plain orchestrated Python, deliberately |
| Database | SQLite index + JSON snapshot files, not a full DB server |

## 11. Findings from real-world testing (v1.1)

The first real user test (typing "coco cola" and "pepsi" instead of domains) surfaced problems that unit tests alone hadn't caught — expected, since they require actual network/LLM behavior. Each is a real, reproduced bug, not a hypothetical.

### 11.1 Plain company names silently produced an empty result

**Symptom:** entering "coco cola" / "pepsi" (not domains) rendered a matrix of "Not stated" everywhere with no explanation.

**Root cause:** `_normalize_domain` only prepended `https://` — it never handled a name with spaces and no TLD. `"coco cola"` became the invalid URL `https://coco cola`, which failed to resolve. The failure was swallowed (by design, per FR-11 — one bad domain shouldn't kill a scan) but never surfaced anywhere the user could see it.

**Fix:**
- `normalize_company_input()` (`crawler.py`) makes a best-effort guess for plain names (strip spaces, lowercase, append `.com`) — explicitly **not** a real name-to-domain resolver (that needs a search API, which is the exact thing PRD §4.3 already defers as unreliable). It's a convenience for the common typo case, not a promise of correctness.
- `DomainScanStatus` (new schema) is returned alongside the brief for every input — resolved domain, success, pages fetched, confidence, and a **human-readable** error (crawl4ai's raw error text is a multi-line traceback; `_clean_error_message()` maps common cases like `ERR_NAME_NOT_RESOLVED` to a plain sentence). The UI renders this as a status list before the matrix, so a failed domain is loud, not silent.
- `crawl_domain()` now returns `(pages, error)` instead of just `pages`, and wraps the whole crawl in try/except — some failures (DNS errors) raise instead of setting `.success = False` on the result object.

### 11.2 Extraction was unreliable even when the crawl succeeded

Testing against real sites (Basecamp, Asana) surfaced two distinct correctness bugs the "coco cola" fix didn't touch:

**Bug A — confident emptiness.** Given Basecamp's pricing page (unambiguous: 5 tiers, clear prices, bullet lists), extraction once returned a completely empty profile while self-reporting `extraction_confidence: "high"`. The prompt's instruction ("set confidence based on how clearly the pages state it") was simply not a reliable signal — the model's self-assessment didn't track its own output.

**Bug B — degenerate generation.** `missing_fields` (originally a free `list[str]`) once contained ~70 invented, nonsensical entries (`"company_funding_rounds_details_count_count"`, etc.) that aren't part of the schema at all. Constraining it to an enum (`MissingField` in `schemas.py`) stopped the *invented names*, but testing then caught the same failure in a different shape: the model got stuck repeating one *valid* enum value (`"company_name"`) hundreds of times, burning the entire output budget and truncating the response mid-JSON.

**Root cause, once actually captured (see debugging note below) — not context truncation, despite first appearances:** raising `num_ctx` from Ollama's 4096 default to 16384 didn't fix anything; the response kept truncating at the exact same byte offset regardless, which ruled out input-context truncation and pointed at `num_predict` (the output cap) instead. The real fix wasn't a bigger cap — it was removing the reason for the degeneration to happen at all.

**Fix — stop asking the LLM to grade itself:**
- `extraction_agent.py` now asks the LLM for a separate, narrower `_ExtractionResult` schema — just the five substantive fields (`company_name`, `value_proposition`, `target_icp`, `pricing_tiers`, `features`). No `extraction_confidence`, no `missing_fields` in that schema at all.
- `missing_fields` and `extraction_confidence` on the final `CompanyProfile` are always computed in code (`_actual_missing_fields`, `_confidence_from_missing`) from what the extraction result actually contains — the same "don't trust the LLM with what code can verify" principle used in every other project in this portfolio.
- A genuinely empty-looking result (no value prop, no pricing, no features) triggers exactly one retry with a more directive prompt before being accepted, since an empty result despite non-empty source pages is more likely a miss than a true absence.
- `ollama_client.py`: `temperature` lowered to `0.0` (was `0.1`), `num_predict` capped at `6000` (a backstop against genuine runaway generation, not a normal-case constraint — 2048 was tried first and was wrong, since a company with 5 detailed pricing tiers legitimately needs more than that), `num_ctx` raised to `8192` (modest headroom, not 16384 — that measurably slowed every call without fixing anything), and the client timeout raised to `300s` to match.

**Verification:** re-ran extraction against the actual Basecamp pricing page (same content, captured from a real snapshot) after each change. Before: empty profile / `"high"` confidence, or a 180s timeout, or truncated JSON at a suspiciously consistent byte offset. After: all 5 tiers extracted correctly (names, prices, billing periods, inclusions) in ~33s, with confidence honestly reported as `"medium"` (2 of 5 fields — `value_proposition`, `target_icp` — genuinely weren't on that page).

### 11.3 Crawling was sequential; now concurrent

`run_market_scan` crawled each domain one at a time in a `for` loop. Since each domain is an independent headless-browser crawl with no shared state, this was pure wasted wall-clock time for a 4–6 domain scan. Changed to `asyncio.gather(...)` so all domains crawl concurrently — the scan's total time is now bounded by the slowest single domain, not the sum of all of them.

### 11.4 A failed domain's empty profile still reached synthesis — and got hallucinated over

Fixing §11.1 and §11.2 wasn't the end of it: once "coco cola" correctly failed to crawl (0 pages, clean error message) and "pepsi" correctly succeeded, running both together through the live UI produced a full SWOT for **"cococola.com" anyway** — "brand recognition and loyalty," "intense competition from PepsiCo" — content the (empty) profile could not possibly have supplied. The synthesis LLM recognized the domain name and filled in the SWOT from its own training knowledge of the real Coca-Cola brand, directly violating the "grounded only in provided profiles" instruction it was given.

**Root cause:** `run_market_scan` appended every non-exception `scan_one_domain` result to `snapshots` regardless of whether anything was actually fetched — a domain with 0 pages produces a *valid* (schema-wise) but entirely empty `CompanyProfile`, which was passed into `synthesize_market_brief` right alongside the real one.

**Fix:** snapshots are now filtered by `status.success` before synthesis — a domain with zero pages fetched never reaches the synthesis prompt at all, only the "Scan status" panel. The synthesis prompt was also hardened as defense-in-depth (explicit: "this applies even to companies you recognize by name... never what you already know about the real company"), for the case where a *partial* but famous-brand profile might tempt the same failure.

**Verification:** re-ran the exact "coco cola" + "pepsi" scenario through the live UI after the fix. The failed domain no longer appears anywhere in the matrix/SWOT/narrative; PepsiCo's own genuine data gaps are now labeled "insufficient data extracted to assess" instead of guessed, and the narrative honestly states the comparison is incomplete due to missing Coca-Cola data — exactly the honest degradation this tool is supposed to produce under partial information.
