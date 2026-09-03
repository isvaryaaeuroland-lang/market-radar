"""Fast, no-network tests for the input normalization that fixed the
"coco cola" / "pepsi" bug — plain company names with spaces and no TLD
previously produced an invalid URL and silently crawled nothing."""
from radar.crawler import normalize_company_input


def test_plain_company_name_with_spaces_gets_slugged_and_given_a_tld():
    assert normalize_company_input("coco cola") == "cococola.com"


def test_lowercase_single_word_name_gets_a_tld():
    assert normalize_company_input("pepsi") == "pepsi.com"


def test_real_domain_passes_through_unchanged():
    assert normalize_company_input("coca-cola.com") == "coca-cola.com"


def test_full_url_passes_through_unchanged():
    assert normalize_company_input("https://coca-cola.com/") == "https://coca-cola.com"


def test_mixed_case_and_punctuation_in_a_name_is_slugged():
    assert normalize_company_input("Coca-Cola Inc.") == "cocacolainc.com"


def test_empty_input_returns_empty():
    assert normalize_company_input("   ") == ""


def test_url_with_path_is_not_mistaken_for_a_domain_with_a_path():
    # A domain with a stray path segment (no scheme) should keep just the host part.
    assert normalize_company_input("acme.com/pricing") == "acme.com"
