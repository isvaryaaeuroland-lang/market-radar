"""The deterministic half of the diff agent (raw field-level diffing) is
tested here without any LLM call — see TRD §8. The LLM classification half
is exercised separately, marked @pytest.mark.llm, since it needs Ollama."""
import json
from pathlib import Path

import pytest

from radar.agents.diff_agent import _raw_diff, diff_profiles
from radar.llm import get_llm_client
from radar.schemas import CompanyProfile

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> CompanyProfile:
    return CompanyProfile.model_validate(json.loads((FIXTURES / name).read_text()))


def test_raw_diff_detects_price_change():
    previous = _load("acme_profile_v1.json")
    current = _load("acme_profile_v2.json")

    changes = _raw_diff(previous, current)
    fields = [c.field for c in changes]

    assert any("Growth" in f for f in fields), f"expected a Growth tier change in {fields}"


def test_raw_diff_detects_new_tier():
    previous = _load("acme_profile_v1.json")
    current = _load("acme_profile_v2.json")

    changes = _raw_diff(previous, current)
    new_tier_changes = [c for c in changes if "Enterprise" in c.field]

    assert len(new_tier_changes) == 1
    assert new_tier_changes[0].before == "(new tier)"


def test_raw_diff_detects_new_feature():
    previous = _load("acme_profile_v1.json")
    current = _load("acme_profile_v2.json")

    changes = _raw_diff(previous, current)
    feature_additions = [c for c in changes if c.field == "features" and c.after == "SSO (SAML)"]

    assert len(feature_additions) == 1


def test_raw_diff_detects_cosmetic_value_prop_rewrite():
    previous = _load("acme_profile_v1.json")
    current = _load("acme_profile_v2.json")

    changes = _raw_diff(previous, current)
    vp_changes = [c for c in changes if c.field == "value_proposition"]

    assert len(vp_changes) == 1  # detected as changed — classification (material/cosmetic) is the LLM's job


def test_raw_diff_finds_nothing_when_profiles_are_identical():
    profile = _load("acme_profile_v1.json")
    assert _raw_diff(profile, profile) == []


@pytest.mark.llm
def test_diff_profiles_classifies_price_change_as_material():
    """Requires a running Ollama instance. Run explicitly with: pytest -m llm"""
    previous = _load("acme_profile_v1.json")
    current = _load("acme_profile_v2.json")
    llm = get_llm_client()

    result = diff_profiles("v1", "v2", previous, current, llm)

    assert result.has_material_change
    price_changes = [c for c in result.changes if "Growth" in c.field]
    assert price_changes, "expected the Growth tier price change to be classified"
    assert price_changes[0].classification == "material"


@pytest.mark.llm
def test_diff_profiles_classifies_wording_rewrite_as_cosmetic():
    """Requires a running Ollama instance. Run explicitly with: pytest -m llm"""
    previous = _load("acme_profile_v1.json")
    current = _load("acme_profile_v2.json")
    llm = get_llm_client()

    result = diff_profiles("v1", "v2", previous, current, llm)

    vp_changes = [c for c in result.changes if c.field == "value_proposition"]
    assert vp_changes
    assert vp_changes[0].classification == "cosmetic"
