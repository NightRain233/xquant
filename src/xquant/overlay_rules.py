"""S&P 500 overlay rules, a daily engine that sees the actual weight, and DCA-account helpers.

Used by the 2026-11-10 "S&P 500 enhancement vs DCA" study. Conventions match
``style_combo.run_backtest`` (checked to the last digit in the research script):

* a rule decides at the close of day ``i``; the order fills at the close of day ``i + 1``;
* cost ``cost`` per side on the traded notional (fixed point over the trade size);
* uninvested cash earns the factor in ``cash_pos`` (T-bill); borrowed cash (negative) uses ``cash_neg``;
* the engine starts in cash at close ``start_i`` and buys no earlier than ``start_i + 1``.

Assets are two columns: ``a`` = S&P 500 (dividend-adjusted), ``b`` = bond (IEF or synthetic bond).
Every rule returns a length-2 weight vector; ``b`` is zero except for the DM-IEF rule.

A signal is ``sig(i, weights_now) -> np.ndarray | None``. ``weights_now`` are the end-of-day weights at
close ``i`` (asset value / NAV), so the volatility-target band can use the actual weight.
Every decision uses only data up to its own close (calendar facts are known in advance and passed
in explicitly: ``MarketData.calendar``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import pandas as pd

from xquant import position_rules as pr
from xquant import style_combo as sc

Signal = Callable[[int, np.ndarray], Optional[np.ndarray]]
TRADING_DAYS = 252
DEFAULT_CAP = {"S1": 1.5, "VT15": 1.5}


# --------------------------------------------------------------------------- calendars

def month_end_mask(dates) -> np.ndarray:
    """True on the last trading day of each month; False on the final date (no next close to trade at)."""
    dates = pd.DatetimeIndex(dates)
    mask = np.zeros(len(dates), dtype=bool)
    if len(dates) > 1:
        mask[:-1] = dates[:-1].to_period("M") != dates[1:].to_period("M")
    return mask


def captured_mask(calendar, *, months=None, first_n: int = 0, last_n: int = 0) -> np.ndarray:
    """Days whose close-to-close return the holder wants to capture.

    ``months``: whole calendar months; ``first_n`` / ``last_n``: first / last trading days of each month.
    """
    cal = pd.DatetimeIndex(calendar)
    keys = cal.to_period("M").astype(str)
    position = np.arange(len(cal))
    mask = np.zeros(len(cal), dtype=bool)
    if months is not None:
        mask |= np.isin(cal.month, list(months))
    if first_n:
        mask |= pd.Series(position).groupby(keys).cumcount().to_numpy() < first_n
    if last_n:
        mask |= pd.Series(position).groupby(keys).cumcount(ascending=False).to_numpy() < last_n
    return mask


def held_by_date(calendar, captured: np.ndarray) -> pd.Series:
    """Weight held at the close of day s: 1 when the return of the next trading day is captured.

    Entry at the close before the first captured day and exit at the close of the last captured day's
    predecessor, so exactly the captured returns are earned.
    """
    cal = pd.DatetimeIndex(calendar)
    held = np.r_[np.asarray(captured, bool)[1:], False]
    return pd.Series(held, index=cal)


# --------------------------------------------------------------------------- data bundle

@dataclass
class MarketData:
    """Everything a rule may read. All arrays are aligned to ``dates``.

    ``cash_pos[i]`` / ``cash_neg[i]``: cash growth factor over the period ending at close i (day 0 is 1).
    ``unrate``: monthly UNRATE indexed by ``PeriodIndex`` (percent); used only by GTT.
    ``calendar``: full trading calendar for calendar-known rules (TOM, HAL); defaults to ``dates``.
    """
    dates: pd.DatetimeIndex
    spy: pd.Series
    bond: pd.Series
    cash_pos: np.ndarray
    cash_neg: np.ndarray
    unrate: Optional[pd.Series] = None
    calendar: Optional[pd.DatetimeIndex] = None

    def __post_init__(self):
        self.dates = pd.DatetimeIndex(self.dates)
        if self.calendar is None:
            self.calendar = self.dates
        self.cash_index = pd.Series(np.cumprod(self.cash_pos), index=self.dates)


def calendar_cash_factors(dates, annual_rate, borrow_spread: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Factors as in ``run_backtest``: the previous close's annual rate applied per 365 calendar days."""
    dates = pd.DatetimeIndex(dates)
    rate = np.asarray(annual_rate, float)
    pos, neg = np.ones(len(dates)), np.ones(len(dates))
    days = (dates[1:] - dates[:-1]).days.to_numpy(float)
    pos[1:] = (1.0 + rate[:-1]) ** (days / 365.0)
    neg[1:] = (1.0 + rate[:-1] + borrow_spread) ** (days / 365.0)
    return pos, neg


def daily_cash_factors(daily_annual_rate, borrow_spread: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Trading-day convention: annual rate / 252 per trading day (rate known before the day it applies to)."""
    rate = np.asarray(daily_annual_rate, float)
    pos, neg = np.ones(len(rate)), np.ones(len(rate))
    pos[1:] = 1.0 + rate[1:] / TRADING_DAYS
    neg[1:] = 1.0 + (rate[1:] + borrow_spread) / TRADING_DAYS
    return pos, neg


# --------------------------------------------------------------------------- engine

@dataclass
class EngineResult:
    nav: pd.Series
    weights: pd.DataFrame            # end-of-day weights, columns a, b
    trades: pd.DataFrame             # one row per execution: date, traded_frac, cost, is_initial
    tbill_daily: pd.Series           # T-bill return earned per day (rf for Sharpe), first day 0
    checks: dict = field(default_factory=dict)


def run_overlay(prices: pd.DataFrame, signal: Signal, start_i: int, cost: float, cash_pos: np.ndarray,
                cash_neg: np.ndarray) -> EngineResult:
    """Same mechanics as ``style_combo.run_backtest`` plus the actual weight passed to the signal."""
    cols = ["a", "b"]
    dates = prices.index
    px = prices[cols].to_numpy(float)
    n = len(dates)
    shares = np.zeros(2)
    cash = 1.0
    pending = None
    nav, wts, trades = [], [], []
    max_resid = 0.0
    target_min, target_max = np.inf, -np.inf
    for i in range(start_i, n):
        if i > start_i:
            cash *= cash_neg[i] if cash < 0 else cash_pos[i]
        if pending is not None:
            hold = shares * px[i]
            total = hold.sum() + cash
            c_est = 0.0
            for _ in range(8):  # cost depends on trade size, which depends on cost
                tgt = pending * (total - c_est)
                c_est = cost * np.abs(tgt - hold).sum()
            tgt = pending * (total - c_est)
            traded = np.abs(tgt - hold).sum()
            new_cash = total - c_est - tgt.sum()
            max_resid = max(max_resid, abs((tgt.sum() + new_cash + c_est) - total))
            shares = tgt / px[i]
            cash = new_cash
            trades.append({"exec_date": dates[i], "traded_frac": traded / total, "cost": c_est,
                           "is_initial": len(trades) == 0})
            pending = None
        value = shares * px[i]
        total = value.sum() + cash
        nav.append(total)
        wts.append(value / total)
        target = signal(i, value / total)
        if target is not None and i + 1 < n:
            pending = np.asarray(target, float)
            target_min = min(target_min, float(pending.min()))
            target_max = max(target_max, float(pending.sum()))
    index = dates[start_i:]
    tbill = pd.Series(0.0, index=index, name="tbill")
    tbill.iloc[1:] = cash_pos[start_i + 1:] - 1.0
    weights = pd.DataFrame(wts, index=index, columns=cols)
    checks = {"max_cash_plus_holdings_residual": max_resid, "min_nav": float(np.min(nav)),
              "min_weight": float(weights.min().min()), "max_gross_weight": float(weights.sum(axis=1).max()),
              "min_target_weight": target_min, "max_target_gross": target_max}
    return EngineResult(pd.Series(nav, index=index, name="nav"), weights,
                        pd.DataFrame(trades, columns=["exec_date", "traded_frac", "cost", "is_initial"]),
                        tbill, checks)


# --------------------------------------------------------------------------- state rules

def state_signal(state: np.ndarray, start_i: int) -> Signal:
    """Hold ``state[i]`` decided at close i; submit only when the decided vector changes (fills next close)."""
    state = np.asarray(state, float)

    def sig(i, _weights_now):
        if i == start_i or np.any(state[i] != state[i - 1]):
            return state[i].copy()
        return None
    return sig


def _ffill_decisions(n: int, positions: np.ndarray, values: np.ndarray, default: float) -> np.ndarray:
    series = pd.Series(np.nan, index=np.arange(n))
    series.iloc[positions] = values
    return series.ffill().fillna(default).to_numpy(float)


def _binary_state(on: np.ndarray, on_vec=(1.0, 0.0), off_vec=(0.0, 0.0)) -> np.ndarray:
    return np.where(on[:, None] > 0.5, np.asarray(on_vec, float), np.asarray(off_vec, float))


def sma_month_end_state(close: pd.Series, months: int = 10) -> np.ndarray:
    """Faber: on at a month-end close above the mean of the last ``months`` month-end closes; off otherwise."""
    dates = close.index
    idx = np.flatnonzero(month_end_mask(dates))
    values = close.to_numpy(float)[idx]
    sma = pd.Series(values).rolling(months).mean().to_numpy()
    decision = (values > sma).astype(float)  # NaN comparison -> off during warm-up
    return _ffill_decisions(len(dates), idx, decision, 0.0)


def absolute_momentum_state(close: pd.Series, cash_index: pd.Series, months: int = 12) -> np.ndarray:
    """Antonacci: on at a month-end when the trailing ``months`` total return beats the T-bill return."""
    idx = np.flatnonzero(month_end_mask(close.index))
    spy_m = pd.Series(close.to_numpy(float)[idx])
    cash_m = pd.Series(cash_index.to_numpy(float)[idx])
    spy_ret = spy_m / spy_m.shift(months) - 1.0
    cash_ret = cash_m / cash_m.shift(months) - 1.0
    decision = (spy_ret > cash_ret).astype(float)
    return _ffill_decisions(len(close), idx, decision.to_numpy(), 0.0)


def gtt_state(close: pd.Series, unrate: pd.Series, months: int = 10) -> np.ndarray:
    """Growth-trend timing (monthly). Out only when the month-end close is below its ``months`` SMA AND the
    latest published UNRATE is above the mean of the 12 latest published values. UNRATE of month m is published
    after the month-end of m+1, so at month-end m only observations up to month m-1 are used. Months without a
    published value (e.g. Oct 2025, not published) are skipped: the latest and the 12-value mean are over
    the observations that exist."""
    idx = np.flatnonzero(month_end_mask(close.index))
    values = close.to_numpy(float)[idx]
    sma = pd.Series(values).rolling(months).mean().to_numpy()
    periods = close.index[idx].to_period("M")
    obs = unrate.dropna().sort_index()
    calendar = pd.period_range(obs.index[0], periods.max(), freq="M")
    latest = obs.reindex(calendar).ffill()                   # latest published value as of each month
    mean12 = obs.rolling(12).mean().reindex(calendar).ffill()  # mean of the 12 latest published values
    lag = periods - 1
    bad = latest.reindex(lag).to_numpy(float) > mean12.reindex(lag).to_numpy(float)  # NaN -> False
    out = (values < sma) & bad  # NaN comparisons are False, so no exit before both are known
    decision = np.where(out, 0.0, 1.0)
    return _ffill_decisions(len(close), idx, decision, 1.0)


def fixed_weight_signal(weight: float, dates: pd.DatetimeIndex, start_i: int) -> Signal:
    """Constant SPY weight, rebalanced at every month-end (the rest in T-bills)."""
    month_end = month_end_mask(dates)

    def sig(i, _w):
        if i == start_i or month_end[i]:
            return np.array([weight, 0.0])
        return None
    return sig


def wilder_rsi(close: pd.Series, n: int = 2) -> np.ndarray:
    """Wilder RSI(n) with exponential smoothing alpha = 1/n (seeded at the first change)."""
    diff = close.diff()
    gain = diff.clip(lower=0.0).ewm(alpha=1.0 / n, adjust=False).mean()
    loss = (-diff).clip(lower=0.0).ewm(alpha=1.0 / n, adjust=False).mean()
    return (100.0 - 100.0 / (1.0 + gain / loss)).to_numpy(float)


def rsi2_signal(close: pd.Series, start_i: int, entry_below: float = 10.0, trend_ma: int = 200,
                exit_ma: int = 5) -> Signal:
    """Connors RSI(2): enter when close > trend_ma SMA and RSI(2) < entry_below; exit when close > exit_ma SMA."""
    c = close.to_numpy(float)
    trend = close.rolling(trend_ma).mean().to_numpy(float)
    exit_level = close.rolling(exit_ma).mean().to_numpy(float)
    rsi = wilder_rsi(close, 2)
    state = {"pos": 0.0}

    def sig(i, _w):
        prev = state["pos"]
        new = prev
        if prev == 0.0:
            if c[i] > trend[i] and rsi[i] < entry_below:
                new = 1.0
        elif c[i] > exit_level[i]:
            new = 0.0
        state["pos"] = new
        if i == start_i or new != prev:
            return np.array([new, 0.0])
        return None
    return sig


def vol_target_band(close: pd.Series, start_i: int, target: float = 0.15, cap: float = 1.0, window: int = 21,
                    band: float = 0.10, gate: Optional[np.ndarray] = None) -> Signal:
    """Moreira-Muir volatility target: weight = min(cap, target / realized vol) where realized vol is the
    std of the last ``window`` daily log returns (annualized). Trade only when the wanted weight differs
    from the actual weight by more than ``band``. With ``gate`` (0/1 per day) the wanted weight is 0 when gated off."""
    log_ret = np.log(close).diff()
    vol = log_ret.rolling(window).std(ddof=1).to_numpy(float) * np.sqrt(TRADING_DAYS)
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = np.where(vol > 0, target / vol, np.inf)
    wanted = np.minimum(cap, raw)
    wanted = np.where(np.isnan(vol), np.nan, wanted)
    if gate is not None:
        wanted = wanted * np.asarray(gate, float)

    def sig(i, weights_now):
        desired = wanted[i]
        if np.isnan(desired):
            return None
        if i == start_i or abs(desired - weights_now[0]) > band:
            return np.array([desired, 0.0])
        return None
    return sig


def _dict_adapter(sig_fn) -> Signal:
    def sig(i, _w):
        out = sig_fn(i)
        return None if out is None else np.array([out["a"], out["b"]], float)
    return sig


# --------------------------------------------------------------------------- rule registry

RULES = ("B0", "S2", "S1", "F10", "DM", "DM_IEF", "GTT", "VT", "VT15", "F10xVT", "TOM", "HAL", "RSI2")


def build_signal(name: str, data: MarketData, start_i: int, **params) -> Signal:
    """Signal for a named rule. ``params`` override the frozen defaults (used only by the sensitivity runs)."""
    n = len(data.dates)
    spy = data.spy
    if name == "B0":
        return state_signal(np.tile([1.0, 0.0], (n, 1)), start_i)
    if name == "S2":
        states = pr.stage_states(spy)
        return _dict_adapter(pr.rule_stage_blend(states, data.dates, start_i, on=1.0, off=0.5))
    if name == "S1":
        return _dict_adapter(pr.rule_trend_leverage(spy, start_i, ma_days=200, leverage=1.5))
    if name == "F10":
        on = sma_month_end_state(spy, params.get("months", 10))
        return state_signal(_binary_state(on), start_i)
    if name in ("DM", "DM_IEF"):
        on = absolute_momentum_state(spy, data.cash_index, params.get("months", 12))
        off_vec = (0.0, 1.0) if name == "DM_IEF" else (0.0, 0.0)
        return state_signal(_binary_state(on, off_vec=off_vec), start_i)
    if name == "GTT":
        if data.unrate is None:
            raise ValueError("GTT needs UNRATE")
        on = gtt_state(spy, data.unrate, params.get("months", 10))
        return state_signal(_binary_state(on, on_vec=(1.0, 0.0), off_vec=(0.0, 0.0)), start_i)
    if name in ("VT", "VT15"):
        default_cap = DEFAULT_CAP.get(name, 1.0)
        return vol_target_band(spy, start_i, target=params.get("target", 0.15),
                               cap=params.get("cap", default_cap), window=params.get("window", 21))
    if name == "F10xVT":
        gate = sma_month_end_state(spy, params.get("months", 10))
        return vol_target_band(spy, start_i, target=params.get("target", 0.15), cap=1.0,
                               window=params.get("window", 21), gate=gate)
    if name == "TOM":
        captured = captured_mask(data.calendar, last_n=params.get("last_n", 1), first_n=params.get("first_n", 3))
        return _calendar_state(data, captured, start_i)
    if name == "HAL":
        captured = captured_mask(data.calendar, months=(11, 12, 1, 2, 3, 4))
        return _calendar_state(data, captured, start_i)
    if name == "RSI2":
        return rsi2_signal(spy, start_i, entry_below=params.get("entry_below", 10.0))
    if name == "FIXED":
        return fixed_weight_signal(params["weight"], data.dates, start_i)
    raise ValueError(f"unknown rule {name}")


def _calendar_state(data: MarketData, captured: np.ndarray, start_i: int) -> Signal:
    held = held_by_date(data.calendar, captured)
    dates = data.dates
    n = len(dates)
    decided = np.zeros(n)
    decided[:-1] = held.reindex(dates[1:]).fillna(False).to_numpy(float)
    return state_signal(_binary_state(decided), start_i)


def simulate(data: MarketData, name: str, start, *, cost: float = 0.001, **params) -> EngineResult:
    """Run one named rule from ``start`` (a date) with the common prices and cash factors."""
    start_i = int(data.dates.searchsorted(pd.Timestamp(start)))
    prices = pd.DataFrame({"a": data.spy.to_numpy(float), "b": data.bond.to_numpy(float)}, index=data.dates)
    signal = build_signal(name, data, start_i, **params)
    return run_overlay(prices, signal, start_i, cost, data.cash_pos, data.cash_neg)


# --------------------------------------------------------------------------- metrics

def excess_sharpe(returns: pd.Series, tbill: pd.Series) -> float:
    """mean(daily return - daily T-bill) / std(same) * sqrt(252)."""
    excess = (returns - tbill.reindex(returns.index)).dropna()
    sd = excess.std(ddof=1)
    return float(excess.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 0 else float("nan")


def yearly_returns(nav: pd.Series) -> pd.Series:
    """Calendar-year returns; the first year starts from the first NAV (1.0)."""
    last = nav.groupby(nav.index.year).last()
    prev = last.shift(1)
    prev.iloc[0] = nav.iloc[0]
    return last / prev - 1.0


def segment_slice(nav: pd.Series, start, end) -> pd.Series:
    """Prior close (if any) plus the closes in [start, end], so the first return is inside the segment."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    prior = nav[nav.index < start]
    seg = nav[(nav.index >= start) & (nav.index <= end)]
    return pd.concat([prior.iloc[-1:], seg]) if len(prior) and len(seg) else seg


def perf_metrics(nav: pd.Series, tbill: pd.Series, spy_weight: pd.Series, n_trades: int) -> dict:
    """CAGR, vol, Sharpe, MaxDD, Calmar and the descriptive columns used in the study."""
    ret = nav.pct_change().dropna()
    dd = sc.drawdown(nav)
    cagr = sc.annualized(nav)
    max_dd = float(dd.min())
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    yearly = yearly_returns(nav)
    return {"cagr": cagr, "vol": float(ret.std(ddof=1) * np.sqrt(TRADING_DAYS)),
            "sharpe": excess_sharpe(ret, tbill), "max_dd": max_dd,
            "calmar": cagr / abs(max_dd) if max_dd else float("nan"),
            "avg_weight": float(spy_weight.iloc[1:].mean()), "trades_per_year": n_trades / years,
            "share_days_dd_below_20": float((dd < -0.20).mean()),
            "worst_year": float(yearly.min()), "worst_year_label": int(yearly.idxmin()),
            "final_multiple": float(nav.iloc[-1] / nav.iloc[0]), "years": years}


def count_trades(result: EngineResult) -> int:
    """Executions that change the position, excluding the initial purchase."""
    t = result.trades
    if t.empty:
        return 0
    return int(((t["traded_frac"] > 1e-9) & (~t["is_initial"])).sum())


def key_period_stats(nav: pd.Series, start: str, end: str) -> dict:
    return sc.period_stats(nav, start, end)


# --------------------------------------------------------------------------- timing placebo (generic)

def placebo_scores(weights: np.ndarray, returns: np.ndarray, dates, cash_annual: float, shifts) -> dict:
    """Circular shifts of the weight path, scored like ``band_timing.timing_placebo`` (previous-day weights,
    constant cash rate per 365 calendar days) but also returning the Sharpe ratio.

    ``weights`` / ``returns``: (n, k) arrays aligned to ``dates``. Returns the shift-0 ("actual") tuple and
    arrays of CAGR, Sharpe and MaxDD over the shifts.
    """
    dates = pd.DatetimeIndex(dates)
    days = np.r_[0.0, (dates[1:] - dates[:-1]).days.to_numpy(float)]
    cash = (1.0 + cash_annual) ** (days / 365.0) - 1.0
    years = (dates[-1] - dates[0]).days / 365.25

    def score(path: np.ndarray) -> tuple[float, float, float]:
        held = np.vstack([path[:1], path[:-1]])
        port = (held * returns).sum(axis=1) + (1.0 - held.sum(axis=1)) * cash
        nav = np.cumprod(1.0 + port)
        excess = (port - cash)[1:]
        sd = excess.std(ddof=1)
        sharpe = float(excess.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 0 else float("nan")
        dd = float((nav / np.maximum.accumulate(nav) - 1.0).min())
        return float(nav[-1] ** (1.0 / years) - 1.0), sharpe, dd

    actual = score(weights)
    shifted = np.array([score(np.roll(weights, s, axis=0)) for s in shifts])
    return {"actual": actual, "cagr": shifted[:, 0], "sharpe": shifted[:, 1], "dd": shifted[:, 2]}


# --------------------------------------------------------------------------- DCA lens

def contribution_dates(dates, start, end) -> pd.DatetimeIndex:
    """First trading day of every month between ``start`` and ``end`` (inclusive)."""
    d = pd.DatetimeIndex(dates)
    d = d[(d >= pd.Timestamp(start)) & (d <= pd.Timestamp(end))]
    return d[~d.to_period("M").duplicated()]


def ten_year_window(dates, first_contribution) -> Optional[tuple[pd.DatetimeIndex, pd.Timestamp]]:
    """120 monthly contributions starting at ``first_contribution``; the terminal date is the last trading day
    of the 120th month. Returns None unless that month is complete in the data."""
    d = pd.DatetimeIndex(dates)
    first_period = pd.Timestamp(first_contribution).to_period("M")
    periods = pd.period_range(first_period, periods=120, freq="M")
    if periods[-1] >= d[-1].to_period("M"):
        return None
    months = d.to_period("M")
    contrib = d[~months.duplicated() & months.isin(periods)]
    end = d[months == periods[-1]][-1]
    return contrib, end


def dca_account(nav: pd.Series, contrib: pd.DatetimeIndex, end, fee: float = 0.001) -> dict:
    """Unified account: each 1-unit contribution buys strategy units at that day's NAV, net of ``fee``.

    Account value V_t = sum(units bought up to t) * NAV_t; principal_t = contributions up to t.
    XIRR with ``cashflow_research.xirr``; unit-value drawdown is the NAV (TWR) drawdown inside the window.
    """
    from xquant.cashflow_research import xirr

    nav = nav[(nav.index >= contrib[0]) & (nav.index <= pd.Timestamp(end))]
    add = pd.Series(0.0, index=nav.index)
    add.loc[contrib] = (1.0 - fee) / nav.loc[contrib].to_numpy(float)
    units = add.cumsum()
    flow = pd.Series(0.0, index=nav.index)
    flow.loc[contrib] = 1.0
    principal = flow.cumsum()
    value = units * nav
    float_ret = value / principal - 1.0
    unit_dd = nav / nav.cummax() - 1.0
    terminal = float(value.iloc[-1])
    rate = xirr(pd.Series(1.0, index=contrib), terminal, nav.index[-1])
    max_dd = float(unit_dd.min())
    return {"xirr": rate, "terminal_value": terminal, "contributed": float(len(contrib)),
            "terminal_per_contributed": terminal / float(len(contrib)),
            "max_float_loss": float(float_ret.min()), "unit_max_dd": max_dd,
            "ratio": rate / abs(max_dd) if max_dd < 0 else float("nan")}


def sd1_account(spy: pd.Series, cash_pos: pd.Series, contrib: pd.DatetimeIndex, end, thresholds=(-0.10, -0.20),
                fee: float = 0.001) -> dict:
    """SD1 smart DCA: each contribution is 1 unit. Drawdown DD = SPY below its running max at the previous close.
    DD > t1: invest 0.8, keep 0.2 in T-bills. t2 < DD <= t1: invest 1 + 50% of the reserve. DD <= t2: invest 1 + all
    of the reserve. Invested money is SPY bought at that close (net of ``fee``); the reserve earns T-bills.
    Terminal value = SPY units * SPY + reserve. Returns the account stats used in the DCA comparison."""
    from xquant.cashflow_research import xirr

    t1, t2 = thresholds
    dd_prev = (spy / spy.cummax() - 1.0).shift(1).fillna(0.0)  # no history yet: no drawdown
    idx = spy.index[(spy.index >= contrib[0]) & (spy.index <= pd.Timestamp(end))]
    px = spy.loc[idx].to_numpy(float)
    growth = cash_pos.loc[idx].to_numpy(float)
    prior = dd_prev.loc[idx].to_numpy(float)
    is_contrib = idx.isin(contrib)
    units, reserve, principal = 0.0, 0.0, 0.0
    value = np.empty(len(idx))
    princ = np.empty(len(idx))
    invested_total = 0.0
    for k in range(len(idx)):
        if k:
            reserve *= growth[k]
        if is_contrib[k]:
            principal += 1.0
            dd = prior[k]
            if dd > t1:
                invest = 0.8
                reserve += 0.2
            elif dd > t2:
                invest = 1.0 + 0.5 * reserve
                reserve *= 0.5
            else:
                invest = 1.0 + reserve
                reserve = 0.0
            invested_total += invest
            units += invest * (1.0 - fee) / px[k]
        value[k] = units * px[k] + reserve
        princ[k] = principal
    float_ret = value / princ - 1.0
    terminal = float(value[-1])
    rate = xirr(pd.Series(1.0, index=contrib), terminal, idx[-1])
    return {"xirr": rate, "terminal_value": terminal, "contributed": principal,
            "terminal_per_contributed": terminal / principal, "max_float_loss": float(float_ret.min()),
            "final_reserve": reserve, "invested_total": invested_total}


def synthetic_bond_returns(dgs10_pct: pd.Series) -> pd.Series:
    """Daily bond return from the 10-year yield (percent, aligned to trading days, already forward-filled):
    r_t = y_{t-1}/252 - 7.5 * (y_t - y_{t-1}), with y in decimals (carry minus duration times yield change)."""
    y = dgs10_pct / 100.0
    previous = y.shift(1)
    ret = previous / TRADING_DAYS - 7.5 * (y - previous)
    ret.iloc[0] = 0.0
    return ret.rename("synthetic_bond_return")


def long_total_return(price: pd.Series, annual_dividend_yield: pd.Series) -> pd.Series:
    """Total-return index: daily price return plus the month's annual dividend yield / 252 on every day."""
    ret = price.pct_change() + annual_dividend_yield.reindex(price.index).to_numpy(float) / TRADING_DAYS
    ret.iloc[0] = 0.0
    return (1.0 + ret).cumprod() * float(price.iloc[0])
