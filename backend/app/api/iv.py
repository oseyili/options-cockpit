from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.options.implied_vol import implied_vol_bisection

router = APIRouter(prefix="/api/iv", tags=["implied_vol"])

class IVRequest(BaseModel):
    S: float = Field(..., gt=0)
    K: float = Field(..., gt=0)
    T: float = Field(..., gt=0, description="Years to expiry")
    r: float = Field(..., description="Risk-free rate (decimal)")
    q: float = Field(0.0, description="Dividend yield (decimal)")
    market_price: float = Field(..., gt=0)
    option_type: str = Field(..., description="call or put")

class IVResponse(BaseModel):
    implied_vol: float
    iterations: int

@router.post("/solve", response_model=IVResponse)
def solve(req: IVRequest):
    try:
        res = implied_vol_bisection(
            S=req.S, K=req.K, T=req.T, r=req.r, q=req.q,
            market_price=req.market_price, option_type=req.option_type
        )
        return IVResponse(implied_vol=res.implied_vol, iterations=res.iterations)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
