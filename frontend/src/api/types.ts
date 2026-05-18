export type AccountStatus = "pending" | "google_authenticated" | "manual_required" | "invalid_credentials" | "locked" | "error" | string;
export type ServiceStatus = "pending" | "running" | "success" | "manual_required" | "failed" | "unsupported" | "error" | string;
export type TaskStatus = "pending" | "running" | "completed" | "failed" | "cancelled" | "partial_manual_required" | string;
export type TaskType = "login_gmail" | "login_service" | "login_all_services";

export type Account = {
  id: number;
  email: string;
  password?: string | null;
  recovery_email?: string | null;
  totp_secret?: string | null;
  account_year?: string | null;
  country?: string | null;
  status: AccountStatus;
  message?: string | null;
  proxy_url?: string | null;
  proxy_ssid?: string | null;
  proxy_country?: string | null;
  proxy_state_region?: string | null;
  proxy_region_slug?: string | null;
  proxy_ip?: string | null;
  proxy_country_name?: string | null;
  proxy_country_code?: string | null;
  proxy_latitude?: number | null;
  proxy_longitude?: number | null;
  proxy_postal?: string | null;
  proxy_checked_at?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type AccountListResponse = {
  total: number;
  items: Account[];
};

export type AccountCreate = {
  email: string;
  password?: string;
  recovery_email?: string;
  totp_secret?: string;
  account_year?: string;
  country?: string;
};

export type ImportAccountsResponse = {
  imported: number;
  errors: string[];
  account_ids: number[];
};

export type BrowserEnsureRequest = {
  account_id: number;
  template_browser_id?: string | null;
  rotate_proxy?: boolean;
};

export type BrowserOpenResponse = {
  browser_id: string;
  ws?: string | null;
};

export type ConfigResponse = {
  bitbrowser_url: string;
  ipdata_configured: boolean;
  proxy_host: string;
  proxy_port: number;
  proxy_username_prefix: string;
  proxy_session_ttl: number;
};

export type ServiceLogin = {
  account_id: number;
  service: string;
  status: ServiceStatus;
  message?: string | null;
  last_attempt_at?: string | null;
  last_success_at?: string | null;
};

export type Task = {
  id: string;
  type: TaskType | string;
  status: TaskStatus;
  total: number;
  completed: number;
  failed: number;
  manual_required: number;
  message?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type TaskCreateRequest = {
  type: TaskType;
  account_ids: number[];
  services?: string[];
  close_after?: boolean;
  concurrency?: number;
  template_browser_id?: string | null;
  proxy_urls?: string[];
};

export type WsMessage =
  | { type: "log"; data: { level: string; message: string; task_id?: string; account_id?: number; service?: string } }
  | { type: "task_progress"; data: Task }
  | { type: "account_progress"; data: { task_id: string; account_id: number; status: string } }
  | { type: "service_progress"; data: { task_id: string; account_id: number; service: string; status: string } };
