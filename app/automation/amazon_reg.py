import asyncio
import random
import re
import string
from collections.abc import Awaitable, Callable

from app.automation.detectors import detect_manual_verification, find_visible
from app.automation.sms_otp import fetch_otp
from app.schemas import AutomationResult

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
    first = random.choice(US_NAMES)
    last_initials = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
                     "Davis", "Wilson", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris"]
    return f"{first} {random.choice(last_initials)}"


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
    if "validatecaptcha" in url or "errors/validatecaptcha" in url or "/ap/cvf/" in url:
        return True
    try:
        captcha_input = await find_visible(page, [
            'input#captchacharacters',
            'input[name="captchacharacters"]',
            'img[src*="captcha"]',
        ], timeout=1000)
        if captcha_input:
            return True
        body = await page.locator("body").inner_text(timeout=3000)
        if any(p in body.lower() for p in ["type the characters you see", "enter the characters", "solve this puzzle"]):
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
            if not await _detect_amazon_captcha(page):
                await _emit(callback, "info", "captcha cleared, continuing...")
                return True
        except Exception:
            pass
    await _emit(callback, "warning", "timed out waiting for captcha to be solved")
    return False


async def register_amazon(page, phone: str, sms_url: str, callback: Callback | None = None) -> tuple[AutomationResult, str, str]:
    """Returns (result, name, password)."""
    name = random_name()
    password = random_password()

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

    # Step 3: Find and click Sign in button
    sign_clicked = False
    for selector in [
        '#nav-link-accountList',
        'a[href*="signin"]',
        'a:has-text("Sign in")',
        'a:has-text("Sign")',
        '#nav-link-accountList-nav-line-1',
    ]:
        try:
            loc = page.locator(selector).first
            if await loc.count() > 0 and await loc.is_visible():
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
        await phone_input.fill(phone)
        await _emit(callback, "info", f"filled phone: {phone}")
        await asyncio.sleep(2)
        await _click_text(page, ["Continue"])
        await asyncio.sleep(4)
    else:
        await _emit(callback, "warning", f"phone input not found, url={page.url}")

    await _emit(callback, "info", f"after continue: {page.url}")

    # Step 5: Click "Proceed to create an account" / "Create your Amazon account"
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

    if await _detect_amazon_captcha(page):
        await _emit(callback, "info", "captcha detected on landing page")
        if not await _wait_for_captcha_solved(page, callback):
            return AutomationResult(success=False, manual_required=True, status="manual_captcha", message="captcha timeout", data={"url": page.url}), name, password

    manual = await detect_manual_verification(page)
    if manual:
        return AutomationResult(success=False, manual_required=True, status=manual.status, message=manual.message, data={"url": page.url}), name, password

    await _emit(callback, "info", f"current url: {page.url}")

    if await _detect_amazon_captcha(page):
        if not await _wait_for_captcha_solved(page, callback):
            return AutomationResult(success=False, manual_required=True, status="manual_captcha", message="captcha timeout", data={"url": page.url}), name, password

    # Fill name
    name_input = await find_visible(page, [
        'input[name="customerName"]',
        'input[id="ap_customer_name"]',
        'input[placeholder*="name" i]',
    ], timeout=8000)
    if name_input:
        await name_input.fill(name)
        await _emit(callback, "info", f"filled name: {name}")
        await asyncio.sleep(2)
    else:
        body_snippet = (await page.locator("body").inner_text(timeout=3000))[:300]
        await _emit(callback, "warning", f"name input not found. url={page.url} body={body_snippet}")
        return AutomationResult(success=False, status="failed", message="name input not found", data={"url": page.url}), name, password

    # Fill password
    pwd_input = await find_visible(page, ['input[name="password"]', 'input[id="ap_password"]', 'input[type="password"]'], timeout=3000)
    if pwd_input:
        await pwd_input.fill(password)
        await asyncio.sleep(1)

    pwd_check = await find_visible(page, ['input[name="passwordCheck"]', 'input[id="ap_password_check"]'], timeout=2000)
    if pwd_check:
        await pwd_check.fill(password)
        await asyncio.sleep(1)

    await _emit(callback, "info", "submitting registration form")
    await _click_text(page, ["Continue", "Create your Amazon account", "Verify mobile number"])
    await asyncio.sleep(4)

    if await _detect_amazon_captcha(page):
        await _emit(callback, "info", "captcha detected after form submit")
        if not await _wait_for_captcha_solved(page, callback):
            return AutomationResult(success=False, manual_required=True, status="manual_captcha", message="captcha timeout", data={"url": page.url}), name, password

    manual = await detect_manual_verification(page)
    if manual:
        return AutomationResult(success=False, manual_required=True, status=manual.status, message=manual.message, data={"url": page.url}), name, password

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
            return AutomationResult(success=True, status="created", message="amazon account created"), name, password
        return AutomationResult(success=False, status="failed", message="OTP input not found", data={"url": page.url}), name, password

    await _emit(callback, "info", "waiting for OTP from SMS service...")
    otp = await fetch_otp(sms_url, timeout=180.0)
    if not otp:
        return AutomationResult(success=False, status="failed", message="OTP not received within 3 minutes"), name, password

    await _emit(callback, "info", f"received OTP: {otp}")
    await otp_input.fill(otp)
    await asyncio.sleep(1)
    await _click_text(page, ["Create your Amazon account", "Verify", "Continue", "Submit"])
    await asyncio.sleep(5)

    if await _detect_amazon_captcha(page):
        await _emit(callback, "info", "captcha detected after OTP submit")
        if not await _wait_for_captcha_solved(page, callback):
            return AutomationResult(success=False, manual_required=True, status="manual_captcha", message="captcha timeout", data={"url": page.url}), name, password

    manual = await detect_manual_verification(page)
    if manual:
        return AutomationResult(success=False, manual_required=True, status=manual.status, message=manual.message, data={"url": page.url}), name, password

    body = await page.locator("body").inner_text(timeout=5000)
    url = page.url.lower()
    if any(t in body.lower() for t in ["your account", "hello,", "account & lists"]) or ("amazon.com" in url and "register" not in url and "ap/" not in url):
        return AutomationResult(success=True, status="created", message="amazon account created"), name, password

    return AutomationResult(success=False, status="failed", message="registration not confirmed", data={"url": page.url}), name, password
