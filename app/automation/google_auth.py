import asyncio
import re
import urllib.parse
from collections.abc import Awaitable, Callable

from app.automation.detectors import detect_google_logged_in, detect_invalid_credentials, detect_manual_verification, find_visible
from app.automation.totp import current_totp
from app.schemas import AutomationResult

Callback = Callable[[str, str], Awaitable[None] | None]


async def _emit(callback: Callback | None, level: str, message: str) -> None:
    if not callback:
        return
    result = callback(level, message)
    if hasattr(result, "__await__"):
        await result


async def _click_text(page, words: list[str]) -> bool:
    for word in words:
        try:
            button = page.get_by_role("button", name=re.compile(re.escape(word), re.I)).first
            if await button.count() > 0 and await button.is_visible():
                await button.click()
                return True
        except Exception:
            pass
        try:
            locator = page.get_by_text(re.compile(re.escape(word), re.I)).first
            if await locator.count() > 0 and await locator.is_visible():
                await locator.click()
                return True
        except Exception:
            pass
    return False


async def _choose_account_or_use_another(page, email: str | None) -> None:
    if email:
        try:
            account = page.get_by_text(re.compile(re.escape(email), re.I)).first
            if await account.count() > 0 and await account.is_visible():
                await account.click()
                await asyncio.sleep(2)
                return
        except Exception:
            pass
        account_selector = await find_visible(page, [f'[data-identifier="{email}"]', f'[data-email="{email}"]'])
        if account_selector:
            await account_selector.click()
            await asyncio.sleep(2)
            return
    first_account = await find_visible(page, ['[data-identifier]', 'div[role="link"][data-identifier]'])
    if first_account:
        await first_account.click()
        await asyncio.sleep(2)
        return
    await _click_text(page, ["Use another account", "Add account", "Sign in"])
    await asyncio.sleep(1)


async def _handle_recovery_email(page, recovery_email: str | None, callback: Callback | None) -> bool:
    if not recovery_email:
        return False
    await _click_text(page, ["Try another way"])
    await asyncio.sleep(1)
    clicked = await _click_text(page, ["Confirm your recovery email", "Confirm your backup email", "recovery email"])
    if not clicked:
        return False
    await asyncio.sleep(1)
    email_input = await find_visible(page, ['input[type="email"]', 'input[type="text"]'])
    if email_input:
        await email_input.fill(recovery_email)
    await _click_text(page, ["Next", "Continue", "Confirm"])
    await _emit(callback, "info", "submitted recovery email challenge")
    await asyncio.sleep(2)
    return True


async def _handle_totp(page, secret: str | None, callback: Callback | None) -> AutomationResult | None:
    code_input = await find_visible(page, [
        'input[name="totpPin"]',
        'input[id="totpPin"]',
        'input[type="tel"]',
        'input[inputmode="numeric"]',
        'input[autocomplete="one-time-code"]',
        'input[aria-label*="code" i]',
    ])
    if not code_input:
        return None
    if not secret:
        return AutomationResult(success=False, status="missing_totp_secret", message="TOTP prompt found but account has no secret")
    code = current_totp(secret)
    await code_input.fill(code)
    await _click_text(page, ["Next", "Verify", "Continue"])
    await _emit(callback, "info", "submitted TOTP challenge")
    await asyncio.sleep(6)
    return None


async def _click_oauth_allow(page) -> bool:
    """Click Allow/Continue/I agree on Google OAuth consent screen using multiple strategies."""
    # Try button by text
    for label in ["Allow", "Continue", "I agree", "Yes"]:
        try:
            btn = page.get_by_role("button", name=re.compile(re.escape(label), re.I)).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                return True
        except Exception:
            pass
    # Try by selector — Google consent uses specific data-action or jsname attributes
    for selector in [
        'button[data-action="allow"]',
        'button[jsname="LgbsSe"]',
        'button[jsname="tHlp8d"]',
        '#submit_approve_access',
        'input[value="Allow"]',
        'button:has-text("Allow")',
        'div[role="button"]:has-text("Allow")',
    ]:
        try:
            locator = page.locator(selector).first
            if await locator.count() > 0 and await locator.is_visible():
                await locator.click(force=True)
                return True
        except Exception:
            pass
    return False


async def _wait_for_popup_redirect(page, timeout: float = 15.0) -> bool:
    """Wait until popup navigates away from accounts.google.com or closes."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if page.is_closed():
                return True
            if "accounts.google" not in page.url:
                return True
        except Exception:
            return True
        await asyncio.sleep(0.5)
    return False


async def ensure_google_authenticated(page, account: dict, callback: Callback | None = None, navigate: bool = True) -> AutomationResult:
    await _emit(callback, "info", "checking Google session")
    if navigate:
        try:
            await page.goto("https://accounts.google.com", timeout=60000, wait_until="domcontentloaded")
        except Exception:
            await asyncio.sleep(2)

    if await detect_google_logged_in(page):
        return AutomationResult(success=True, status="google_authenticated", message="Google session is already authenticated")

    totp_result = await _handle_totp(page, account.get("totp_secret"), callback)
    if totp_result:
        return totp_result

    manual = await detect_manual_verification(page)
    if manual:
        return AutomationResult(success=False, manual_required=True, status=manual.status, message=manual.message, data={"url": page.url})

    await _choose_account_or_use_another(page, account.get("email"))

    email_input = await find_visible(page, ['input[type="email"]', 'input[name="identifier"]'], timeout=3000)
    if email_input:
        await email_input.fill(account.get("email") or "")
        await _click_text(page, ["Next"])
        await asyncio.sleep(2)

    if await detect_invalid_credentials(page):
        return AutomationResult(success=False, status="invalid_credentials", message="Google rejected the email or password")

    password_input = await find_visible(page, ['input[type="password"]', 'input[name="Passwd"]'], timeout=5000)
    if password_input:
        await password_input.fill(account.get("password") or "")
        await _click_text(page, ["Next"])
        await asyncio.sleep(3)

    for i in range(10):
        try:
            current_url = page.url
        except Exception:
            return AutomationResult(success=True, status="google_authenticated", message="Google OAuth authentication completed")

        await _emit(callback, "info", f"auth loop {i+1}/10 url={current_url[:80]}")

        try:
            if not navigate and page.is_closed():
                return AutomationResult(success=True, status="google_authenticated", message="Google OAuth authentication completed")
            if not navigate and "accounts.google" not in current_url:
                return AutomationResult(success=True, status="google_authenticated", message="Google OAuth authentication completed")
        except Exception:
            return AutomationResult(success=True, status="google_authenticated", message="Google OAuth authentication completed")

        if await detect_invalid_credentials(page):
            return AutomationResult(success=False, status="invalid_credentials", message="Google rejected the email or password")

        # If stuck on account chooser, try clicking the account or fall back to email input
        if "accountchooser" in current_url or "signinchooser" in current_url:
            if i < 3:
                await _choose_account_or_use_another(page, account.get("email"))
            else:
                # Fallback: click "Use another account" to reach email input
                await _click_text(page, ["Use another account", "Add account", "Sign in with a different account"])
                await asyncio.sleep(2)
                email_input = await find_visible(page, ['input[type="email"]', 'input[name="identifier"]'], timeout=4000)
                if email_input:
                    await email_input.fill(account.get("email") or "")
                    await _click_text(page, ["Next"])
                    await asyncio.sleep(3)
            await asyncio.sleep(2)
            continue

        totp_result = await _handle_totp(page, account.get("totp_secret"), callback)
        if totp_result:
            return totp_result

        manual = await detect_manual_verification(page)
        if manual:
            return AutomationResult(success=False, manual_required=True, status=manual.status, message=manual.message, data={"url": page.url})

        await _handle_recovery_email(page, account.get("recovery_email"), callback)

        password_input = await find_visible(page, ['input[type="password"]', 'input[name="Passwd"]'])
        if password_input:
            await password_input.fill(account.get("password") or "")
            await _click_text(page, ["Next"])
            await asyncio.sleep(3)

        if not navigate:
            clicked = await _click_oauth_allow(page)
            if clicked:
                await _emit(callback, "info", f"clicked oauth consent, waiting for redirect (url={current_url[:80]})")
                redirected = await _wait_for_popup_redirect(page, timeout=20.0)
                if redirected:
                    return AutomationResult(success=True, status="google_authenticated", message="Google OAuth authentication completed")

        await _click_text(page, ["Not now", "Skip", "Cancel"])

        if await detect_google_logged_in(page):
            return AutomationResult(success=True, status="google_authenticated", message="Google authentication succeeded")

        await asyncio.sleep(2)

    try:
        if not navigate and page.is_closed():
            return AutomationResult(success=True, status="google_authenticated", message="Google OAuth authentication completed")
        if not navigate and "accounts.google" not in page.url:
            return AutomationResult(success=True, status="google_authenticated", message="Google OAuth authentication completed")
    except Exception:
        return AutomationResult(success=True, status="google_authenticated", message="Google OAuth authentication completed")

    if await detect_google_logged_in(page):
        return AutomationResult(success=True, status="google_authenticated", message="Google authentication succeeded")
    return AutomationResult(success=False, status="google_auth_failed", message="Google authentication did not complete", data={"url": page.url})