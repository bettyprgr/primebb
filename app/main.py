from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import accounts, amazon, browsers, config, services, tasks
from app.core.amazon_scheduler import start_suspend_scheduler
from app.core.websocket import router as websocket_router
from app.db import DB

DB.init()
DB.cleanup_zombie_tasks(stale_minutes=0)
start_suspend_scheduler()

app = FastAPI(title="PrimeBB Automation", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router)
app.include_router(amazon.router)
app.include_router(browsers.router)
app.include_router(config.router)
app.include_router(tasks.router)
app.include_router(services.router)
app.include_router(websocket_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve frontend — must be last so API routes take priority
_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _dist.exists():
    from fastapi.responses import FileResponse

    @app.get("/")
    def root():
        return FileResponse(_dist / "index.html")

    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")
else:
    @app.get("/")
    def root():
        return {"message": "PrimeBB Automation API"}
