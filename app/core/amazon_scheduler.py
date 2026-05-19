import threading
import time

from app.core.amazon_runner import amazon_suspend_checker
from app.db import DB

_started = False
_lock = threading.Lock()


def start_suspend_scheduler() -> None:
    global _started
    with _lock:
        if _started:
            return
        _started = True
    t = threading.Thread(target=_loop, daemon=True)
    t.start()


def _loop() -> None:
    tick = 0
    while True:
        try:
            pending = DB.list_amazon_accounts_pending_check()
            for account in pending:
                amazon_suspend_checker.check_account(account["id"])
        except Exception:
            pass
        # Clean zombie tasks every 10 ticks (~10 min), stale > 60 min
        tick += 1
        if tick % 10 == 0:
            try:
                cleaned = DB.cleanup_zombie_tasks(stale_minutes=60)
                if cleaned:
                    DB.add_event(None, None, None, "warning", "zombie_cleanup", f"cleaned {cleaned} zombie task(s)")
            except Exception:
                pass
        time.sleep(60)
