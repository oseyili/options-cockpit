from dataclasses import dataclass
from typing import List, Literal, Optional

OptionType = Literal["call", "put"]
Side = Literal["long", "short"]

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

def single_option_pnl(
    option_type: str,
    side: str,
    S: float,
    K: float,
    premium: float,
    qty: int = 1,
    contract_size: int = 100,
) -> float:
    if premium < 0:
        raise ValueError("premium must be >= 0")
    if qty <= 0:
        raise ValueError("qty must be > 0")
    if contract_size <= 0:
        raise ValueError("contract_size must be > 0")

    payoff = _payoff_at_expiry(option_type, S, K)
    # Long pays premium, Short receives premium
    pnl_per_share = (payoff - premium) if side.lower().strip() == "long" else (premium - payoff)
    return pnl_per_share * qty * contract_size

def single_breakevens(option_type: str, K: float, premium: float) -> List[float]:
    option_type = option_type.lower().strip()
    if option_type == "call":
        return [K + premium]
    if option_type == "put":
        return [K - premium]
    raise ValueError("option_type must be 'call' or 'put'")

def single_max_pl(option_type: str, side: str, K: float, premium: float, qty: int, contract_size: int):
    option_type = option_type.lower().strip()
    side = side.lower().strip()
    # Return (max_profit, max_loss) at expiry. Use None for unbounded.
    if side == "long":
        max_loss = -premium * qty * contract_size
        if option_type == "call":
            return (None, max_loss)  # unbounded upside
        else:
            max_profit = (K - premium) * qty * contract_size  # when S -> 0
            return (max_profit, max_loss)

    if side == "short":
        max_profit = premium * qty * contract_size
        if option_type == "call":
            return (max_profit, None)  # unbounded loss
        else:
            max_loss = -(K - premium) * qty * contract_size  # when S -> 0
            return (max_profit, max_loss)

    raise ValueError("side must be 'long' or 'short'")

def vertical_spread_pnl(
    option_type: str,
    side: str,                 # "long" = long spread, "short" = short spread
    S: float,
    K_long: float,
    K_short: float,
    premium_long: float,
    premium_short: float,
    qty: int = 1,
    contract_size: int = 100,
) -> float:
    # Long spread = buy one strike, sell another
    # For calls: usually K_long < K_short (debit). For puts: usually K_long > K_short (debit)
    payoff_long = _payoff_at_expiry(option_type, S, K_long)
    payoff_short = _payoff_at_expiry(option_type, S, K_short)

    debit = premium_long - premium_short  # can be negative (credit) but we’ll handle sign via side
    payoff_spread = payoff_long - payoff_short

    if side.lower().strip() == "long":
        pnl_per_share = payoff_spread - debit
    elif side.lower().strip() == "short":
        pnl_per_share = debit - payoff_spread
    else:
        raise ValueError("side must be 'long' or 'short'")

    return pnl_per_share * qty * contract_size

def vertical_breakeven(option_type: str, side: str, K_long: float, K_short: float, premium_long: float, premium_short: float) -> List[float]:
    option_type = option_type.lower().strip()
    side = side.lower().strip()
    debit = premium_long - premium_short

    # Return breakeven for the position specified by side
    # For long call spread: BE = K_long + debit
    # For long put spread:  BE = K_long - debit (where K_long is the higher strike typically)
    if side == "long":
        if option_type == "call":
            return [K_long + debit]
        if option_type == "put":
            return [K_long - debit]
    if side == "short":
        # Short spread flips: BE depends on the short's effective strike; simplest is same formula with negative debit
        # Using -debit effectively converts credit to positive.
        credit = -debit
        if option_type == "call":
            return [K_long - credit]
        if option_type == "put":
            return [K_long + credit]

    raise ValueError("option_type must be 'call' or 'put' and side must be 'long' or 'short'")

def vertical_max_pl(option_type: str, side: str, K_long: float, K_short: float, premium_long: float, premium_short: float, qty: int, contract_size: int):
    option_type = option_type.lower().strip()
    side = side.lower().strip()
    debit = premium_long - premium_short

    width = abs(K_short - K_long)

    # Long spread:
    # max_loss = -debit
    # max_profit = width - debit
    if side == "long":
        max_loss = -debit * qty * contract_size
        max_profit = (width - debit) * qty * contract_size
        return (max_profit, max_loss)

    # Short spread:
    # max_profit = debit (which is negative for credit spreads). Better expressed as credit = -debit.
    # max_loss = -(width - credit)
    if side == "short":
        credit = -debit
        max_profit = credit * qty * contract_size
        max_loss = -(width - credit) * qty * contract_size
        return (max_profit, max_loss)

    raise ValueError("side must be 'long' or 'short'")

def payoff_curve_single(option_type: str, side: str, K: float, premium: float, qty: int, contract_size: int, s_min: float, s_max: float, steps: int) -> List[PLPoint]:
    if steps < 2:
        raise ValueError("steps must be >= 2")
    if s_max <= s_min:
        raise ValueError("s_max must be > s_min")
    out: List[PLPoint] = []
    step = (s_max - s_min) / (steps - 1)
    for i in range(steps):
        s = s_min + i * step
        out.append(PLPoint(underlying=s, pnl=single_option_pnl(option_type, side, s, K, premium, qty, contract_size)))
    return out

def payoff_curve_vertical(option_type: str, side: str, K_long: float, K_short: float, premium_long: float, premium_short: float, qty: int, contract_size: int, s_min: float, s_max: float, steps: int) -> List[PLPoint]:
    if steps < 2:
        raise ValueError("steps must be >= 2")
    if s_max <= s_min:
        raise ValueError("s_max must be > s_min")
    out: List[PLPoint] = []
    step = (s_max - s_min) / (steps - 1)
    for i in range(steps):
        s = s_min + i * step
        out.append(PLPoint(underlying=s, pnl=vertical_spread_pnl(option_type, side, s, K_long, K_short, premium_long, premium_short, qty, contract_size)))
    return out
