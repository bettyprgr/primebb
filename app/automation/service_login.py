import asyncio
import re
from collections.abc import Awaitable, Callable
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.automation.detectors import detect_manual_verification, find_visible, service_success
from app.automation.google_auth import ensure_google_authenticated
from app.schemas import AutomationResult

Callback = Callable[[str, str], Awaitable[None] | None]

SUPPORTED_SERVICES = ["youtube", "quora", "reddit", "x", "ebay"]

SERVICE_CONFIGS = {
    "youtube": {
        "start_url": "https://www.youtube.com/",
        "login_selectors": ['a[href*="accounts.google.com/ServiceLogin"]', 'a:has-text("Sign in")', 'tp-yt-paper-button:has-text("Sign in")'],
        "google_selectors": [],
        "logout_url": "https://accounts.google.com/Logout?continue=https://www.youtube.com/",
    },
    "quora": {
        "start_url": "https://www.quora.com/",
        "login_selectors": ['button:has-text("Log In")', 'button:has-text("Login")', 'text=/Log In|Login/i'],
        "google_selectors": ['button:has-text("Continue with Google")', 'div[role="button"]:has-text("Continue with Google")', 'text=/Continue with Google|Google/i', '[aria-label*="Google" i]', '[id*="google" i]'],
        "menu_selectors": ['[aria-label*="Profile" i]', '[aria-label*="Account" i]', 'img[alt*="Profile" i]'],
        "logout_selectors": ['text=/Log Out|Logout|Sign Out|Sign out/i'],
    },
    "reddit": {
        "start_url": "https://www.reddit.com/login/",
        "home_url": "https://www.reddit.com/",
        "login_selectors": [],
        "google_selectors": ['button:has-text("Continue with Google")', 'div[role="button"]:has-text("Google")', 'span:has-text("Continue with Google")', '[aria-label*="Google" i]', 'button[id*="google" i]', 'iframe[src*="accounts.google"]'],
        "logout_url": "https://www.reddit.com/logout",
        "logout_selectors": ['button:has-text("Log Out")', 'button:has-text("Log out")', 'text=/Log Out|Log out/i'],
    },
    "x": {
        "start_url": "https://x.com/i/flow/login",
        "home_url": "https://x.com/home",
        "login_selectors": [],
        "google_selectors": ['div[role="button"]:has-text("Google")', 'span:has-text("Sign in with Google")', '[data-testid*="google" i]', 'iframe[src*="accounts.google"]'],
        "logout_url": "https://x.com/logout",
        "logout_selectors": ['div[role="button"]:has-text("Log out")', '[data-testid="confirmationSheetConfirm"]'],
    },
    "ebay": {
        "start_url": "https://signin.ebay.com/",
        "home_url": "https://www.ebay.com/",
        "login_selectors": [],
        "google_selectors": ['button:has-text("Continue with Google")', 'button:has-text("Sign in with Google")', '[data-testid*="google" i]', 'text=/Continue with Google|Google/i', '[id*="google" i]', '[aria-label*="Google" i]'],
        "logout_url": "https://signin.ebay.com/ws/eBayISAPI.dll?SignIn&lgout=1",
    },
}


async def _emit(callback: Callback | None, level: str, message: str) -> None:
    if not callback:
        return
    result = callback(level, message)
    if hasattr(result, "__await__"):
        await result


async def _goto(page, url: str) -> None:
    try:
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
    except Exception:
        await asyncio.sleep(3)


async def _click_first(page, selectors: list[str]) -> bool:
    locator = await find_visible(page, selectors, timeout=3000) if selectors else None
    if locator:
        await locator.click(force=True)
        return True
    return False


async def _click_first_with_popup(page, selectors: list[str]) -> tuple[bool, Any]:
    locator = await find_visible(page, selectors, timeout=3000) if selectors else None
    if not locator:
        return False, page
    try:
        async with page.expect_popup(timeout=5000) as popup_info:
            await locator.click(force=True)
        popup = await popup_info.value
        try:
            await popup.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass
        return True, popup
    except PlaywrightTimeoutError:
        return True, page


async def _click_google_iframe_with_popup(page) -> tuple[bool, Any]:
    for frame in page.frames:
        if "accounts.google.com/gsi/button" not in frame.url:
            continue
        for selector in ['div[role="button"]', '#container', 'body']:
            try:
                locator = frame.locator(selector).first
                if await locator.count() == 0:
                    continue
                async with page.expect_popup(timeout=5000) as popup_info:
                    await locator.click(force=True)
                popup = await popup_info.value
                try:
                    await popup.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception:
                    pass
                return True, popup
            except PlaywrightTimeoutError:
                return True, page
            except Exception:
                continue
    return False, page


async def _click_menu_then_logout(page, config: dict) -> bool:
    if await _click_first(page, config.get("menu_selectors", [])):
        await asyncio.sleep(1)
    return await _click_first(page, config.get("logout_selectors", []))


async def sign_out_service(page, service: str, callback: Callback | None = None) -> AutomationResult:
    if service not in SERVICE_CONFIGS:
        return AutomationResult(success=False, status="unsupported", message=f"unsupported service: {service}")
    config = SERVICE_CONFIGS[service]
    await _emit(callback, "info", f"signing out {service}")

    if config.get("home_url"):
        await _goto(page, config["home_url"])
        await asyncio.sleep(3)
        if not await service_success(page, service):
            return AutomationResult(success=True, status="signed_out", message=f"{service} signed out")

    url = config.get("logout_url") or config.get("home_url") or config["start_url"]
    await _goto(page, url)
    await asyncio.sleep(3)
    await _click_first(page, config.get("logout_selectors", []))
    await asyncio.sleep(1)
    await _click_menu_then_logout(page, config)
    await asyncio.sleep(3)

    manual = await detect_manual_verification(page)
    if manual:
        return AutomationResult(success=False, manual_required=True, status=manual.status, message=manual.message, data={"url": page.url})
    if not await service_success(page, service):
        return AutomationResult(success=True, status="signed_out", message=f"{service} signed out")
    return AutomationResult(success=False, status="failed", message=f"{service} sign out not confirmed", data={"url": page.url})


async def _choose_google_account_if_present(page, email: str) -> None:
    try:
        account = page.get_by_text(re.compile(re.escape(email), re.I)).first
        if await account.count() > 0 and await account.is_visible():
            await account.click()
            await asyncio.sleep(2)
    except Exception:
        pass


async def _continue_oauth_if_present(page) -> None:
    for label in ["Continue", "Allow", "I agree"]:
        try:
            button = page.get_by_role("button", name=re.compile(label, re.I)).first
            if await button.count() > 0 and await button.is_visible():
                await button.click()
                await asyncio.sleep(2)
                return
        except Exception:
            pass


async def _complete_ebay_registration_if_present(page) -> bool:
    if "signup.ebay.com" not in page.url.lower():
        return False
    clicked = await _click_first(page, [
        'button:has-text("Create account")',
        'button:has-text("Create an account")',
        'input[value="Create account"]',
    ])
    if clicked:
        await asyncio.sleep(8)
    return clicked


async def login_service_with_google(page, service: str, account: dict, callback: Callback | None = None) -> AutomationResult:
    if service not in SERVICE_CONFIGS:
        return AutomationResult(success=False, status="unsupported", message=f"unsupported service: {service}")

    config = SERVICE_CONFIGS[service]
    await _emit(callback, "info", f"opening {service}")
    await _goto(page, config["start_url"])
    await asyncio.sleep(2)

    manual = await detect_manual_verification(page)
    if manual:
        return AutomationResult(success=False, manual_required=True, status=manual.status, message=manual.message, data={"url": page.url})

    if await service_success(page, service):
        return AutomationResult(success=True, status="success", message=f"{service} is already signed in")

    await _click_first(page, config.get("login_selectors", []))
    await asyncio.sleep(2)

    clicked_google, auth_page = await _click_first_with_popup(page, config.get("google_selectors", []))
    if clicked_google and auth_page == page and "accounts.google" not in page.url:
        iframe_clicked, iframe_auth_page = await _click_google_iframe_with_popup(page)
        if iframe_clicked:
            auth_page = iframe_auth_page
    if not clicked_google and service == "youtube":
        auth = await ensure_google_authenticated(page, account, callback)
        if not auth.success:
            return auth
        await _goto(page, config["start_url"])
        await asyncio.sleep(5)
        if await service_success(page, service):
            return AutomationResult(success=True, status="success", message=f"{service} login succeeded")
        await _click_first(page, config.get("login_selectors", []))
        await asyncio.sleep(5)
        await _choose_google_account_if_present(page, account.get("email") or "")
        await asyncio.sleep(5)
        if await service_success(page, service):
            return AutomationResult(success=True, status="success", message=f"{service} login succeeded")
        return AutomationResult(success=False, status="failed", message=f"{service} login not confirmed", data={"url": page.url})
    elif not clicked_google:
        return AutomationResult(success=False, status="unsupported", message=f"Google login button not found for {service}", data={"url": page.url})

    await asyncio.sleep(3)
    await _choose_google_account_if_present(auth_page, account.get("email") or "")
    auth = await ensure_google_authenticated(auth_page, account, callback, navigate=False)
    if not auth.success:
        return auth
    if not auth_page.is_closed():
        await _continue_oauth_if_present(auth_page)
    await asyncio.sleep(5)
    if service == "ebay" and await _complete_ebay_registration_if_present(page):
        manual = await detect_manual_verification(page)
        if manual:
            return AutomationResult(success=False, manual_required=True, status=manual.status, message=manual.message, data={"url": page.url})
        if await service_success(page, service):
            return AutomationResult(success=True, status="success", message="ebay login succeeded")
    if config.get("home_url"):
        await _goto(page, config["home_url"])
        await asyncio.sleep(5)

    manual = await detect_manual_verification(page)
    if manual:
        return AutomationResult(success=False, manual_required=True, status=manual.status, message=manual.message, data={"url": page.url})
    if service == "ebay" and await _complete_ebay_registration_if_present(page):
        manual = await detect_manual_verification(page)
        if manual:
            return AutomationResult(success=False, manual_required=True, status=manual.status, message=manual.message, data={"url": page.url})

    if await service_success(page, service):
        return AutomationResult(success=True, status="success", message=f"{service} login succeeded")
    return AutomationResult(success=False, status="failed", message=f"{service} login not confirmed", data={"url": page.url})
