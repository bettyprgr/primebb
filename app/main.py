from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import accounts, browsers, config, services, tasks
from app.core.websocket import router as websocket_router
from app.db import DB

DB.init()

app = FastAPI(title="PrimeBB Automation", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router)
app.include_router(browsers.router)
app.include_router(config.router)
app.include_router(tasks.router)
app.include_router(services.router)
app.include_router(websocket_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "PrimeBB Automation API"}
