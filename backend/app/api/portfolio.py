from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from app.options.portfolio import Leg as CoreLeg, portfolio_pnl_at_expiry, portfolio_curve, breakevens_from_curve

router = APIRouter(prefix="/api/pl", tags=["payoff"])

Instrument = Literal["option","stock"]
OptionType = Literal["call","put"]
Side = Literal["long","short"]

class OptionLeg(BaseModel):
    instrument: Literal["option"] = "option"
    option_type: OptionType
    side: Side
    strike: float = Field(..., gt=0)
    premium: float = Field(..., ge=0)
    qty: int = Field(1, ge=1)
    contract_size: int = Field(100, ge=1)

class StockLeg(BaseModel):
    instrument: Literal["stock"] = "stock"
    side: Side
    shares: int = Field(..., ge=1, description="Number of shares")
    entry_price: float = Field(..., gt=0, description="Share entry price (cost basis)")

Leg = OptionLeg | StockLeg

class CurveSpec(BaseModel):
    s_min: float = Field(..., gt=0)
    s_max: float = Field(..., gt=0)
    steps: int = Field(201, ge=2, le=2001)

class PortfolioRequest(BaseModel):
    legs: List[Leg] = Field(..., min_length=1)
    underlying: float = Field(..., gt=0, description="Underlying price to evaluate P/L at expiry")
    curve: CurveSpec | None = None

class CurvePoint(BaseModel):
    underlying: float
    pnl: float

class PortfolioResponse(BaseModel):
    pnl: float
    breakevens: List[float]
    curve: Optional[List[CurvePoint]] = None

def _to_core(leg: Leg) -> CoreLeg:
    d = leg.model_dump()
    return CoreLeg(**d)

@router.post("/portfolio", response_model=PortfolioResponse)
def portfolio(req: PortfolioRequest):
    try:
        core_legs = [_to_core(l) for l in req.legs]
        pnl = portfolio_pnl_at_expiry(core_legs, req.underlying)

        curve = None
        breakevens: List[float] = []
        if req.curve is not None:
            pts = portfolio_curve(core_legs, req.curve.s_min, req.curve.s_max, req.curve.steps)
            curve = [CurvePoint(underlying=p.underlying, pnl=p.pnl) for p in pts]
            breakevens = breakevens_from_curve(pts)

        return PortfolioResponse(pnl=pnl, breakevens=breakevens, curve=curve)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
