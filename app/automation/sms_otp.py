import asyncio
import re

import httpx


async def fetch_otp(sms_url: str, timeout: float = 180.0, poll_interval: float = 5.0) -> str | None:
    """Poll sms_url until a 6-digit OTP appears in the plain-text response."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    async with httpx.AsyncClient(timeout=15) as client:
        while loop.time() < deadline:
            try:
                resp = await client.get(sms_url)
                text = resp.text.strip()
                match = re.search(r"\b(\d{6})\b", text)
                if match:
                    return match.group(1)
            except Exception:
                pass
            await asyncio.sleep(poll_interval)
    return None
