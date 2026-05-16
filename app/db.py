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
