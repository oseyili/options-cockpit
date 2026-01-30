from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional

router = APIRouter(prefix="/api/strategies", tags=["strategies"])

OptionType = Literal["call", "put"]
Side = Literal["long", "short"]

class Leg(BaseModel):
    instrument: Literal["option"] = "option"
    option_type: OptionType
    side: Side
    strike: float = Field(..., gt=0)
    premium: float = Field(..., ge=0)
    qty: int = Field(1, ge=1)
    contract_size: int = Field(100, ge=1)

class TemplateParam(BaseModel):
    name: str
    type: str
    required: bool = True
    description: str

class StrategyTemplate(BaseModel):
    name: str
    description: str
    params: List[TemplateParam]

# ---- Templates ----
TEMPLATES: List[StrategyTemplate] = [
    StrategyTemplate(
        name="long_call",
        description="Buy 1 call. Bullish, limited risk, unlimited upside.",
        params=[
            TemplateParam(name="strike", type="number", description="Call strike"),
            TemplateParam(name="premium", type="number", description="Call premium paid"),
            TemplateParam(name="qty", type="integer", required=False, description="Contracts (default 1)"),
            TemplateParam(name="contract_size", type="integer", required=False, description="Shares per contract (default 100)"),
        ],
    ),
    StrategyTemplate(
        name="long_put",
        description="Buy 1 put. Bearish, limited risk, large downside profit.",
        params=[
            TemplateParam(name="strike", type="number", description="Put strike"),
            TemplateParam(name="premium", type="number", description="Put premium paid"),
            TemplateParam(name="qty", type="integer", required=False, description="Contracts (default 1)"),
            TemplateParam(name="contract_size", type="integer", required=False, description="Shares per contract (default 100)"),
        ],
    ),
    StrategyTemplate(
        name="short_put",
        description="Sell 1 put. Bullish/neutral. Limited profit, large downside risk.",
        params=[
            TemplateParam(name="strike", type="number", description="Put strike"),
            TemplateParam(name="premium", type="number", description="Put premium received"),
            TemplateParam(name="qty", type="integer", required=False, description="Contracts (default 1)"),
            TemplateParam(name="contract_size", type="integer", required=False, description="Shares per contract (default 100)"),
        ],
    ),
    StrategyTemplate(
        name="covered_call",
        description="Long 100 shares + short 1 call. (Shares leg not modeled yet; options legs returned only.)",
        params=[
            TemplateParam(name="call_strike", type="number", description="Call strike sold"),
            TemplateParam(name="call_premium", type="number", description="Call premium received"),
            TemplateParam(name="qty", type="integer", required=False, description="Option contracts (default 1)"),
            TemplateParam(name="contract_size", type="integer", required=False, description="Shares per contract (default 100)"),
        ],
    ),
    StrategyTemplate(
        name="long_straddle",
        description="Buy 1 call + buy 1 put at same strike. Volatility bet.",
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
        description="Buy OTM call + buy OTM put. Cheaper than straddle, needs bigger move.",
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
        description="Buy call (lower strike) + sell call (higher strike). Debit spread.",
        params=[
            TemplateParam(name="long_strike", type="number", description="Strike bought"),
            TemplateParam(name="short_strike", type="number", description="Strike sold"),
            TemplateParam(name="long_premium", type="number", description="Premium paid for long call"),
            TemplateParam(name="short_premium", type="number", description="Premium received for short call"),
            TemplateParam(name="qty", type="integer", required=False, description="Spreads (default 1)"),
            TemplateParam(name="contract_size", type="integer", required=False, description="Shares per contract (default 100)"),
        ],
    ),
    StrategyTemplate(
        name="bear_put_spread",
        description="Buy put (higher strike) + sell put (lower strike). Debit spread.",
        params=[
            TemplateParam(name="long_strike", type="number", description="Strike bought (higher)"),
            TemplateParam(name="short_strike", type="number", description="Strike sold (lower)"),
            TemplateParam(name="long_premium", type="number", description="Premium paid for long put"),
            TemplateParam(name="short_premium", type="number", description="Premium received for short put"),
            TemplateParam(name="qty", type="integer", required=False, description="Spreads (default 1)"),
            TemplateParam(name="contract_size", type="integer", required=False, description="Shares per contract (default 100)"),
        ],
    ),
    StrategyTemplate(
        name="iron_condor",
        description="Sell OTM put spread + sell OTM call spread. Credit strategy, range-bound bet.",
        params=[
            TemplateParam(name="put_long_strike", type="number", description="Put wing bought (lowest strike)"),
            TemplateParam(name="put_short_strike", type="number", description="Put short strike"),
            TemplateParam(name="call_short_strike", type="number", description="Call short strike"),
            TemplateParam(name="call_long_strike", type="number", description="Call wing bought (highest strike)"),
            TemplateParam(name="put_long_premium", type="number", description="Premium paid for long put"),
            TemplateParam(name="put_short_premium", type="number", description="Premium received for short put"),
            TemplateParam(name="call_short_premium", type="number", description="Premium received for short call"),
            TemplateParam(name="call_long_premium", type="number", description="Premium paid for long call"),
            TemplateParam(name="qty", type="integer", required=False, description="Condors (default 1)"),
            TemplateParam(name="contract_size", type="integer", required=False, description="Shares per contract (default 100)"),
        ],
    ),
]

@router.get("/templates", response_model=List[StrategyTemplate])
def templates():
    return TEMPLATES

# ---- Builder ----
class BuildRequest(BaseModel):
    name: str = Field(..., description="Template name, e.g. 'iron_condor'")
    params: Dict[str, Any] = Field(default_factory=dict)

class BuildResponse(BaseModel):
    name: str
    legs: List[Leg]

def _num(params: Dict[str, Any], k: str) -> float:
    if k not in params:
        raise ValueError(f"Missing param: {k}")
    try:
        return float(params[k])
    except Exception:
        raise ValueError(f"Param '{k}' must be a number")

def _int(params: Dict[str, Any], k: str, default: int) -> int:
    if k not in params:
        return default
    try:
        v = int(params[k])
        return v
    except Exception:
        raise ValueError(f"Param '{k}' must be an integer")

def _build(name: str, p: Dict[str, Any]) -> List[Leg]:
    name = name.strip()

    qty = _int(p, "qty", 1)
    contract_size = _int(p, "contract_size", 100)

    if name == "long_call":
        return [Leg(option_type="call", side="long", strike=_num(p,"strike"), premium=_num(p,"premium"), qty=qty, contract_size=contract_size)]
    if name == "long_put":
        return [Leg(option_type="put", side="long", strike=_num(p,"strike"), premium=_num(p,"premium"), qty=qty, contract_size=contract_size)]
    if name == "short_put":
        return [Leg(option_type="put", side="short", strike=_num(p,"strike"), premium=_num(p,"premium"), qty=qty, contract_size=contract_size)]

    if name == "covered_call":
        # Shares leg not modeled; return the short call leg only.
        return [Leg(option_type="call", side="short", strike=_num(p,"call_strike"), premium=_num(p,"call_premium"), qty=qty, contract_size=contract_size)]

    if name == "long_straddle":
        strike = _num(p,"strike")
        return [
            Leg(option_type="call", side="long", strike=strike, premium=_num(p,"call_premium"), qty=qty, contract_size=contract_size),
            Leg(option_type="put",  side="long", strike=strike, premium=_num(p,"put_premium"),  qty=qty, contract_size=contract_size),
        ]

    if name == "long_strangle":
        return [
            Leg(option_type="put",  side="long", strike=_num(p,"put_strike"),  premium=_num(p,"put_premium"),  qty=qty, contract_size=contract_size),
            Leg(option_type="call", side="long", strike=_num(p,"call_strike"), premium=_num(p,"call_premium"), qty=qty, contract_size=contract_size),
        ]

    if name == "bull_call_spread":
        return [
            Leg(option_type="call", side="long",  strike=_num(p,"long_strike"),  premium=_num(p,"long_premium"),  qty=qty, contract_size=contract_size),
            Leg(option_type="call", side="short", strike=_num(p,"short_strike"), premium=_num(p,"short_premium"), qty=qty, contract_size=contract_size),
        ]

    if name == "bear_put_spread":
        return [
            Leg(option_type="put", side="long",  strike=_num(p,"long_strike"),  premium=_num(p,"long_premium"),  qty=qty, contract_size=contract_size),
            Leg(option_type="put", side="short", strike=_num(p,"short_strike"), premium=_num(p,"short_premium"), qty=qty, contract_size=contract_size),
        ]

    if name == "iron_condor":
        # put spread (credit): long put wing + short put
        # call spread (credit): short call + long call wing
        return [
            Leg(option_type="put",  side="long",  strike=_num(p,"put_long_strike"),  premium=_num(p,"put_long_premium"),  qty=qty, contract_size=contract_size),
            Leg(option_type="put",  side="short", strike=_num(p,"put_short_strike"), premium=_num(p,"put_short_premium"), qty=qty, contract_size=contract_size),
            Leg(option_type="call", side="short", strike=_num(p,"call_short_strike"), premium=_num(p,"call_short_premium"), qty=qty, contract_size=contract_size),
            Leg(option_type="call", side="long",  strike=_num(p,"call_long_strike"),  premium=_num(p,"call_long_premium"),  qty=qty, contract_size=contract_size),
        ]

    raise ValueError(f"Unknown template name: {name}")

@router.post("/build", response_model=BuildResponse)
def build(req: BuildRequest):
    try:
        legs = _build(req.name, req.params)
        return BuildResponse(name=req.name, legs=legs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
