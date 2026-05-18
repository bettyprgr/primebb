import asyncio
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from playwright.async_api import async_playwright

from app.automation.amazon_check import check_amazon_suspended
from app.automation.amazon_reg import register_amazon
from app.config import get_settings
from app.core.bitbrowser import BitBrowserClient
from app.core.browser_sessions import verify_proxy_geo
from app.core.proxies import bitbrowser_proxy_fields, build_proxy_url
from app.core.websocket import manager
from app.db import DB

executor = ThreadPoolExecutor(max_workers=5)
_account_locks: dict[int, threading.Lock] = {}
_account_locks_guard = threading.Lock()


def _account_lock(account_id: int) -> threading.Lock:
    with _account_locks_guard:
        if account_id not in _account_locks:
            _account_locks[account_id] = threading.Lock()
        return _account_locks[account_id]


def _emit(coro) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
    else:
        loop.create_task(coro)


def _log(task_id: str, amazon_id: int | None, level: str, message: str) -> None:
    DB.add_event(task_id, amazon_id, "amazon", level, "automation", message)
    _emit(manager.log(level, message, task_id=task_id, account_id=amazon_id, service="amazon"))


class AmazonTaskRunner:
    def create_task(self, amazon_ids: list[int], template_browser_id: str | None, concurrency: int, proxy_urls: list[str] | None = None) -> dict[str, Any]:
        if not amazon_ids:
            raise ValueError("amazon_ids is required")
        task_id = str(uuid.uuid4())[:8]
        total = len(dict.fromkeys(amazon_ids))
        DB.create_task(task_id, "amazon_create", total)
        for aid in dict.fromkeys(amazon_ids):
            DB.create_task_item(task_id, aid)
        executor.submit(self._run_task, task_id, amazon_ids, template_browser_id, concurrency, proxy_urls or [])
        return DB.get_task(task_id) or {"id": task_id}

    def _run_task(self, task_id: str, amazon_ids: list[int], template_browser_id: str | None, concurrency: int, proxy_urls: list[str]) -> None:
        unique_ids = list(dict.fromkeys(amazon_ids))
        proxy_map: dict[int, str] = {}
        for i, aid in enumerate(unique_ids):
            if i < len(proxy_urls):
                proxy_map[aid] = proxy_urls[i]
        concurrency = max(1, min(concurrency, get_settings().max_task_concurrency))
        DB.update_task(task_id, status="running", message="running")
        _emit(manager.task_progress(DB.get_task(task_id) or {}))

        stats = {"completed": 0, "failed": 0, "manual_required": 0}
        stats_lock = threading.Lock()

        def process(amazon_id: int) -> str:
            status = self._process_account(task_id, amazon_id, template_browser_id, proxy_map.get(amazon_id))
            with stats_lock:
                if status == "success":
                    stats["completed"] += 1
                elif status == "manual_required":
                    stats["manual_required"] += 1
                else:
                    stats["failed"] += 1
                DB.update_task(task_id, completed=stats["completed"], failed=stats["failed"], manual_required=stats["manual_required"])
                _emit(manager.task_progress(DB.get_task(task_id) or {}))
            return status

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(process, aid) for aid in unique_ids]
            for future in futures:
                try:
                    future.result()
                except Exception as exc:
                    _log(task_id, None, "error", str(exc))
                    with stats_lock:
                        stats["failed"] += 1

        final = "completed" if not stats["failed"] and not stats["manual_required"] else ("partial_manual_required" if stats["manual_required"] else "failed")
        DB.update_task(task_id, status=final, message="finished")
        _emit(manager.task_progress(DB.get_task(task_id) or {}))

    def _process_account(self, task_id: str, amazon_id: int, template_browser_id: str | None, proxy_url_override: str | None = None) -> str:
        with _account_lock(amazon_id):
            account = DB.get_amazon_account(amazon_id)
            if not account:
                return "failed"
            DB.update_task_item(task_id, amazon_id, "running", "running")
            _emit(manager.account_progress({"task_id": task_id, "account_id": amazon_id, "status": "running"}))
            try:
                result = asyncio.run(self._run_async(task_id, account, template_browser_id, proxy_url_override))
                DB.update_task_item(task_id, amazon_id, result, result)
                _emit(manager.account_progress({"task_id": task_id, "account_id": amazon_id, "status": result}))
                return result
            except Exception as exc:
                DB.upsert_amazon_account({"phone": account["phone"], "status": "failed", "message": str(exc)})
                DB.update_task_item(task_id, amazon_id, "error", str(exc))
                _log(task_id, amazon_id, "error", str(exc))
                return "failed"

    async def _run_async(self, task_id: str, account: dict[str, Any], template_browser_id: str | None, proxy_url_override: str | None = None) -> str:
        client = BitBrowserClient()
        proxy_url = proxy_url_override or account.get("proxy_url") or ""

        # Fallback to config proxy if none provided
        if not proxy_url:
            proxy_url, _, _, _ = build_proxy_url({"country": "US"})

        # Save proxy_url override to account
        if proxy_url_override:
            DB.upsert_amazon_account({"phone": account["phone"], "proxy_url": proxy_url_override})

        # Ensure browser profile
        bitbrowser_id = account.get("bitbrowser_id")
        existing = client.get_profile(bitbrowser_id) if bitbrowser_id else None
        if not existing:
            fake_account = {
                "email": account["phone"],
                "password": account.get("password") or "",
                "totp_secret": None,
            }
            bitbrowser_id = client.create_profile_from_template(fake_account, proxy_url, template_browser_id)
            DB.upsert_amazon_account({"phone": account["phone"], "bitbrowser_id": bitbrowser_id})
        else:
            # Update proxy on existing profile before opening
            if proxy_url:
                client.partial_update_profile(bitbrowser_id, bitbrowser_proxy_fields(proxy_url))

        open_data = client.open_profile(bitbrowser_id)
        ws = open_data.get("ws")
        if not ws:
            raise RuntimeError("BitBrowser did not return a Playwright websocket endpoint")

        async def callback(level: str, message: str) -> None:
            _log(task_id, account["id"], level, message)

        async with async_playwright() as playwright:
            # Retry CDP connection up to 3 times — browser may need a moment to start
            browser = None
            for attempt in range(3):
                try:
                    browser = await playwright.chromium.connect_over_cdp(ws)
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(3)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[-1] if context.pages else await context.new_page()
            try:
                # Try to get proxy region using a separate tab
                try:
                    geo_page = await context.new_page()
                    geo = await verify_proxy_geo(geo_page, {"proxy_url": proxy_url, "email": account["phone"]})
                    await geo_page.close()
                    if geo:
                        region = geo.get("region") or geo.get("country_name") or ""
                        DB.upsert_amazon_account({"phone": account["phone"], "proxy_region": region})
                except Exception:
                    pass

                result, name, password = await register_amazon(page, account["phone"], account["sms_url"], callback)
                check_after = (datetime.now(timezone.utc) + timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
                DB.upsert_amazon_account({
                    "phone": account["phone"],
                    "status": result.status,
                    "message": result.message,
                    "name": name,
                    "password": password,
                    "check_after_at": check_after if result.success else None,
                })
                if result.manual_required:
                    return "manual_required"
                return "success" if result.success else "failed"
            finally:
                await browser.close()


class AmazonSuspendChecker:
    def check_account(self, amazon_id: int, template_browser_id: str | None = None) -> None:
        executor.submit(self._run, amazon_id, template_browser_id)

    def _run(self, amazon_id: int, template_browser_id: str | None) -> None:
        account = DB.get_amazon_account(amazon_id)
        if not account:
            return
        try:
            asyncio.run(self._run_async(account, template_browser_id))
        except Exception as exc:
            DB.upsert_amazon_account({"phone": account["phone"], "status": "error", "message": str(exc)})

    async def _run_async(self, account: dict[str, Any], template_browser_id: str | None) -> None:
        client = BitBrowserClient()
        bitbrowser_id = account.get("bitbrowser_id")
        existing = client.get_profile(bitbrowser_id) if bitbrowser_id else None
        if not existing:
            return

        open_data = client.open_profile(bitbrowser_id)
        ws = open_data.get("ws")
        if not ws:
            return

        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(ws)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[-1] if context.pages else await context.new_page()
            try:
                suspended, message = await check_amazon_suspended(page)
                now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                DB.upsert_amazon_account({
                    "phone": account["phone"],
                    "status": "suspended" if suspended else "active",
                    "message": message,
                    "last_checked_at": now,
                    "check_after_at": None,
                })
            finally:
                await browser.close()


amazon_task_runner = AmazonTaskRunner()
amazon_suspend_checker = AmazonSuspendChecker()
