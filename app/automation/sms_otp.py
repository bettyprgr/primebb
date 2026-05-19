import asyncio
import re
from collections.abc import Awaitable, Callable

import httpx

Callback = Callable[[str, str], Awaitable[None] | None] | None


async def _emit(callback: Callback, level: str, message: str) -> None:
    if not callback:
        return
    result = callback(level, message)
    if hasattr(result, "__await__"):
        await result


async def fetch_otp(sms_url: str, timeout: float = 300.0, poll_interval: float = 5.0, callback: Callback = None) -> str | None:
    """Poll sms_url until a 6-digit OTP appears. Logs each poll result via callback."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    last_text = None
    async with httpx.AsyncClient(timeout=15) as client:
        while loop.time() < deadline:
            try:
                resp = await client.get(sms_url)
                text = resp.text.strip()
                match = re.search(r"\b(\d{6})\b", text)
                if match:
                    return match.group(1)
                # Only log when response changes to avoid spam
                if text != last_text:
                    await _emit(callback, "info", f"sms poll: {text[:120]}")
                    last_text = text
            except Exception as exc:
                await _emit(callback, "warning", f"sms poll error: {exc}")
            await asyncio.sleep(poll_interval)
    await _emit(callback, "warning", f"OTP timeout after {int(timeout)}s, last response: {last_text or 'none'}")
    return None
