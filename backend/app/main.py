from fastapi import FastAPI
from app.api.bs import router as bs_router

app = FastAPI()
app.include_router(bs_router)

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/version")
def version():
    return {"commit": "01a7abe"}
