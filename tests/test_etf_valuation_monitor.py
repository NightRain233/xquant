from datetime import datetime,timezone

from xquant.etf_valuation_monitor import assess_observation,session_status,timestamp


def now():return timestamp("2026-10-08T10:00:00+08:00")


def quote():return {"quote_at":"2026-10-08T09:59:50+08:00","ask":2.02,"bid":2.019,"nav":2.,"nav_date":"2026-09-29"}


def reference():
    return {"lower":2.,"upper":2.01,"as_of":"2026-10-08T09:59:50+08:00",
            "first_seen_at":"2026-10-08T09:59:55+08:00","researcher_verified":True,
            "basis_description":"synthetic test fixture", "method_source":"fixture",
            "error_bound_reason":"fixture", "underlying_price_at":"2026-10-08T09:59:50+08:00",
            "fx_at":"2026-10-08T09:59:50+08:00","issuer_warning_checked_at":"2026-10-08T09:00:00+08:00",
            "issuer_warning_active":False}


def test_nav_date_does_not_establish_a_current_bound():
    result=assess_observation(quote(),now(),cap=.01)
    assert result["optional_gate_eligible"] is False
    assert result["premium_upper"] is None
    assert "current_valuation_interval_unverified" in result["diagnostic_reasons"]


def test_no_cap_is_observation_only_and_does_not_change_baseline():
    result=assess_observation(quote(),now())
    assert result["filter_enabled"] is False
    assert result["optional_gate_eligible"] is None
    assert result["baseline"]=="domestic_price_IV20_no_premium_filter"


def test_verified_research_interval_can_pass_optional_paper_gate():
    result=assess_observation(quote(),now(),reference(),cap=.0101)
    assert result["optional_gate_eligible"] is True
    assert abs(result["premium_upper"]-.01)<1e-12
    assert result["premium_lower"]<result["premium_upper"]
    assert not assess_observation(quote(),now(),reference(),cap=.005)["optional_gate_eligible"]


def test_future_reference_and_stale_quote_are_rejected():
    r=reference();r["first_seen_at"]="2026-10-08T10:01:00+08:00"
    q=quote();q["quote_at"]="2026-10-08T09:58:00+08:00"
    result=assess_observation(q,now(),r,cap=.01)
    assert "future_reference" in result["diagnostic_reasons"]
    assert "stale_quote" in result["diagnostic_reasons"]


def test_holiday_and_lunch_do_not_count_as_observation_sessions():
    assert session_status(timestamp("2026-10-04T10:00:00+08:00"))=="market_closed"
    assert session_status(timestamp("2026-10-08T12:00:00+08:00"))=="outside_continuous_session"
    assert session_status(timestamp("2027-01-04T10:00:00+08:00"))=="calendar_not_verified"


def test_future_underlying_or_missing_warning_check_prevents_eligibility():
    r=reference();r["underlying_price_at"]="2026-10-08T10:01:00+08:00";r.pop("issuer_warning_checked_at")
    result=assess_observation(quote(),now(),r,cap=.02)
    assert "future_underlying_or_fx" in result["diagnostic_reasons"]
    assert "issuer_status_not_checked" in result["diagnostic_reasons"]
    r=reference();r["issuer_warning_checked_at"]="invalid clock"
    assert "issuer_status_clock_invalid" in assess_observation(quote(),now(),r,cap=.02)["diagnostic_reasons"]
