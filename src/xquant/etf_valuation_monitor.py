"""Research-only valuation diagnostics; no market-data value implies a bound."""
from __future__ import annotations

from datetime import datetime, time, timezone
import math
from zoneinfo import ZoneInfo

CN = ZoneInfo("Asia/Shanghai")
HOLIDAYS_2026 = [("2026-01-01","2026-01-03"),("2026-02-15","2026-02-23"),
                 ("2026-04-04","2026-04-06"),("2026-05-01","2026-05-05"),
                 ("2026-06-19","2026-06-21"),("2026-09-25","2026-09-27"),
                 ("2026-10-01","2026-10-07")]
CALENDAR_SOURCE = "https://www.sse.com.cn/disclosure/dealinstruc/closed/"


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp must have an explicit timezone")
    return result.astimezone(timezone.utc)


def session_status(now):
    local = now.astimezone(CN)
    if local.year != 2026:
        return "calendar_not_verified"
    day = local.date().isoformat()
    if local.weekday() >= 5 or any(start <= day <= end for start,end in HOLIDAYS_2026):
        return "market_closed"
    t = local.time().replace(tzinfo=None)
    if time(9,30) <= t <= time(11,30) or time(13) <= t <= time(15):
        return "continuous_session"
    return "outside_continuous_session"


def assess_observation(row, now, reference=None, cap=None):
    """Optional paper gate; unavailable interval is not a high-premium finding.

    An interval supplied by a researcher remains an explicit research input.
    Latest published NAV, unverified app IOPV, or an index estimate cannot
    automatically become a justified current liquidation-value interval.
    """
    reasons = []
    status = session_status(now)
    if status != "continuous_session":
        reasons.append(status)
    quote_age = None
    if row.get("quote_at"):
        quote_age = (now-timestamp(row["quote_at"])).total_seconds()
        if quote_age < 0:reasons.append("future_quote")
        elif quote_age > 60:reasons.append("stale_quote")
    else:
        reasons.append("quote_missing")
    ask, bid = row.get("ask"), row.get("bid")
    if not ask or not bid or ask < bid:
        reasons.append("invalid_or_empty_book")
    interval_low = interval_high = premium_low = premium_high = None
    reference_age = None
    reference = reference or {}
    required = ("lower", "upper", "as_of", "first_seen_at", "basis_description",
                "method_source", "error_bound_reason", "underlying_price_at", "fx_at")
    verified = reference.get("researcher_verified") is True and all(reference.get(k) is not None for k in required)
    if not verified:
        reasons.append("current_valuation_interval_unverified")
    else:
        try:
            ref_at = timestamp(reference["as_of"])
            available = timestamp(reference["first_seen_at"])
            reference_age = (now-ref_at).total_seconds()
            if available > now or ref_at > now:
                reasons.append("future_reference")
            if reference_age > 60:reasons.append("stale_reference")
            underlying_at, fx_at = timestamp(reference["underlying_price_at"]),timestamp(reference["fx_at"])
            if underlying_at > now or fx_at > now:reasons.append("future_underlying_or_fx")
            interval_low, interval_high = float(reference["lower"]),float(reference["upper"])
            if not math.isfinite(interval_low) or not math.isfinite(interval_high) or not 0 < interval_low <= interval_high:
                reasons.append("invalid_interval")
                interval_low = interval_high = None
            elif ask:
                premium_low, premium_high = ask/interval_high-1,ask/interval_low-1
                if cap is not None and premium_high > cap:
                    reasons.append("premium_over_optional_cap")
        except (ValueError, TypeError):
            reasons.append("invalid_reference_clock_or_value")
    if reference.get("issuer_warning_checked_at"):
        try:
            warning_at=timestamp(reference["issuer_warning_checked_at"])
            if warning_at > now or (now-warning_at).total_seconds() > 86400:
                reasons.append("issuer_status_stale_or_future")
            elif reference.get("issuer_warning_active") is not False:
                reasons.append("issuer_warning_active_or_unknown")
        except (ValueError,TypeError):reasons.append("issuer_status_clock_invalid")
    else:
        reasons.append("issuer_status_not_checked")
    return {"session_status":status,"quote_age_seconds":quote_age,
            "reference_age_seconds":reference_age,"fair_value_lower":interval_low,
            "fair_value_upper":interval_high,"premium_lower":premium_low,"premium_upper":premium_high,
            "cap":cap,"filter_enabled":cap is not None,
            "optional_gate_eligible":not reasons if cap is not None else None,
            "diagnostic_reasons":reasons,"baseline":"domestic_price_IV20_no_premium_filter"}
