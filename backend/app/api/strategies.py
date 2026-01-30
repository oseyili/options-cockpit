from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal

router = APIRouter(prefix="/api/strategies", tags=["strategies"])

Instrument = Literal["option","stock"]
OptionType = Literal["call","put"]
Side = Literal["long","short"]

class Leg(BaseModel):
    instrument: Instrument

    # option fields
    option_type: OptionType | None = None
    side: Side = "long"
    strike: float | None = None
    premium: float | None = None
    qty: int = 1
    contract_size: int = 100

    # stock fields
    shares: int | None = None
    entry_price: float | None = None

class TemplateParam(BaseModel):
    name: str
    type: str
    required: bool = True
    description: str

class StrategyTemplate(BaseModel):
    name: str
    description: str
    params: List[TemplateParam]

TEMPLATES: List[StrategyTemplate] = [
    StrategyTemplate(
        name="covered_call",
        description="Long shares + short call. Fully modeled (stock + option).",
        params=[
            TemplateParam(name="shares", type="integer", description="Number of shares (e.g., 100)"),
            TemplateParam(name="entry_price", type="number", description="Share entry price (cost basis)"),
            TemplateParam(name="call_strike", type="number", description="Call strike sold"),
            TemplateParam(name="call_premium", type="number", description="Call premium received"),
            TemplateParam(name="qty", type="integer", required=False, description="Option contracts (default 1)"),
            TemplateParam(name="contract_size", type="integer", required=False, description="Shares per contract (default 100)"),
        ],
    ),
    StrategyTemplate(
        name="collar",
        description="Long shares + long protective put + short call (same expiry). Fully modeled.",
        params=[
            TemplateParam(name="shares", type="integer", description="Number of shares (e.g., 100)"),
            TemplateParam(name="entry_price", type="number", description="Share entry price (cost basis)"),
            TemplateParam(name="put_strike", type="number", description="Protective put strike bought"),
            TemplateParam(name="put_premium", type="number", description="Put premium paid"),
            TemplateParam(name="call_strike", type="number", description="Call strike sold"),
            TemplateParam(name="call_premium", type="number", description="Call premium received"),
            TemplateParam(name="qty", type="integer", required=False, description="Option contracts (default 1)"),
            TemplateParam(name="contract_size", type="integer", required=False, description="Shares per contract (default 100)"),
        ],
    ),
]

@router.get("/templates", response_model=List[StrategyTemplate])
def templates():
    return TEMPLATES

class BuildRequest(BaseModel):
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)

class BuildResponse(BaseModel):
    name: str
    legs: List[Leg]

def _num(p: Dict[str, Any], k: str) -> float:
    if k not in p:
        raise ValueError(f"Missing param: {k}")
    try:
        return float(p[k])
    except Exception:
        raise ValueError(f"Param '{k}' must be a number")

def _int(p: Dict[str, Any], k: str, default: int | None = None) -> int:
    if k not in p:
        if default is None:
            raise ValueError(f"Missing param: {k}")
        return default
    try:
        return int(p[k])
    except Exception:
        raise ValueError(f"Param '{k}' must be an integer")

def _build(name: str, p: Dict[str, Any]) -> List[Leg]:
    name = name.strip()
    qty = _int(p, "qty", 1)
    contract_size = _int(p, "contract_size", 100)

    if name == "covered_call":
        shares = _int(p, "shares", None)
        entry = _num(p, "entry_price")
        call_strike = _num(p, "call_strike")
        call_prem = _num(p, "call_premium")

        return [
            Leg(instrument="stock", side="long", shares=shares, entry_price=entry),
            Leg(instrument="option", option_type="call", side="short", strike=call_strike, premium=call_prem, qty=qty, contract_size=contract_size),
        ]

    if name == "collar":
        shares = _int(p, "shares", None)
        entry = _num(p, "entry_price")
        put_strike = _num(p, "put_strike")
        put_prem = _num(p, "put_premium")
        call_strike = _num(p, "call_strike")
        call_prem = _num(p, "call_premium")

        return [
            Leg(instrument="stock", side="long", shares=shares, entry_price=entry),
            Leg(instrument="option", option_type="put",  side="long",  strike=put_strike,  premium=put_prem,  qty=qty, contract_size=contract_size),
            Leg(instrument="option", option_type="call", side="short", strike=call_strike, premium=call_prem, qty=qty, contract_size=contract_size),
        ]

    raise ValueError(f"Unknown template name: {name}")

@router.post("/build", response_model=BuildResponse)
def build(req: BuildRequest):
    try:
        legs = _build(req.name, req.params)
        return BuildResponse(name=req.name, legs=legs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
