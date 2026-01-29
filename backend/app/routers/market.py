from fastapi import APIRouter, WebSocket
from app.services.sim_market import SimMarket
import asyncio

router = APIRouter(tags=["market"])
sim = SimMarket(symbol="SPY", start_price=480.0)

@router.get("/market/quote")
def get_quote():
    return sim.tick()

@router.websocket("/ws/market")
async def ws_market(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_json(sim.tick())
            await asyncio.sleep(1.0)
    except Exception:
        return
