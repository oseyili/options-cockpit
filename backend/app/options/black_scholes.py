import math
from dataclasses import dataclass

SQRT_2PI = math.sqrt(2.0 * math.pi)

def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / SQRT_2PI

def _norm_cdf(x: float) -> float:
    # Standard normal CDF using erf (no external deps)
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

@dataclass(frozen=True)
class BSResult:
    call_price: float
    put_price: float
    delta_call: float
    delta_put: float
    gamma: float
    vega: float
    theta_call: float
    theta_put: float
    rho_call: float
    rho_put: float

def black_scholes(
    S: float,   # spot
    K: float,   # strike
    T: float,   # time to expiry in years
    r: float,   # risk-free rate (decimal)
    q: float,   # dividend yield (decimal)
    sigma: float # volatility (decimal)
) -> BSResult:
    if S <= 0 or K <= 0:
        raise ValueError("S and K must be > 0")
    if T <= 0:
        raise ValueError("T must be > 0 (years)")
    if sigma <= 0:
        raise ValueError("sigma must be > 0")

    sqrtT = math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrtT)
    d2 = d1 - sigma * sqrtT

    Nd1 = _norm_cdf(d1)
    Nd2 = _norm_cdf(d2)
    Nmd1 = _norm_cdf(-d1)
    Nmd2 = _norm_cdf(-d2)

    disc_r = math.exp(-r * T)
    disc_q = math.exp(-q * T)

    call = S * disc_q * Nd1 - K * disc_r * Nd2
    put  = K * disc_r * Nmd2 - S * disc_q * Nmd1

    pdf_d1 = _norm_pdf(d1)

    delta_c = disc_q * Nd1
    delta_p = disc_q * (Nd1 - 1.0)

    gamma = (disc_q * pdf_d1) / (S * sigma * sqrtT)
    vega  = S * disc_q * pdf_d1 * sqrtT  # per 1.00 vol (i.e., decimal, not %)

    # Theta (per year). Many UIs want per day; convert at API if needed.
    theta_c = (-S * disc_q * pdf_d1 * sigma / (2.0 * sqrtT)
               - r * K * disc_r * Nd2
               + q * S * disc_q * Nd1)

    theta_p = (-S * disc_q * pdf_d1 * sigma / (2.0 * sqrtT)
               + r * K * disc_r * Nmd2
               - q * S * disc_q * Nmd1)

    rho_c = K * T * disc_r * Nd2
    rho_p = -K * T * disc_r * Nmd2

    return BSResult(
        call_price=call,
        put_price=put,
        delta_call=delta_c,
        delta_put=delta_p,
        gamma=gamma,
        vega=vega,
        theta_call=theta_c,
        theta_put=theta_p,
        rho_call=rho_c,
        rho_put=rho_p,
    )
