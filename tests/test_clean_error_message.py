from radar.crawler import _clean_error_message


def test_dns_failure_gets_a_plain_sentence():
    raw = (
        "Unexpected error in _crawl_web at line 778\n"
        "Error: Failed on navigating ACS-GOTO:\n"
        "Page.goto: net::ERR_NAME_NOT_RESOLVED at https://cococola.com/\n"
        "Call log:\n  - navigating to ..."
    )
    assert _clean_error_message(raw) == "This domain doesn't exist or can't be resolved (DNS lookup failed)."


def test_connection_refused_gets_a_plain_sentence():
    assert "Connection refused" in _clean_error_message("net::ERR_CONNECTION_REFUSED")


def test_timeout_gets_a_plain_sentence():
    assert "timed out" in _clean_error_message("Navigation Timeout Exceeded: 30000ms")


def test_unrecognized_error_falls_back_to_first_line_truncated():
    raw = "Some totally new crawler error we haven't seen\nwith extra trailing context lines"
    assert _clean_error_message(raw) == "Some totally new crawler error we haven't seen"
