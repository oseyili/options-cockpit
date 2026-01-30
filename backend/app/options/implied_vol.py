from dataclasses import dataclass
from app.options.black_scholes import black_scholes

@dataclass(frozen=True)
class IVResult:
    implied_vol: float
    iterations: int

def implied_vol_bisection(
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    market_price: float,
    option_type: str,   # "call" or "put"
    vol_low: float = 1e-6,
    vol_high: float = 5.0,
    tol: float = 1e-6,
    max_iter: int = 200,
) -> IVResult:
    if market_price <= 0:
        raise ValueError("market_price must be > 0")
    option_type = option_type.lower().strip()
    if option_type not in ("call", "put"):
        raise ValueError("option_type must be 'call' or 'put'")

    def price_for(vol: float) -> float:
        res = black_scholes(S, K, T, r, q, vol)
        return res.call_price if option_type == "call" else res.put_price

    # Ensure bracket contains a root: f(low) <= 0 <= f(high) or vice versa
    f_low = price_for(vol_low) - market_price
    f_high = price_for(vol_high) - market_price

    # If both same sign, expand high a bit (limited)
    expand_steps = 0
    while f_low * f_high > 0 and expand_steps < 20:
        vol_high *= 1.5
        f_high = price_for(vol_high) - market_price
        expand_steps += 1

    if f_low * f_high > 0:
        raise ValueError("Could not bracket implied vol (market price out of model range).")

    low, high = vol_low, vol_high
    for i in range(1, max_iter + 1):
        mid = (low + high) / 2.0
        f_mid = price_for(mid) - market_price

        if abs(f_mid) < tol or (high - low) / 2.0 < tol:
            return IVResult(implied_vol=mid, iterations=i)

        # Keep the sub-interval that contains the root
        if f_low * f_mid <= 0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid

    return IVResult(implied_vol=(low + high) / 2.0, iterations=max_iter)
