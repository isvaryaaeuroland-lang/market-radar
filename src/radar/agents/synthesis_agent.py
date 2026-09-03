"""N CompanyProfiles -> a parity matrix + SWOT + narrative brief.

This is where cross-company comparison happens: profiles are extracted
independently (extraction agent has no cross-company context), so aligning
them onto a shared set of comparison vectors and writing the narrative is
its own reasoning step, not a template fill."""
from __future__ import annotations

from datetime import datetime, timezone

from ..llm import LLMClient
from ..schemas import CompanyProfile, MarketBrief

_SYSTEM_PROMPT = """You are a product strategy analyst producing a competitive brief
for a product manager. You will be given structured profiles for one "own company"
and one or more competitors, already extracted from their own websites.

Your job:
1. Build a feature/pricing parity matrix across a shared set of comparison
   vectors (e.g. "Pricing model", "Entry-level price", "Enterprise/SSO",
   "API access", "Self-serve vs sales-led", plus 2-3 vectors specific to
   what these particular companies actually compete on). One row per vector,
   one value per company domain. If a company's data doesn't cover a vector,
   say "Not stated" rather than guessing.
2. For each company, list 2-4 strengths, weaknesses, opportunities, and
   threats, grounded ONLY in what's in the provided profiles. This applies
   even to companies you recognize by name and already know things about —
   use only what's in the profile text below, never what you already know
   about the real company. If a profile has little or no real data (empty
   pricing, no features, no value proposition), say so explicitly in that
   company's SWOT (e.g. "insufficient data extracted to assess") rather
   than filling in plausible-sounding entries from general knowledge.
3. Write a short narrative (150-250 words) synthesizing the single most
   important strategic takeaway for the own company: where it's exposed,
   and where competitors are exposed.

Be honest about "Not stated" data — do not fill gaps with assumptions.
"""


def _build_prompt(own_domain: str, profiles: list[CompanyProfile]) -> str:
    lines = [f"Own company domain: {own_domain}\n", "Profiles:\n"]
    for profile in profiles:
        role = "OWN COMPANY" if profile.domain == own_domain else "COMPETITOR"
        lines.append(f"[{role}] {profile.model_dump_json(indent=2)}\n")
    return "\n".join(lines)


def synthesize_market_brief(own_domain: str, profiles: list[CompanyProfile], llm: LLMClient) -> MarketBrief:
    prompt = _build_prompt(own_domain, profiles)
    brief = llm.complete(system=_SYSTEM_PROMPT, prompt=prompt, schema=MarketBrief)
    brief.generated_at = datetime.now(timezone.utc)
    brief.companies = [p.domain for p in profiles]
    return brief
