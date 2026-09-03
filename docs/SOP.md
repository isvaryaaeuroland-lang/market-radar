# SOP — Autonomous Competitor & Market Radar

Day-to-day procedures for building, running, testing, and demoing this project.

---

## 1. One-time environment setup

```bash
cd "01-competitor-market-radar"
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # one-time browser download for Crawl4AI
cp .env.example .env          # then fill in .env — see §2
```

Confirm Ollama is running and has the required models:

```bash
ollama list   # should show qwen2.5:14b-instruct-q4_K_M and nomic-embed-text at minimum
```

If a model is missing: `ollama pull qwen2.5:14b-instruct-q4_K_M`

## 2. Configuration (`.env`)

| Variable | Required | Notes |
|---|---|---|
| `LLM_PROVIDER` | No (defaults to `ollama`) | `ollama` or `openai_compat` |
| `OLLAMA_BASE_URL` | No (defaults to `http://localhost:11434`) | |
| `OLLAMA_MODEL` | No (defaults to `qwen2.5:14b-instruct-q4_K_M`) | |
| `OPENAI_COMPAT_BASE_URL` | Only if `LLM_PROVIDER=openai_compat` | e.g. Groq/Together/OpenRouter endpoint |
| `OPENAI_COMPAT_API_KEY` | Only if `LLM_PROVIDER=openai_compat` | **Never paste this into chat with Claude — put it directly in your local `.env` file.** |
| `OPENAI_COMPAT_MODEL` | Only if `LLM_PROVIDER=openai_compat` | |
| `SLACK_WEBHOOK_URL` | No (alerts silently no-op without it) | For v1.5 alerting |

`.env` is gitignored. `.env.example` documents the shape without real values.

## 3. Running the app

```bash
source .venv/bin/activate
streamlit run src/app.py
```

Opens a local web UI: enter your domain + competitor URLs, run a scan, view the matrix/brief, export.

## 4. Running the continuous monitoring daemon (v1.5)

```bash
source .venv/bin/activate
python -m radar.scheduler_daemon
```

Runs in the foreground, re-crawling the saved watchlist on the configured interval and firing Slack alerts on material changes. For a demo, set the interval to a few minutes rather than a week so a change actually fires within the demo window.

## 5. Adding a competitor to the watchlist

Done through the Streamlit UI's "Watchlist" tab, or directly:

```bash
python -m radar.cli add-watchlist --domain example.com --competitor competitor-a.com --competitor competitor-b.com
```

## 6. Running tests

```bash
source .venv/bin/activate
pytest                      # fast tests only — no network, no LLM calls
pytest -m llm               # slow tests that call the running Ollama instance
pytest -m network           # slow tests that need real internet access (no LLM)
```

## 7. Demo procedure (interview-safe)

1. **Never crawl live during the actual interview.** Live sites break, rate-limit, or render layout-shifted mid-demo.
2. Before the interview, run one full crawl against the agreed public demo niche and let it complete cleanly — this becomes the **golden run**, saved under `data/snapshots/`.
3. Demo flow: open the Streamlit app pointed at the golden run's data → walk through the matrix and brief → then separately show the pipeline code and explain the crawl → extract → synthesize → diff stages without re-running them live.
4. If asked to show it "actually working," a **short, pre-tested** live run against 1–2 pages (not the full competitor set) is lower-risk than a full live run — decide in advance which one or two pages are reliable enough to risk live.

## 8. Data hygiene

- `data/` (snapshots + `radar.db`) is gitignored — it's working output, not source.
- Never add real Euroland/employer URLs, or any client-confidential data, to the watchlist. Public SaaS companies' own marketing/pricing pages only.
- `.env` is gitignored. If a `.env` is ever accidentally staged, unstage it before any commit — check `git status` before committing.

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ConnectionError` to `localhost:11434` | Ollama not running | `ollama serve` (or open the Ollama app) |
| A domain shows "Not stated" everywhere with no explanation | You're on a version before v1.1 — this was the original "coco cola" bug | Update; the "Scan status" panel now always shows per-domain success/failure and the resolved domain that was actually attempted |
| A plain company name resolves to the wrong domain | `normalize_company_input()` is a best-effort guess (spaces removed, `.com` appended), not a real name resolver | Just retype the real domain directly (e.g. `coca-cola.com`) — the UI always shows what was actually attempted so a wrong guess is obvious immediately |
| Extraction returns mostly `missing_fields` | Site is JS-heavy and Crawl4AI got an empty shell, OR the page genuinely doesn't cover those fields | Check the cached raw page in the snapshot to see what was actually fetched; `missing_fields` is now computed from the real extraction result, not the model's self-report, so it should be trustworthy — if it disagrees with what's visibly on the page, that's a real bug, not a calibration issue |
| Extraction call is very slow (1–2+ minutes) or times out | Ollama generating a long structured response (many pricing tiers), or `num_predict`/`num_ctx` too tight for the content | See TRD §11.2 for the full debugging story; current settings (`num_predict=6000`, `num_ctx=8192`, 300s client timeout) were tuned against a real 5-tier pricing page — if a future site needs more, raise `num_predict` first, not `num_ctx` (raising context didn't fix anything in testing and measurably slowed every call) |
| A JSON parse error mentions "Unterminated string" | The response got cut off mid-generation — almost certainly hit `num_predict` | Same as above — this is a length-cap issue, not a validation-logic bug |
| Crawl4AI hangs or times out | Site blocking bots / slow response (seen: Asana's `/pricing` page once took 130s to fetch) | Lower to a single page for that domain, or exclude it from the demo set |
| Diff agent flags everything as material | Diff prompt not distinguishing wording changes from substantive ones | Tighten the diff-agent prompt with more few-shot examples of cosmetic vs. material changes (see `tests/test_diff_agent.py` for the target cases) |
| A failed domain shows a full SWOT with plausible-looking content anyway | Testing found the synthesis agent will fill in a real company's SWOT from background knowledge if its (empty) profile ever reaches synthesis | Should not happen as of v1.1 — `run_market_scan` now excludes any domain with `pages_fetched == 0` from synthesis entirely. If you see this, it's a regression: check `pipeline.py`'s snapshot-filtering logic first |
| Code changes don't seem to take effect in the running Streamlit app | Streamlit's autoreload re-executes `app.py` but doesn't always deeply reload already-imported nested package modules (`radar.pipeline`, `radar.crawler`, etc.) | Stop and restart the Streamlit process rather than trusting hot-reload after editing anything under `src/radar/` — seen firsthand during testing, where a stale process produced a confusing `too many values to unpack` error that a fresh restart resolved immediately |
