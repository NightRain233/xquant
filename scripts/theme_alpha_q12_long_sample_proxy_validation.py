from pathlib import Path
from dataclasses import dataclass
import json
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

from xquant.indicators import select_low_vol_trend, supertrend_direction
from xquant.metrics import (
    drawdown_series as calculate_drawdown_series,
    nav_from_returns as calculate_nav_from_returns,
)
from xquant.portfolio import (
    inverse_volatility_weights,
    normalize_weights,
)
from xquant.project import find_repo_root

warnings.filterwarnings("ignore")
plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "STHeiti"]
plt.rcParams["axes.unicode_minus"] = False


REPO_ROOT = find_repo_root(Path(__file__))
OUTPUT_DIR = REPO_ROOT / "outputs/theme-alpha-q12-long-sample-proxy-validation"
NOTE_PATH = REPO_ROOT / "docs/notes/theme-alpha-q12-long-sample-proxy-validation-review.md"
NOTEBOOK_PATH = REPO_ROOT / "research/notebooks/theme-alpha-q12-long-sample-proxy-validation-practice.ipynb"

TRADING_DAYS = 252
INITIAL_NAV = 100.0
END = (pd.Timestamp.today() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

MA_WINDOW = 60
MOM_WINDOW = 63
VOL_WINDOW = 60
TOP_N = 3
RP_VOL_WINDOW = 20
CAP = 0.50
DEFENSE_WINDOW = 200
BASE_COST_BPS = 20
THRESHOLD = 0.02
MAX_TRADE = 0.15
DEFAULT_ATR = 10
DEFAULT_MULTIPLIER = 3.0

CORE_ROLES = ("CSI300", "NASDAQ", "GOLD")
EXPANDED_ROLES = (
    "NASDAQ",
    "NONFERROUS",
    "CHIP",
    "COMM",
    "GOLD",
    "DIVIDEND",
    "ENERGY",
    "BROKER",
    "HK_TECH",
    "HEALTHCARE",
)

ETF_SYMBOLS = {
    "CSI300": "510300.SS",
    "NASDAQ": "513100.SS",
    "GOLD": "518880.SS",
    "NONFERROUS": "512400.SS",
    "CHIP": "159995.SZ",
    "COMM": "515880.SS",
    "DIVIDEND": "510880.SS",
    "ENERGY": "159930.SZ",
    "BROKER": "512880.SS",
    "HK_TECH": "513180.SS",
    "HEALTHCARE": "512170.SS",
}

ETF_NAMES = {
    "CSI300": "沪深300ETF",
    "NASDAQ": "纳指100ETF",
    "GOLD": "黄金ETF",
    "NONFERROUS": "有色金属ETF",
    "CHIP": "芯片ETF",
    "COMM": "通信ETF",
    "DIVIDEND": "红利ETF",
    "ENERGY": "能源ETF",
    "BROKER": "证券ETF",
    "HK_TECH": "恒生科技ETF",
    "HEALTHCARE": "医疗ETF",
}

PROXY_SYMBOLS = {
    "CSI300": "ASHR",
    "NASDAQ": "QQQ",
    "GOLD": "GLD",
    "NONFERROUS": "DBB",
    "CHIP": "SOXX",
    "COMM": "VOX",
    "DIVIDEND": "DVY",
    "ENERGY": "XLE",
    "BROKER": "KCE",
    "HK_TECH": "KWEB",
    "HEALTHCARE": "XLV",
}

PROXY_NAMES = {
    "CSI300": "ASHR A股代理",
    "NASDAQ": "QQQ 纳指代理",
    "GOLD": "GLD 黄金代理",
    "NONFERROUS": "DBB 基本金属代理",
    "CHIP": "SOXX 半导体代理",
    "COMM": "VOX 通信服务代理",
    "DIVIDEND": "DVY 股息代理",
    "ENERGY": "XLE 能源代理",
    "BROKER": "KCE 券商/资本市场代理",
    "HK_TECH": "KWEB 中国互联网代理",
    "HEALTHCARE": "XLV 医疗代理",
}

PROXY_NOTES = {
    "CSI300": "ASHR 是美元计价 A 股 ETF，不等同人民币沪深300ETF或指数。",
    "NASDAQ": "QQQ 是美元计价美国 ETF，和境内 QDII 纳指 ETF 有汇率、限购和溢价差异。",
    "GOLD": "GLD 是美元计价黄金 ETF，和境内黄金 ETF 的货币与交易时段不同。",
    "NONFERROUS": "DBB 跟踪基本金属期货，不等同有色金属股票 ETF。",
    "CHIP": "SOXX 是美国半导体股票 ETF，不等同中国芯片 ETF。",
    "COMM": "VOX 是美国通信服务 ETF，不等同中国通信 ETF。",
    "DIVIDEND": "DVY 是美国高股息 ETF，不等同中国红利 ETF。",
    "ENERGY": "XLE 是美国能源股票 ETF，不等同中国能源 ETF。",
    "BROKER": "KCE 是美国资本市场/券商 ETF，不等同中国证券 ETF。",
    "HK_TECH": "KWEB 是中国互联网 ETF，不等同恒生科技 ETF。",
    "HEALTHCARE": "XLV 是美国医疗 ETF，不等同中国医疗 ETF。",
}

ROLE_EXTRA_FRICTION_BPS = {
    "CSI300": 5,
    "GOLD": 5,
    "DIVIDEND": 5,
    "NASDAQ": 20,
    "HK_TECH": 20,
    "NONFERROUS": 10,
    "CHIP": 10,
    "COMM": 10,
    "ENERGY": 10,
    "BROKER": 10,
    "HEALTHCARE": 10,
}

WINDOWS = {
    "full_sample": (None, None),
    "2015_2018": ("2015-01-01", "2018-12-31"),
    "2019_2021": ("2019-01-01", "2021-12-31"),
    "2022_2026": ("2022-01-01", None),
    "2020_to_date_real_etf": ("2020-01-01", None),
    "2025_to_date": ("2025-01-01", None),
    "2026_ytd": ("2026-01-01", None),
}

STRATEGY_DEFINITIONS = {
    "Original_RiskParity_3Asset": "原三资产 RiskParity：沪深300/纳指/黄金或对应 proxy，固定半月调仓。",
    "Expanded_LVT_100": "全仓 Expanded LowVolTrend：扩展资产池内 MA60+63D 动量通过后选低波 Top3，RP cap50。",
    "Core80_LVT20_Def200_Cash": "Core80 / Expanded LVT20 / Def200 Cash，Q8 当前准实盘候选。",
    "Core60_LVT40_Def200_Cash": "Core60 / Expanded LVT40 / Def200 Cash，更进攻卫星档位。",
    "Core80_LVT20_STEntry_Def200_Cash": "Q11 混合候选：LVT 新进入资产必须 SuperTrend 多头，已有资产可由 LVT 自然退出。",
    "Core80_LVT20_STHalf_Def200_Cash": "Q11 仓位降权候选：LVT 选中但 ST 空头时卫星权重减半，释放到现金。",
}


@dataclass
class StudyContext:
    layer: str
    symbols_by_role: dict
    names_by_role: dict
    data_start: str
    note_by_role: dict | None = None
    common_start: str | None = None

    @property
    def roles(self):
        return tuple(dict.fromkeys(CORE_ROLES + EXPANDED_ROLES))

    @property
    def core_symbols(self):
        return tuple(self.symbols_by_role[r] for r in CORE_ROLES)

    @property
    def expanded_symbols(self):
        return tuple(self.symbols_by_role[r] for r in EXPANDED_ROLES)

    @property
    def all_symbols(self):
        return tuple(dict.fromkeys(self.core_symbols + self.expanded_symbols))

    def role_for_symbol(self, symbol):
        for role, sym in self.symbols_by_role.items():
            if sym == symbol:
                return role
        raise KeyError(symbol)

    def name_for_symbol(self, symbol):
        role = self.role_for_symbol(symbol)
        return self.names_by_role[role]

    def friction_for_symbol(self, symbol):
        return ROLE_EXTRA_FRICTION_BPS[self.role_for_symbol(symbol)]


def flatten_yfinance_columns(df, symbol):
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [col[0] if len(col) > 1 and col[1] == symbol else "_".join(map(str, col)).strip() for col in out.columns]
    out.columns = [str(c).lower().replace(" ", "_") for c in out.columns]
    return out


def download_symbol(symbol, start):
    df = yf.download(symbol, start=start, end=END, auto_adjust=True, progress=False, threads=False)
    if df.empty:
        raise RuntimeError(f"No data downloaded for {symbol}")
    df = flatten_yfinance_columns(df, symbol)
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"{symbol} missing columns: {missing}")
    df = df[required].dropna(subset=["close"]).copy()
    df.index = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
    return df


def download_market(ctx):
    raw = {sym: download_symbol(sym, ctx.data_start) for sym in ctx.all_symbols}
    index = pd.DatetimeIndex(sorted(set().union(*[set(df.index) for df in raw.values()])))
    frames = {}
    for field in ["open", "high", "low", "close", "volume"]:
        frames[field] = pd.DataFrame({sym: raw[sym][field].reindex(index) for sym in ctx.all_symbols})
    market = {
        "open_raw": frames["open"],
        "high_raw": frames["high"],
        "low_raw": frames["low"],
        "close_raw": frames["close"],
        "volume_raw": frames["volume"],
        "open": frames["open"].ffill(),
        "high": frames["high"].ffill(),
        "low": frames["low"].ffill(),
        "close": frames["close"].ffill(),
        "volume": frames["volume"].fillna(0.0),
    }
    market["returns"] = market["close"].pct_change(fill_method=None)
    market["value_traded"] = market["close_raw"] * market["volume_raw"]
    return market


def availability_table(ctx, market):
    rows = []
    for role in ctx.roles:
        sym = ctx.symbols_by_role[role]
        px = market["close_raw"][sym].dropna()
        vol = market["volume_raw"][sym].dropna()
        rows.append({
            "layer": ctx.layer,
            "role": role,
            "symbol": sym,
            "name": ctx.names_by_role[role],
            "first_date": px.index.min().date() if len(px) else pd.NaT,
            "last_date": px.index.max().date() if len(px) else pd.NaT,
            "price_rows": int(len(px)),
            "volume_rows": int(len(vol)),
            "proxy_note": (ctx.note_by_role or {}).get(role, ""),
        })
    return pd.DataFrame(rows)


def signal_dates(index):
    idx = pd.DatetimeIndex(index)
    dates = []
    months = pd.period_range(idx.min().to_period("M"), idx.max().to_period("M"), freq="M")
    for period in months:
        for day in (10, 25):
            anchor = pd.Timestamp(year=period.year, month=period.month, day=min(day, period.days_in_month))
            pos = idx.searchsorted(anchor)
            if pos < len(idx) and idx[pos].to_period("M") == period:
                dates.append(idx[pos])
    return set(pd.DatetimeIndex(sorted(set(dates))))


def enough_history(close, sym, loc, window):
    if loc < window:
        return False
    hist = close[sym].iloc[loc - window + 1:loc + 1]
    return hist.notna().all()


def enough_return_history(returns, sym, loc, window):
    if loc < window:
        return False
    hist = returns[sym].iloc[loc - window + 1:loc + 1]
    return hist.notna().all()


def risk_parity_weight(market, date, eligible, universe, cap=None):
    close = market["close"]
    returns = market["returns"]
    loc = close.index.get_loc(date)
    eligible = [sym for sym in eligible if sym in universe and enough_return_history(returns, sym, loc, RP_VOL_WINDOW)]
    if not eligible:
        return normalize_weights({}, universe)
    hist = returns.iloc[loc - RP_VOL_WINDOW + 1:loc + 1][eligible]
    return inverse_volatility_weights(hist, universe, cap)


def low_vol_trend_select(market, universe, date):
    return select_low_vol_trend(
        market["close"],
        market["returns"],
        date,
        universe,
        ma_window=MA_WINDOW,
        momentum_window=MOM_WINDOW,
        volatility_window=VOL_WINDOW,
        top_n=TOP_N,
    )


def build_supertrend_matrix(market, universe):
    return pd.DataFrame({
        sym: supertrend_direction(
            market["high"][sym],
            market["low"][sym],
            market["close"][sym],
            atr_window=DEFAULT_ATR,
            multiplier=DEFAULT_MULTIPLIER,
        )
        for sym in universe
    })


def build_signal_weights(market, universe, selector, allocator):
    sdates = signal_dates(market["close"].index)
    rows = []
    last = normalize_weights({}, universe)
    for date in market["close"].index:
        if date in sdates:
            last = allocator(date, selector(date))
        rows.append(last)
    out = pd.DataFrame(rows, index=market["close"].index).fillna(0.0)
    for col in list(universe) + ["CASH"]:
        if col not in out.columns:
            out[col] = 0.0
    return out[list(universe) + ["CASH"]]


def build_core_defense(market, ctx, core_weights):
    close = market["close"]
    sdates = signal_dates(close.index)
    rows = []
    core_universe = list(ctx.core_symbols)
    csi = ctx.symbols_by_role["CSI300"]
    nasdaq = ctx.symbols_by_role["NASDAQ"]
    last = normalize_weights({}, core_universe)
    for date in close.index:
        if date in sdates:
            loc = close.index.get_loc(date)
            base = core_weights.loc[date, core_universe + ["CASH"]].copy()
            for sym in (csi, nasdaq):
                risk_on = enough_history(close, sym, loc, DEFENSE_WINDOW) and close.at[date, sym] > close[sym].iloc[loc - DEFENSE_WINDOW + 1:loc + 1].mean()
                if not risk_on:
                    moved = base[sym]
                    base[sym] = 0.0
                    base["CASH"] += moved
            last = normalize_weights(base.to_dict(), core_universe)
        rows.append(last)
    out = pd.DataFrame(rows, index=close.index).fillna(0.0)
    return out[core_universe + ["CASH"]]


def expand_weights(weights, all_symbols):
    out = pd.DataFrame(0.0, index=weights.index, columns=list(all_symbols) + ["CASH"])
    for col in weights.columns:
        if col in out.columns:
            out[col] = weights[col]
    return out


def combine_weights(market, ctx, sleeves):
    out = pd.DataFrame(0.0, index=market["close"].index, columns=list(ctx.all_symbols) + ["CASH"])
    for allocation, weights in sleeves:
        out += allocation * expand_weights(weights, ctx.all_symbols).reindex(market["close"].index).ffill().fillna(0.0)
    total = out[list(ctx.all_symbols)].sum(axis=1) + out["CASH"]
    return out.div(total.replace(0, np.nan), axis=0).fillna(0.0)


def apply_execution_timing(market, ctx, target_weights):
    cols = list(ctx.all_symbols) + ["CASH"]
    sdates = signal_dates(market["close"].index)
    idx = market["close"].index
    executed_rows = []
    current = pd.Series(0.0, index=cols)
    current["CASH"] = 1.0
    pending = None
    for i, date in enumerate(idx):
        if pending is not None and pending["execute_date"] == date:
            desired = pending["target"]
            turnover = 0.5 * (desired - current).abs().sum()
            if turnover >= THRESHOLD - 1e-12:
                asset_cols = list(ctx.all_symbols)
                delta = (desired[asset_cols] - current[asset_cols]).clip(lower=-MAX_TRADE, upper=MAX_TRADE)
                new_assets = (current[asset_cols] + delta).clip(lower=0.0)
                asset_sum = new_assets.sum()
                if asset_sum > 1.0:
                    new_assets = new_assets / asset_sum
                    cash = 0.0
                else:
                    cash = 1.0 - asset_sum
                current = pd.concat([new_assets, pd.Series({"CASH": cash})]).reindex(cols).fillna(0.0)
            pending = None
        if date in sdates:
            desired = target_weights.loc[date, cols].copy()
            execute_idx = min(i + 1, len(idx) - 1)
            pending = {"execute_date": idx[execute_idx], "target": desired}
        executed_rows.append(current.to_dict())
    return pd.DataFrame(executed_rows, index=idx).fillna(0.0)[cols]


def asset_turnover(weights, asset_cols):
    return weights[list(asset_cols)].diff().abs().fillna(weights[list(asset_cols)].abs())


def backtest(market, ctx, weights):
    asset_cols = list(ctx.all_symbols)
    gross = (weights[asset_cols].shift(1).fillna(0.0) * market["returns"][asset_cols]).sum(axis=1).fillna(0.0)
    trades = asset_turnover(weights, asset_cols)
    cost_rates = pd.Series({sym: (BASE_COST_BPS + ctx.friction_for_symbol(sym)) / 10000.0 for sym in asset_cols})
    costs = (trades * cost_rates).sum(axis=1).fillna(0.0)
    return {"returns": gross - costs, "gross_returns": gross, "costs": costs, "weights": weights, "trades": trades}


def nav_from_returns(r):
    return calculate_nav_from_returns(r, initial_capital=INITIAL_NAV)


def drawdown_series(nav):
    return calculate_drawdown_series(nav, initial_capital=INITIAL_NAV)


def drawdown_events(nav):
    dd = drawdown_series(nav)
    events = []
    in_dd = False
    start = trough = None
    min_dd = 0.0
    for date, val in dd.items():
        if val < -1e-12 and not in_dd:
            in_dd = True
            start = date
            trough = date
            min_dd = float(val)
        elif in_dd:
            if val < min_dd:
                min_dd = float(val)
                trough = date
            if val >= -1e-12:
                events.append({
                    "start": start,
                    "trough": trough,
                    "recovery": date,
                    "max_depth": min_dd,
                    "duration_days": int((date - start).days),
                    "recovered": True,
                })
                in_dd = False
    if in_dd:
        events.append({
            "start": start,
            "trough": trough,
            "recovery": pd.NaT,
            "max_depth": min_dd,
            "duration_days": int((dd.index[-1] - start).days),
            "recovered": False,
        })
    return pd.DataFrame(events)


def period_slice(obj, start, end):
    out = obj.copy()
    if start is not None:
        out = out.loc[pd.Timestamp(start):]
    if end is not None:
        out = out.loc[:pd.Timestamp(end)]
    if isinstance(out, pd.DataFrame):
        return out.dropna(how="all")
    return out.dropna()


def repair_stats(nav):
    events = drawdown_events(nav)
    if events.empty:
        return {
            "平均修复天数": 0.0,
            "最长修复天数": 0,
            "未修复回撤": 0.0,
            "未修复已持续天数": 0,
        }
    recovered = events[events["recovered"]]
    unrecovered = events[~events["recovered"]]
    return {
        "平均修复天数": float(recovered["duration_days"].mean()) if len(recovered) else 0.0,
        "最长修复天数": int(recovered["duration_days"].max()) if len(recovered) else 0,
        "未修复回撤": float(unrecovered["max_depth"].iloc[-1]) if len(unrecovered) else 0.0,
        "未修复已持续天数": int(unrecovered["duration_days"].iloc[-1]) if len(unrecovered) else 0,
    }


def metrics_row(ctx, name, port, start, end):
    r = period_slice(port["returns"], start, end)
    w = period_slice(port["weights"], start, end)
    costs = period_slice(port["costs"], start, end)
    trades = period_slice(port["trades"], start, end)
    if len(r) < 20:
        return None
    nav = nav_from_returns(r)
    total = float((1.0 + r).prod() - 1.0)
    years = max(len(r) / TRADING_DAYS, 1e-12)
    ann = (1.0 + total) ** (1.0 / years) - 1.0
    vol = float(r.std(ddof=1) * np.sqrt(TRADING_DAYS))
    sharpe = ann / vol if vol > 0 else np.nan
    downside = r[r < 0].std(ddof=1) * np.sqrt(TRADING_DAYS)
    sortino = ann / downside if downside and downside > 0 else np.nan
    dd = drawdown_series(nav)
    mdd = float(dd.min()) if len(dd) else np.nan
    calmar = ann / abs(mdd) if mdd < 0 else np.nan
    monthly = r.resample("ME").apply(lambda x: (1.0 + x).prod() - 1.0)
    gains = monthly[monthly > 0]
    losses = monthly[monthly < 0]
    under = dd < -1e-12
    rep = repair_stats(nav)
    row = {
        "layer": ctx.layer,
        "strategy": name,
        "definition": STRATEGY_DEFINITIONS[name],
        "start": r.index.min().date(),
        "end": r.index.max().date(),
        "observations": int(len(r)),
        "累计收益": total,
        "年化收益": ann,
        "年化波动": vol,
        "最大回撤": mdd,
        "Sharpe": sharpe,
        "Calmar": calmar,
        "Sortino": sortino,
        "月胜率": float((monthly > 0).mean()) if len(monthly) else np.nan,
        "平均盈利月": float(gains.mean()) if len(gains) else 0.0,
        "平均亏损月": float(losses.mean()) if len(losses) else 0.0,
        "最差月份": float(monthly.min()) if len(monthly) else np.nan,
        "最好月份": float(monthly.max()) if len(monthly) else np.nan,
        "盈利因子": float(gains.sum() / abs(losses.sum())) if abs(losses.sum()) > 1e-12 else np.nan,
        "水下时间占比": float(under.mean()) if len(under) else np.nan,
        "平均水下": float(dd[under].mean()) if under.any() else 0.0,
        "超过-10%回撤天数": int((dd <= -0.10).sum()),
        "超过-20%回撤天数": int((dd <= -0.20).sum()),
        "年化换手": float(trades.sum(axis=1).sum() / years),
        "交易成本": float(costs.sum()),
        "年化成本拖累": float(costs.sum() / years),
        "平均现金": float(w["CASH"].mean()),
        "当前现金": float(w["CASH"].iloc[-1]),
    }
    row.update(rep)
    for sym in ctx.all_symbols:
        label = ctx.name_for_symbol(sym)
        row[f"平均权重_{label}"] = float(w[sym].mean()) if sym in w else 0.0
        row[f"当前权重_{label}"] = float(w[sym].iloc[-1]) if sym in w else 0.0
    return row


def annual_returns_table(portfolios):
    rows = []
    for layer_strategy, port in portfolios.items():
        layer, strategy = layer_strategy
        annual = port["returns"].resample("YE").apply(lambda x: (1.0 + x).prod() - 1.0)
        for date, value in annual.items():
            rows.append({"layer": layer, "strategy": strategy, "year": int(date.year), "return": float(value)})
    return pd.DataFrame(rows)


def monthly_returns_table(portfolios):
    rows = []
    for layer_strategy, port in portfolios.items():
        layer, strategy = layer_strategy
        monthly = port["returns"].resample("ME").apply(lambda x: (1.0 + x).prod() - 1.0)
        for date, value in monthly.items():
            rows.append({"layer": layer, "strategy": strategy, "month": date.strftime("%Y-%m"), "return": float(value)})
    return pd.DataFrame(rows)


def build_portfolios(ctx, market):
    core_universe = ctx.core_symbols
    expanded_universe = ctx.expanded_symbols
    all_symbols = ctx.all_symbols
    st = build_supertrend_matrix(market, expanded_universe)

    core = build_signal_weights(
        market,
        core_universe,
        lambda _date: list(core_universe),
        lambda date, eligible: risk_parity_weight(market, date, eligible, core_universe, None),
    )
    core_def = build_core_defense(market, ctx, core)
    lvt = build_signal_weights(
        market,
        expanded_universe,
        lambda date: low_vol_trend_select(market, expanded_universe, date),
        lambda date, eligible: risk_parity_weight(market, date, eligible, expanded_universe, CAP),
    )

    sdates = signal_dates(market["close"].index)
    entry_rows = []
    last = normalize_weights({}, expanded_universe)
    for date in market["close"].index:
        if date in sdates:
            lvt_selected = low_vol_trend_select(market, expanded_universe, date)
            st_long = set(st.columns[st.loc[date].fillna(False)])
            last_active = {sym for sym in expanded_universe if last.get(sym, 0.0) > 1e-10}
            eligible = [sym for sym in lvt_selected if (sym in st_long) or (sym in last_active)]
            last = risk_parity_weight(market, date, eligible, expanded_universe, CAP)
        entry_rows.append(last)
    lvt_entry = pd.DataFrame(entry_rows, index=market["close"].index).fillna(0.0)
    for col in list(expanded_universe) + ["CASH"]:
        if col not in lvt_entry.columns:
            lvt_entry[col] = 0.0
    lvt_entry = lvt_entry[list(expanded_universe) + ["CASH"]]

    def half_allocator(date, eligible):
        base = risk_parity_weight(market, date, eligible, expanded_universe, CAP)
        if not eligible:
            return base
        st_long = set(st.columns[st.loc[date].fillna(False)])
        adjusted = {}
        for sym in expanded_universe:
            val = base.get(sym, 0.0)
            adjusted[sym] = val if sym in st_long else val * 0.5
        return normalize_weights(adjusted, expanded_universe)

    lvt_half = build_signal_weights(
        market,
        expanded_universe,
        lambda date: low_vol_trend_select(market, expanded_universe, date),
        half_allocator,
    )

    targets = {
        "Original_RiskParity_3Asset": combine_weights(market, ctx, [(1.00, core)]),
        "Expanded_LVT_100": combine_weights(market, ctx, [(1.00, lvt)]),
        "Core80_LVT20_Def200_Cash": combine_weights(market, ctx, [(0.80, core_def), (0.20, lvt)]),
        "Core60_LVT40_Def200_Cash": combine_weights(market, ctx, [(0.60, core_def), (0.40, lvt)]),
        "Core80_LVT20_STEntry_Def200_Cash": combine_weights(market, ctx, [(0.80, core_def), (0.20, lvt_entry)]),
        "Core80_LVT20_STHalf_Def200_Cash": combine_weights(market, ctx, [(0.80, core_def), (0.20, lvt_half)]),
    }
    return {name: backtest(market, ctx, apply_execution_timing(market, ctx, target)) for name, target in targets.items()}


def restrict_market_from(market, start):
    if start is None:
        return market
    start_ts = pd.Timestamp(start)
    return {key: value.loc[start_ts:].copy() if isinstance(value, pd.DataFrame) else value for key, value in market.items()}


def run_layer(ctx, output_dir):
    market = download_market(ctx)
    availability = availability_table(ctx, market)
    availability.to_csv(output_dir / f"data_availability_{ctx.layer}.csv", index=False, encoding="utf-8-sig")
    if ctx.common_start:
        market = restrict_market_from(market, ctx.common_start)
    portfolios = build_portfolios(ctx, market)
    summary_rows = []
    for window, (start, end) in WINDOWS.items():
        for name, port in portfolios.items():
            row = metrics_row(ctx, name, port, start, end)
            if row is None:
                continue
            row["window"] = window
            summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_dir / f"summary_{ctx.layer}.csv", index=False, encoding="utf-8-sig")

    latest = []
    average = []
    for name, port in portfolios.items():
        w = port["weights"]
        latest.append({"layer": ctx.layer, "strategy": name, **{ctx.name_for_symbol(sym): float(w[sym].iloc[-1]) for sym in ctx.all_symbols}, "现金": float(w["CASH"].iloc[-1])})
        average.append({"layer": ctx.layer, "strategy": name, **{ctx.name_for_symbol(sym): float(w[sym].mean()) for sym in ctx.all_symbols}, "现金": float(w["CASH"].mean())})
    pd.DataFrame(latest).to_csv(output_dir / f"latest_weights_{ctx.layer}.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(average).to_csv(output_dir / f"average_weights_{ctx.layer}.csv", index=False, encoding="utf-8-sig")

    nav_cols = {}
    uw_cols = {}
    for name, port in portfolios.items():
        nav = nav_from_returns(port["returns"])
        nav_cols[name] = nav
        uw_cols[name] = drawdown_series(nav)
        events = drawdown_events(nav)
        events.insert(0, "strategy", name)
        events.insert(0, "layer", ctx.layer)
        events.to_csv(output_dir / f"drawdown_events_{ctx.layer}_{name}.csv", index=False, encoding="utf-8-sig")
    nav_df = pd.DataFrame(nav_cols)
    uw_df = pd.DataFrame(uw_cols)
    nav_df.to_csv(output_dir / f"nav_{ctx.layer}.csv", encoding="utf-8-sig")
    uw_df.to_csv(output_dir / f"underwater_{ctx.layer}.csv", encoding="utf-8-sig")

    for window, (start, end) in {"2015_2018": WINDOWS["2015_2018"], "2022_2026": WINDOWS["2022_2026"], "2025_to_date": WINDOWS["2025_to_date"]}.items():
        sliced = period_slice(nav_df, start, end)
        if len(sliced) < 20:
            continue
        ax = (sliced / sliced.iloc[0] * INITIAL_NAV).plot(figsize=(12, 6), linewidth=1.5)
        ax.set_title(f"{ctx.layer} NAV - {window}")
        ax.set_ylabel("NAV")
        ax.grid(True, alpha=0.25)
        plt.tight_layout()
        plt.savefig(output_dir / f"nav_{ctx.layer}_{window}.png", dpi=160)
        plt.close()
        sliced_uw = period_slice(uw_df, start, end)
        ax = sliced_uw.plot(figsize=(12, 5), linewidth=1.5)
        ax.set_title(f"{ctx.layer} Underwater - {window}")
        ax.set_ylabel("Drawdown")
        ax.grid(True, alpha=0.25)
        plt.tight_layout()
        plt.savefig(output_dir / f"underwater_{ctx.layer}_{window}.png", dpi=160)
        plt.close()

    return market, portfolios, availability, summary


def build_diagnostics(all_summary, availability):
    full = all_summary[all_summary["window"].isin(["full_sample", "2015_2018", "2019_2021", "2022_2026", "2020_to_date_real_etf", "2025_to_date", "2026_ytd"])].copy()
    pivot_cols = ["累计收益", "年化收益", "最大回撤", "Sharpe", "Calmar", "水下时间占比", "超过-10%回撤天数", "超过-20%回撤天数", "年化换手", "年化成本拖累", "平均现金"]
    score = full[["layer", "window", "strategy"] + pivot_cols]
    lvt_risk = score[score["strategy"].isin(["Expanded_LVT_100", "Core80_LVT20_Def200_Cash", "Core60_LVT40_Def200_Cash"])].copy()

    def compare(layer, window, left, right, metric):
        sub = score[(score["layer"] == layer) & (score["window"] == window)].set_index("strategy")
        if left not in sub.index or right not in sub.index:
            return np.nan
        return float(sub.loc[left, metric] - sub.loc[right, metric])

    rows = []
    for layer in score["layer"].unique():
        for window in score["window"].unique():
            rows.append({
                "layer": layer,
                "window": window,
                "lvt_mdd_minus_core80_mdd": compare(layer, window, "Expanded_LVT_100", "Core80_LVT20_Def200_Cash", "最大回撤"),
                "lvt_underwater_minus_core80": compare(layer, window, "Expanded_LVT_100", "Core80_LVT20_Def200_Cash", "水下时间占比"),
                "core60_return_minus_core80": compare(layer, window, "Core60_LVT40_Def200_Cash", "Core80_LVT20_Def200_Cash", "累计收益"),
                "core60_mdd_minus_core80": compare(layer, window, "Core60_LVT40_Def200_Cash", "Core80_LVT20_Def200_Cash", "最大回撤"),
                "st_entry_calmar_minus_core80": compare(layer, window, "Core80_LVT20_STEntry_Def200_Cash", "Core80_LVT20_Def200_Cash", "Calmar"),
            })
    diagnostics = pd.DataFrame(rows)
    availability_diag = availability.copy()
    availability_diag["first_date"] = pd.to_datetime(availability_diag["first_date"])
    pool = availability_diag.groupby("layer").agg(
        earliest_asset_start=("first_date", "min"),
        latest_asset_start=("first_date", "max"),
        latest_asset_role=("role", lambda x: ""),
        asset_count=("role", "count"),
    ).reset_index()
    return score, lvt_risk, diagnostics, pool


def write_notebook():
    source = f'''# Theme Alpha Q12 Long Sample Proxy Validation

本 notebook 是 Q12 的可重复运行入口。它不修改旧 notebook，实际计算由脚本 `scripts/theme_alpha_q12_long_sample_proxy_validation.py` 完成。

研究分三层：

1. 真实 ETF 样本：当前可交易 ETF，沿用 Q8 fixed twice-monthly / next close / asset friction 口径。
2. 长样本 proxy：用 ASHR、QQQ、GLD 等长期 proxy 拉长至 2015 前后，只做结构验证。
3. 共同样本：真实 ETF 使用共同可用时间窗口，检查资产池和上市时间依赖。
'''
    bootstrap = '''# Keep relative research paths stable after this notebook moved.
import os
from xquant.project import find_repo_root

REPO_ROOT = find_repo_root()
os.chdir(REPO_ROOT)
'''
    code = '''%run scripts/theme_alpha_q12_long_sample_proxy_validation.py
'''
    nb = {
        "cells": [
            {"cell_type": "markdown", "id": "q12-overview", "metadata": {}, "source": source.splitlines(True)},
            {
                "cell_type": "code",
                "id": "repo-root-bootstrap",
                "execution_count": None,
                "metadata": {"tags": ["bootstrap"]},
                "outputs": [],
                "source": bootstrap.splitlines(True),
            },
            {"cell_type": "code", "id": "q12-run-script", "execution_count": None, "metadata": {}, "outputs": [], "source": code.splitlines(True)},
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTEBOOK_PATH.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")


def pct(x):
    if pd.isna(x):
        return "NA"
    return f"{x:.2%}"


def num(x):
    if pd.isna(x):
        return "NA"
    return f"{x:.2f}"


def write_review_note(all_summary, diagnostics, pool, availability):
    def row(layer, window, strategy):
        sub = all_summary[(all_summary["layer"] == layer) & (all_summary["window"] == window) & (all_summary["strategy"] == strategy)]
        return sub.iloc[0] if len(sub) else None

    def bullet(layer, window, strategy):
        r = row(layer, window, strategy)
        if r is None:
            return f"- `{layer}` / `{window}` / `{strategy}`: no data"
        return (
            f"- `{layer}` / `{window}` / `{strategy}`: "
            f"收益 {pct(r['累计收益'])}, 年化 {pct(r['年化收益'])}, "
            f"最大回撤 {pct(r['最大回撤'])}, Sharpe {r['Sharpe']:.2f}, "
            f"Calmar {r['Calmar']:.2f}, 水下 {pct(r['水下时间占比'])}, "
            f">-10% 天数 {int(r['超过-10%回撤天数'])}"
        )

    etf_full = "2020_to_date_real_etf"
    proxy_full = "full_sample"
    lines = [
        "# Theme Alpha Q12 Long Sample and Proxy Validation Review",
        "",
        f"Date: {pd.Timestamp.today().date()}",
        "",
        "## 研究目的",
        "",
        "Q12 检验 Q8 当前准实盘候选在更长样本和 proxy 样本中的结构稳健性。重点不是找最高收益，而是判断 LVT、Core/Satellite、Def200 Cash 和 Q11 SuperTrend/LVT 混合候选是否跨周期站得住。",
        "",
        "当前 Q8 实盘候选保持为：",
        "",
        "- `Core80 / Expanded LVT20 / Def200 Cash / fixed twice-monthly / close-signal-next-day-trade / asset-friction`",
        "",
        "本次三层严格分开：",
        "",
        "1. 真实 ETF 样本：当前可交易 ETF，沿用 Q8 准实盘口径。",
        "2. 长样本 proxy：使用 ASHR/QQQ/GLD/DBB/SOXX/VOX/DVY/XLE/KCE/KWEB/XLV 等代理，从 2014 下载、主要观察 2015 以来窗口。",
        "3. 共同样本：真实 ETF 限制到所有当前资产共同可用后的时间窗口，检查资产上市时间和资产池变化影响。",
        "",
        "重要限制：proxy 是结构验证，不是可直接实盘结果。它有币种、交易时段、成分、行业定义和 ETF 机制差异。",
        "",
        "## 策略",
        "",
        "| Strategy | 定义 |",
        "|---|---|",
    ]
    for key, value in STRATEGY_DEFINITIONS.items():
        lines.append(f"| `{key}` | {value} |")
    lines.extend([
        "",
        "## 数据可用性与 proxy 差异",
        "",
        "真实 ETF 与 proxy 的角色对应关系见 `data_availability_all_layers.csv`。共同样本诊断见 `asset_pool_common_sample_diagnostics.csv`。",
        "",
        "proxy 与真实 ETF 的主要差异：",
    ])
    for role in EXPANDED_ROLES:
        lines.append(f"- {role}: {PROXY_SYMBOLS[role]}，{PROXY_NOTES[role]}")

    lines.extend([
        "",
        "## 第一层：真实 ETF 样本",
        "",
        "真实 ETF 层主要回答“现在这套 ETF 是否可实盘”。核心看 2020 至今、2025 至今和 2026 YTD。",
        "",
        "### 2020 至今",
        "",
        bullet("real_etf", etf_full, "Original_RiskParity_3Asset"),
        bullet("real_etf", etf_full, "Expanded_LVT_100"),
        bullet("real_etf", etf_full, "Core80_LVT20_Def200_Cash"),
        bullet("real_etf", etf_full, "Core60_LVT40_Def200_Cash"),
        bullet("real_etf", etf_full, "Core80_LVT20_STEntry_Def200_Cash"),
        "",
        "### 2025 至今与 2026 YTD",
        "",
        bullet("real_etf", "2025_to_date", "Core80_LVT20_Def200_Cash"),
        bullet("real_etf", "2025_to_date", "Core60_LVT40_Def200_Cash"),
        bullet("real_etf", "2025_to_date", "Expanded_LVT_100"),
        bullet("real_etf", "2026_ytd", "Core80_LVT20_Def200_Cash"),
        bullet("real_etf", "2026_ytd", "Core60_LVT40_Def200_Cash"),
        bullet("real_etf", "2026_ytd", "Expanded_LVT_100"),
        "",
        "### ETF 层解释",
        "",
        "真实 ETF 样本仍支持 Q8 的实盘候选。全仓 LVT 通常收益更强，但回撤、水下和策略解释难度更高；Core80/LVT20/Def200 Cash 的路径更像可以长期执行的组合，而不是单一主题轮动押注。",
        "",
        "Core60/LVT40 是更进攻档位：如果投资者能接受更深回撤和更高主题暴露，它可作为研究候选；但默认实盘仍不应直接把卫星提高到 40%。",
        "",
        "## 第二层：长样本 proxy 验证",
        "",
        "proxy 层回答“LVT 和 Core/Satellite 思想是否只在 2020 后有效”。这里不能当成境内 ETF 可交易结果，只看结构方向。",
        "",
        "### 2015-2018：A股高波动与熊市压力",
        "",
        bullet("proxy_long_sample", "2015_2018", "Original_RiskParity_3Asset"),
        bullet("proxy_long_sample", "2015_2018", "Expanded_LVT_100"),
        bullet("proxy_long_sample", "2015_2018", "Core80_LVT20_Def200_Cash"),
        bullet("proxy_long_sample", "2015_2018", "Core60_LVT40_Def200_Cash"),
        bullet("proxy_long_sample", "2015_2018", "Core80_LVT20_STEntry_Def200_Cash"),
        "",
        "### 2019-2021：成长/科技与结构行情",
        "",
        bullet("proxy_long_sample", "2019_2021", "Original_RiskParity_3Asset"),
        bullet("proxy_long_sample", "2019_2021", "Expanded_LVT_100"),
        bullet("proxy_long_sample", "2019_2021", "Core80_LVT20_Def200_Cash"),
        bullet("proxy_long_sample", "2019_2021", "Core60_LVT40_Def200_Cash"),
        "",
        "### 2022-2026：近年完整样本",
        "",
        bullet("proxy_long_sample", "2022_2026", "Original_RiskParity_3Asset"),
        bullet("proxy_long_sample", "2022_2026", "Expanded_LVT_100"),
        bullet("proxy_long_sample", "2022_2026", "Core80_LVT20_Def200_Cash"),
        bullet("proxy_long_sample", "2022_2026", "Core60_LVT40_Def200_Cash"),
        "",
        "### proxy 层解释",
        "",
        "长样本 proxy 没有给 LVT 一个漂亮的跨周期胜利。2015-2018 和 2022-2026 中，全仓 Expanded LVT 的收益、回撤和水下质量都偏弱，说明不能把近五年真实 ETF 的 LVT 表现简单外推成“通用 alpha”。更准确的解释是：LVT 在当前 ETF 扩展池里有用，但 proxy 长样本降低了我们对它作为独立主引擎的信心。",
        "",
        "Core/Satellite 在 proxy 里的结论也不是单向胜利：2015-2018 和 2019-2021 原三资产 RiskParity 更强；但 2022-2026 里 Core80/LVT20/Def200 Cash 明显降低回撤和 -10% 以下水下天数。这说明它更像压力期风险结构，而不是每个牛市都能跑赢的收益结构。",
        "",
        "## 第三层：共同样本/共同资产池验证",
        "",
        "共同样本层只使用当前 ETF 共同可用后的时间窗口，避免某些 ETF 后来才出现造成的错觉。",
        "",
        bullet("real_etf_common_sample", "full_sample", "Original_RiskParity_3Asset"),
        bullet("real_etf_common_sample", "full_sample", "Expanded_LVT_100"),
        bullet("real_etf_common_sample", "full_sample", "Core80_LVT20_Def200_Cash"),
        bullet("real_etf_common_sample", "full_sample", "Core60_LVT40_Def200_Cash"),
        bullet("real_etf_common_sample", "full_sample", "Core80_LVT20_STEntry_Def200_Cash"),
        "",
        "共同样本结果没有显示结论完全依赖“后来上市 ETF”。如果共同样本和真实 ETF 全样本差异较小，主要原因是当前扩展池大多在 2020 年初已有数据；真正需要警惕的是 proxy 和真实 ETF 的资产定义差异，而不是 ETF 数据缺口本身。",
        "",
        "## 重点诊断",
        "",
    ])

    diag_rows = diagnostics[(diagnostics["layer"].isin(["real_etf", "proxy_long_sample", "real_etf_common_sample"])) & (diagnostics["window"].isin(["2020_to_date_real_etf", "2015_2018", "2022_2026", "full_sample"]))]
    if not diag_rows.empty:
        lines.append("| layer | window | LVT MDD - Core80 MDD | LVT underwater - Core80 | Core60 return - Core80 | Core60 MDD - Core80 | ST Entry Calmar - Core80 |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for _, r in diag_rows.iterrows():
            lines.append(
                f"| {r['layer']} | {r['window']} | {pct(r['lvt_mdd_minus_core80_mdd'])} | {pct(r['lvt_underwater_minus_core80'])} | "
                f"{pct(r['core60_return_minus_core80'])} | {pct(r['core60_mdd_minus_core80'])} | {num(r['st_entry_calmar_minus_core80'])} |"
            )

    lines.extend([
        "",
        "解释：最大回撤差值为负，代表全仓 LVT 比 Core80 更深；水下差值为正，代表全仓 LVT 更长时间处于回撤。Core60 收益差值为正但回撤差值为负时，说明它确实是用更大路径风险换收益。",
        "",
        "## 对 Q11 SuperTrend/LVT 混合的长样本判断",
        "",
        "Q11 的 `EntryFilter` 在真实 ETF 和共同样本里仍是合理纸面候选：收益几乎不输 Q8 基准，回撤和 Calmar 略有改善。但长样本 proxy 不支持把它升级成默认主策略。它更像风险确认层：某些窗口能改善 Calmar 或回撤，但优势不稳定，且 proxy 层的资产定义差异会放大判断噪声。",
        "",
        "`STHalf` 的逻辑更防守，适合继续观察“降低卫星暴露是否能换来更平滑路径”，但它不应替代 Q8 基准。Q11 的原结论仍成立：SuperTrend 可作为 LVT 的确认灯，而不是 LVT 的替代 alpha。",
        "",
        "## 通俗结论",
        "",
        "### 近五年结论是否可能过拟合？",
        "",
        "有可能部分过拟合。近五年包含黄金、纳指和部分主题 ETF 很有利的阶段，且真实 ETF 样本不够长。长样本 proxy 没有证明 LVT 是通用赢家，反而提示近五年可能高估了 LVT 的路径舒适度。",
        "",
        "### 拉长到十年后，LVT 因子是否仍值得相信？",
        "",
        "仍值得继续研究和使用，但只能作为卫星因子相信。当前真实 ETF 样本支持 LVT 有用；proxy 长样本则提醒我们，它不是稳定跑赢所有周期的主引擎，不能承担整个组合的风险管理责任。",
        "",
        "### 全仓 LVT 是否适合作为主策略？",
        "",
        "不适合。全仓 LVT 的收益可能很诱人，但长样本下最大回撤、水下时间和未修复回撤风险更差，容易在真正压力期让执行者放弃策略。",
        "",
        "### Core80/LVT20/Def200 Cash 是否仍是最稳妥实盘候选？",
        "",
        "是，但理由要说准确：它不是因为所有样本都收益最好，而是因为真实 ETF 和共同样本里风险调整后最稳，proxy 压力期也显示 Def200 Cash 能明显降低深回撤。Def200 Cash 的价值在于把核心权益风险从“硬扛”改成“风险差时降暴露”。",
        "",
        "### 是否应该提高 LVT 仓位到 30%、40% 或 60%？",
        "",
        "不建议直接提高到 60%，也不建议把 40% 升为默认。40% 在真实 ETF 近年样本里更进攻，但共同样本和 proxy 长样本并不支持它作为更稳答案。30% 是下一阶段最值得补测的中间档：如果要提高进攻性，应该先验证 30%，而不是跳到 40% 或 60%。",
        "",
        "### 下一阶段应该研究什么？",
        "",
        "1. 用同一 Q8 口径补测 Core70/LVT30/Def200 Cash，作为 20% 和 40% 之间的真实中间档。",
        "2. 做 proxy 资产替代敏感性：例如 ASHR vs 000300 指数、DBB vs XME、KWEB vs 恒生科技指数。",
        "3. 加入组合层风控：当核心和卫星同时弱势时，是否需要 portfolio-level risk-off。",
        "4. 做 live paper tracking，把 Q8 Baseline、Q11 EntryFilter、Core60/40 进攻档分开跟踪，而不是提前合并结论。",
        "",
        "## 文件",
        "",
        "- Notebook: `research/notebooks/theme-alpha-q12-long-sample-proxy-validation-practice.ipynb`",
        "- Outputs: `outputs/theme-alpha-q12-long-sample-proxy-validation/`",
        "- Main summary: `summary_all_layers.csv`",
        "- Diagnostics: `long_sample_diagnostics.csv`, `asset_pool_common_sample_diagnostics.csv`",
        "- Availability: `data_availability_all_layers.csv`",
    ])
    NOTE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    contexts = [
        StudyContext("real_etf", ETF_SYMBOLS, ETF_NAMES, "2020-01-01"),
        StudyContext("proxy_long_sample", PROXY_SYMBOLS, PROXY_NAMES, "2014-01-01", PROXY_NOTES),
    ]
    layer_results = []
    all_availability = []
    all_portfolios = {}
    for ctx in contexts:
        print(f"Running layer: {ctx.layer}")
        market, portfolios, availability, summary = run_layer(ctx, OUTPUT_DIR)
        all_availability.append(availability)
        layer_results.append(summary)
        for name, port in portfolios.items():
            all_portfolios[(ctx.layer, name)] = port
        if ctx.layer == "real_etf":
            latest_start = pd.to_datetime(availability["first_date"]).max()
            common_ctx = StudyContext("real_etf_common_sample", ETF_SYMBOLS, ETF_NAMES, "2020-01-01", common_start=str(latest_start.date()))
            print(f"Running layer: {common_ctx.layer} from {common_ctx.common_start}")
            common_market, common_portfolios, common_availability, common_summary = run_layer(common_ctx, OUTPUT_DIR)
            all_availability.append(common_availability)
            layer_results.append(common_summary)
            for name, port in common_portfolios.items():
                all_portfolios[(common_ctx.layer, name)] = port

    all_summary = pd.concat(layer_results, ignore_index=True)
    availability = pd.concat(all_availability, ignore_index=True)
    all_summary.to_csv(OUTPUT_DIR / "summary_all_layers.csv", index=False, encoding="utf-8-sig")
    availability.to_csv(OUTPUT_DIR / "data_availability_all_layers.csv", index=False, encoding="utf-8-sig")

    annual_returns_table(all_portfolios).to_csv(OUTPUT_DIR / "annual_returns.csv", index=False, encoding="utf-8-sig")
    monthly_returns_table(all_portfolios).to_csv(OUTPUT_DIR / "monthly_returns.csv", index=False, encoding="utf-8-sig")

    score, lvt_risk, diagnostics, pool = build_diagnostics(all_summary, availability)
    score.to_csv(OUTPUT_DIR / "scorecard_selected_metrics.csv", index=False, encoding="utf-8-sig")
    lvt_risk.to_csv(OUTPUT_DIR / "lvt_vs_core_satellite_risk_diagnostics.csv", index=False, encoding="utf-8-sig")
    diagnostics.to_csv(OUTPUT_DIR / "long_sample_diagnostics.csv", index=False, encoding="utf-8-sig")
    pool.to_csv(OUTPUT_DIR / "asset_pool_common_sample_diagnostics.csv", index=False, encoding="utf-8-sig")

    write_notebook()
    write_review_note(all_summary, diagnostics, pool, availability)
    print(f"Wrote {OUTPUT_DIR}")
    print(f"Wrote {NOTEBOOK_PATH}")
    print(f"Wrote {NOTE_PATH}")


if __name__ == "__main__":
    main()
