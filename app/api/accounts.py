from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db import DB
from app.schemas import Account, AccountCreate, AccountListResponse, AccountUpdate, ImportAccountsRequest, ImportAccountsResponse

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def parse_pipe_account_line(line: str) -> dict[str, str]:
    parts = [part.strip() for part in line.split("|")]
    if len(parts) != 6:
        raise ValueError("expected 6 pipe-separated fields")
    email, password, recovery_email, totp_secret, account_year, country = parts
    if not email or "@" not in email:
        raise ValueError("invalid email")
    return {
        "email": email,
        "password": password,
        "recovery_email": recovery_email,
        "totp_secret": totp_secret,
        "account_year": account_year,
        "country": country,
        "status": "pending",
    }


@router.get("", response_model=AccountListResponse)
def list_accounts(search: str | None = None, status: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    items = DB.list_accounts()
    if search:
        needle = search.lower()
        items = [item for item in items if needle in (item.get("email") or "").lower()]
    if status:
        items = [item for item in items if item.get("status") == status]
    total = len(items)
    start = (page - 1) * page_size
    return {"total": total, "items": items[start:start + page_size]}


@router.post("", response_model=Account)
def create_account(data: AccountCreate):
    try:
        return DB.upsert_account(data.model_dump(exclude_unset=True))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import", response_model=ImportAccountsResponse)
def import_accounts(data: ImportAccountsRequest):
    imported = 0
    errors: list[str] = []
    account_ids: list[int] = []
    for index, raw_line in enumerate(data.content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            account = parse_pipe_account_line(line)
            saved = DB.upsert_account(account)
            account_ids.append(saved["id"])
            imported += 1
        except Exception as exc:
            errors.append(f"line {index}: {exc}")
    return {"imported": imported, "errors": errors, "account_ids": account_ids}


@router.get("/{account_id}", response_model=Account)
def get_account(account_id: int):
    account = DB.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    return account


@router.patch("/{account_id}", response_model=Account)
def update_account(account_id: int, data: AccountUpdate):
    account = DB.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    payload = data.model_dump(exclude_unset=True)
    if "status" in payload and payload["status"] is not None:
        payload["status"] = payload["status"].value
    payload["email"] = account["email"]
    return DB.upsert_account(payload)


@router.delete("/{account_id}")
def delete_account(account_id: int):
    if not DB.delete_account(account_id):
        raise HTTPException(status_code=404, detail="account not found")
    return {"message": "deleted"}


class BulkDeleteRequest(BaseModel):
    account_ids: list[int]


@router.post("/bulk-delete")
def bulk_delete_accounts(data: BulkDeleteRequest):
    deleted = DB.delete_accounts_bulk(data.account_ids)
    return {"deleted": deleted}


@router.delete("")
def delete_all_accounts():
    deleted = DB.delete_all_accounts()
    return {"deleted": deleted}
