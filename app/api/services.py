from fastapi import APIRouter, HTTPException

from app.automation.service_login import SUPPORTED_SERVICES
from app.db import DB

router = APIRouter(prefix="/api", tags=["services"])


@router.get("/services")
def list_services():
    return {"items": SUPPORTED_SERVICES}


@router.get("/accounts/{account_id}/services")
def account_services(account_id: int):
    account = DB.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    existing = {row["service"]: row for row in DB.list_service_logins(account_id)}
    return {
        "account_id": account_id,
        "items": [existing.get(service) or {"account_id": account_id, "service": service, "status": "pending"} for service in SUPPORTED_SERVICES],
    }
