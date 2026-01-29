from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from datetime import datetime
from sqlalchemy.orm import Session
import csv
import io

from app.db.database import SessionLocal, engine, Base
from app.models.trade import Trade

Base.metadata.create_all(bind=engine)

router = APIRouter(tags=["execution"])

class TradeRequest(BaseModel):
    symbol: str = Field(..., min_length=1)
    strategy: str = Field(..., min_length=1)
    max_loss: float = Field(..., ge=0)
    contracts: int = Field(1, ge=1, le=500)
    short_strike: float | None = None
    long_strike: float | None = None
    credit: float | None = None

def validate(req: TradeRequest):
    if req.strategy == "bull_put_credit_spread":
        if req.short_strike is None or req.long_strike is None or req.credit is None:
            raise HTTPException(status_code=400, detail="Spread requires short_strike, long_strike, credit.")
        if req.short_strike <= req.long_strike:
            raise HTTPException(status_code=400, detail="Invalid spread: short_strike must be > long_strike.")
        width = req.short_strike - req.long_strike
        if req.credit <= 0:
            raise HTTPException(status_code=400, detail="Invalid spread: credit must be > 0.")
        if req.credit >= width:
            raise HTTPException(status_code=400, detail="Invalid spread: credit must be < width.")

@router.post("/execute")
def execute_trade(req: TradeRequest):
    validate(req)

    db: Session = SessionLocal()
    trade = Trade(
        symbol=req.symbol,
        strategy=req.strategy,
        max_loss=req.max_loss,
        timestamp=datetime.utcnow().isoformat()
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    db.close()

    return {"status": "accepted", "trade": {"id": trade.id, "symbol": trade.symbol, "strategy": trade.strategy, "max_loss": trade.max_loss, "timestamp": trade.timestamp}}

@router.get("/trades")
def get_trades():
    db: Session = SessionLocal()
    items = db.query(Trade).order_by(Trade.id.desc()).limit(500).all()
    db.close()
    return [{"id": t.id, "symbol": t.symbol, "strategy": t.strategy, "max_loss": t.max_loss, "timestamp": t.timestamp} for t in items]

@router.get("/trades/export")
def export_trades_csv():
    db: Session = SessionLocal()
    items = db.query(Trade).order_by(Trade.id.asc()).all()
    db.close()

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id", "symbol", "strategy", "max_loss", "timestamp"])
    for t in items:
        w.writerow([t.id, t.symbol, t.strategy, t.max_loss, t.timestamp])
    out.seek(0)

    return StreamingResponse(
        out,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades.csv"}
    )
