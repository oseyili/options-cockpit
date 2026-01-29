from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services.recommender import pick_best_strategy

router = APIRouter(tags=["recommend"])

class RecommendRequest(BaseModel):
    symbol: str = Field("SPY", min_length=1)
    spot: float = Field(..., gt=0)
    dte: int = Field(30, ge=1, le=365)
    contracts: int = Field(1, ge=1, le=500)

    # Constraints
    max_loss_dollars: float | None = Field(None, ge=0)
    max_drawdown_dollars: float | None = Field(None, ge=0)  # VaR worst-tail loss cap
    var_alpha: float = Field(0.95, ge=0.5, le=0.999)

    min_expected_profit: float = Field(-1e18)
    min_prob_profit: float = Field(0.0, ge=0.0, le=1.0)
    min_reward_risk: float = Field(0.0, ge=0.0)

    min_oi: int = Field(0, ge=0)
    min_vol: int = Field(0, ge=0)
    max_spread_pct: float = Field(100.0, ge=0.0)

    allow_single_call: bool = True
    allow_bull_put: bool = True

@router.post("/recommend")
def recommend(req: RecommendRequest):
    return pick_best_strategy(
        symbol=req.symbol,
        spot=req.spot,
        dte=req.dte,
        contracts=req.contracts,
        max_loss_dollars=req.max_loss_dollars,
        max_drawdown_dollars=req.max_drawdown_dollars,
        var_alpha=req.var_alpha,
        min_expected_profit=req.min_expected_profit,
        min_prob_profit=req.min_prob_profit,
        min_reward_risk=req.min_reward_risk,
        min_oi=req.min_oi,
        min_vol=req.min_vol,
        max_spread_pct=req.max_spread_pct,
        allow_single_call=req.allow_single_call,
        allow_bull_put=req.allow_bull_put,
    )
