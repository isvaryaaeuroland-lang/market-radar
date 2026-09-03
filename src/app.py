"""Streamlit UI — SOP §3. Run with: streamlit run src/app.py"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))  # so `radar` resolves when run via `streamlit run`

from radar.discovery import discover_competitors  # noqa: E402
from radar.export import brief_to_markdown  # noqa: E402
from radar.llm import get_llm_client  # noqa: E402
from radar.pipeline import run_market_scan  # noqa: E402
from radar.storage import add_to_watchlist, list_watchlist, remove_from_watchlist  # noqa: E402

st.set_page_config(page_title="Competitor & Market Radar", layout="wide")
st.title("🎯 Autonomous Competitor & Market Radar")
st.caption(
    "Enter your domain and a handful of competitors to get a feature/pricing parity "
    "matrix and a SWOT brief — built from what's actually on their sites, not a template."
)

tab_scan, tab_watchlist = st.tabs(["Run a scan", "Watchlist"])

with tab_scan:
    col1, col2 = st.columns(2)
    with col1:
        own_domain = st.text_input(
            "Your domain",
            placeholder="yourcompany.com",
            help="A real domain works best (e.g. coca-cola.com). A plain company name "
            "will be guessed at (spaces removed, .com added) but the guess may be "
            "wrong — the resolved domain is always shown below after running.",
        )
        discover_clicked = st.button(
            "🔍 Discover competitors (free web search, suggestions only)",
            disabled=not own_domain,
        )

        # Must run — and, on success, st.rerun() — before the text_area below
        # is instantiated: Streamlit forbids writing to a widget's
        # session_state key in the same run after that widget has already
        # been created (hit this exact exception during testing).
        if discover_clicked:
            with st.spinner("Searching the web, reading a real article, and extracting named competitors..."):
                try:
                    llm = get_llm_client()
                    suggestions = asyncio.run(discover_competitors(own_domain, None, llm))
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Discovery failed: {exc}")
                    suggestions = []

            if suggestions:
                st.session_state["competitors_raw"] = "\n".join(s.domain or s.name for s in suggestions)
                st.session_state["last_discovery"] = suggestions
                st.rerun()
            else:
                st.warning(
                    "No competitors could be found via free search for this input — "
                    "enter them manually instead."
                )

    with col2:
        competitors_raw = st.text_area(
            "Competitor domains (one per line, 3–5 recommended)",
            placeholder="competitor-a.com\ncompetitor-b.com\ncompetitor-c.com",
            height=100,
            key="competitors_raw",
        )

    last_discovery = st.session_state.get("last_discovery")
    if last_discovery:
        with st.expander(f"Why these {len(last_discovery)} were suggested", expanded=False):
            for suggestion in last_discovery:
                st.markdown(f"**{suggestion.name}**{f' (`{suggestion.domain}`)' if suggestion.domain else ''}")
                st.caption(suggestion.reasoning)
        st.caption(
            "These are suggestions, not verified competitors — edit the list above before "
            "running the scan. Domains left blank above use the company name; replace with "
            "the real domain if you know it."
        )

    run_clicked = st.button("Run scan", type="primary", disabled=not own_domain)

    if run_clicked:
        competitor_domains = [line.strip() for line in competitors_raw.splitlines() if line.strip()]
        if not competitor_domains:
            st.warning("Add at least one competitor domain.")
        else:
            with st.spinner(f"Crawling and analyzing {1 + len(competitor_domains)} companies — this can take a few minutes..."):
                try:
                    brief, statuses = asyncio.run(run_market_scan(own_domain, competitor_domains))
                    st.session_state["last_brief"] = brief
                    st.session_state["last_statuses"] = statuses
                except Exception as exc:  # noqa: BLE001 — surface the failure in the UI, don't crash the app
                    st.error(f"Scan failed: {exc}")
                    st.session_state["last_brief"] = None
                    st.session_state["last_statuses"] = []

    statuses = st.session_state.get("last_statuses") or []
    if statuses:
        st.subheader("Scan status")
        any_failed = False
        for status in statuses:
            resolved_note = (
                f" (interpreted as `{status.resolved_domain}`)"
                if status.resolved_domain != status.input_value
                else ""
            )
            if not status.success:
                any_failed = True
                st.error(
                    f"❌ **{status.input_value}**{resolved_note} — could not fetch anything"
                    + (f": {status.error}" if status.error else "")
                    + ". Check it's a real, reachable domain."
                )
            elif status.extraction_confidence == "low":
                st.warning(
                    f"⚠️ **{status.input_value}**{resolved_note} — fetched {status.pages_fetched} page(s), "
                    f"but extraction confidence is low. Missing: {', '.join(status.missing_fields) or 'several fields'}."
                )
            else:
                st.success(
                    f"✅ **{status.input_value}**{resolved_note} — fetched {status.pages_fetched} page(s), "
                    f"{status.extraction_confidence} confidence."
                )
        if any_failed:
            st.caption(
                "Domains that failed above are excluded from the matrix/brief below — "
                "results only cover what was successfully fetched."
            )

    brief = st.session_state.get("last_brief")
    if brief:
        st.subheader("Feature & Pricing Parity Matrix")
        matrix_rows = [{"Vector": row.vector, **row.values} for row in brief.matrix]
        st.dataframe(matrix_rows, use_container_width=True)

        st.subheader("SWOT by company")
        swot_cols = st.columns(len(brief.companies))
        for col, domain in zip(swot_cols, brief.companies):
            with col:
                st.markdown(f"**{domain}**")
                swot = brief.swot.get(domain, {})
                for category in ("strengths", "weaknesses", "opportunities", "threats"):
                    st.markdown(f"_{category.capitalize()}_")
                    for item in swot.get(category, []):
                        st.markdown(f"- {item}")

        st.subheader("Strategic narrative")
        st.write(brief.narrative)

        st.download_button(
            "Download as Markdown",
            data=brief_to_markdown(brief),
            file_name="competitive-brief.md",
            mime="text/markdown",
        )

with tab_watchlist:
    st.subheader("Watchlist (used by the scheduled monitoring daemon)")
    with st.form("add_watchlist_form", clear_on_submit=True):
        wl_own = st.text_input("Own domain")
        wl_competitor = st.text_input("Competitor domain")
        submitted = st.form_submit_button("Add")
        if submitted:
            if wl_own:
                add_to_watchlist(wl_own, is_own_company=True)
            if wl_competitor:
                add_to_watchlist(wl_competitor, is_own_company=False)
            st.rerun()

    rows = list_watchlist()
    if not rows:
        st.info("Watchlist is empty. Add domains above, or run `python -m radar.cli add-watchlist`.")
    else:
        for row in rows:
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(row["domain"])
            c2.write("own" if row["is_own_company"] else "competitor")
            if c3.button("Remove", key=f"remove_{row['domain']}"):
                remove_from_watchlist(row["domain"])
                st.rerun()

    st.caption(
        "Run `python -m radar.scheduler_daemon --interval-minutes 5` in a separate terminal "
        "to start watching this list."
    )
