import asyncio
import random
import re
import string
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from app.automation.detectors import detect_manual_verification, find_visible
from app.automation.sms_otp import fetch_otp
from app.schemas import AutomationResult

if TYPE_CHECKING:
    from app.core.bitbrowser import BitBrowserClient

Callback = Callable[[str, str], Awaitable[None] | None]

US_NAMES = [
    "Jacob", "Michael", "Joshua", "Matthew", "Ethan", "Andrew", "Daniel", "Christopher",
    "Anthony", "William", "Ryan", "Nicholas", "Tyler", "Zachary", "Brandon", "Justin",
    "David", "Nathan", "Samuel", "Noah", "Dylan", "Benjamin", "Logan", "Gabriel",
    "Austin", "Kevin", "Elijah", "James", "Alexander", "Caleb",
    "Emily", "Madison", "Emma", "Olivia", "Hannah", "Abigail", "Isabella", "Samantha",
    "Elizabeth", "Ashley", "Alexis", "Sarah", "Sophia", "Alyssa", "Grace", "Ava",
    "Taylor", "Brianna", "Lauren", "Chloe",
]


def random_name() -> str:
    return random.choice(US_NAMES)


def random_password(length: int = 14) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = "".join(random.choices(chars, k=length))
        if (any(c.isupper() for c in pwd) and any(c.islower() for c in pwd)
                and any(c.isdigit() for c in pwd) and any(c in "!@#$%^&*" for c in pwd)):
            return pwd


async def _emit(callback: Callback | None, level: str, message: str) -> None:
    if not callback:
        return
    result = callback(level, message)
    if hasattr(result, "__await__"):
        await result


async def _autopaste_fill(page, element, text: str, bitbrowser_id: str, client: "BitBrowserClient") -> None:
    """Set clipboard via JS execCommand, focus the input, then call BitBrowser autopaste API."""
    # Set clipboard using a hidden textarea + execCommand — works without clipboard permissions
    await page.evaluate("""(t) => {
        const el = document.createElement('textarea');
        el.value = t;
        el.style.cssText = 'position:fixed;opacity:0;top:0;left:0';
        document.body.appendChild(el);
        el.focus();
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
    }""", text)
    await asyncio.sleep(0.2)
    # Focus the target input field
    await element.click()
    await asyncio.sleep(0.3)
    # Call BitBrowser autopaste — runs in thread pool to avoid blocking event loop
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, client.autopaste, bitbrowser_id, page.url)
    await asyncio.sleep(0.5)


async def _click_text(page, texts: list[str]) -> bool:
    for text in texts:
        try:
            btn = page.get_by_role("button", name=re.compile(re.escape(text), re.I)).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                return True
        except Exception:
            pass
        try:
            loc = page.get_by_text(re.compile(re.escape(text), re.I)).first
            if await loc.count() > 0 and await loc.is_visible():
                await loc.click()
                return True
        except Exception:
            pass
    return False


async def _detect_amazon_captcha(page) -> bool:
    url = page.url.lower()
    if "validatecaptcha" in url or "errors/validatecaptcha" in url:
        return True
    try:
        body = await page.locator("body").inner_text(timeout=3000)
        body_lower = body.lower()
        # /ap/cvf/request is shared between CVF grid captcha and OTP verification page
        if "/ap/cvf/request" in url:
            otp_page = any(p in body_lower for p in ["verify mobile number", "enter security code", "enter the security code"])
            if otp_page:
                return False
            return any(p in body_lower for p in ["solve this puzzle", "choose all", "type the characters", "enter the characters"])
        captcha_input = await find_visible(page, [
            'input#captchacharacters',
            'input[name="captchacharacters"]',
            'img[src*="captcha"]',
        ], timeout=1000)
        if captcha_input:
            return True
        if any(p in body_lower for p in ["type the characters you see", "enter the characters", "solve this puzzle"]):
            return True
    except Exception:
        pass
    return False


async def _wait_for_captcha_solved(page, callback: Callback | None = None, timeout: float = 300.0) -> bool:
    """Wait for user to manually solve captcha. Returns True when captcha is gone, False on timeout."""
    await _emit(callback, "warning", f"captcha detected at {page.url} — please solve it manually in the browser")
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        await asyncio.sleep(3)
        try:
            current_url = page.url
            still_captcha = await _detect_amazon_captcha(page)
            body_snippet = (await page.locator("body").inner_text(timeout=3000))[:200].replace("\n", " ").strip()
            await _emit(callback, "info", f"captcha poll: url={current_url} still={still_captcha} body={body_snippet}")
            if not still_captcha:
                await _emit(callback, "info", "captcha cleared, continuing...")
                return True
        except Exception as exc:
            await _emit(callback, "info", f"captcha poll error: {exc}")
    await _emit(callback, "warning", "timed out waiting for captcha to be solved")
    return False


async def _do_register(page, phone: str, sms_url: str, name: str, password: str, callback: Callback | None, wait_on_captcha: bool, bitbrowser_id: str = "", client: "BitBrowserClient | None" = None) -> tuple[AutomationResult, bool]:
    """
    Run one registration attempt on the given page.
    Returns (result, hit_captcha).
    hit_captcha=True means captcha was encountered and we should retry (if wait_on_captcha=False).
    """
    await _emit(callback, "info", f"opening amazon registration (phone={phone})")

    # Step 1: Search Google for "amazon deal"
    for attempt in range(3):
        try:
            await page.goto("https://www.google.com/search?q=amazon+deal", timeout=60000, wait_until="domcontentloaded")
            if "chrome-error" not in page.url:
                break
        except Exception:
            pass
        await asyncio.sleep(3)
    await asyncio.sleep(3)

    if "chrome-error" in page.url:
        await _emit(callback, "warning", "browser crashed on Google, navigating directly to amazon")
        try:
            await page.goto("https://www.amazon.com", timeout=60000, wait_until="domcontentloaded")
        except Exception:
            pass
        await asyncio.sleep(4)

    # Step 2: Click amazon.com result
    amazon_clicked = False
    if "amazon.com" not in page.url:
        for selector in [
            'a[href*="//www.amazon.com/"]',
            'a[href^="https://www.amazon.com"]',
        ]:
            try:
                locs = page.locator(selector)
                count = await locs.count()
                for i in range(count):
                    loc = locs.nth(i)
                    href = await loc.get_attribute("href") or ""
                    if "google" in href or "gstatic" in href or "googleapis" in href:
                        continue
                    if await loc.is_visible():
                        await loc.click()
                        amazon_clicked = True
                        break
                if amazon_clicked:
                    break
            except Exception:
                pass
        if not amazon_clicked:
            await _emit(callback, "warning", "amazon.com link not found in Google, navigating directly")
            try:
                await page.goto("https://www.amazon.com", timeout=30000, wait_until="domcontentloaded")
            except Exception:
                pass
        await asyncio.sleep(4)
    await _emit(callback, "info", f"on amazon: {page.url}")

    # Ensure we're on amazon.com before clicking Sign in
    if "amazon.com" not in page.url:
        await _emit(callback, "warning", f"not on amazon.com after navigation, going directly. url={page.url}")
        try:
            await page.goto("https://www.amazon.com", timeout=30000, wait_until="domcontentloaded")
        except Exception:
            pass
        await asyncio.sleep(4)

    # Step 3: Find and click Sign in button — only on amazon.com
    sign_clicked = False
    if "amazon.com" in page.url:
        for selector in [
            '#nav-link-accountList',
            '#nav-link-accountList-nav-line-1',
            'a[href*="amazon.com"][href*="signin"]',
            'a:has-text("Sign in")',
        ]:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible():
                    href = await loc.get_attribute("href") or ""
                    if "google" in href or "accounts.google" in href:
                        continue
                    await loc.click()
                    sign_clicked = True
                    break
            except Exception:
                pass
    if not sign_clicked:
        await _emit(callback, "warning", "Sign button not found on amazon.com")
    await asyncio.sleep(4)
    await _emit(callback, "info", f"after sign click: {page.url}")

    # Step 4: Fill phone number and click Continue
    phone_input = await find_visible(page, [
        'input[name="email"]',
        'input[id="ap_email"]',
        'input[type="email"]',
        'input[type="tel"]',
    ], timeout=8000)
    if phone_input:
        if client and bitbrowser_id:
            await _autopaste_fill(page, phone_input, phone, bitbrowser_id, client)
        else:
            await phone_input.fill(phone)
        await _emit(callback, "info", f"filled phone: {phone}")
        await asyncio.sleep(2)
        await _click_text(page, ["Continue"])
        await asyncio.sleep(4)
    else:
        await _emit(callback, "warning", f"phone input not found, url={page.url}")

    await _emit(callback, "info", f"after continue: {page.url}")

    # Step 5: Click "Proceed to create an account" / "Create your Amazon account"
    # Loop handles /ax/claim redirect — Amazon sometimes bounces back to phone input
    for _ax_attempt in range(4):
        await asyncio.sleep(2)
        create_clicked = await _click_text(page, [
            "Proceed to create an account",
            "Create your Amazon account",
            "Create account",
            "New to Amazon",
        ])
        if create_clicked:
            await asyncio.sleep(4)
        await _emit(callback, "info", f"after create click: {page.url}")

        # If Amazon redirected back to a phone-input page, fill phone again and retry
        cur_url = page.url
        if "/ax/claim" in cur_url or "/ap/signin" in cur_url:
            phone_again = await find_visible(page, [
                'input[name="email"]', 'input[id="ap_email"]',
                'input[type="email"]', 'input[type="tel"]',
            ], timeout=3000)
            if phone_again:
                if client and bitbrowser_id:
                    await _autopaste_fill(page, phone_again, phone, bitbrowser_id, client)
                else:
                    await phone_again.fill(phone)
                await _emit(callback, "info", f"re-filled phone on {cur_url}")
                await asyncio.sleep(1)
                await _click_text(page, ["Continue"])
                await asyncio.sleep(4)
                continue
        break

    # Detect existing account: Amazon shows password page instead of registration
    try:
        body_check = (await page.locator("body").inner_text(timeout=3000)).lower()
        if "forgot password" in body_check and "password" in body_check and "create" not in body_check:
            await _emit(callback, "warning", f"phone {phone} already has an Amazon account (password page shown)")
            return AutomationResult(success=False, status="account_exists", message="phone already has an Amazon account", data={"url": page.url}), False
    except Exception:
        pass

    # Captcha check 1: landing page
    if await _detect_amazon_captcha(page):
        await _emit(callback, "info", "captcha detected on landing page")
        if not wait_on_captcha:
            return AutomationResult(success=False, status="captcha", message="captcha on landing page"), True
        if not await _wait_for_captcha_solved(page, callback):
            return AutomationResult(success=False, manual_required=True, status="manual_captcha", message="captcha timeout", data={"url": page.url}), True

    manual = await detect_manual_verification(page)
    if manual:
        return AutomationResult(success=False, manual_required=True, status=manual.status, message=manual.message, data={"url": page.url}), False

    await _emit(callback, "info", f"current url: {page.url}")

    # Captcha check 2
    if await _detect_amazon_captcha(page):
        if not wait_on_captcha:
            return AutomationResult(success=False, status="captcha", message="captcha before name form"), True
        if not await _wait_for_captcha_solved(page, callback):
            return AutomationResult(success=False, manual_required=True, status="manual_captcha", message="captcha timeout", data={"url": page.url}), True

    # Fill name
    name_input = await find_visible(page, [
        'input[name="customerName"]',
        'input[id="ap_customer_name"]',
        'input[placeholder*="name" i]',
    ], timeout=8000)
    if name_input:
        if client and bitbrowser_id:
            await _autopaste_fill(page, name_input, name, bitbrowser_id, client)
        else:
            await name_input.fill(name)
        await _emit(callback, "info", f"filled name: {name}")
        await asyncio.sleep(2)
    else:
        body_snippet = (await page.locator("body").inner_text(timeout=3000))[:300]
        await _emit(callback, "warning", f"name input not found. url={page.url} body={body_snippet}")
        return AutomationResult(success=False, status="failed", message="name input not found", data={"url": page.url}), False

    # Fill password
    pwd_input = await find_visible(page, ['input[name="password"]', 'input[id="ap_password"]', 'input[type="password"]'], timeout=3000)
    if pwd_input:
        if client and bitbrowser_id:
            await _autopaste_fill(page, pwd_input, password, bitbrowser_id, client)
        else:
            await pwd_input.fill(password)
        await asyncio.sleep(1)

    pwd_check = await find_visible(page, ['input[name="passwordCheck"]', 'input[id="ap_password_check"]'], timeout=2000)
    if pwd_check:
        if client and bitbrowser_id:
            await _autopaste_fill(page, pwd_check, password, bitbrowser_id, client)
        else:
            await pwd_check.fill(password)
        await asyncio.sleep(1)

    await _emit(callback, "info", "submitting registration form")
    await _click_text(page, ["Continue", "Create your Amazon account", "Verify mobile number"])
    await asyncio.sleep(4)

    # Captcha check 3: after form submit
    if await _detect_amazon_captcha(page):
        await _emit(callback, "info", "captcha detected after form submit")
        if not wait_on_captcha:
            return AutomationResult(success=False, status="captcha", message="captcha after form submit"), True
        if not await _wait_for_captcha_solved(page, callback):
            return AutomationResult(success=False, manual_required=True, status="manual_captcha", message="captcha timeout", data={"url": page.url}), True

    manual = await detect_manual_verification(page)
    if manual:
        return AutomationResult(success=False, manual_required=True, status=manual.status, message=manual.message, data={"url": page.url}), False

    # Check if OTP page
    otp_input = await find_visible(page, [
        'input[name="cvf_captcha_input"]',
        'input[id="cvf-input-code"]',
        'input[autocomplete="one-time-code"]',
        'input[inputmode="numeric"]',
        'input[name="code"]',
    ], timeout=5000)

    if not otp_input:
        body = await page.locator("body").inner_text(timeout=5000)
        if any(t in body.lower() for t in ["your account", "hello,", "sign out", "account & lists"]):
            return AutomationResult(success=True, status="created", message="amazon account created"), False
        return AutomationResult(success=False, status="failed", message="OTP input not found", data={"url": page.url}), False

    await _emit(callback, "info", "waiting for OTP from SMS service...")
    otp = await fetch_otp(sms_url, timeout=180.0)
    if not otp:
        return AutomationResult(success=False, status="failed", message="OTP not received within 3 minutes"), False

    await _emit(callback, "info", f"received OTP: {otp}")
    if client and bitbrowser_id:
        await _autopaste_fill(page, otp_input, otp, bitbrowser_id, client)
    else:
        await otp_input.fill(otp)
    await asyncio.sleep(1)
    await _click_text(page, ["Create your Amazon account", "Verify", "Continue", "Submit"])
    await asyncio.sleep(8)

    # Captcha check 4: after OTP submit
    if await _detect_amazon_captcha(page):
        await _emit(callback, "info", "captcha detected after OTP submit")
        if not wait_on_captcha:
            return AutomationResult(success=False, status="captcha", message="captcha after OTP submit"), True
        if not await _wait_for_captcha_solved(page, callback):
            return AutomationResult(success=False, manual_required=True, status="manual_captcha", message="captcha timeout", data={"url": page.url}), True

    manual = await detect_manual_verification(page)
    if manual:
        return AutomationResult(success=False, manual_required=True, status=manual.status, message=manual.message, data={"url": page.url}), False

    body = await page.locator("body").inner_text(timeout=5000)
    url = page.url.lower()
    body_lower = body.lower()
    body_snippet = body[:400].replace("\n", " ").strip()
    await _emit(callback, "info", f"final check: url={page.url} body={body_snippet}")

    # new_account=1 in URL is a reliable Amazon signal that registration succeeded
    if "new_account=1" in url:
        return AutomationResult(success=True, status="created", message="amazon account created"), False

    success_body = ["your account", "hello,", "account & lists", "start shopping",
                    "welcome to amazon", "protect your account", "add a payment method",
                    "keep shopping", "sign out"]
    if any(t in body_lower for t in success_body):
        return AutomationResult(success=True, status="created", message="amazon account created"), False

    # OTP was accepted if we're no longer on the OTP input page.
    # Amazon sometimes redirects back to /ap/register after account creation.
    otp_still = await find_visible(page, [
        'input[name="cvf_captcha_input"]', 'input[id="cvf-input-code"]',
        'input[autocomplete="one-time-code"]', 'input[inputmode="numeric"]',
        'input[name="code"]',
    ], timeout=1000)
    if not otp_still:
        # OTP page is gone — account was created
        return AutomationResult(success=True, status="created", message="amazon account created"), False

    auth_paths = ["/ap/", "/ax/", "signin", "register", "validatecaptcha"]
    if "amazon.com" in url and not any(p in url for p in auth_paths):
        return AutomationResult(success=True, status="created", message="amazon account created"), False

    return AutomationResult(success=False, status="failed", message="registration not confirmed", data={"url": page.url}), False


async def register_amazon(context, phone: str, sms_url: str, callback: Callback | None = None, preset_name: str | None = None, bitbrowser_id: str = "", client: "BitBrowserClient | None" = None) -> tuple[AutomationResult, str, str]:
    """
    Returns (result, name, password).
    Retries up to 2 times on captcha by closing and reopening a fresh tab.
    On the 3rd attempt, waits for the user to solve the captcha manually.
    """
    name = preset_name.strip() if preset_name and preset_name.strip() else random_name()
    password = random_password()

    max_auto_retries = 2  # attempts 1 and 2 auto-retry; attempt 3 waits for user

    for attempt in range(1, max_auto_retries + 2):
        wait_on_captcha = attempt > max_auto_retries
        if attempt > 1:
            await _emit(callback, "info", f"retry attempt {attempt} (captcha on previous attempt, opening fresh tab)")

        page = await context.new_page()
        try:
            result, hit_captcha = await _do_register(page, phone, sms_url, name, password, callback, wait_on_captcha, bitbrowser_id=bitbrowser_id, client=client)
        except Exception as exc:
            await _emit(callback, "error", f"attempt {attempt} error: {exc}")
            result, hit_captcha = AutomationResult(success=False, status="failed", message=str(exc)), False
        finally:
            try:
                await page.close()
            except Exception:
                pass

        if not hit_captcha or wait_on_captcha:
            return result, name, password

        await _emit(callback, "info", f"captcha hit on attempt {attempt}, will retry with fresh tab")

    return result, name, password
