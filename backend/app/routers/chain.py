from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services.chain_sim import make_chain

router = APIRouter(tags=["chain"])

class ChainRequest(BaseModel):
    spot: float = Field(..., gt=0)
    dte: int = Field(30, ge=1, le=365)

@router.post("/chain")
def get_chain(req: ChainRequest):
    return make_chain(req.spot, req.dte)
