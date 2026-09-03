from datetime import datetime, timezone

from radar.schemas import CompanyProfile, PricingTier


def test_company_profile_minimal_construction():
    profile = CompanyProfile(domain="example.com", extracted_at=datetime.now(timezone.utc))
    assert profile.pricing_tiers == []
    assert profile.features == []
    assert profile.missing_fields == []
    assert profile.extraction_confidence == "medium"


def test_missing_fields_are_explicit_not_silent():
    profile = CompanyProfile(
        domain="example.com",
        extracted_at=datetime.now(timezone.utc),
        extraction_confidence="low",
        missing_fields=["pricing_tiers", "target_icp"],
    )
    assert "pricing_tiers" in profile.missing_fields
    assert profile.pricing_tiers == []


def test_pricing_tier_price_stays_a_literal_string():
    tier = PricingTier(name="Growth", price="$49/mo", billing_period="monthly", key_inclusions=["A", "B"])
    assert tier.price == "$49/mo"  # no currency/period normalization, by design


def test_pricing_tier_allows_custom_pricing_without_a_period():
    tier = PricingTier(name="Enterprise", price="Custom", billing_period=None)
    assert tier.billing_period is None
    assert tier.key_inclusions == []
