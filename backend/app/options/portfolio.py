from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

OptionType = Literal["call", "put"]
Side = Literal["long", "short"]

@dataclass(frozen=True)
class Leg:
    instrument: Literal["option"]
    option_type: OptionType
    side: Side
    strike: float
    premium: float
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

def leg_pnl_at_expiry(leg: Leg, S: float) -> float:
    if leg.strike <= 0:
        raise ValueError("strike must be > 0")
    if leg.premium < 0:
        raise ValueError("premium must be >= 0")
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

def portfolio_pnl_at_expiry(legs: List[Leg], S: float) -> float:
    if not legs:
        raise ValueError("legs must be a non-empty list")
    return sum(leg_pnl_at_expiry(leg, S) for leg in legs)

def portfolio_curve(
    legs: List[Leg],
    s_min: float,
    s_max: float,
    steps: int = 201
) -> List[PLPoint]:
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
    # Finds x where pnl crosses 0 by linear interpolation between adjacent points.
    if len(curve) < 2:
        return []
    bes: List[float] = []
    for a, b in zip(curve, curve[1:]):
        ya, yb = a.pnl, b.pnl
        if ya == 0.0:
            bes.append(a.underlying)
            continue
        if ya * yb < 0:  # sign change
            # linear interpolation: x = x0 + (0 - y0)*(x1-x0)/(y1-y0)
            x0, x1 = a.underlying, b.underlying
            x = x0 + (-ya) * (x1 - x0) / (yb - ya)
            bes.append(x)
    # de-dup near equals
    bes_sorted = sorted(bes)
    out: List[float] = []
    for x in bes_sorted:
        if not out or abs(x - out[-1]) > 1e-6:
            out.append(x)
    return out
