import asyncio
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from playwright.async_api import async_playwright

from app.automation.google_auth import ensure_google_authenticated
from app.automation.service_login import SUPPORTED_SERVICES, login_service_with_google
from app.config import get_settings
from app.core.browser_sessions import BrowserSessionManager, verify_proxy_geo
from app.core.websocket import manager
from app.db import DB
from app.schemas import TaskCreateRequest, TaskStatus, TaskType

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


def log_event(task_id: str, account_id: int | None, service: str | None, level: str, event_type: str, message: str) -> None:
    DB.add_event(task_id, account_id, service, level, event_type, message)
    _emit(manager.log(level, message, task_id=task_id, account_id=account_id, service=service))


class TaskRunner:
    def create_task(self, request: TaskCreateRequest) -> dict[str, Any]:
        if not request.account_ids:
            raise ValueError("account_ids is required")
        task_id = str(uuid.uuid4())[:8]
        total = len(dict.fromkeys(request.account_ids))
        DB.create_task(task_id, request.type.value, total)
        for account_id in dict.fromkeys(request.account_ids):
            DB.create_task_item(task_id, account_id)
        executor.submit(self._run_task, task_id, request)
        return DB.get_task(task_id) or {"id": task_id}

    def _run_task(self, task_id: str, request: TaskCreateRequest) -> None:
        account_ids = list(dict.fromkeys(request.account_ids))
        proxy_map: dict[int, str] = {}
        if request.proxy_urls:
            for i, account_id in enumerate(account_ids):
                if i < len(request.proxy_urls):
                    proxy_map[account_id] = request.proxy_urls[i]
        concurrency = max(1, min(request.concurrency, get_settings().max_task_concurrency))
        DB.update_task(task_id, status=TaskStatus.running.value, message="running")
        _emit(manager.task_progress(DB.get_task(task_id) or {}))

        stats = {"completed": 0, "failed": 0, "manual_required": 0}
        stats_lock = threading.Lock()

        def process(account_id: int) -> str:
            status = self._process_account(task_id, request, account_id, proxy_map.get(account_id))
            with stats_lock:
                if status == "success":
                    stats["completed"] += 1
                elif status == "manual_required":
                    stats["manual_required"] += 1
                else:
                    stats["failed"] += 1
                DB.update_task(
                    task_id,
                    completed=stats["completed"],
                    failed=stats["failed"],
                    manual_required=stats["manual_required"],
                )
                _emit(manager.task_progress(DB.get_task(task_id) or {}))
            return status

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(process, account_id) for account_id in account_ids]
            for future in futures:
                try:
                    future.result()
                except Exception as exc:
                    log_event(task_id, None, None, "error", "task_error", str(exc))
                    with stats_lock:
                        stats["failed"] += 1

        final_status = TaskStatus.completed.value
        if stats["manual_required"]:
            final_status = TaskStatus.partial_manual_required.value
        elif stats["failed"]:
            final_status = TaskStatus.failed.value
        DB.update_task(task_id, status=final_status, message="finished")
        _emit(manager.task_progress(DB.get_task(task_id) or {}))

    def _process_account(self, task_id: str, request: TaskCreateRequest, account_id: int, proxy_url_override: str | None = None) -> str:
        with _account_lock(account_id):
            account = DB.get_account(account_id)
            if not account:
                log_event(task_id, account_id, None, "error", "account_missing", "account not found")
                return "failed"
            DB.update_task_item(task_id, account_id, "running", "running")
            _emit(manager.account_progress({"task_id": task_id, "account_id": account_id, "status": "running"}))
            try:
                result = asyncio.run(self._run_account_async(task_id, request, account, proxy_url_override))
                DB.update_task_item(task_id, account_id, result, result)
                _emit(manager.account_progress({"task_id": task_id, "account_id": account_id, "status": result}))
                return result
            except Exception as exc:
                DB.upsert_account({"email": account["email"], "status": "error", "message": str(exc)})
                DB.update_task_item(task_id, account_id, "error", str(exc))
                log_event(task_id, account_id, None, "error", "account_error", str(exc))
                return "failed"

    async def _run_account_async(self, task_id: str, request: TaskCreateRequest, account: dict[str, Any], proxy_url_override: str | None = None) -> str:
        browser_manager = BrowserSessionManager()
        ensured = browser_manager.ensure_browser_for_account(
            account["id"],
            template_browser_id=request.template_browser_id,
            rotate_proxy=False,
            proxy_url_override=proxy_url_override,
        )
        browser_id = ensured["browser_id"]
        open_data = browser_manager.open_browser(browser_id)
        ws = open_data.get("ws")
        if not ws:
            raise RuntimeError("BitBrowser did not return a Playwright websocket endpoint")

        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(ws)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[-1] if context.pages else await context.new_page()
            result = "failed"
            try:
                try:
                    geo = await verify_proxy_geo(page, account)
                    if geo:
                        log_event(task_id, account["id"], None, "info", "proxy_geo", "proxy geo verified")
                except Exception as exc:
                    log_event(task_id, account["id"], None, "warning", "proxy_geo_failed", f"proxy geo check failed: {exc}")

                async def callback(level: str, message: str) -> None:
                    log_event(task_id, account["id"], None, level, "automation", message)

                google_result = await ensure_google_authenticated(page, DB.get_account(account["id"]) or account, callback)
                DB.upsert_account({"email": account["email"], "status": google_result.status, "message": google_result.message})
                if google_result.manual_required:
                    result = "manual_required"
                    return result
                if not google_result.success:
                    result = "failed"
                    return result
                if request.type == TaskType.login_gmail:
                    result = "success"
                    return result

                services = request.services or SUPPORTED_SERVICES
                for service in services:
                    DB.upsert_service_login(account["id"], service, "running", "running")
                    DB.create_task_item(task_id, account["id"], service)
                    _emit(manager.service_progress({"task_id": task_id, "account_id": account["id"], "service": service, "status": "running"}))

                    async def service_callback(level: str, message: str, svc: str = service) -> None:
                        log_event(task_id, account["id"], svc, level, "automation", message)

                    service_result = await login_service_with_google(page, service, DB.get_account(account["id"]) or account, service_callback)
                    svc_status = "manual_required" if service_result.manual_required else service_result.status
                    DB.upsert_service_login(account["id"], service, svc_status, service_result.message)
                    DB.update_task_item(task_id, account["id"], svc_status, service_result.message, service)
                    _emit(manager.service_progress({"task_id": task_id, "account_id": account["id"], "service": service, "status": svc_status}))
                    if service_result.manual_required:
                        result = "manual_required"
                        return result
                result = "success"
                return result
            finally:
                await browser.close()
                if result == "success":
                    settings = get_settings()
                    if settings.delete_browser_after_complete:
                        try:
                            browser_manager.delete_browser(browser_id)
                        except Exception:
                            pass
                    else:
                        try:
                            browser_manager.close_browser(browser_id)
                        except Exception:
                            pass
                elif request.close_after:
                    browser_manager.close_browser(browser_id)


task_runner = TaskRunner()
