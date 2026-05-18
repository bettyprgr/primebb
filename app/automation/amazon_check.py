import asyncio


async def check_amazon_suspended(page) -> tuple[bool, str]:
    """Returns (is_suspended, message)."""
    try:
        await page.goto("https://www.amazon.com", timeout=60000, wait_until="domcontentloaded")
    except Exception:
        await asyncio.sleep(3)

    await asyncio.sleep(3)

    try:
        body = await page.locator("body").inner_text(timeout=5000)
        body_lower = body.lower()
    except Exception:
        return False, "could not read page"

    suspended_phrases = [
        "your account has been suspended",
        "account has been suspended",
        "account suspended",
        "your account has been locked",
        "account has been locked",
        "we have placed a temporary hold",
        "your account is on hold",
        "verify your identity",
        "account on hold",
    ]
    for phrase in suspended_phrases:
        if phrase in body_lower:
            return True, f"suspended: {phrase}"

    url = page.url.lower()
    if "ap/signin" in url or "ap/register" in url:
        return False, "not signed in"

    return False, "account active"
