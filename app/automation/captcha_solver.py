import asyncio
import base64
import re

from twocaptcha import TwoCaptcha

from app.config import get_settings


def _get_solver() -> TwoCaptcha | None:
    key = get_settings().twocaptcha_api_key
    if not key:
        return None
    return TwoCaptcha(key)


async def solve_image_captcha(image_url: str) -> str | None:
    solver = _get_solver()
    if not solver:
        return None
    try:
        import urllib.request
        loop = asyncio.get_running_loop()
        # Download image ourselves so 2captcha doesn't need to reach the URL
        with urllib.request.urlopen(image_url, timeout=15) as resp:
            image_bytes = resp.read()
        b64 = base64.b64encode(image_bytes).decode()
        result = await loop.run_in_executor(None, lambda: solver.normal(f"data:image/png;base64,{b64}"))
        return result.get("code") if isinstance(result, dict) else str(result)
    except Exception:
        return None


async def solve_amazon_waf(page_url: str, sitekey: str, iv: str, context: str) -> str | None:
    solver = _get_solver()
    if not solver:
        return None
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: solver.amazon_waf(sitekey=sitekey, iv=iv, context=context, url=page_url),
        )
        return result.get("code") if isinstance(result, dict) else str(result)
    except Exception:
        return None


async def solve_grid_captcha(image_bytes: bytes, instruction: str) -> list[int] | None:
    """Solve image grid captcha. Returns list of 1-indexed cell numbers to click."""
    solver = _get_solver()
    if not solver:
        return None
    try:
        b64 = base64.b64encode(image_bytes).decode()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: solver.grid(file=f"data:image/png;base64,{b64}", textinstructions=instruction),
        )
        code = result.get("code") if isinstance(result, dict) else str(result)
        # Response format: "click:1/3/5" or just "1/3/5"
        code = code.replace("click:", "").strip()
        return [int(x) for x in code.split("/") if x.strip().isdigit()]
    except Exception:
        return None


async def extract_waf_params(page) -> dict | None:
    try:
        content = await page.content()
        sitekey = re.search(r'"key"\s*:\s*"([^"]+)"', content)
        iv = re.search(r'"iv"\s*:\s*"([^"]+)"', content)
        context = re.search(r'"context"\s*:\s*"([^"]+)"', content)
        if sitekey and iv and context:
            return {
                "sitekey": sitekey.group(1),
                "iv": iv.group(1),
                "context": context.group(1),
            }
    except Exception:
        pass
    return None
