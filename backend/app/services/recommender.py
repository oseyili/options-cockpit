import math
import random
from typing import Any, Dict, List, Optional

from app.services.chain_sim import make_chain

def _normals(n: int) -> List[float]:
    out = []
    for _ in range((n + 1)//2):
        u1 = max(1e-12, random.random())
        u2 = max(1e-12, random.random())
        r = math.sqrt(-2.0 * math.log(u1))
        th = 2.0 * math.pi * u2
        out.append(r * math.cos(th))
        out.append(r * math.sin(th))
    return out[:n]

def simulate_terminal_prices(S0: float, iv: float, dte: int, n: int = 9000) -> List[float]:
    T = max(1, dte) / 365.0
    vol = max(1e-6, iv)
    drift = -0.5 * vol * vol * T
    scale = vol * math.sqrt(T)
    zs = _normals(n)
    return [S0 * math.exp(drift + scale * z) for z in zs]

def _pop(per_share: List[float]) -> float:
    wins = sum(1 for x in per_share if x > 0)
    return wins / max(1, len(per_share))

def _var_worst_loss_dollars(per_share: List[float], alpha: float, contracts: int) -> float:
    """
    Max drawdown proxy: worst-tail loss (VaR-like).
    alpha=0.95 => look at worst 5% outcomes. Return positive loss dollars.
    """
    if not per_share:
        return 0.0
    a = min(max(alpha, 0.50), 0.999)
    sorted_pnl = sorted(per_share)  # ascending (worst first)
    idx = int((1.0 - a) * (len(sorted_pnl) - 1))
    idx = min(max(idx, 0), len(sorted_pnl) - 1)
    pnl_share = sorted_pnl[idx]  # likely negative
    loss_share = max(0.0, -pnl_share)
    return loss_share * 100.0 * contracts

def score_candidate(c: Dict[str, Any], pop_weight: float = 0.35, ev_weight: float = 0.65) -> float:
    ev = float(c.get("expected_profit", -1e18))
    pop = float(c.get("prob_profit", 0.0))
    return (ev_weight * ev) + (pop_weight * (pop * 100.0))

def ev_single_call(S0: float, K: float, premium: float, iv: float, dte: int, contracts: int, var_alpha: float) -> Dict[str, Any]:
    sims = simulate_terminal_prices(S0, iv, dte)
    per_share = [max(s - K, 0.0) - premium for s in sims]
    ev = sum(per_share) / len(per_share) * 100.0 * contracts
    pop = _pop(per_share)
    max_loss = premium * 100.0 * contracts
    var_loss = _var_worst_loss_dollars(per_share, var_alpha, contracts)
    rr = 999999.0  # calls have unlimited upside; treat as always passing min RR
    return {
        "strategy": "single_call",
        "legs": {"strike": K, "premium": premium},
        "expected_profit": round(ev, 2),
        "prob_profit": round(pop, 4),
        "entry_cost": round(premium * 100.0 * contracts, 2),
        "cost_type": "debit",
        "max_loss": round(max_loss, 2),
        "max_profit": "unlimited",
        "breakeven": round(K + premium, 2),
        "var_worst_loss": round(var_loss, 2),
        "reward_risk": rr,
        "_per_share": per_share,  # internal only; removed before return
    }

def ev_bull_put_credit(S0: float, Kshort: float, Klong: float, credit: float, iv: float, dte: int, contracts: int, var_alpha: float) -> Dict[str, Any]:
    width = max(0.0, Kshort - Klong)
    if width <= 0.0 or credit <= 0.0 or credit >= width:
        return {"expected_profit": -1e18, "prob_profit": 0.0}

    sims = simulate_terminal_prices(S0, iv, dte)
    per_share = []
    for s in sims:
        payoff = credit - max(Kshort - s, 0.0) + max(Klong - s, 0.0)
        per_share.append(payoff)

    ev = sum(per_share) / len(per_share) * 100.0 * contracts
    pop = _pop(per_share)
    max_profit = credit * 100.0 * contracts
    max_loss = (width - credit) * 100.0 * contracts
    var_loss = _var_worst_loss_dollars(per_share, var_alpha, contracts)

    rr = (max_profit / max_loss) if max_loss > 0 else 0.0

    return {
        "strategy": "bull_put_credit_spread",
        "legs": {"short_put": Kshort, "long_put": Klong, "credit": credit},
        "expected_profit": round(ev, 2),
        "prob_profit": round(pop, 4),
        "entry_cost": round(credit * 100.0 * contracts, 2),
        "cost_type": "credit",
        "max_loss": round(max_loss, 2),
        "max_profit": round(max_profit, 2),
        "breakeven": round(Kshort - credit, 2),
        "var_worst_loss": round(var_loss, 2),
        "reward_risk": round(rr, 4),
        "_per_share": per_share,  # internal only; removed before return
    }

def passes_liquidity(x: Dict[str, Any], min_oi: int, min_vol: int, max_spread_pct: float) -> bool:
    try:
        oi = int(x.get("oi", 0))
        vol = int(x.get("vol", 0))
        call_sp = float(x["call"]["spread_pct"])
        put_sp = float(x["put"]["spread_pct"])
        mx = max(call_sp, put_sp)
        return (oi >= min_oi) and (vol >= min_vol) and (mx <= max_spread_pct)
    except Exception:
        return False

def pick_best_strategy(
    symbol: str,
    spot: float,
    dte: int,
    contracts: int = 1,

    # existing constraints
    max_loss_dollars: Optional[float] = None,
    min_expected_profit: float = -1e18,
    min_prob_profit: float = 0.0,
    min_oi: int = 0,
    min_vol: int = 0,
    max_spread_pct: float = 100.0,
    allow_single_call: bool = True,
    allow_bull_put: bool = True,

    # NEW constraints
    min_reward_risk: float = 0.0,
    max_drawdown_dollars: Optional[float] = None,   # implemented as VaR worst-tail loss
    var_alpha: float = 0.95,                        # 0.95 => worst 5%
) -> Dict[str, Any]:
    chain = make_chain(spot, dte)
    items = chain["items"]
    step = float(chain.get("step", 5))

    candidates: List[Dict[str, Any]] = []

    if allow_single_call:
        for x in items:
            if not passes_liquidity(x, min_oi, min_vol, max_spread_pct):
                continue
            K = float(x["strike"])
            premium = float(x["call"]["mid"])
            iv = float(x["iv"])
            c = ev_single_call(spot, K, premium, iv, dte, contracts, var_alpha)
            c["meta"] = {"oi": x.get("oi"), "vol": x.get("vol"), "max_spread_pct": max(float(x["call"]["spread_pct"]), float(x["put"]["spread_pct"]))}
            candidates.append(c)

    if allow_bull_put:
        strike_to = {float(x["strike"]): x for x in items}
        strikes = sorted(strike_to.keys())

        for Kshort in strikes:
            if Kshort > spot:
                continue
            s_item = strike_to[Kshort]
            if not passes_liquidity(s_item, min_oi, min_vol, max_spread_pct):
                continue

            for w_steps in (1, 2, 3):
                Klong = Kshort - (w_steps * step)
                if Klong not in strike_to:
                    continue
                l_item = strike_to[Klong]
                if not passes_liquidity(l_item, min_oi, min_vol, max_spread_pct):
                    continue

                credit = max(0.01, float(s_item["put"]["mid"]) - float(l_item["put"]["mid"]))
                iv = float(s_item["iv"])
                c = ev_bull_put_credit(spot, Kshort, Klong, credit, iv, dte, contracts, var_alpha)
                c["meta"] = {"oi": s_item.get("oi"), "vol": s_item.get("vol"), "max_spread_pct": max(float(s_item["call"]["spread_pct"]), float(s_item["put"]["spread_pct"]))}
                candidates.append(c)

    constrained: List[Dict[str, Any]] = []
    for c in candidates:
        ev = float(c.get("expected_profit", -1e18))
        pop = float(c.get("prob_profit", 0.0))
        ml = c.get("max_loss")
        rr = float(c.get("reward_risk", 0.0))
        dd = float(c.get("var_worst_loss", 0.0))

        # Risk caps
        if isinstance(ml, (int, float)) and max_loss_dollars is not None and float(ml) > float(max_loss_dollars):
            continue
        # NEW: max drawdown cap (VaR worst-tail loss)
        if max_drawdown_dollars is not None and dd > float(max_drawdown_dollars):
            continue
        # Profitability constraints
        if ev < float(min_expected_profit):
            continue
        if pop < float(min_prob_profit):
            continue
        # NEW: reward:risk constraint (for spreads this is meaningful; calls always pass)
        if rr < float(min_reward_risk):
            continue

        constrained.append(c)

    use = constrained if constrained else candidates
    if not use:
        return {
            "symbol": symbol,
            "spot": round(float(spot), 2),
            "dte": int(dte),
            "contracts": int(contracts),
            "error": "No candidates available under constraints.",
            "note": "Loosen constraints: lower min_reward_risk/min_prob_profit/min_expected_profit, raise max_drawdown/max_loss, or relax liquidity filters."
        }

    best = max(use, key=lambda x: score_candidate(x))
    best["score"] = round(score_candidate(best), 2)

    # remove internal per-share array
    if "_per_share" in best:
        del best["_per_share"]

    return {
        "symbol": symbol,
        "spot": round(float(spot), 2),
        "dte": int(dte),
        "contracts": int(contracts),
        "constraints": {
            "max_loss_dollars": max_loss_dollars,
            "max_drawdown_dollars": max_drawdown_dollars,
            "var_alpha": var_alpha,
            "min_expected_profit": min_expected_profit,
            "min_prob_profit": min_prob_profit,
            "min_reward_risk": min_reward_risk,
            "min_oi": min_oi,
            "min_vol": min_vol,
            "max_spread_pct": max_spread_pct,
            "allow_single_call": allow_single_call,
            "allow_bull_put": allow_bull_put,
        },
        "recommendation": best,
        "note": "Max drawdown implemented as VaR-style worst-tail loss over the simulated P&L distribution (not multi-step equity curve drawdown).",
    }
