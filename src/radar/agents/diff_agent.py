"""Two CrawlSnapshots for the same domain -> DiffResult.

Two-stage by design (see TRD §4 / §8): a deterministic field-level diff finds
every raw change first (cheap, no LLM, no false negatives), then a single LLM
call classifies each raw change as material or cosmetic. Splitting it this
way means the LLM's job is narrow (classify, don't discover) which is the
more reliable thing to ask an LLM to do."""
from __future__ import annotations

from pydantic import BaseModel

from ..llm import LLMClient
from ..schemas import ChangeItem, CompanyProfile, DiffResult

_SYSTEM_PROMPT = """You classify detected changes to a company's public website
content as either "material" (a customer or competitor would care: a price
changed, a feature/tier was added or removed, a real shift in positioning)
or "cosmetic" (wording tweaks, formatting, reordering, a copyright year, or a
rephrase that doesn't change the actual offer). For each change, give a one
sentence reasoning. Do not classify something as material just because text
differs — many diffs are purely cosmetic rewrites of the same fact."""


class _RawChange(BaseModel):
    field: str
    before: str
    after: str


class _ClassificationResult(BaseModel):
    changes: list[ChangeItem]


def _raw_diff(previous: CompanyProfile, current: CompanyProfile) -> list[_RawChange]:
    changes: list[_RawChange] = []

    if (previous.value_proposition or "") != (current.value_proposition or ""):
        changes.append(
            _RawChange(
                field="value_proposition",
                before=previous.value_proposition or "(none)",
                after=current.value_proposition or "(none)",
            )
        )

    if (previous.target_icp or "") != (current.target_icp or ""):
        changes.append(
            _RawChange(field="target_icp", before=previous.target_icp or "(none)", after=current.target_icp or "(none)")
        )

    prev_tiers = {t.name: t for t in previous.pricing_tiers}
    curr_tiers = {t.name: t for t in current.pricing_tiers}

    for name in prev_tiers.keys() - curr_tiers.keys():
        changes.append(_RawChange(field=f"pricing_tiers[{name}]", before=prev_tiers[name].model_dump_json(), after="(removed)"))
    for name in curr_tiers.keys() - prev_tiers.keys():
        changes.append(_RawChange(field=f"pricing_tiers[{name}]", before="(new tier)", after=curr_tiers[name].model_dump_json()))
    for name in prev_tiers.keys() & curr_tiers.keys():
        if prev_tiers[name].model_dump_json() != curr_tiers[name].model_dump_json():
            changes.append(
                _RawChange(
                    field=f"pricing_tiers[{name}]",
                    before=prev_tiers[name].model_dump_json(),
                    after=curr_tiers[name].model_dump_json(),
                )
            )

    prev_features, curr_features = set(previous.features), set(current.features)
    for removed in prev_features - curr_features:
        changes.append(_RawChange(field="features", before=removed, after="(removed)"))
    for added in curr_features - prev_features:
        changes.append(_RawChange(field="features", before="(new)", after=added))

    return changes


def diff_profiles(
    previous_id: str,
    current_id: str,
    previous: CompanyProfile,
    current: CompanyProfile,
    llm: LLMClient,
) -> DiffResult:
    raw_changes = _raw_diff(previous, current)

    if not raw_changes:
        return DiffResult(
            domain=current.domain,
            previous_snapshot_id=previous_id,
            current_snapshot_id=current_id,
            changes=[],
        )

    prompt = "Classify each of these detected changes:\n\n" + "\n".join(
        f"- field: {c.field}\n  before: {c.before}\n  after: {c.after}" for c in raw_changes
    )
    result = llm.complete(system=_SYSTEM_PROMPT, prompt=prompt, schema=_ClassificationResult)

    return DiffResult(
        domain=current.domain,
        previous_snapshot_id=previous_id,
        current_snapshot_id=current_id,
        changes=result.changes,
    )
