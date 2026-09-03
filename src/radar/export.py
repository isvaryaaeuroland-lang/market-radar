"""Render a MarketBrief to Markdown (and, on top of that, PDF). Plain string
templating — the content shape is simple and fixed enough that a templating
engine would be overhead, not clarity."""
from __future__ import annotations

from pathlib import Path

from .schemas import MarketBrief


def brief_to_markdown(brief: MarketBrief) -> str:
    lines = [
        "# Competitive Market Brief",
        f"_Generated {brief.generated_at.strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        f"**Companies covered:** {', '.join(brief.companies)}",
        "",
        "## Feature & Pricing Parity Matrix",
        "",
        "| Vector | " + " | ".join(brief.companies) + " |",
        "|---|" + "---|" * len(brief.companies),
    ]
    for row in brief.matrix:
        values = " | ".join(row.values.get(domain, "Not stated") for domain in brief.companies)
        lines.append(f"| {row.vector} | {values} |")

    lines += ["", "## SWOT by Company", ""]
    for domain in brief.companies:
        swot = brief.swot.get(domain, {})
        lines.append(f"### {domain}")
        for category in ("strengths", "weaknesses", "opportunities", "threats"):
            items = swot.get(category, [])
            lines.append(f"**{category.capitalize()}:**")
            lines.extend(f"- {item}" for item in items) if items else lines.append("- (none identified)")
        lines.append("")

    lines += ["## Strategic Narrative", "", brief.narrative]
    return "\n".join(lines)


def save_markdown(brief: MarketBrief, path: Path) -> Path:
    path.write_text(brief_to_markdown(brief), encoding="utf-8")
    return path


def save_pdf(brief: MarketBrief, path: Path) -> Path:
    """Best-effort PDF export via markdown -> HTML -> PDF (weasyprint). If
    weasyprint isn't installed/working on this machine, callers should fall
    back to the Markdown export — this is intentionally not a hard dependency
    of the rest of the pipeline."""
    import markdown as md_lib

    html_body = md_lib.markdown(brief_to_markdown(brief), extensions=["tables"])
    html = f"<html><head><meta charset='utf-8'></head><body>{html_body}</body></html>"

    from weasyprint import HTML  # imported lazily — optional dependency

    HTML(string=html).write_pdf(str(path))
    return path
