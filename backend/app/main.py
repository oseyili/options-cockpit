from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


    param($m)
    $line = $m.Groups[0].Value
    if ($line -match "recommend") { $line } else { $line + ", recommend" }
  

app = FastAPI(title="Options Cockpit API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(risk.router, prefix="/api")
app.include_router(execution.router, prefix="/api")
app.include_router(chain.router, prefix="/api")


app.include_router(recommend.router, prefix="/api")

