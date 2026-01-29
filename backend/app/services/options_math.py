import math
from dataclasses import dataclass

@dataclass
class Greeks:
    delta: float
    gamma: float
    theta: float
    vega: float

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def _norm_pdf(x: float) -> float:
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)

def black_scholes_greeks(S: float, K: float, T: float, r: float, sigma: float, is_call: bool) -> Greeks:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return Greeks(0.0, 0.0, 0.0, 0.0)

    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    pdf_d1 = _norm_pdf(d1)

    delta = _norm_cdf(d1) if is_call else (_norm_cdf(d1) - 1.0)
    gamma = pdf_d1 / (S * sigma * math.sqrt(T))
    vega = S * pdf_d1 * math.sqrt(T) / 100.0

    theta = (
        -(S * pdf_d1 * sigma) / (2.0 * math.sqrt(T))
        - (r * K * math.exp(-r * T) * (_norm_cdf(d2) if is_call else _norm_cdf(-d2)))
    ) / 365.0

    return Greeks(delta=delta, gamma=gamma, theta=theta, vega=vega)
