import json
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.core.bitbrowser import BitBrowserClient
from app.core.proxies import bitbrowser_proxy_fields, build_proxy_url, region_slug
from app.db import DB


class BrowserSessionManager:
    def __init__(self) -> None:
        self.client = BitBrowserClient()

    def ensure_browser_for_account(self, account_id: int, template_browser_id: str | None = None, rotate_proxy: bool = False, proxy_url_override: str | None = None) -> dict[str, Any]:
        account = DB.get_account(account_id)
        if not account:
            raise ValueError("account not found")

        if proxy_url_override:
            proxy_url = proxy_url_override
            DB.upsert_account({"email": account["email"], "proxy_url": proxy_url})
        else:
            proxy_url, ssid, proxy_country, saved_region_slug = build_proxy_url(account, rotate=rotate_proxy)
            DB.upsert_account({
                "email": account["email"],
                "proxy_url": proxy_url,
                "proxy_ssid": ssid,
                "proxy_country": proxy_country,
                "proxy_region_slug": saved_region_slug,
            })
        account = DB.get_account(account_id) or account

        profile_row = DB.get_browser_profile_by_account(account_id)
        bitbrowser_id = profile_row.get("bitbrowser_id") if profile_row else None
        existing_profile = self.client.get_profile(bitbrowser_id) if bitbrowser_id else None

        if existing_profile:
            if rotate_proxy:
                self.client.partial_update_profile(bitbrowser_id, bitbrowser_proxy_fields(proxy_url))
                existing_profile = self.client.get_profile(bitbrowser_id) or existing_profile
            DB.save_browser_profile(account_id, bitbrowser_id, existing_profile, template_browser_id, status="created")
            return {"browser_id": bitbrowser_id, "profile": existing_profile, "proxy_url": proxy_url}

        browser_id = self.client.create_profile_from_template(account, proxy_url, template_browser_id)
        profile = self.client.get_profile(browser_id) or {"id": browser_id, "userName": account.get("email")}
        DB.save_browser_profile(account_id, browser_id, profile, template_browser_id, status="created")
        return {"browser_id": browser_id, "profile": profile, "proxy_url": proxy_url}

    def open_browser(self, browser_id: str) -> dict[str, Any]:
        data = self.client.open_profile(browser_id)
        DB.update_browser_profile_status(browser_id, "open")
        return data

    def close_browser(self, browser_id: str) -> None:
        self.client.close_profile(browser_id)
        DB.update_browser_profile_status(browser_id, "closed")


async def verify_proxy_geo(page, account: dict[str, Any]) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.ipdata_api_key:
        return None
    url = "https://api.ipdata.co/?api-key={key}&fields=ip,region,country_name,country_code,latitude,longitude,postal".format(
        key=settings.ipdata_api_key
    )
    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
    body = await page.locator("body").inner_text(timeout=10000)
    data = json.loads(body)
    region = data.get("region")
    payload = {
        "email": account["email"],
        "proxy_ip": data.get("ip"),
        "proxy_state_region": region,
        "proxy_region_slug": region_slug(region),
        "proxy_country_name": data.get("country_name"),
        "proxy_country_code": data.get("country_code"),
        "proxy_latitude": data.get("latitude"),
        "proxy_longitude": data.get("longitude"),
        "proxy_postal": data.get("postal"),
        "proxy_checked_at": datetime.now(timezone.utc).isoformat(),
    }
    DB.upsert_account(payload)
    return data
