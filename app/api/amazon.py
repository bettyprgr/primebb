from fastapi import APIRouter

from app.core.amazon_runner import amazon_task_runner
from app.core.proxies import build_proxy_url, state_full_name
from app.db import DB

router = APIRouter(prefix="/api/amazon")


def _parse_phone_line(line: str) -> dict | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = line.split("|")
    if len(parts) < 2:
        return None
    phone, sms_url = parts[0].strip(), parts[1].strip()
    if not phone or not sms_url:
        return None
    result: dict = {"phone": phone, "sms_url": sms_url, "status": "pending", "message": None}
    if len(parts) >= 3 and parts[2].strip():
        result["name"] = parts[2].strip()
    if len(parts) >= 4 and parts[3].strip():
        abbr = parts[3].strip().upper()
        full = state_full_name(abbr)
        if full:
            proxy_url, _, _, _ = build_proxy_url({"proxy_state_region": full, "country": "US"}, rotate=True)
            result["proxy_url"] = proxy_url
            result["proxy_region"] = abbr
    return result


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


@router.patch("/accounts/{account_id}")
def update_account(account_id: int, body: dict):
    account = DB.get_amazon_account(account_id)
    if not account:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="not found")
    payload: dict = {"phone": account["phone"]}
    if "status" in body:
        payload["status"] = body["status"]
    if "message" in body:
        payload["message"] = body["message"]
    return DB.upsert_amazon_account(payload)


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
