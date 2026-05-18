from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AccountStatus(str, Enum):
    pending = "pending"
    google_authenticated = "google_authenticated"
    manual_required = "manual_required"
    invalid_credentials = "invalid_credentials"
    locked = "locked"
    error = "error"


class ServiceStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    manual_required = "manual_required"
    failed = "failed"
    unsupported = "unsupported"
    error = "error"


class TaskType(str, Enum):
    login_gmail = "login_gmail"
    login_service = "login_service"
    login_all_services = "login_all_services"


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    partial_manual_required = "partial_manual_required"


class AccountCreate(BaseModel):
    email: str
    password: str | None = None
    recovery_email: str | None = None
    totp_secret: str | None = None
    account_year: str | None = None
    country: str | None = None


class AccountUpdate(BaseModel):
    password: str | None = None
    recovery_email: str | None = None
    totp_secret: str | None = None
    account_year: str | None = None
    country: str | None = None
    status: AccountStatus | None = None
    message: str | None = None


class Account(AccountCreate):
    id: int
    status: str = "pending"
    message: str | None = None
    proxy_url: str | None = None
    proxy_ssid: str | None = None
    proxy_country: str | None = None
    proxy_state_region: str | None = None
    proxy_region_slug: str | None = None
    proxy_ip: str | None = None
    proxy_country_name: str | None = None
    proxy_country_code: str | None = None
    proxy_latitude: float | None = None
    proxy_longitude: float | None = None
    proxy_postal: str | None = None
    proxy_checked_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AccountListResponse(BaseModel):
    total: int
    items: list[Account]


class ImportAccountsRequest(BaseModel):
    content: str


class ImportAccountsResponse(BaseModel):
    imported: int
    errors: list[str] = Field(default_factory=list)
    account_ids: list[int] = Field(default_factory=list)


class BrowserEnsureRequest(BaseModel):
    account_id: int
    template_browser_id: str | None = None
    rotate_proxy: bool = False


class BrowserOpenResponse(BaseModel):
    browser_id: str
    ws: str | None = None


class TaskCreateRequest(BaseModel):
    type: TaskType
    account_ids: list[int]
    services: list[str] = Field(default_factory=list)
    close_after: bool = False
    concurrency: int = 1
    template_browser_id: str | None = None
    proxy_urls: list[str] = Field(default_factory=list)


class TaskProgress(BaseModel):
    id: str
    type: str
    status: str
    total: int = 0
    completed: int = 0
    failed: int = 0
    manual_required: int = 0
    message: str | None = None


class AutomationResult(BaseModel):
    success: bool = False
    manual_required: bool = False
    status: str = "failed"
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class ServiceLogin(BaseModel):
    account_id: int
    service: str
    status: str
    message: str | None = None
    last_attempt_at: str | None = None
    last_success_at: str | None = None
