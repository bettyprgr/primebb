from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
def get_config():
    settings = get_settings()
    return {
        "bitbrowser_url": settings.bitbrowser_url,
        "ipdata_configured": bool(settings.ipdata_api_key),
        "proxy_host": settings.proxy_host,
        "proxy_port": settings.proxy_port,
        "proxy_username_prefix": settings.proxy_username_prefix,
        "proxy_session_ttl": settings.proxy_session_ttl,
    }
