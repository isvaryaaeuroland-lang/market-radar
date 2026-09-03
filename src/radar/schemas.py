"""Pydantic schemas shared across the pipeline. These are the contract every
agent is held to — extraction, synthesis, and diffing all read/write these
models rather than passing raw dicts around."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CompetitorSuggestion(BaseModel):
    """One candidate competitor surfaced by free-source discovery — always a
    suggestion for the user to confirm/edit, never auto-added to a scan."""

    name: str
    domain: str | None = Field(
        default=None, description="Only set when confidently known — never guessed"
    )
    reasoning: str = Field(description="Why this was suggested, grounded in the source article")


class PricingTier(BaseModel):
    name: str
    price: str | None = Field(
        default=None,
        description='Kept as the literal string shown on the page, e.g. "$29/mo", '
        '"Custom pricing", "Free". Currency/period normalization is a non-goal.',
    )
    billing_period: str | None = None
    key_inclusions: list[str] = Field(default_factory=list)


# The only real gaps a CompanyProfile can have. Constrained to this exact
# set (not a free `list[str]`) after testing showed the model would otherwise
# invent an unbounded, nonsensical taxonomy of "missing fields" that don't
# correspond to anything in this schema (e.g. "company_funding_rounds_
# details_count_count") — a real degenerate-generation failure caught in
# testing, not a hypothetical one. Constraining the JSON schema's enum here
# closes off that failure mode at the decoding level, not just the prompt.
MissingField = Literal["company_name", "value_proposition", "target_icp", "pricing_tiers", "features"]


class CompanyProfile(BaseModel):
    domain: str
    company_name: str | None = None
    value_proposition: str | None = None
    target_icp: str | None = None
    pricing_tiers: list[PricingTier] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    extracted_at: datetime
    source_pages: list[str] = Field(default_factory=list)
    extraction_confidence: Literal["high", "medium", "low"] = "medium"
    missing_fields: list[MissingField] = Field(
        default_factory=list,
        description="Which of this schema's own fields could not be found. Must "
        "only be drawn from: company_name, value_proposition, target_icp, "
        "pricing_tiers, features — never an invented field name.",
    )


class DomainScanStatus(BaseModel):
    """What actually happened when scanning one input, surfaced to the UI so
    a failed/empty crawl is never silently rendered as a normal result."""

    input_value: str  # exactly what the user typed
    resolved_domain: str  # what was actually fetched, after normalization
    success: bool
    pages_fetched: int = 0
    extraction_confidence: Literal["high", "medium", "low"] = "low"
    missing_fields: list[str] = Field(default_factory=list)
    error: str | None = None


class CrawlSnapshot(BaseModel):
    id: str  # "{domain}__{iso_timestamp}"
    profile: CompanyProfile
    raw_pages: dict[str, str] = Field(
        default_factory=dict, description="url -> markdown, cached for debugging/re-extraction"
    )


class ChangeItem(BaseModel):
    field: str
    before: str
    after: str
    classification: Literal["material", "cosmetic"]
    reasoning: str


class DiffResult(BaseModel):
    domain: str
    previous_snapshot_id: str
    current_snapshot_id: str
    changes: list[ChangeItem] = Field(default_factory=list)

    @property
    def has_material_change(self) -> bool:
        return any(c.classification == "material" for c in self.changes)


class ParityMatrixRow(BaseModel):
    vector: str  # e.g. "Pricing model", "SSO / enterprise auth", "API access"
    values: dict[str, str]  # domain -> value for this vector


class MarketBrief(BaseModel):
    generated_at: datetime
    companies: list[str]  # domains covered
    matrix: list[ParityMatrixRow]
    swot: dict[str, dict[str, list[str]]]  # domain -> {"strengths": [...], "weaknesses": [...], ...}
    narrative: str
