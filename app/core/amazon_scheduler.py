import threading
import time

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
        tick += 1
        if tick % 10 == 0:
            try:
                cleaned = DB.cleanup_zombie_tasks(stale_minutes=60)
                if cleaned:
                    DB.add_event(None, None, None, "warning", "zombie_cleanup", f"cleaned {cleaned} zombie task(s)")
            except Exception:
                pass
        time.sleep(60)
