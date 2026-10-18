"""Simplified Weinstein stage-2 trend strategy on A-share ETFs (weekly signals).

Rules (frozen in the 2026-10-18 review):

* weekly close = last trading day close of each Monday–Friday week;
* buy when weekly close > N-week SMA, SMA > SMA four weeks earlier, and the
  26-week return beats the benchmark's (510300) 26-week return;
* sell when weekly close < N-week SMA;
* orders fill at the next trading day's open; equal slot sizing, at most
  ``max_positions`` holdings, ranking new candidates by relative strength;
  existing holdings are never displaced by better-ranked candidates.

The same engine is reused unchanged for the US sector-ETF review
(``weinstein-us-sector-2026-10-18``, benchmark SPY); the only additions for that
review are ``load_yfinance_csv`` and the optional cash-yield accrual
(``cash_growth_from_yield`` / ``cash_growth=``), which default to the original
0 % cash behaviour.

Signals use only data up to the signal week's close; ``signal_week_dates`` and
``execution_dates`` make that boundary explicit and testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import numpy as np
import pandas as pd

from xquant.metrics import drawdown_series


@dataclass(frozen=True)
class CostModel:
    fee_rate: float = 0.0005
    slippage: float = 0.0005


@dataclass(frozen=True)
class StageParams:
    ma_weeks: int = 30
    slope_lag_weeks: int = 4
    rs_weeks: int = 26
    max_positions: int = 5
    slot_weight: float = 0.20


# --------------------------------------------------------------------------- data

def load_tickflow_batches(paths, *, provider_to_symbol=None) -> dict[str, pd.DataFrame]:
    """Parse TickFlow batch kline JSON files into ``{symbol: DataFrame[open, close]}``."""
    frames = {}
    for path in paths:
        payload = json.loads(Path(path).read_text())
        for key, data in (payload.get("data") or {}).items():
            if not data.get("timestamp"):
                continue
            index = (pd.to_datetime(data["timestamp"], unit="ms", utc=True)
                     .tz_convert("Asia/Shanghai").tz_localize(None).normalize())
            frame = pd.DataFrame({"open": data["open"], "close": data["close"]}, index=index, dtype=float)
            frame = frame.loc[~frame.index.duplicated()].sort_index().dropna()
            symbol = (provider_to_symbol or {}).get(key, key)
            frames[symbol] = frame
    return frames


def panel(frames: dict[str, pd.DataFrame], column: str, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """Align one price column to a common trading calendar (no fill)."""
    return pd.DataFrame({s: f[column] for s, f in frames.items()}).reindex(calendar)


def load_yfinance_csv(path) -> pd.DataFrame:
    """Parse a saved ``yfinance`` ``history()`` CSV into tz-naive ``DataFrame[open, close]`` by exchange date.

    The CSV is expected to be written with ``auto_adjust=True`` (Open/Close already
    adjusted for splits and dividends). Exchange-local dates are kept as is.
    """
    raw = pd.read_csv(path)
    dates = pd.DatetimeIndex([pd.Timestamp(str(v)[:10]) for v in raw["Date"]])
    frame = pd.DataFrame({"open": raw["Open"].to_numpy(dtype=float), "close": raw["Close"].to_numpy(dtype=float)},
                         index=dates)
    return frame.loc[~frame.index.duplicated()].sort_index().dropna()


def cash_growth_from_yield(annual_yield_pct: pd.Series, calendar: pd.DatetimeIndex) -> pd.Series:
    """Multiplicative cash accrual per trading day from an annualised yield in percent (e.g. ^IRX).

    The factor on day ``d`` covers the calendar days since the previous trading day
    and uses the yield observed on that previous day (known before ``d``): no
    look-ahead. The first day has factor 1.0. Missing yields are forward-filled
    from earlier observations only.
    """
    y = annual_yield_pct.reindex(annual_yield_pct.index.union(calendar)).sort_index().ffill().reindex(calendar)
    prev_y = y.shift(1)
    gaps = pd.Series(calendar, index=calendar).diff().dt.days
    growth = (1.0 + prev_y.clip(lower=0.0) / 100.0) ** (gaps / 365.0)
    growth.iloc[0] = 1.0
    if growth.isna().any():
        raise ValueError("cash yield missing before the first trading day")
    return growth.rename("cash_growth")


def weekly_closes(daily_close: pd.DataFrame) -> pd.DataFrame:
    """Last available close per Mon–Fri week, labelled by the week's last calendar trading day."""
    periods = daily_close.index.to_period("W-FRI")
    weekly = daily_close.groupby(periods).last()  # last non-NaN per column within the week
    last_day = pd.Series(daily_close.index, index=daily_close.index).groupby(periods).max()
    weekly.index = pd.DatetimeIndex(last_day.loc[weekly.index].to_numpy())
    weekly.index.name = "week_end"
    return weekly


def execution_dates(week_ends: pd.DatetimeIndex, calendar: pd.DatetimeIndex) -> pd.Series:
    """Next trading day after each week end; NaT when the week is the last in the data."""
    pos = calendar.searchsorted(week_ends, side="right")
    values = [calendar[p] if p < len(calendar) else pd.NaT for p in pos]
    return pd.Series(values, index=week_ends, name="execution_date")


# ------------------------------------------------------------------------ signals

@dataclass
class StageSignals:
    close: pd.DataFrame
    ma: pd.DataFrame
    rising: pd.DataFrame
    rs: pd.DataFrame
    eligible: pd.DataFrame
    buy: pd.DataFrame
    sell: pd.DataFrame


def stage_signals(weekly_close: pd.DataFrame, benchmark: str, params: StageParams = StageParams()) -> StageSignals:
    """Weekly entry/exit flags. Row ``t`` only uses weekly closes at or before ``t``."""
    ma = weekly_close.rolling(params.ma_weeks, min_periods=params.ma_weeks).mean()
    ma_prev = ma.shift(params.slope_lag_weeks)
    ret = weekly_close / weekly_close.shift(params.rs_weeks) - 1.0
    rs = ret.sub(ret[benchmark], axis=0)
    eligible = ma.notna() & ma_prev.notna() & rs.notna() & weekly_close.notna()
    rising = ma > ma_prev
    buy = eligible & (weekly_close > ma) & rising & (rs > 0)
    sell = weekly_close.notna() & ma.notna() & (weekly_close < ma)
    return StageSignals(weekly_close, ma, rising, rs, eligible, buy, sell)


# ------------------------------------------------------------------------- engine

@dataclass
class Book:
    """Cash + fractional share ledger with next-open fills and round-trip records."""
    cash: float = 1.0
    costs: CostModel = field(default_factory=CostModel)
    shares: dict = field(default_factory=dict)
    lots: dict = field(default_factory=dict)
    trades: list = field(default_factory=list)
    fills: list = field(default_factory=list)

    def value(self, prices: pd.Series) -> float:
        return float(sum(q * prices[s] for s, q in self.shares.items()))

    def buy(self, date, symbol, open_price, spend, signal_week=None):
        spend = min(spend, self.cash)
        if spend <= 1e-12:
            return
        fill = open_price * (1 + self.costs.slippage)
        qty = spend / (fill * (1 + self.costs.fee_rate))
        self.cash -= spend
        self.shares[symbol] = self.shares.get(symbol, 0.0) + qty
        lot = self.lots.setdefault(symbol, {"symbol": symbol, "entry_signal_week": signal_week, "entry_date": date,
                                            "entry_open": open_price, "spent": 0.0, "received": 0.0})
        lot["spent"] += spend
        self.fills.append({"date": date, "symbol": symbol, "side": "buy", "open": open_price,
                           "fill_price": fill, "quantity": qty, "cash_flow": -spend, "signal_week": signal_week})

    def sell(self, date, symbol, open_price, quantity=None, signal_week=None):
        held = self.shares.get(symbol, 0.0)
        qty = held if quantity is None else min(quantity, held)
        if qty <= 0:
            return
        fill = open_price * (1 - self.costs.slippage)
        proceeds = qty * fill * (1 - self.costs.fee_rate)
        self.cash += proceeds
        remaining = held - qty
        lot = self.lots[symbol]
        lot["received"] += proceeds
        self.fills.append({"date": date, "symbol": symbol, "side": "sell", "open": open_price,
                           "fill_price": fill, "quantity": qty, "cash_flow": proceeds, "signal_week": signal_week})
        if remaining <= 1e-12 * max(held, 1.0):
            del self.shares[symbol]
            lot = self.lots.pop(symbol)
            self.trades.append({**lot, "exit_signal_week": signal_week, "exit_date": date, "exit_open": open_price,
                                "status": "closed"})
        else:
            self.shares[symbol] = remaining


def _mark(book: Book, date, close_row: pd.Series, last_close: dict) -> dict:
    for s in book.shares:
        if pd.notna(close_row.get(s, np.nan)):
            last_close[s] = close_row[s]
    holdings = sum(q * last_close[s] for s, q in book.shares.items())
    nav = book.cash + holdings
    return {"date": date, "cash": book.cash, "holdings": holdings, "nav": nav,
            "exposure": holdings / nav if nav > 0 else 0.0, "positions": len(book.shares)}


def _open_or_last(open_row, s, last_close):
    price = open_row.get(s, np.nan)
    return price if pd.notna(price) else last_close.get(s, np.nan)


def _finalize(book: Book, rows, last_close, end_date):
    nav = pd.DataFrame(rows).set_index("date")
    trades = list(book.trades)
    for s, lot in book.lots.items():  # mark open positions at the last close, without exit costs
        trades.append({**lot, "received": book.shares[s] * last_close[s], "exit_signal_week": pd.NaT,
                       "exit_date": end_date, "exit_open": np.nan, "status": "open"})
    trades = pd.DataFrame(trades)
    if not trades.empty:
        trades["return"] = trades["received"] / trades["spent"] - 1.0
        trades["holding_weeks"] = (pd.to_datetime(trades["exit_date"]) - pd.to_datetime(trades["entry_date"])).dt.days / 7.0
    return nav, trades, pd.DataFrame(book.fills)


def run_stage_strategy(daily_open: pd.DataFrame, daily_close: pd.DataFrame, signals: StageSignals,
                       start, params: StageParams = StageParams(), costs: CostModel = CostModel(),
                       cash_growth: pd.Series | None = None):
    """Simulate the stage strategy from ``start`` (first execution day) to the end of the data.

    Decisions for signal week ``w`` are taken from the holdings that exist after
    week ``w-1``'s orders filled and execute at the next trading day's open.
    ``cash_growth`` (optional, see ``cash_growth_from_yield``) accrues interest on
    idle cash at the start of each day, before that day's orders; default 0 %.
    """
    calendar = daily_close.index
    exec_map = execution_dates(signals.close.index, calendar).dropna()
    exec_map = exec_map[exec_map >= pd.Timestamp(start)]
    by_exec = {d: w for w, d in exec_map.items()}
    book = Book(cash=1.0, costs=costs)
    last_close: dict = {}
    pending: list = []  # orders whose symbol had no open on the scheduled day
    rows = []
    days = calendar[calendar >= pd.Timestamp(start)]
    for d in days:
        open_row, close_row = daily_open.loc[d], daily_close.loc[d]
        if cash_growth is not None and d != days[0]:
            book.cash *= float(cash_growth.loc[d])
        orders = pending
        pending = []
        if d in by_exec:
            w = by_exec[d]
            held_after_sells = [s for s in book.shares if not bool(signals.sell.at[w, s])]
            for s in list(book.shares):
                if bool(signals.sell.at[w, s]):
                    orders.append(("sell", s, w))
            slots = params.max_positions - len(held_after_sells)
            if slots > 0:
                cand = signals.rs.loc[w][signals.buy.loc[w]].drop(labels=held_after_sells, errors="ignore")
                ranked = sorted(cand.index, key=lambda s: (-cand[s], s))  # RS desc, code as tie-break
                for s in ranked[:slots]:
                    orders.append(("buy", s, w))
        sells = [o for o in orders if o[0] == "sell"]
        buys = [o for o in orders if o[0] == "buy"]
        for _, s, w in sells:
            if pd.notna(open_row.get(s, np.nan)):
                book.sell(d, s, open_row[s], signal_week=w)
            else:
                pending.append(("sell", s, w))
        if buys:
            nav_open = book.cash + sum(q * _open_or_last(open_row, s, last_close) for s, q in book.shares.items())
            for _, s, w in buys:
                if s in book.shares:
                    continue
                if pd.notna(open_row.get(s, np.nan)):
                    book.buy(d, s, open_row[s], params.slot_weight * nav_open, signal_week=w)
                else:
                    pending.append(("buy", s, w))
        rows.append(_mark(book, d, close_row, last_close))
    return _finalize(book, rows, last_close, days[-1])


def run_target_weights(daily_open: pd.DataFrame, daily_close: pd.DataFrame, schedule: dict, start,
                       costs: CostModel = CostModel(), cash_growth: pd.Series | None = None):
    """Rebalance to ``schedule[exec_date] = {symbol: weight}`` at that day's open (sells first)."""
    calendar = daily_close.index
    days = calendar[calendar >= pd.Timestamp(start)]
    book = Book(cash=1.0, costs=costs)
    last_close: dict = {}
    rows = []
    for d in days:
        open_row, close_row = daily_open.loc[d], daily_close.loc[d]
        if cash_growth is not None and d != days[0]:
            book.cash *= float(cash_growth.loc[d])
        if d in schedule:
            target = schedule[d]
            prices = {s: _open_or_last(open_row, s, last_close) for s in set(book.shares) | set(target)}
            nav_open = book.cash + sum(q * prices[s] for s, q in book.shares.items())
            for s in list(book.shares):
                want = target.get(s, 0.0) * nav_open / prices[s]
                if book.shares[s] > want + 1e-12:
                    book.sell(d, s, prices[s], quantity=book.shares[s] - want if want > 0 else None)
            for s, wgt in target.items():
                have = book.shares.get(s, 0.0) * prices[s]
                if wgt * nav_open > have + 1e-12:
                    book.buy(d, s, prices[s], wgt * nav_open - have)
        rows.append(_mark(book, d, close_row, last_close))
    return _finalize(book, rows, last_close, days[-1])


# ------------------------------------------------------------------------ metrics

def nav_metrics(nav: pd.Series, initial: float = 1.0) -> dict:
    nav = nav.dropna()
    start, end = nav.index[0], nav.index[-1]
    years = ((end - start).days + 1) / 365.25
    rets = pd.concat([pd.Series([nav.iloc[0] / initial - 1.0], index=[start]), nav.pct_change().iloc[1:]])
    dd = drawdown_series(nav, initial_capital=initial)
    return {
        "start": start.date().isoformat(), "end": end.date().isoformat(), "years": years,
        "total_return": nav.iloc[-1] / initial - 1.0,
        "cagr": (nav.iloc[-1] / initial) ** (1 / years) - 1.0,
        "max_drawdown": float(dd.min()),
        "max_drawdown_trough": dd.idxmin().date().isoformat(),
        **longest_underwater(nav, initial),
        "annual_volatility": float(rets.std(ddof=1) * np.sqrt(252)),
    }


def longest_underwater(nav: pd.Series, initial: float = 1.0) -> dict:
    """Longest calendar-day span from a high-water mark until it is regained (or the end)."""
    peak_value, peak_date = initial, nav.index[0] - pd.Timedelta(days=1)
    best = (0, None, None, True)
    underwater = False
    for date, value in nav.items():
        if value >= peak_value:
            if underwater and (date - peak_date).days > best[0]:
                best = ((date - peak_date).days, peak_date, date, True)
            peak_value, peak_date, underwater = value, date, False
        else:
            underwater = True
    if underwater and (nav.index[-1] - peak_date).days > best[0]:
        best = ((nav.index[-1] - peak_date).days, peak_date, None, False)
    return {"longest_recovery_days": int(best[0]),
            "longest_recovery_from": best[1].date().isoformat() if best[1] is not None else None,
            "longest_recovery_to": best[2].date().isoformat() if best[2] is not None else None,
            "longest_recovery_completed": bool(best[3])}


def annual_returns(nav: pd.Series, initial: float = 1.0) -> pd.Series:
    year_end = nav.groupby(nav.index.year).last()
    prev = year_end.shift(1)
    prev.iloc[0] = initial
    return year_end / prev - 1.0


def window_return(nav: pd.Series, start, end, initial: float = 1.0) -> dict:
    """Return and in-window max drawdown from the close before ``start`` to the last close <= ``end``."""
    before = nav[nav.index < pd.Timestamp(start)]
    base = before.iloc[-1] if len(before) else initial
    seg = nav[(nav.index >= pd.Timestamp(start)) & (nav.index <= pd.Timestamp(end))]
    path = pd.concat([pd.Series([base]), seg.reset_index(drop=True)])
    return {"return": seg.iloc[-1] / base - 1.0, "max_drawdown": float((path / path.cummax() - 1).min())}


def trade_metrics(trades: pd.DataFrame, years: float) -> dict:
    closed = trades[trades["status"] == "closed"] if not trades.empty else trades
    if closed.empty:
        return {"round_trips": 0}
    wins, losses = closed[closed["return"] > 0], closed[closed["return"] <= 0]
    avg_win = wins["return"].mean() if len(wins) else np.nan
    avg_loss = losses["return"].mean() if len(losses) else np.nan
    return {
        "round_trips": int(len(closed)),
        "open_positions_at_end": int((trades["status"] == "open").sum()),
        "round_trips_per_year": len(closed) / years,
        "orders": int(2 * len(closed) + (trades["status"] == "open").sum()),
        "win_rate": len(wins) / len(closed),
        "avg_win": avg_win, "avg_loss": avg_loss,
        "payoff_ratio": avg_win / abs(avg_loss) if avg_loss and not np.isnan(avg_loss) else np.nan,
        "profit_factor": (wins["received"] - wins["spent"]).sum() / abs((losses["received"] - losses["spent"]).sum())
        if len(losses) else np.nan,
        "avg_trade_return": closed["return"].mean(),
        "median_trade_return": closed["return"].median(),
        "avg_holding_weeks": closed["holding_weeks"].mean(),
        "median_holding_weeks": closed["holding_weeks"].median(),
        "best_trade": closed["return"].max(), "worst_trade": closed["return"].min(),
    }
