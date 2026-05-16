import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        if not self.connections:
            return
        text = json.dumps(message, ensure_ascii=False)
        disconnected: list[WebSocket] = []
        for websocket in self.connections:
            try:
                await websocket.send_text(text)
            except Exception:
                disconnected.append(websocket)
        for websocket in disconnected:
            self.disconnect(websocket)

    async def log(self, level: str, message: str, task_id: str | None = None, account_id: int | None = None, service: str | None = None) -> None:
        await self.broadcast({
            "type": "log",
            "data": {"level": level, "message": message, "task_id": task_id, "account_id": account_id, "service": service},
        })

    async def task_progress(self, data: dict[str, Any]) -> None:
        await self.broadcast({"type": "task_progress", "data": data})

    async def account_progress(self, data: dict[str, Any]) -> None:
        await self.broadcast({"type": "account_progress", "data": data})

    async def service_progress(self, data: dict[str, Any]) -> None:
        await self.broadcast({"type": "service_progress", "data": data})


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
