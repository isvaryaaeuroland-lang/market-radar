"""Fast, no-LLM tests for the confidence/missing-fields grounding that fixed
a real bug: the model once returned an entirely empty profile while
self-reporting "high" confidence. These fields are now computed from the
profile's actual contents, never trusted to the model."""
from datetime import datetime, timezone

from radar.agents.extraction_agent import _actual_missing_fields, _confidence_from_missing, _is_essentially_empty
from radar.schemas import CompanyProfile, PricingTier


def _profile(**overrides) -> CompanyProfile:
    base = dict(domain="acme.com", extracted_at=datetime.now(timezone.utc))
    base.update(overrides)
    return CompanyProfile(**base)


def test_fully_empty_profile_is_low_confidence_regardless_of_model_claim():
    profile = _profile(extraction_confidence="high")  # model's own (wrong) claim
    missing = _actual_missing_fields(profile)
    assert set(missing) == {"company_name", "value_proposition", "target_icp", "pricing_tiers", "features"}
    assert _confidence_from_missing(missing) == "low"


def test_fully_populated_profile_is_high_confidence():
    profile = _profile(
        company_name="Acme",
        value_proposition="We do things",
        target_icp="SMBs",
        pricing_tiers=[PricingTier(name="Pro", price="$29/mo")],
        features=["API access"],
    )
    assert _actual_missing_fields(profile) == []
    assert _confidence_from_missing([]) == "high"


def test_partially_populated_profile_is_medium_confidence():
    profile = _profile(
        company_name="Acme",
        value_proposition="We do things",
        pricing_tiers=[PricingTier(name="Pro", price="$29/mo")],
        # target_icp and features left empty -> 2 of 5 missing
    )
    missing = _actual_missing_fields(profile)
    assert len(missing) == 2
    assert _confidence_from_missing(missing) == "medium"


def test_essentially_empty_detection_triggers_on_core_fields_only():
    # company_name/target_icp are secondary; the retry trigger cares about
    # the three substantive fields actually worth re-extracting for.
    profile = _profile(company_name="Acme")
    assert _is_essentially_empty(profile)

    profile_with_value_prop = _profile(company_name="Acme", value_proposition="We do things")
    assert not _is_essentially_empty(profile_with_value_prop)
