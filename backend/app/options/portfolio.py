from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

Instrument = Literal["option", "stock"]
OptionType = Literal["call", "put"]
Side = Literal["long", "short"]

@dataclass(frozen=True)
class Leg:
    instrument: Instrument

    # option fields
    option_type: OptionType | None = None
    strike: float | None = None
    premium: float | None = None

    # stock fields
    shares: int | None = None
    entry_price: float | None = None

    # common
    side: Side = "long"
    qty: int = 1
    contract_size: int = 100

@dataclass(frozen=True)
class PLPoint:
    underlying: float
    pnl: float

def _payoff_at_expiry(option_type: str, S: float, K: float) -> float:
    option_type = option_type.lower().strip()
    if option_type == "call":
        return max(S - K, 0.0)
    if option_type == "put":
        return max(K - S, 0.0)
    raise ValueError("option_type must be 'call' or 'put'")

def _option_leg_pnl(leg: Leg, S: float) -> float:
    if leg.option_type is None:
        raise ValueError("option_type is required for option legs")
    if leg.strike is None or leg.strike <= 0:
        raise ValueError("strike must be > 0 for option legs")
    if leg.premium is None or leg.premium < 0:
        raise ValueError("premium must be >= 0 for option legs")
    if leg.qty <= 0:
        raise ValueError("qty must be > 0")
    if leg.contract_size <= 0:
        raise ValueError("contract_size must be > 0")

    payoff = _payoff_at_expiry(leg.option_type, S, leg.strike)

    if leg.side == "long":
        pnl_per_share = payoff - leg.premium
    elif leg.side == "short":
        pnl_per_share = leg.premium - payoff
    else:
        raise ValueError("side must be 'long' or 'short'")

    return pnl_per_share * leg.qty * leg.contract_size

def _stock_leg_pnl(leg: Leg, S: float) -> float:
    if leg.shares is None or leg.shares <= 0:
        raise ValueError("shares must be > 0 for stock legs")
    if leg.entry_price is None or leg.entry_price <= 0:
        raise ValueError("entry_price must be > 0 for stock legs")

    pnl_per_share = (S - leg.entry_price)
    if leg.side == "long":
        return pnl_per_share * leg.shares
    elif leg.side == "short":
        return (-pnl_per_share) * leg.shares
    else:
        raise ValueError("side must be 'long' or 'short'")

def leg_pnl_at_expiry(leg: Leg, S: float) -> float:
    if leg.instrument == "option":
        return _option_leg_pnl(leg, S)
    if leg.instrument == "stock":
        return _stock_leg_pnl(leg, S)
    raise ValueError("instrument must be 'option' or 'stock'")

def portfolio_pnl_at_expiry(legs: List[Leg], S: float) -> float:
    if not legs:
        raise ValueError("legs must be a non-empty list")
    return sum(leg_pnl_at_expiry(leg, S) for leg in legs)

def net_cashflow_at_entry(legs: List[Leg]) -> float:
    """
    Signed cashflow at entry:
      + means cash received (credit)
      - means cash paid (debit)

    Options:
      long option -> pay premium (negative)
      short option -> receive premium (positive)

    Stock:
      long stock -> pay entry_price * shares (negative)
      short stock -> receive proceeds (positive)
    """
    if not legs:
        raise ValueError("legs must be a non-empty list")

    total = 0.0
    for leg in legs:
        if leg.instrument == "option":
            if leg.premium is None:
                raise ValueError("premium is required for option legs")
            if leg.qty <= 0 or leg.contract_size <= 0:
                raise ValueError("qty and contract_size must be > 0")
            cash = leg.premium * leg.qty * leg.contract_size
            total += cash if leg.side == "short" else -cash

        elif leg.instrument == "stock":
            if leg.shares is None or leg.entry_price is None:
                raise ValueError("shares and entry_price are required for stock legs")
            cash = leg.entry_price * leg.shares
            total += cash if leg.side == "short" else -cash

        else:
            raise ValueError("instrument must be 'option' or 'stock'")

    return total

def portfolio_curve(legs: List[Leg], s_min: float, s_max: float, steps: int = 201) -> List[PLPoint]:
    if steps < 2:
        raise ValueError("steps must be >= 2")
    if s_min <= 0 or s_max <= 0:
        raise ValueError("s_min and s_max must be > 0")
    if s_max <= s_min:
        raise ValueError("s_max must be > s_min")

    out: List[PLPoint] = []
    step = (s_max - s_min) / (steps - 1)
    for i in range(steps):
        s = s_min + i * step
        out.append(PLPoint(underlying=s, pnl=portfolio_pnl_at_expiry(legs, s)))
    return out

def breakevens_from_curve(curve: List[PLPoint]) -> List[float]:
    if len(curve) < 2:
        return []
    bes: List[float] = []
    for a, b in zip(curve, curve[1:]):
        ya, yb = a.pnl, b.pnl
        if ya == 0.0:
            bes.append(a.underlying)
            continue
        if ya * yb < 0:
            x0, x1 = a.underlying, b.underlying
            x = x0 + (-ya) * (x1 - x0) / (yb - ya)
            bes.append(x)
    bes_sorted = sorted(bes)
    out: List[float] = []
    for x in bes_sorted:
        if not out or abs(x - out[-1]) > 1e-6:
            out.append(x)
    return out

def extrema_from_curve(curve: List[PLPoint]) -> Tuple[float, float]:
    if not curve:
        raise ValueError("curve must be non-empty")
    pnls = [p.pnl for p in curve]
    return (max(pnls), min(pnls))
