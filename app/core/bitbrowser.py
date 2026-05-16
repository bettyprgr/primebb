import time
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests

from app.config import get_settings
from app.core.proxies import bitbrowser_proxy_fields

NO_PROXY = {"http": None, "https": None}


class BitBrowserError(RuntimeError):
    pass


class BitBrowserClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.bitbrowser_url.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        self.session = requests.Session()
        self.session.trust_env = False

    def _request(self, path: str, payload: dict[str, Any] | None = None, timeout: int = 15, attempts: int = 2) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = self.session.post(
                    f"{self.base_url}{path}",
                    json=payload or {},
                    headers=self.headers,
                    timeout=timeout,
                    proxies=NO_PROXY,
                )
                response.raise_for_status()
                data = response.json()
                if self._is_success(data):
                    return data
                raise BitBrowserError(data.get("msg") or data.get("message") or str(data))
            except Exception as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(0.5 * (attempt + 1))
        raise BitBrowserError(str(last_error))

    @staticmethod
    def _is_success(data: dict[str, Any]) -> bool:
        return data.get("success") is True or data.get("code") == 0

    def list_profiles(self, page: int = 0, page_size: int = 1000) -> list[dict[str, Any]]:
        data = self._request("/browser/list", {"page": page, "pageSize": page_size}, timeout=10)
        result = data.get("data", {})
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("list", []) or []
        return []

    def get_profile(self, browser_id: str) -> dict[str, Any] | None:
        for profile in self.list_profiles():
            if profile.get("id") == browser_id:
                return profile
        return None

    def open_profile(self, browser_id: str) -> dict[str, Any]:
        data = self._request("/browser/open", {"id": browser_id}, timeout=30)
        open_data = data.get("data", {}) or {}
        return self._normalize_remote_debugger_addresses(open_data)

    def _normalize_remote_debugger_addresses(self, open_data: dict[str, Any]) -> dict[str, Any]:
        api_host = urlparse(self.base_url).hostname
        if not api_host or api_host in {"127.0.0.1", "localhost"}:
            return open_data
        for key in ("ws", "http"):
            value = open_data.get(key)
            if not value:
                continue
            parsed = urlparse(value if "://" in value else f"http://{value}")
            if parsed.hostname in {"127.0.0.1", "localhost"}:
                replaced = parsed._replace(netloc=f"{api_host}:{parsed.port}")
                normalized = urlunparse(replaced)
                open_data[key] = normalized if "://" in value else normalized.removeprefix("http://")
        return open_data

    def close_profile(self, browser_id: str) -> None:
        self._request("/browser/close", {"id": browser_id}, timeout=10)

    def delete_profile(self, browser_id: str) -> None:
        self._request("/browser/delete", {"id": browser_id}, timeout=10)

    def partial_update_profile(self, browser_id: str, data: dict[str, Any]) -> dict[str, Any]:
        payload = {"ids": [browser_id], **data}
        return self._request("/browser/update/partial", payload, timeout=10)

    def create_profile_from_template(self, account: dict[str, Any], proxy_url: str, template_browser_id: str | None = None) -> str:
        template = self.get_profile(template_browser_id) if template_browser_id else None
        if template_browser_id and not template:
            raise BitBrowserError(f"template browser not found: {template_browser_id}")
        if not template:
            profiles = self.list_profiles(page_size=50)
            template = profiles[0] if profiles else {}

        excluded = {"id", "name", "remark", "userName", "password", "faSecretKey", "createTime", "updateTime"}
        payload = {key: value for key, value in template.items() if key not in excluded}
        payload.update(bitbrowser_proxy_fields(proxy_url))
        payload["name"] = account.get("email") or "gmail-account"
        payload["userName"] = account.get("email") or ""
        payload["password"] = account.get("password") or ""
        payload["remark"] = self._build_remark(account)
        if account.get("totp_secret"):
            payload["faSecretKey"] = account["totp_secret"]
        payload.setdefault("browserFingerPrint", {})
        payload["browserFingerPrint"]["coreVersion"] = payload["browserFingerPrint"].get("coreVersion") or "140"
        payload["randomFingerprint"] = True
        payload["isRandomFinger"] = True
        response = self._request("/browser/update", payload, timeout=15)
        browser_id = (response.get("data") or {}).get("id")
        if not browser_id:
            raise BitBrowserError("BitBrowser did not return a browser id")
        return browser_id

    @staticmethod
    def _build_remark(account: dict[str, Any]) -> str:
        parts = [
            account.get("email") or "",
            account.get("password") or "",
            account.get("recovery_email") or "",
            account.get("totp_secret") or "",
            account.get("account_year") or "",
            account.get("country") or "",
        ]
        while parts and not parts[-1]:
            parts.pop()
        return "|".join(parts)
