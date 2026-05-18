from fastapi import APIRouter

from app.core.amazon_runner import amazon_task_runner
from app.db import DB

router = APIRouter(prefix="/api/amazon")


def _parse_phone_line(line: str) -> dict | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = line.split("|", 1)
    if len(parts) != 2:
        return None
    phone, sms_url = parts[0].strip(), parts[1].strip()
    if not phone or not sms_url:
        return None
    return {"phone": phone, "sms_url": sms_url}


@router.post("/phones/import")
def import_phones(body: dict):
    content = body.get("content", "")
    lines = content.strip().splitlines()
    imported, errors, ids = 0, [], []
    for i, line in enumerate(lines, 1):
        parsed = _parse_phone_line(line)
        if not parsed:
            if line.strip():
                errors.append(f"line {i}: invalid format")
            continue
        try:
            row = DB.upsert_amazon_account(parsed)
            ids.append(row["id"])
            imported += 1
        except Exception as exc:
            errors.append(f"line {i}: {exc}")
    return {"imported": imported, "errors": errors, "account_ids": ids}


@router.get("/accounts")
def list_accounts():
    return {"items": DB.list_amazon_accounts()}


@router.delete("/accounts/{account_id}")
def delete_account(account_id: int):
    deleted = DB.delete_amazon_account(account_id)
    if not deleted:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


@router.post("/accounts/bulk-delete")
def bulk_delete(body: dict):
    ids = body.get("ids", [])
    count = DB.delete_amazon_accounts_bulk(ids)
    return {"deleted": count}


@router.post("/tasks")
def create_task(body: dict):
    amazon_ids = body.get("amazon_ids", [])
    template_browser_id = body.get("template_browser_id") or None
    concurrency = int(body.get("concurrency", 1))
    proxy_urls = body.get("proxy_urls") or []
    return amazon_task_runner.create_task(amazon_ids, template_browser_id, concurrency, proxy_urls)
