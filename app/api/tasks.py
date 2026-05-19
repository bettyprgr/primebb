from fastapi import APIRouter, HTTPException

from app.core.task_runner import task_runner
from app.db import DB
from app.schemas import TaskCreateRequest

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("")
def create_task(data: TaskCreateRequest):
    try:
        return task_runner.create_task(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
def list_tasks():
    return DB.list_tasks()


@router.get("/{task_id}")
def get_task(task_id: str):
    task = DB.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.delete("/{task_id}")
def cancel_task(task_id: str):
    task = DB.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    DB.update_task(task_id, status="cancelled", message="cancelled")
    return {"message": "cancelled"}


@router.post("/cleanup/zombies")
def cleanup_zombies():
    cleaned = DB.cleanup_zombie_tasks(stale_minutes=0)
    return {"cleaned": cleaned}
