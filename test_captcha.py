"""
Test 2captcha integration for Amazon captcha types.
Run: python test_captcha.py
"""
import asyncio
import struct
import zlib
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from twocaptcha import TwoCaptcha
from app.config import get_settings
from app.automation.captcha_solver import solve_image_captcha, solve_grid_captcha, solve_amazon_waf


def _make_png(width: int, height: int, pattern: str = "noise") -> bytes:
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            if pattern == "grid":
                cell_x = x // max(1, width // 3)
                cell_y = y // max(1, height // 3)
                shade = min(255, 80 + (cell_x + cell_y * 3) * 20)
                shade2 = min(255, shade + 30)
                if x % max(1, width // 3) < 2 or y % max(1, height // 3) < 2:
                    row.extend([0, 0, 0])
                else:
                    row.extend([shade, shade, shade2])
            else:
                # noise pattern resembling captcha text
                if 10 < y < height - 10 and 20 < x < width - 20 and (x * 3 + y * 7) % 11 < 3:
                    row.extend([0, 0, 0])
                else:
                    row.extend([255, 255, 255])
        rows.append(bytes(row))
    raw = b"".join(rows)
    compressed = zlib.compress(raw)

    def chunk(name: bytes, data: bytes) -> bytes:
        c = name + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")


def check_balance() -> float | None:
    key = get_settings().twocaptcha_api_key
    if not key:
        print("[SKIP] TWOCAPTCHA_API_KEY not set")
        return None
    solver = TwoCaptcha(key)
    try:
        balance = solver.balance()
        print(f"[OK] API key valid — balance: ${balance}")
        return float(balance)
    except Exception as exc:
        print(f"[FAIL] API key check failed: {exc}")
        return None


async def test_image_captcha():
    """Test image captcha using a locally generated PNG (simulates Amazon validatecaptcha page)."""
    print("\n[TEST] Image captcha — locally generated PNG (200x60)")
    image_bytes = _make_png(200, 60, pattern="noise")
    print(f"[INFO] Image size: {len(image_bytes)} bytes")

    # Write to temp file so solve_image_captcha can fetch it via file:// URL
    import tempfile, urllib.request
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(image_bytes)
        tmp_path = f.name

    try:
        file_url = f"file://{tmp_path}"
        result = await solve_image_captcha(file_url)
        if result:
            print(f"[OK] Image captcha solved: '{result}'")
        else:
            print("[FAIL] Image captcha returned None")
    finally:
        os.unlink(tmp_path)
    return result


async def test_grid_captcha():
    """Test grid captcha using a locally generated 3x3 grid PNG."""
    print("\n[TEST] Grid captcha — locally generated 300x300 grid PNG")
    image_bytes = _make_png(300, 300, pattern="grid")
    print(f"[INFO] Image size: {len(image_bytes)} bytes")

    instruction = "Choose all the bags"
    print(f"[INFO] Instruction: '{instruction}'")
    result = await solve_grid_captcha(image_bytes, instruction)
    if result is not None:
        print(f"[OK] Grid captcha solved: cells={result}")
    else:
        print("[FAIL] Grid captcha returned None")
    return result


async def test_waf_captcha_mock():
    """Test WAF captcha API connectivity with mock params."""
    print("\n[TEST] WAF captcha — mock params (expect API error, not None)")
    key = get_settings().twocaptcha_api_key
    if not key:
        print("[SKIP] No API key")
        return
    solver = TwoCaptcha(key)
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: solver.amazon_waf(
                sitekey="test-sitekey-invalid",
                iv="test-iv",
                context="test-context",
                url="https://www.amazon.com",
            ),
        )
        print(f"[OK] WAF returned (unexpected success with mock): {result}")
    except Exception as exc:
        err = str(exc)
        if any(e in err for e in ["ERROR_WRONG_CAPTCHA_ID", "ERROR_CAPTCHA_UNSOLVABLE", "ERROR"]):
            print(f"[OK] WAF API reachable — expected error with mock params: {err[:80]}")
        else:
            print(f"[FAIL] WAF unexpected error: {err}")


async def main():
    print("=" * 60)
    print("2captcha integration test")
    print("=" * 60)

    balance = check_balance()
    if balance is None:
        print("\nAborting — cannot verify API key.")
        return
    if balance < 0.1:
        print(f"\n[WARN] Balance is low (${balance}), captcha solving may fail.")

    await test_image_captcha()
    await test_grid_captcha()
    await test_waf_captcha_mock()

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
