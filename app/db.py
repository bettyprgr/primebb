import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.config import get_settings

_lock = threading.RLock()


class DB:
    @staticmethod
    def path() -> str:
        path = Path(get_settings().database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    @staticmethod
    def connect() -> sqlite3.Connection:
        conn = sqlite3.connect(DB.path(), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    @contextmanager
    def session():
        conn = DB.connect()
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def init() -> None:
        with _lock, DB.session() as conn:
            cursor = conn.cursor()
            cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT NOT NULL UNIQUE,
                  password TEXT,
                  recovery_email TEXT,
                  totp_secret TEXT,
                  account_year TEXT,
                  country TEXT,
                  proxy_url TEXT,
                  proxy_ssid TEXT,
                  proxy_country TEXT,
                  proxy_state_region TEXT,
                  proxy_region_slug TEXT,
                  proxy_ip TEXT,
                  proxy_country_name TEXT,
                  proxy_country_code TEXT,
                  proxy_latitude REAL,
                  proxy_longitude REAL,
                  proxy_postal TEXT,
                  proxy_checked_at TEXT,
                  status TEXT NOT NULL DEFAULT 'pending',
                  message TEXT,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS browser_profiles (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  account_id INTEGER NOT NULL,
                  bitbrowser_id TEXT NOT NULL UNIQUE,
                  name TEXT,
                  template_browser_id TEXT,
                  config_json TEXT,
                  status TEXT NOT NULL DEFAULT 'created',
                  last_opened_at TEXT,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(account_id) REFERENCES accounts(id)
                );

                CREATE TABLE IF NOT EXISTS service_logins (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  account_id INTEGER NOT NULL,
                  service TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'pending',
                  message TEXT,
                  last_attempt_at TEXT,
                  last_success_at TEXT,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(account_id, service),
                  FOREIGN KEY(account_id) REFERENCES accounts(id)
                );

                CREATE TABLE IF NOT EXISTS tasks (
                  id TEXT PRIMARY KEY,
                  type TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'pending',
                  total INTEGER NOT NULL DEFAULT 0,
                  completed INTEGER NOT NULL DEFAULT 0,
                  failed INTEGER NOT NULL DEFAULT 0,
                  manual_required INTEGER NOT NULL DEFAULT 0,
                  message TEXT,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS task_items (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL,
                  account_id INTEGER NOT NULL,
                  service TEXT,
                  status TEXT NOT NULL DEFAULT 'pending',
                  message TEXT,
                  started_at TEXT,
                  finished_at TEXT,
                  FOREIGN KEY(task_id) REFERENCES tasks(id),
                  FOREIGN KEY(account_id) REFERENCES accounts(id)
                );

                CREATE TABLE IF NOT EXISTS events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT,
                  account_id INTEGER,
                  service TEXT,
                  level TEXT NOT NULL DEFAULT 'info',
                  event_type TEXT NOT NULL,
                  message TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS amazon_accounts (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  phone TEXT NOT NULL UNIQUE,
                  sms_url TEXT NOT NULL,
                  name TEXT,
                  password TEXT,
                  proxy_url TEXT,
                  proxy_region TEXT,
                  bitbrowser_id TEXT,
                  status TEXT NOT NULL DEFAULT 'pending',
                  message TEXT,
                  check_after_at TEXT,
                  last_checked_at TEXT,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.commit()

    @staticmethod
    def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row else None

    @staticmethod
    def upsert_account(data: dict[str, Any]) -> dict[str, Any]:
        email = (data.get("email") or "").strip()
        if not email:
            raise ValueError("email is required")
        fields = [
            "password",
            "recovery_email",
            "totp_secret",
            "account_year",
            "country",
            "status",
            "message",
            "proxy_url",
            "proxy_ssid",
            "proxy_country",
            "proxy_state_region",
            "proxy_region_slug",
            "proxy_ip",
            "proxy_country_name",
            "proxy_country_code",
            "proxy_latitude",
            "proxy_longitude",
            "proxy_postal",
            "proxy_checked_at",
        ]
        with _lock, DB.session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM accounts WHERE email = ?", (email,))
            exists = cursor.fetchone()
            if exists:
                updates = []
                values = []
                for field in fields:
                    if field in data:
                        updates.append(f"{field} = ?")
                        values.append(data[field])
                if updates:
                    updates.append("updated_at = CURRENT_TIMESTAMP")
                    values.append(email)
                    cursor.execute(f"UPDATE accounts SET {', '.join(updates)} WHERE email = ?", values)
            else:
                insert_fields = ["email"] + [field for field in fields if field in data]
                placeholders = ", ".join("?" for _ in insert_fields)
                values = [email] + [data.get(field) for field in insert_fields[1:]]
                cursor.execute(
                    f"INSERT INTO accounts ({', '.join(insert_fields)}) VALUES ({placeholders})",
                    values,
                )
            conn.commit()
        account = DB.get_account_by_email(email)
        if not account:
            raise RuntimeError("account upsert failed")
        return account

    @staticmethod
    def get_account(account_id: int) -> dict[str, Any] | None:
        with _lock, DB.session() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
            return DB.row_to_dict(row)

    @staticmethod
    def get_account_by_email(email: str) -> dict[str, Any] | None:
        with _lock, DB.session() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE email = ?", (email,)).fetchone()
            return DB.row_to_dict(row)

    @staticmethod
    def list_accounts() -> list[dict[str, Any]]:
        with _lock, DB.session() as conn:
            rows = conn.execute("SELECT * FROM accounts ORDER BY id DESC").fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def delete_account(account_id: int) -> bool:
        with _lock, DB.session() as conn:
            cursor = conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def delete_accounts_bulk(account_ids: list[int]) -> int:
        if not account_ids:
            return 0
        placeholders = ",".join("?" * len(account_ids))
        with _lock, DB.session() as conn:
            cursor = conn.execute(f"DELETE FROM accounts WHERE id IN ({placeholders})", account_ids)
            conn.commit()
            return cursor.rowcount

    @staticmethod
    def delete_all_accounts() -> int:
        with _lock, DB.session() as conn:
            cursor = conn.execute("DELETE FROM accounts")
            conn.commit()
            return cursor.rowcount

    @staticmethod
    def save_browser_profile(account_id: int, bitbrowser_id: str, config: dict[str, Any] | None, template_browser_id: str | None = None, status: str = "created") -> dict[str, Any]:
        config_json = json.dumps(config or {}, ensure_ascii=False)
        name = (config or {}).get("name") or (config or {}).get("userName")
        with _lock, DB.session() as conn:
            conn.execute(
                """
                INSERT INTO browser_profiles (account_id, bitbrowser_id, name, template_browser_id, config_json, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(bitbrowser_id) DO UPDATE SET
                    account_id = excluded.account_id,
                    name = excluded.name,
                    template_browser_id = excluded.template_browser_id,
                    config_json = excluded.config_json,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (account_id, bitbrowser_id, name, template_browser_id, config_json, status),
            )
            conn.commit()
        profile = DB.get_browser_profile_by_account(account_id)
        if not profile:
            raise RuntimeError("browser profile save failed")
        return profile

    @staticmethod
    def get_browser_profile_by_account(account_id: int) -> dict[str, Any] | None:
        with _lock, DB.session() as conn:
            row = conn.execute(
                "SELECT * FROM browser_profiles WHERE account_id = ? ORDER BY id DESC LIMIT 1",
                (account_id,),
            ).fetchone()
            return DB.row_to_dict(row)

    @staticmethod
    def update_browser_profile_status(bitbrowser_id: str, status: str) -> None:
        with _lock, DB.session() as conn:
            conn.execute(
                "UPDATE browser_profiles SET status = ?, last_opened_at = CASE WHEN ? = 'open' THEN CURRENT_TIMESTAMP ELSE last_opened_at END, updated_at = CURRENT_TIMESTAMP WHERE bitbrowser_id = ?",
                (status, status, bitbrowser_id),
            )
            conn.commit()

    @staticmethod
    def upsert_service_login(account_id: int, service: str, status: str, message: str | None = None) -> None:
        last_success = "CURRENT_TIMESTAMP" if status == "success" else "NULL"
        with _lock, DB.session() as conn:
            conn.execute(
                f"""
                INSERT INTO service_logins (account_id, service, status, message, last_attempt_at, last_success_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, {last_success})
                ON CONFLICT(account_id, service) DO UPDATE SET
                    status = excluded.status,
                    message = excluded.message,
                    last_attempt_at = CURRENT_TIMESTAMP,
                    last_success_at = CASE WHEN excluded.status = 'success' THEN CURRENT_TIMESTAMP ELSE service_logins.last_success_at END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (account_id, service, status, message),
            )
            conn.commit()

    @staticmethod
    def list_service_logins(account_id: int) -> list[dict[str, Any]]:
        with _lock, DB.session() as conn:
            rows = conn.execute("SELECT * FROM service_logins WHERE account_id = ? ORDER BY service", (account_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_task(task_id: str, task_type: str, total: int) -> None:
        with _lock, DB.session() as conn:
            conn.execute(
                "INSERT INTO tasks (id, type, status, total) VALUES (?, ?, 'pending', ?)",
                (task_id, task_type, total),
            )
            conn.commit()

    @staticmethod
    def update_task(task_id: str, **fields: Any) -> None:
        if not fields:
            return
        allowed = {"status", "completed", "failed", "manual_required", "message"}
        updates = []
        values = []
        for key, value in fields.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(value)
        if not updates:
            return
        updates.append("updated_at = CURRENT_TIMESTAMP")
        values.append(task_id)
        with _lock, DB.session() as conn:
            conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", values)
            conn.commit()

    @staticmethod
    def get_task(task_id: str) -> dict[str, Any] | None:
        with _lock, DB.session() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return DB.row_to_dict(row)

    @staticmethod
    def list_tasks() -> list[dict[str, Any]]:
        with _lock, DB.session() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_task_item(task_id: str, account_id: int, service: str | None = None) -> None:
        with _lock, DB.session() as conn:
            conn.execute(
                "INSERT INTO task_items (task_id, account_id, service) VALUES (?, ?, ?)",
                (task_id, account_id, service),
            )
            conn.commit()

    @staticmethod
    def update_task_item(task_id: str, account_id: int, status: str, message: str | None = None, service: str | None = None) -> None:
        with _lock, DB.session() as conn:
            conn.execute(
                """
                UPDATE task_items
                SET status = ?, message = ?, started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                    finished_at = CASE WHEN ? IN ('success', 'failed', 'manual_required', 'error') THEN CURRENT_TIMESTAMP ELSE finished_at END
                WHERE task_id = ? AND account_id = ? AND (service IS ? OR service = ?)
                """,
                (status, message, status, task_id, account_id, service, service),
            )
            conn.commit()

    @staticmethod
    def add_event(task_id: str | None, account_id: int | None, service: str | None, level: str, event_type: str, message: str) -> None:
        with _lock, DB.session() as conn:
            conn.execute(
                "INSERT INTO events (task_id, account_id, service, level, event_type, message) VALUES (?, ?, ?, ?, ?, ?)",
                (task_id, account_id, service, level, event_type, message),
            )
            conn.commit()

    # ── Amazon accounts ──────────────────────────────────────────────────────

    @staticmethod
    def upsert_amazon_account(data: dict[str, Any]) -> dict[str, Any]:
        phone = (data.get("phone") or "").strip()
        if not phone:
            raise ValueError("phone is required")
        fields = ["sms_url", "name", "password", "proxy_url", "proxy_region", "bitbrowser_id", "status", "message", "check_after_at", "last_checked_at"]
        with _lock, DB.session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM amazon_accounts WHERE phone = ?", (phone,))
            exists = cursor.fetchone()
            if exists:
                updates, values = [], []
                for field in fields:
                    if field in data:
                        updates.append(f"{field} = ?")
                        values.append(data[field])
                if updates:
                    updates.append("updated_at = CURRENT_TIMESTAMP")
                    values.append(phone)
                    cursor.execute(f"UPDATE amazon_accounts SET {', '.join(updates)} WHERE phone = ?", values)
            else:
                insert_fields = ["phone"] + [f for f in fields if f in data]
                placeholders = ", ".join("?" for _ in insert_fields)
                values = [phone] + [data.get(f) for f in insert_fields[1:]]
                cursor.execute(f"INSERT INTO amazon_accounts ({', '.join(insert_fields)}) VALUES ({placeholders})", values)
            conn.commit()
        row = DB.get_amazon_account_by_phone(phone)
        if not row:
            raise RuntimeError("amazon account upsert failed")
        return row

    @staticmethod
    def get_amazon_account(account_id: int) -> dict[str, Any] | None:
        with _lock, DB.session() as conn:
            row = conn.execute("SELECT * FROM amazon_accounts WHERE id = ?", (account_id,)).fetchone()
            return DB.row_to_dict(row)

    @staticmethod
    def get_amazon_account_by_phone(phone: str) -> dict[str, Any] | None:
        with _lock, DB.session() as conn:
            row = conn.execute("SELECT * FROM amazon_accounts WHERE phone = ?", (phone,)).fetchone()
            return DB.row_to_dict(row)

    @staticmethod
    def list_amazon_accounts() -> list[dict[str, Any]]:
        with _lock, DB.session() as conn:
            rows = conn.execute("SELECT * FROM amazon_accounts ORDER BY id DESC").fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def delete_amazon_account(account_id: int) -> bool:
        with _lock, DB.session() as conn:
            cursor = conn.execute("DELETE FROM amazon_accounts WHERE id = ?", (account_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def delete_amazon_accounts_bulk(account_ids: list[int]) -> int:
        if not account_ids:
            return 0
        placeholders = ",".join("?" * len(account_ids))
        with _lock, DB.session() as conn:
            cursor = conn.execute(f"DELETE FROM amazon_accounts WHERE id IN ({placeholders})", account_ids)
            conn.commit()
            return cursor.rowcount

    @staticmethod
    def cleanup_zombie_tasks(stale_minutes: int = 60) -> int:
        """Mark running tasks/items as failed if not updated recently.
        stale_minutes=0 cleans all running tasks immediately (use on server restart)."""
        with _lock, DB.session() as conn:
            cur = conn.cursor()
            if stale_minutes == 0:
                cur.execute("SELECT id FROM tasks WHERE status = 'running'")
            else:
                cur.execute(
                    "SELECT id FROM tasks WHERE status = 'running' AND updated_at <= datetime('now', ?)",
                    (f"-{stale_minutes} minutes",),
                )
            zombie_ids = [r[0] for r in cur.fetchall()]
            if not zombie_ids:
                return 0
            placeholders = ",".join("?" * len(zombie_ids))
            cur.execute(
                f"UPDATE tasks SET status='failed', message='cleaned up: zombie task', updated_at=CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                zombie_ids,
            )
            cur.execute(
                f"UPDATE task_items SET status='error', message='cleaned up: zombie task', finished_at=COALESCE(finished_at, CURRENT_TIMESTAMP) WHERE task_id IN ({placeholders}) AND status IN ('running', 'pending')",
                zombie_ids,
            )
            conn.commit()
            return len(zombie_ids)

    @staticmethod
    def list_amazon_accounts_pending_check() -> list[dict[str, Any]]:
        with _lock, DB.session() as conn:
            rows = conn.execute(
                "SELECT * FROM amazon_accounts WHERE status = 'created' AND check_after_at IS NOT NULL AND check_after_at <= CURRENT_TIMESTAMP"
            ).fetchall()
            return [dict(row) for row in rows]
