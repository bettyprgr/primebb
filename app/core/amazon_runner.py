import asyncio
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from playwright.async_api import async_playwright

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


class BrowserClosedByUser(Exception):
    pass


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

        stats = {"completed": 0, "failed": 0, "manual_required": 0, "cancelled": 0}
        stats_lock = threading.Lock()

        def process(amazon_id: int) -> str:
            status = self._process_account(task_id, amazon_id, template_browser_id, proxy_map.get(amazon_id))
            with stats_lock:
                if status == "success":
                    stats["completed"] += 1
                elif status == "manual_required":
                    stats["manual_required"] += 1
                elif status == "cancelled":
                    stats["cancelled"] += 1
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

        if stats["cancelled"] and not stats["failed"] and not stats["manual_required"] and not stats["completed"]:
            final = "cancelled"
        elif stats["cancelled"]:
            final = "partial_cancelled"
        elif not stats["failed"] and not stats["manual_required"]:
            final = "completed"
        elif stats["manual_required"]:
            final = "partial_manual_required"
        else:
            final = "failed"
        DB.update_task(task_id, status=final, message="finished")
        _emit(manager.task_progress(DB.get_task(task_id) or {}))

    def _reset_browser_for_retry(self, task_id: str, account: dict, proxy_url_override: str | None) -> dict:
        """Close and delete the current BitBrowser profile, assign a new proxy ssid.
        Returns refreshed account dict so _run_async creates a clean profile on next attempt."""
        phone = account["phone"]
        bitbrowser_id = account.get("bitbrowser_id")
        if bitbrowser_id:
            client = BitBrowserClient()
            try:
                client.close_profile(bitbrowser_id)
            except Exception:
                pass
            try:
                client.delete_profile(bitbrowser_id)
            except Exception:
                pass
            DB.upsert_amazon_account({"phone": phone, "bitbrowser_id": None})

        if not proxy_url_override:
            new_proxy_url, _, _, _ = build_proxy_url(account, rotate=True)
            DB.upsert_amazon_account({"phone": phone, "proxy_url": new_proxy_url})
            _log(task_id, account["id"], "info", "retry: deleted old browser profile, new proxy ssid assigned")
        else:
            _log(task_id, account["id"], "info", "retry: deleted old browser profile (proxy override kept)")

        return DB.get_amazon_account(account["id"]) or account

    def _process_account(self, task_id: str, amazon_id: int, template_browser_id: str | None, proxy_url_override: str | None = None) -> str:
        with _account_lock(amazon_id):
            account = DB.get_amazon_account(amazon_id)
            if not account:
                return "failed"
            DB.update_task_item(task_id, amazon_id, "running", "running")
            _emit(manager.account_progress({"task_id": task_id, "account_id": amazon_id, "status": "running"}))

            max_retries = 2
            account_timeout = 720  # 12 minutes per attempt
            for attempt in range(1, max_retries + 1):
                try:
                    result = asyncio.run(
                        asyncio.wait_for(
                            self._run_async(task_id, account, template_browser_id, proxy_url_override),
                            timeout=account_timeout,
                        )
                    )
                    DB.update_task_item(task_id, amazon_id, result, result)
                    _emit(manager.account_progress({"task_id": task_id, "account_id": amazon_id, "status": result}))
                    return result
                except BrowserClosedByUser:
                    _log(task_id, amazon_id, "warning", "browser closed by user — task cancelled")
                    DB.upsert_amazon_account({"phone": account["phone"], "status": "cancelled", "message": "browser closed by user"})
                    DB.update_task_item(task_id, amazon_id, "cancelled", "browser closed by user")
                    _emit(manager.account_progress({"task_id": task_id, "account_id": amazon_id, "status": "cancelled"}))
                    return "cancelled"
                except asyncio.TimeoutError:
                    _log(task_id, amazon_id, "warning", f"attempt {attempt}/{max_retries} timed out after {account_timeout}s")
                    if attempt == max_retries:
                        DB.upsert_amazon_account({"phone": account["phone"], "status": "failed", "message": f"timed out after {max_retries} attempts"})
                        DB.update_task_item(task_id, amazon_id, "error", "timed out")
                        return "failed"
                    account = self._reset_browser_for_retry(task_id, account, proxy_url_override)
                except Exception as exc:
                    _log(task_id, amazon_id, "error", f"attempt {attempt}/{max_retries} error: {exc}")
                    if attempt == max_retries:
                        DB.upsert_amazon_account({"phone": account["phone"], "status": "failed", "message": str(exc)})
                        DB.update_task_item(task_id, amazon_id, "error", str(exc))
                        return "failed"
                    account = self._reset_browser_for_retry(task_id, account, proxy_url_override)
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

            # Detect user closing the browser profile.
            # bot_closing flag prevents self-close from being mistaken for user action.
            loop = asyncio.get_running_loop()
            disconnect_future: asyncio.Future = loop.create_future()
            bot_closing = False

            def _on_disconnect():
                if not bot_closing and not disconnect_future.done():
                    disconnect_future.set_result(True)

            browser.on("disconnected", lambda _: _on_disconnect())

            async def _register():
                nonlocal bot_closing
                reg_result = "failed"
                try:
                    # Try to get proxy region using a separate tab
                    try:
                        geo_page = await context.new_page()
                        geo = await verify_proxy_geo(geo_page)
                        await geo_page.close()
                        if geo:
                            region = geo.get("region") or geo.get("country_name") or ""
                            DB.upsert_amazon_account({"phone": account["phone"], "proxy_region": region})
                    except Exception:
                        pass

                    result, name, password = await register_amazon(context, account["phone"], account["sms_url"], callback, preset_name=account.get("name"), bitbrowser_id=bitbrowser_id, client=client)
                    DB.upsert_amazon_account({
                        "phone": account["phone"],
                        "status": result.status,
                        "message": result.message,
                        "name": name,
                        "password": password,
                    })
                    if result.manual_required:
                        reg_result = "manual_required"
                    else:
                        reg_result = "success" if result.success else "failed"
                    return reg_result
                finally:
                    bot_closing = True
                    try:
                        await browser.close()
                    except Exception:
                        pass
                    if reg_result == "success":
                        settings = get_settings()
                        loop = asyncio.get_running_loop()
                        if settings.delete_browser_after_complete:
                            try:
                                await loop.run_in_executor(None, client.delete_profile, bitbrowser_id)
                            except Exception:
                                pass
                        else:
                            try:
                                await loop.run_in_executor(None, client.close_profile, bitbrowser_id)
                            except Exception:
                                pass

            reg_task = asyncio.ensure_future(_register())
            done, pending = await asyncio.wait(
                [reg_task, disconnect_future],
                return_when=asyncio.FIRST_COMPLETED,
            )

            if disconnect_future in done and reg_task not in done:
                # User closed browser — give reg_task a brief grace period to finish
                try:
                    return await asyncio.wait_for(asyncio.shield(reg_task), timeout=10.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    reg_task.cancel()
                    raise BrowserClosedByUser("browser closed by user")

            for t in pending:
                t.cancel()
            return await reg_task


amazon_task_runner = AmazonTaskRunner()
