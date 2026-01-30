from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from app.options.portfolio import (
    Leg as CoreLeg,
    portfolio_pnl_at_expiry,
    portfolio_curve,
    breakevens_from_curve,
    net_cashflow_at_entry,
    extrema_from_curve,
)

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
    shares: int = Field(..., ge=1)
    entry_price: float = Field(..., gt=0)

Leg = OptionLeg | StockLeg

class CurveSpec(BaseModel):
    # Any of these can be omitted; we'll auto-fill.
    s_min: Optional[float] = Field(None, gt=0)
    s_max: Optional[float] = Field(None, gt=0)
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
    net_cashflow: float  # +credit, -debit at entry
    breakevens: List[float]
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    curve: Optional[List[CurvePoint]] = None
    curve_bounds: Optional[CurveSpec] = None  # echo the bounds used (including auto-filled)

def _to_core(leg: Leg) -> CoreLeg:
    return CoreLeg(**leg.model_dump())

def _auto_bounds(core_legs: List[CoreLeg], underlying: float) -> tuple[float, float]:
    # Use strikes + entry_price + underlying to infer a sensible window
    refs: List[float] = [underlying]

    for leg in core_legs:
        if leg.instrument == "option" and leg.strike is not None:
            refs.append(float(leg.strike))
        if leg.instrument == "stock" and leg.entry_price is not None:
            refs.append(float(leg.entry_price))

    lo = min(refs)
    hi = max(refs)

    center = underlying
    span = hi - lo
    # If everything is the same strike/price, give a reasonable default range
    base = span if span > 0 else max(center * 0.25, 10.0)

    # Wider window: +/- 3x base, and never less than +/- 20% of spot
    radius = max(3.0 * base, 0.2 * center)

    s_min = max(0.01, center - radius)
    s_max = center + radius
    if s_max <= s_min:
        s_max = s_min + 1.0
    return s_min, s_max

@router.post("/portfolio", response_model=PortfolioResponse)
def portfolio(req: PortfolioRequest):
    try:
        core_legs = [_to_core(l) for l in req.legs]

        pnl = portfolio_pnl_at_expiry(core_legs, req.underlying)
        net_cf = net_cashflow_at_entry(core_legs)

        curve = None
        breakevens: List[float] = []
        max_profit: Optional[float] = None
        max_loss: Optional[float] = None
        bounds_used: Optional[CurveSpec] = None

        if req.curve is not None:
            s_min, s_max = req.curve.s_min, req.curve.s_max
            if s_min is None or s_max is None:
                auto_min, auto_max = _auto_bounds(core_legs, req.underlying)
                if s_min is None:
                    s_min = auto_min
                if s_max is None:
                    s_max = auto_max

            # Final sanity
            if s_max <= s_min:
                raise ValueError("curve.s_max must be > curve.s_min")

            pts = portfolio_curve(core_legs, s_min, s_max, req.curve.steps)
            curve = [CurvePoint(underlying=p.underlying, pnl=p.pnl) for p in pts]
            breakevens = breakevens_from_curve(pts)
            max_profit, max_loss = extrema_from_curve(pts)
            bounds_used = CurveSpec(s_min=s_min, s_max=s_max, steps=req.curve.steps)

        return PortfolioResponse(
            pnl=pnl,
            net_cashflow=net_cf,
            breakevens=breakevens,
            max_profit=max_profit,
            max_loss=max_loss,
            curve=curve,
            curve_bounds=bounds_used,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
