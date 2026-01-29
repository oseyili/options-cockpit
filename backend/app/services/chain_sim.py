import math
import random

def _round(x, n=2):
    return round(x, n)

def make_chain(spot: float, dte: int = 30):
    """
    Simulated options chain around spot.
    Output: list of strikes with call/put quotes + iv + oi + vol + spread%.
    """
    spot = float(spot)
    step = 1 if spot < 100 else 5
    center = int(round(spot / step) * step)

    strikes = [center + i * step for i in range(-12, 13)]
    chain = []

    base_iv = 0.18 + 0.04 * random.random()  # 18%–22%
    for k in strikes:
        moneyness = (k - spot) / max(1.0, spot)
        skew = 0.12 * abs(moneyness) + (0.03 if k < spot else 0.0)  # puts a bit higher
        iv = max(0.05, base_iv + skew)

        # Price proxy: time value decays with distance from spot, increases with iv & dte
        tv = max(0.05, (iv * math.sqrt(max(1, dte) / 365.0)) * spot * 0.06)
        intrinsic_call = max(0.0, spot - k)
        intrinsic_put = max(0.0, k - spot)

        mid_call = intrinsic_call + tv * math.exp(-abs(moneyness) * 6)
        mid_put  = intrinsic_put  + tv * math.exp(-abs(moneyness) * 6)

        # spreads widen OTM
        spread_factor = 0.04 + 0.10 * min(1.0, abs(moneyness) * 8)
        call_spread = max(0.01, mid_call * spread_factor)
        put_spread  = max(0.01, mid_put * spread_factor)

        call_bid = max(0.01, mid_call - call_spread / 2)
        call_ask = call_bid + call_spread
        put_bid  = max(0.01, mid_put - put_spread / 2)
        put_ask  = put_bid + put_spread

        # Volume/OI (simulated)
        oi = int(max(10, 2000 * math.exp(-abs(moneyness) * 5) + random.randint(-50, 50)))
        vol = int(max(0, 400 * math.exp(-abs(moneyness) * 5) + random.randint(-30, 30)))

        chain.append({
            "strike": k,
            "dte": dte,
            "iv": _round(iv, 4),
            "oi": oi,
            "vol": vol,
            "call": {
                "bid": _round(call_bid, 2),
                "ask": _round(call_ask, 2),
                "mid": _round((call_bid + call_ask) / 2, 2),
                "spread_pct": _round(100 * (call_ask - call_bid) / max(0.01, (call_bid + call_ask) / 2), 2)
            },
            "put": {
                "bid": _round(put_bid, 2),
                "ask": _round(put_ask, 2),
                "mid": _round((put_bid + put_ask) / 2, 2),
                "spread_pct": _round(100 * (put_ask - put_bid) / max(0.01, (put_bid + put_ask) / 2), 2)
            }
        })

    return {
        "spot": _round(spot, 2),
        "dte": dte,
        "step": step,
        "items": chain
    }
