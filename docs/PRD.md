# PRD — Autonomous Competitor & Market Radar

**Author:** Isvarya Laxmi M (Product) · drafted with Claude acting as technical architect
**Status:** Draft v1.0
**Project:** #4 in the AI Portfolio Roadmap — flagship deep build, Month 1

---

## 1. Problem statement

Conducting competitive analysis is manual, tedious, and goes stale within weeks. Product managers and founders spend days scouring competitor landing pages, pricing grids, changelogs, and review platforms by hand. When a competitor changes their pricing model, ships a disruptive feature, or repositions their messaging, most teams find out weeks or months late — from a lost deal, a customer question, or a stray tweet — not from their own tracking.

The cost isn't just wasted analyst hours. It's the strategic decisions made on stale information: a pricing page that hasn't reflected a competitor's new tier in two months, a feature-gap slide that's already wrong by the time it reaches leadership.

## 2. Goal

Give a product manager, founder, or strategy lead a **live, structured view of their competitive landscape**, built from nothing but a starting list of URLs — refreshed automatically, and only surfacing an alert when something *actually* changed.

## 3. Target users & personas

| Persona | Need | How they'd use it |
|---|---|---|
| **Startup founder** | Can't afford a dedicated competitive-intel analyst | Runs it once a week, gets a brief before the Monday leadership sync |
| **Product manager** | Needs a feature-parity view before a roadmap review | Pulls the parity matrix as a slide input |
| **Strategy/GTM lead** | Needs to react fast to a competitor's pricing change | Gets an alert the day it happens, not the month after |

## 4. Scope

### 4.1 In scope — v1 (MVP, Month 1 weeks 1–3)

- **Manual competitor input.** User supplies their own domain + 3–5 competitor URLs. (Auto-discovery of competitors via search APIs is explicitly deferred — see §7.)
- **Deep-crawl a domain** to extract: value proposition, pricing tiers, core features, target ICP signals.
- **Structured entity extraction** via an LLM pipeline, producing a consistent schema across all crawled companies regardless of how their marketing copy is written.
- **Feature/pricing parity matrix** — a table comparing the user's product against each competitor across a shared set of vectors (pricing model, self-serve vs. sales-led, SSO/enterprise features, API access, notable differentiators).
- **SWOT-style synthesis brief** generated from the matrix.
- **Export** the matrix + brief as Markdown/PDF.
- **Simple web UI** to run a scan, view results, and re-run on demand.

### 4.2 In scope — v1.5 (Month 1 weeks 3–4, same month per the two-speed plan)

- **Scheduled re-crawl** of a saved watchlist (e.g., weekly).
- **Semantic diffing** between the current and previous crawl of each competitor, filtering out noise (copyright-year bumps, whitespace, reworded-but-unchanged copy) and surfacing only *material* changes (new pricing tier, changed price point, new enterprise feature, messaging pivot).
- **Alerting** on a material change via a webhook (Slack or email).

### 4.3 Revised: lightweight competitor discovery (v1.6, added post-launch)

The original plan deferred automatic competitor discovery entirely (see the struck-through note below) because a *paid* search API was assumed to be the only way to do it, and that reliability/cost tradeoff wasn't worth taking on for v1. That assumption turned out to be wrong for a scoped-down version: a genuinely useful, **entirely free** discovery flow shipped instead —

1. Free web search (`ddgs`, DuckDuckGo, no API key) for "`{company}` alternatives/competitors" — but these results are almost always review-aggregator listicles (G2, Zapier, Capterra), not the competitors themselves.
2. One real listicle page gets crawled with the project's existing crawler.
3. The LLM extracts the actual named competitors from that real article — grounded in real text, the same discipline used everywhere else in this project.
4. If search/crawl produces nothing, it falls back to the LLM's own general knowledge, and every such suggestion says so explicitly in its reasoning.

This is deliberately **not** the full "Market Discovery Agent" from BRD/VISION.md's FR-2 — there's no entity resolution, no confidence scoring on the match, no ranking by relevance, and result quality depends entirely on whether a decent "alternatives to X" article exists for that company (works well for known SaaS products, poorly for obscure or non-software companies). Every suggestion is shown to the user with its reasoning and must be confirmed/edited before a scan runs — it never bypasses human validation (BRD's VR-6/FR-3 principle, honored even in this scoped-down form).

~~Explicitly out of scope for v1: Automatic competitor discovery (the "Market Discovery Agent" that finds competitors from a single domain via search APIs). This is the least reliable part of the original concept — it depends on third-party search API quality and is the single biggest source of scope risk. Documented as a v2 roadmap item, not built now.~~ *(Superseded by the free-source version above.)*

### 4.4 Still out of scope

- **Live scraping during a demo/interview.** The product should always be demoable against a cached run. Live crawling of real companies' production sites during a demo is both unreliable (breakage, rate limits, JS rendering) and a ToS/optics risk — see §7.
- **Continuous crawling of arbitrary real companies at scale.** The watchlist is small and user-curated, not an open crawl of the web.
- **The full FR-2 vision** (entity resolution, relevance/confidence scoring, ranked direct/indirect/emerging tiers) — that remains in [VISION.md](VISION.md) as future work, not this build.

## 5. User stories

1. *As a founder*, I want to enter my company's URL and a handful of competitor URLs, so that I get a structured comparison without manually visiting every site.
2. *As a PM*, I want a feature-parity matrix I can drop into a roadmap review, so that I don't have to build one from scratch every quarter.
3. *As a strategy lead*, I want to know within a week when a competitor changes their pricing, so that I'm not the last to find out.
4. *As any of the above*, I want the system to tell me *why* something is flagged, not just that it changed, so that I can trust the alert instead of re-checking manually.
5. *As a user re-running a scan*, I want previous results saved, so that a rerun shows me what's new rather than starting cold.

## 6. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | User can input their own domain + 3–5 competitor domains | P0 |
| FR-2 | System crawls each domain's marketing/pricing pages (multi-page within a domain, not full-site crawl) | P0 |
| FR-3 | System extracts a structured record per company: value prop, pricing tiers (name, price, billing period, key inclusions), feature list, target ICP signals | P0 |
| FR-4 | System renders a feature/pricing parity matrix across all crawled companies | P0 |
| FR-5 | System generates a SWOT-style narrative brief from the matrix | P0 |
| FR-6 | User can export the matrix + brief as Markdown and PDF | P0 |
| FR-7 | System stores crawl results with a timestamp, so repeat runs are comparable | P0 |
| FR-8 | System can be scheduled to re-crawl a saved watchlist on an interval | P1 |
| FR-9 | System diffs consecutive crawls per competitor and classifies each change as material / cosmetic | P1 |
| FR-10 | System sends an alert (Slack webhook or email) only for material changes, with a plain-English summary of what changed | P1 |
| FR-11 | System handles crawl failures (site down, blocked, JS-only content) gracefully — partial results, not a hard failure | P0 |

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Auto-discovery of competitors is unreliable | Deferred to v2; v1 takes a user-supplied list |
| Scraping real companies' sites raises ToS/legal optics, especially if continuous | v1.5's scheduled watchlist stays small and user-curated (not a broad crawl); demos always run against a cached result, never live; robots.txt is respected and crawl rate is conservative |
| Semantic diff quality (real change vs. noise) is genuinely hard | v1.5 ships a heuristic pre-filter (structural/length diff) + an LLM classification pass on the remainder, documented as a deliberate simplification rather than a solved problem |
| LLM extraction is inconsistent across very differently-structured sites | Structured output (schema-constrained) rather than free text; a confidence/missing-field indicator per record rather than silently guessing |
| Live demo failure (site changed layout, blocked, down) | Always keep a cached "golden run" for demos; treat live runs as a bonus, not the primary demo path |

## 8. Success metrics (portfolio context — not a live business)

Since this isn't running against a real paying user base, "success" is judged as a portfolio artifact:

- Produces a **correct, readable parity matrix** for a real (but public, non-employer) SaaS niche within one crawl run.
- The v1.5 diff/alert layer demonstrably **fires on a real material change and stays silent on a cosmetic one** in a controlled before/after test.
- The whole pipeline (crawl → extract → synthesize) completes for a typical competitor set in a reasonable time and is **observable** (logs/trace of what happened at each stage), not a black box.
- The system is **explainable in an interview**: architecture, tradeoffs, and the auto-discovery deferral decision can all be defended clearly.

## 9. Milestones

1. **M1 — Crawl + extract** (single company → structured record)
2. **M2 — Multi-company matrix + SWOT brief + export**
3. **M3 — Persistence + scheduled re-crawl**
4. **M4 — Semantic diff + alerting**
5. **M5 — UI polish + cached demo run + writeup**

See `TRD.md` for architecture and `SOP.md` for day-to-day build/run/demo procedures once the tech stack is confirmed.
