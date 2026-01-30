from fastapi import FastAPI
from app.api.saved import router as saved_router
from app.api.strategies import router as strategies_router
from app.api.portfolio import router as portfolio_router
from app.api.pl import router as pl_router
from app.api.iv import router as iv_router
from app.api.bs import router as bs_router

app = FastAPI()
app.include_router(bs_router)
app.include_router(iv_router)
app.include_router(pl_router)
app.include_router(portfolio_router)
app.include_router(strategies_router)
app.include_router(saved_router)

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/version")
def version():
    return {"commit": "01a7abe"}








