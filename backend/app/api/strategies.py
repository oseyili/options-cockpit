from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional

router = APIRouter(prefix="/api/strategies", tags=["strategies"])

Instrument = Literal["option","stock"]
OptionType = Literal["call","put"]
Side = Literal["long","short"]

class Leg(BaseModel):
    instrument: Instrument

    # common
    side: Side = "long"

    # option fields
    option_type: Optional[OptionType] = None
    strike: Optional[float] = Field(None, gt=0)
    premium: Optional[float] = Field(None, ge=0)
    qty: int = Field(1, ge=1)
    contract_size: int = Field(100, ge=1)

    # stock fields
    shares: Optional[int] = Field(None, ge=1)
    entry_price: Optional[float] = Field(None, gt=0)

class TemplateParam(BaseModel):
    name: str
    type: str
    required: bool = True
    description: str

class StrategyTemplate(BaseModel):
    name: str
    description: str
    params: List[TemplateParam]

# ---- Templates (full set) ----
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
        description="Long shares + long put + short call. Fully modeled (stock + options).",
        params=[
            TemplateParam(name="shares", type="integer", description="Number of shares (e.g., 100)"),
            TemplateParam(name="entry_price", type="number", description="Share entry price (cost basis)"),
            TemplateParam(name="put_strike", type="number", description="Put strike bought"),
            TemplateParam(name="put_premium", type="number", description="Put premium paid"),
            TemplateParam(name="call_strike", type="number", description="Call strike sold"),
            TemplateParam(name="call_premium", type="number", description="Call premium received"),
            TemplateParam(name="qty", type="integer", required=False, description="Option contracts (default 1)"),
            TemplateParam(name="contract_size", type="integer", required=False, description="Shares per contract (default 100)"),
        ],
    ),
    StrategyTemplate(
        name="long_straddle",
        description="Buy call + buy put at same strike.",
        params=[
            TemplateParam(name="strike", type="number", description="Common strike"),
            TemplateParam(name="call_premium", type="number", description="Call premium paid"),
            TemplateParam(name="put_premium", type="number", description="Put premium paid"),
            TemplateParam(name="qty", type="integer", required=False, description="Contracts (default 1)"),
            TemplateParam(name="contract_size", type="integer", required=False, description="Shares per contract (default 100)"),
        ],
    ),
    StrategyTemplate(
        name="long_strangle",
        description="Buy OTM put + buy OTM call.",
        params=[
            TemplateParam(name="put_strike", type="number", description="Put strike (lower)"),
            TemplateParam(name="call_strike", type="number", description="Call strike (higher)"),
            TemplateParam(name="put_premium", type="number", description="Put premium paid"),
            TemplateParam(name="call_premium", type="number", description="Call premium paid"),
            TemplateParam(name="qty", type="integer", required=False, description="Contracts (default 1)"),
            TemplateParam(name="contract_size", type="integer", required=False, description="Shares per contract (default 100)"),
        ],
    ),
    StrategyTemplate(
        name="bull_call_spread",
        description="Buy call (lower strike) + sell call (higher strike).",
        params=[
            TemplateParam(name="long_strike", type="number", description="Strike bought"),
            TemplateParam(name="short_strike", type="number", description="Strike sold"),
            TemplateParam(name="long_premium", type="number", description="Premium paid (long call)"),
            TemplateParam(name="short_premium", type="number", description="Premium received (short call)"),
            TemplateParam(name="qty", type="integer", required=False, description="Spreads (default 1)"),
            TemplateParam(name="contract_size", type="integer", required=False, description="Shares per contract (default 100)"),
        ],
    ),
    StrategyTemplate(
        name="bear_put_spread",
        description="Buy put (higher strike) + sell put (lower strike).",
        params=[
            TemplateParam(name="long_strike", type="number", description="Strike bought (higher)"),
            TemplateParam(name="short_strike", type="number", description="Strike sold (lower)"),
            TemplateParam(name="long_premium", type="number", description="Premium paid (long put)"),
            TemplateParam(name="short_premium", type="number", description="Premium received (short put)"),
            TemplateParam(name="qty", type="integer", required=False, description="Spreads (default 1)"),
            TemplateParam(name="contract_size", type="integer", required=False, description="Shares per contract (default 100)"),
        ],
    ),
    StrategyTemplate(
        name="iron_condor",
        description="Short put spread + short call spread (credit).",
        params=[
            TemplateParam(name="put_long_strike", type="number", description="Put wing bought (lowest strike)"),
            TemplateParam(name="put_short_strike", type="number", description="Put strike sold"),
            TemplateParam(name="call_short_strike", type="number", description="Call strike sold"),
            TemplateParam(name="call_long_strike", type="number", description="Call wing bought (highest strike)"),
            TemplateParam(name="put_long_premium", type="number", description="Premium paid (long put wing)"),
            TemplateParam(name="put_short_premium", type="number", description="Premium received (short put)"),
            TemplateParam(name="call_short_premium", type="number", description="Premium received (short call)"),
            TemplateParam(name="call_long_premium", type="number", description="Premium paid (long call wing)"),
            TemplateParam(name="qty", type="integer", required=False, description="Condors (default 1)"),
            TemplateParam(name="contract_size", type="integer", required=False, description="Shares per contract (default 100)"),
        ],
    ),
]

@router.get("/templates", response_model=List[StrategyTemplate])
def templates():
    return TEMPLATES

class BuildRequest(BaseModel):
    name: str = Field(..., description="Template name, e.g. 'iron_condor'")
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

def _int(p: Dict[str, Any], k: str, default: Optional[int] = None) -> int:
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
        entry_price = _num(p, "entry_price")
        call_strike = _num(p, "call_strike")
        call_premium = _num(p, "call_premium")
        return [
            Leg(instrument="stock", side="long", shares=shares, entry_price=entry_price),
            Leg(instrument="option", option_type="call", side="short", strike=call_strike, premium=call_premium, qty=qty, contract_size=contract_size),
        ]

    if name == "collar":
        shares = _int(p, "shares", None)
        entry_price = _num(p, "entry_price")
        put_strike = _num(p, "put_strike")
        put_premium = _num(p, "put_premium")
        call_strike = _num(p, "call_strike")
        call_premium = _num(p, "call_premium")
        return [
            Leg(instrument="stock", side="long", shares=shares, entry_price=entry_price),
            Leg(instrument="option", option_type="put", side="long", strike=put_strike, premium=put_premium, qty=qty, contract_size=contract_size),
            Leg(instrument="option", option_type="call", side="short", strike=call_strike, premium=call_premium, qty=qty, contract_size=contract_size),
        ]

    if name == "long_straddle":
        strike = _num(p, "strike")
        return [
            Leg(instrument="option", option_type="call", side="long", strike=strike, premium=_num(p,"call_premium"), qty=qty, contract_size=contract_size),
            Leg(instrument="option", option_type="put",  side="long", strike=strike, premium=_num(p,"put_premium"),  qty=qty, contract_size=contract_size),
        ]

    if name == "long_strangle":
        return [
            Leg(instrument="option", option_type="put",  side="long", strike=_num(p,"put_strike"),  premium=_num(p,"put_premium"),  qty=qty, contract_size=contract_size),
            Leg(instrument="option", option_type="call", side="long", strike=_num(p,"call_strike"), premium=_num(p,"call_premium"), qty=qty, contract_size=contract_size),
        ]

    if name == "bull_call_spread":
        return [
            Leg(instrument="option", option_type="call", side="long",  strike=_num(p,"long_strike"),  premium=_num(p,"long_premium"),  qty=qty, contract_size=contract_size),
            Leg(instrument="option", option_type="call", side="short", strike=_num(p,"short_strike"), premium=_num(p,"short_premium"), qty=qty, contract_size=contract_size),
        ]

    if name == "bear_put_spread":
        return [
            Leg(instrument="option", option_type="put", side="long",  strike=_num(p,"long_strike"),  premium=_num(p,"long_premium"),  qty=qty, contract_size=contract_size),
            Leg(instrument="option", option_type="put", side="short", strike=_num(p,"short_strike"), premium=_num(p,"short_premium"), qty=qty, contract_size=contract_size),
        ]

    if name == "iron_condor":
        return [
            Leg(instrument="option", option_type="put",  side="long",  strike=_num(p,"put_long_strike"),  premium=_num(p,"put_long_premium"),  qty=qty, contract_size=contract_size),
            Leg(instrument="option", option_type="put",  side="short", strike=_num(p,"put_short_strike"), premium=_num(p,"put_short_premium"), qty=qty, contract_size=contract_size),
            Leg(instrument="option", option_type="call", side="short", strike=_num(p,"call_short_strike"), premium=_num(p,"call_short_premium"), qty=qty, contract_size=contract_size),
            Leg(instrument="option", option_type="call", side="long",  strike=_num(p,"call_long_strike"),  premium=_num(p,"call_long_premium"),  qty=qty, contract_size=contract_size),
        ]

    raise ValueError(f"Unknown template name: {name}")

@router.post("/build", response_model=BuildResponse)
def build(req: BuildRequest):
    try:
        legs = _build(req.name, req.params)
        return BuildResponse(name=req.name, legs=legs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
