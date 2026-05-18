from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PrimeBB Automation"
    database_path: str = str(Path(__file__).resolve().parent.parent / "data" / "primebb.sqlite3")
    bitbrowser_url: str = "http://127.0.0.1:54345"
    ipdata_api_key: str = ""
    proxy_username_prefix: str = ""
    proxy_password: str = ""
    proxy_host: str = "niceproxy.io"
    proxy_port: int = 17521
    proxy_session_ttl: int = 30
    max_task_concurrency: int = 3
    twocaptcha_api_key: str = ""
    delete_browser_after_complete: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
