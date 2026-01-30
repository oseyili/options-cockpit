from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.options.black_scholes import black_scholes

router = APIRouter(prefix="/api/bs", tags=["black_scholes"])

class BSRequest(BaseModel):
    S: float = Field(..., gt=0, description="Spot price")
    K: float = Field(..., gt=0, description="Strike price")
    T: float = Field(..., gt=0, description="Time to expiry in years (e.g., 30/365)")
    r: float = Field(..., description="Risk-free rate as decimal (e.g., 0.05)")
    q: float = Field(0.0, description="Dividend yield as decimal (e.g., 0.01)")
    sigma: float = Field(..., gt=0, description="Volatility as decimal (e.g., 0.25)")

class BSResponse(BaseModel):
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

@router.post("/price", response_model=BSResponse)
def price(req: BSRequest):
    try:
        res = black_scholes(req.S, req.K, req.T, req.r, req.q, req.sigma)
        return BSResponse(**res.__dict__)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
