from fastapi import APIRouter, HTTPException

from app.core.bitbrowser import BitBrowserClient, BitBrowserError
from app.core.browser_sessions import BrowserSessionManager
from app.schemas import BrowserEnsureRequest, BrowserOpenResponse

router = APIRouter(prefix="/api/browsers", tags=["browsers"])


@router.get("")
def list_browsers():
    try:
        return BitBrowserClient().list_profiles()
    except BitBrowserError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/ensure")
def ensure_browser(data: BrowserEnsureRequest):
    try:
        return BrowserSessionManager().ensure_browser_for_account(
            data.account_id,
            template_browser_id=data.template_browser_id,
            rotate_proxy=data.rotate_proxy,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{browser_id}/open", response_model=BrowserOpenResponse)
def open_browser(browser_id: str):
    try:
        data = BrowserSessionManager().open_browser(browser_id)
        return {"browser_id": browser_id, "ws": data.get("ws")}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{browser_id}/close")
def close_browser(browser_id: str):
    try:
        BrowserSessionManager().close_browser(browser_id)
        return {"message": "closed"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
