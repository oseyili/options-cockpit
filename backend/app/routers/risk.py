from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["risk"])

class RiskCheckRequest(BaseModel):
    account_equity: float = Field(..., gt=0)
    max_risk_per_trade_pct: float = Field(1.0, gt=0, le=10)
    trade_max_loss: float = Field(..., ge=0)
    spread_width_pct: float = Field(..., ge=0)

@router.post("/risk/pretrade")
def pretrade(req: RiskCheckRequest):
    max_allowed = req.account_equity * (req.max_risk_per_trade_pct / 100.0)

    hard_blocks = []
    warnings = []

    if req.trade_max_loss > max_allowed:
        hard_blocks.append("Trade max loss exceeds allowed risk per trade.")

    if req.spread_width_pct >= 8.0:
        warnings.append("Wide spread: potential bad fill / slippage risk.")

    return {
        "max_allowed_loss": round(max_allowed, 2),
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "ok": len(hard_blocks) == 0
    }
