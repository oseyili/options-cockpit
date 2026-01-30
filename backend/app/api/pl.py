from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from app.options.payoff import (
    single_option_pnl, single_breakevens, single_max_pl, payoff_curve_single,
    vertical_spread_pnl, vertical_breakeven, vertical_max_pl, payoff_curve_vertical
)

router = APIRouter(prefix="/api/pl", tags=["payoff"])

OptionType = Literal["call","put"]
Side = Literal["long","short"]

class CurveSpec(BaseModel):
    s_min: float = Field(..., gt=0)
    s_max: float = Field(..., gt=0)
    steps: int = Field(101, ge=2, le=1001)

class SinglePLRequest(BaseModel):
    option_type: OptionType
    side: Side
    K: float = Field(..., gt=0)
    premium: float = Field(..., ge=0)
    qty: int = Field(1, ge=1)
    contract_size: int = Field(100, ge=1)
    underlying: float = Field(..., gt=0, description="Underlying price to evaluate P/L at expiry")
    curve: CurveSpec | None = None

class CurvePoint(BaseModel):
    underlying: float
    pnl: float

class SinglePLResponse(BaseModel):
    pnl: float
    breakevens: List[float]
    max_profit: Optional[float]
    max_loss: Optional[float]
    curve: Optional[List[CurvePoint]] = None

@router.post("/single", response_model=SinglePLResponse)
def single(req: SinglePLRequest):
    try:
        pnl = single_option_pnl(req.option_type, req.side, req.underlying, req.K, req.premium, req.qty, req.contract_size)
        bes = single_breakevens(req.option_type, req.K, req.premium)
        mp, ml = single_max_pl(req.option_type, req.side, req.K, req.premium, req.qty, req.contract_size)

        curve = None
        if req.curve is not None:
            pts = payoff_curve_single(req.option_type, req.side, req.K, req.premium, req.qty, req.contract_size, req.curve.s_min, req.curve.s_max, req.curve.steps)
            curve = [CurvePoint(underlying=p.underlying, pnl=p.pnl) for p in pts]

        return SinglePLResponse(pnl=pnl, breakevens=bes, max_profit=mp, max_loss=ml, curve=curve)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

class VerticalPLRequest(BaseModel):
    option_type: OptionType
    side: Side
    K_long: float = Field(..., gt=0)
    K_short: float = Field(..., gt=0)
    premium_long: float = Field(..., ge=0)
    premium_short: float = Field(..., ge=0)
    qty: int = Field(1, ge=1)
    contract_size: int = Field(100, ge=1)
    underlying: float = Field(..., gt=0)
    curve: CurveSpec | None = None

class VerticalPLResponse(BaseModel):
    pnl: float
    breakevens: List[float]
    max_profit: Optional[float]
    max_loss: Optional[float]
    curve: Optional[List[CurvePoint]] = None

@router.post("/vertical", response_model=VerticalPLResponse)
def vertical(req: VerticalPLRequest):
    try:
        pnl = vertical_spread_pnl(req.option_type, req.side, req.underlying, req.K_long, req.K_short, req.premium_long, req.premium_short, req.qty, req.contract_size)
        bes = vertical_breakeven(req.option_type, req.side, req.K_long, req.K_short, req.premium_long, req.premium_short)
        mp, ml = vertical_max_pl(req.option_type, req.side, req.K_long, req.K_short, req.premium_long, req.premium_short, req.qty, req.contract_size)

        curve = None
        if req.curve is not None:
            pts = payoff_curve_vertical(req.option_type, req.side, req.K_long, req.K_short, req.premium_long, req.premium_short, req.qty, req.contract_size, req.curve.s_min, req.curve.s_max, req.curve.steps)
            curve = [CurvePoint(underlying=p.underlying, pnl=p.pnl) for p in pts]

        return VerticalPLResponse(pnl=pnl, breakevens=bes, max_profit=mp, max_loss=ml, curve=curve)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
