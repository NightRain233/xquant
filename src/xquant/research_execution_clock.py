"""Daily-bar research execution with explicit UTC clocks and cash ordering.

This is an idealized fractional, instant-settlement cash ledger, not a broker
model. Prices are carried only after each bar's close becomes available.
"""
from functools import lru_cache
import numpy as np
import pandas as pd
import exchange_calendars as xcals


@lru_cache(maxsize=40000)
def stamp(symbol, day, field):
    day = pd.Timestamp(day).normalize().tz_localize(None)
    if symbol == 'BTC-USD':
        return day.tz_localize('UTC') + (pd.Timedelta(days=1) if field == 'Close' else pd.Timedelta(0))
    if symbol.endswith(('.SS','.SZ')):
        return (day + pd.Timedelta(hours=15 if field == 'Close' else 9, minutes=0 if field == 'Close' else 30)).tz_localize('Asia/Shanghai').tz_convert('UTC')
    cal = us_calendar()
    return cal.session_close(day) if field == 'Close' else cal.session_open(day)


@lru_cache(maxsize=1)
def us_calendar():
    return xcals.get_calendar('XNYS', start='2013-01-01', end='2027-12-31')


class PriceBook:
    def __init__(self, frames):
        self.frames = frames
        self.clocks = {}
        self.values = {}
        self.quote_clocks = {}
        for symbol, frame in frames.items():
            self.clocks[symbol] = np.array([stamp(symbol,d,'Close').value + 10**9 for d in frame.index],dtype=np.int64)
            self.values[symbol] = frame.Close.to_numpy(dtype=float)

    def latest(self, symbol, when):
        pos = int(np.searchsorted(self.clocks[symbol],pd.Timestamp(when).value,side='right'))-1
        if pos < 0:
            raise ValueError(f'No completed {symbol} close before {when}')
        return float(self.values[symbol][pos]), pd.Timestamp(self.clocks[symbol][pos],tz='UTC')

    def next_quote(self, symbol, after, field):
        frame = self.frames[symbol]
        key = (symbol, field)
        if key not in self.quote_clocks:
            self.quote_clocks[key] = np.array([stamp(symbol,d,field).value for d in frame.index],dtype=np.int64)
        clocks = self.quote_clocks[key]
        pos = int(np.searchsorted(clocks,pd.Timestamp(after).value,side='right'))
        if pos >= len(frame):
            return None
        return stamp(symbol,frame.index[pos],field), frame.index[pos], float(frame.iloc[pos][field])

    def mark(self, state, when, quotes=None):
        quotes = quotes or {}
        prices = {}
        clocks = {}
        for symbol, qty in state['shares'].items():
            if qty <= 1e-15:
                continue
            if symbol in quotes:
                prices[symbol] = float(quotes[symbol])
                clocks[symbol] = pd.Timestamp(when)
            else:
                prices[symbol], clocks[symbol] = self.latest(symbol,when)
        nav = float(state['cash']) + sum(qty*prices[s] for s,qty in state['shares'].items() if qty>1e-15)
        return nav, prices, clocks


def rebalance_group(state, target, book, when, quotes, fee_bps, slip_bps, cash_symbol):
    """Rebalance only markets trading now; no later proceeds or quotes enter."""
    gross, prices, clocks = book.mark(state,when,quotes)
    prices.update(quotes)
    clocks.update({s:pd.Timestamp(when) for s in quotes})
    desired = {s:gross*max(0.,target.get(s,0.)) for s in quotes}
    fee, slip = fee_bps/1e4, slip_bps/1e4
    before_cash = float(state['cash'])
    before_shares = dict(state['shares'])
    before_cost = float(state['costPaid'])
    trades = []
    conservation_error = 0.
    for s in sorted(quotes):
        p = float(quotes[s]); qty = state['shares'].get(s,0.)
        sell = max(0.,min(qty,qty-desired[s]/p))
        if sell <= 1e-15:
            continue
        px=p*(1-slip); commission=sell*px*fee
        state['cash'] += sell*px-commission
        state['shares'][s] = qty-sell
        state['costPaid'] += commission+sell*p*slip
        trades.append({'symbol':s,'side':'sell','shares':sell,'price':px,'fee':commission,'executedAt':str(when)})
    needs={s:max(0.,desired[s]-state['shares'].get(s,0.)*quotes[s]) for s in quotes}
    required=sum(needs.values())*(1+fee)
    reserve=max(0.,target.get(cash_symbol,0.))*gross
    available=max(0.,state['cash']-reserve)
    scale=min(1.,available/required) if required>0 else 0.
    for s in sorted(needs):
        budget=needs[s]*scale
        if budget<=1e-15:
            continue
        p=float(quotes[s]); px=p*(1+slip); qty=budget/px; commission=budget*fee
        state['cash']-=budget+commission
        state['shares'][s]=state['shares'].get(s,0.)+qty
        state['costPaid']+=commission+qty*p*slip
        trades.append({'symbol':s,'side':'buy','shares':qty,'price':px,'fee':commission,'executedAt':str(when)})
    reconstructed=before_cash+sum((1 if t['side']=='sell' else -1)*t['shares']*t['price']-t['fee'] for t in trades)
    conservation_error=abs(state['cash']-reconstructed)
    if state['cash'] < -1e-8 or conservation_error > max(1e-8,gross*1e-12):
        raise AssertionError('Cash reconciliation failed')
    state['cash']=max(0.,state['cash'])
    state['shares']={s:q for s,q in state['shares'].items() if q>1e-15}
    post_nav, _, _ = book.mark(state,when,quotes)
    nav_error = abs(post_nav-(gross-(state['costPaid']-before_cost)))
    expected = dict(before_shares)
    for trade in trades:
        s = trade['symbol']
        expected[s] = expected.get(s,0.)+(1 if trade['side']=='buy' else -1)*trade['shares']
    quantity_error = max((abs(q-state['shares'].get(s,0.)) for s,q in expected.items()), default=0.)
    if nav_error > max(1e-8,gross*1e-12) or quantity_error > 1e-8:
        raise AssertionError('NAV/quantity reconciliation failed')
    return {'trades':trades,'gross':gross,'cashBefore':before_cash,'cashAfter':state['cash'],
            'cashError':conservation_error,'navError':nav_error,'quantityError':quantity_error,
            'unfilledDesiredValues':{s:max(0.,desired[s]-state['shares'].get(s,0.)*quotes[s]) for s in quotes},
            'pricesKnownAt':{s:str(t) for s,t in clocks.items()},'executionAt':str(when)}


def available_signal(day, symbols):
    return max(stamp(s,day,'Close') for s in symbols)+pd.Timedelta(seconds=1)
