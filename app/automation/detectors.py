import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ManualChallenge:
    status: str
    message: str


async def body_text(page) -> str:
    try:
        return await page.locator("body").inner_text(timeout=5000)
    except Exception:
        return ""


async def detect_manual_verification(page) -> ManualChallenge | None:
    text = (await body_text(page)).lower()
    checks = [
        ("captcha", ["captcha", "recaptcha", "confirm you're not a robot", "confirm you’re not a robot", "i'm not a robot"]),
        ("phone", ["verify your phone", "verify with your phone", "enter the code sent", "code sent to your phone", "phone verification"]),
        ("suspicious", ["suspicious", "unusual activity", "couldn't verify", "couldn’t verify", "verify it’s you", "verify it's you"]),
        ("locked", ["account disabled", "account has been disabled", "account locked", "couldn't sign you in"]),
    ]
    for status, patterns in checks:
        if any(pattern in text for pattern in patterns):
            return ManualChallenge(f"manual_{status}", f"manual action required: {status}")
    try:
        recaptcha = page.locator('iframe[src*="recaptcha"], iframe[title*="recaptcha"], [title*="reCAPTCHA"]')
        if await recaptcha.count() > 0 and await recaptcha.first.is_visible():
            return ManualChallenge("manual_captcha", "manual action required: captcha")
    except Exception:
        pass
    return None


async def detect_invalid_credentials(page) -> bool:
    text = (await body_text(page)).lower()
    return any(
        phrase in text
        for phrase in [
            "wrong password",
            "couldn't find your google account",
            "couldn’t find your google account",
            "enter a valid email",
            "password was changed",
        ]
    )


async def find_visible(page, selectors: list[str], timeout: int = 0):
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if timeout:
                await locator.wait_for(state="visible", timeout=timeout)
            if await locator.count() > 0 and await locator.is_visible():
                return locator
        except Exception:
            continue
    return None


async def detect_google_logged_in(page) -> bool:
    text = (await body_text(page)).lower()
    if "welcome" in text and "manage your google account" in text:
        return True
    if "myaccount.google.com" in page.url and "signin" not in page.url:
        return True
    avatar = await find_visible(page, ['a[href*="SignOutOptions"], img[alt*="profile" i], [aria-label*="Google Account" i]'])
    return avatar is not None


async def service_success(page, service: str) -> bool:
    text = (await body_text(page)).lower()
    url = page.url.lower()
    if service == "youtube":
        return "youtube.com" in url and await find_visible(page, ['button#avatar-btn', '#avatar-btn', 'a[href*="SignOutOptions"]']) is not None
    if service == "reddit":
        return "reddit.com" in url and (
            any(token in text for token in ["create post", "advertise", "chat", "popular", "all"]) or
            await find_visible(page, ['[aria-label*="profile" i]', 'a[href*="/user/"]', 'button[id*="USER_DROPDOWN"]', '[data-testid*="user" i]']) is not None
        )
    if service == "quora":
        return "quora.com" in url and any(token in text for token in ["add question", "answer", "following", "spaces", "notifications"])
    if service == "x":
        if "x.com" not in url and "twitter.com" not in url:
            return False
        if "/login" in url or "/i/flow" in url:
            return False
        logged_in = await find_visible(page, [
            '[data-testid="SideNav_AccountSwitcher_Button"]',
            '[data-testid="AppTabBar_Home_Link"]',
            '[aria-label="Home"][role="link"]',
            '[data-testid="primaryColumn"]',
        ])
        return logged_in is not None
    if service == "ebay":
        return "ebay." in url and any(token in text for token in ["my ebay", "watchlist", "summary", "sign out", "hi,"])
    return False


def text_regex(words: list[str]) -> re.Pattern:
    return re.compile("|".join(re.escape(word) for word in words), re.I)
