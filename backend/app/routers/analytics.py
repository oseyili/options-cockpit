from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services.options_math import black_scholes_greeks

router = APIRouter(tags=["analytics"])

class GreeksRequest(BaseModel):
    S: float = Field(..., gt=0)
    K: float = Field(..., gt=0)
    T: float = Field(..., gt=0)
    r: float = 0.01
    sigma: float = Field(..., gt=0)
    is_call: bool = True

@router.post("/analytics/greeks")
def greeks(req: GreeksRequest):
    g = black_scholes_greeks(req.S, req.K, req.T, req.r, req.sigma, req.is_call)
    return g.__dict__
