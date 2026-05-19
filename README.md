# PrimeBB Automation

PrimeBB Automation is a local automation workspace for managing BitBrowser-backed browser profiles from a FastAPI backend and a React dashboard.

The current dashboard includes two tools:

- **Social Pumper**: imports Gmail accounts, authenticates Gmail, and connects supported services through Google OAuth.
- **Amazon Creation**: imports phone/SMS records and runs Amazon account creation flows with BitBrowser profiles.

This project is intended only for accounts, phone numbers, browsers, proxies, and third-party services that you are authorized to use. Manual platform challenges may require human action in the opened browser profile.

## Features

- FastAPI backend with SQLite persistence
- React + Vite dashboard
- BitBrowser profile creation, reuse, open, and close actions
- SOCKS5 proxy assignment per account/profile
- Optional proxy geo lookup with ipdata
- Playwright CDP connection to BitBrowser profiles
- Gmail login with password, TOTP, and recovery email handling
- Google OAuth adapters for YouTube, Quora, Reddit, X, and eBay
- Amazon phone import and account creation task runner
- Optional 2captcha integration for CAPTCHA challenge handling in authorized flows
- Batch task runner with concurrency limits and per-account locking
- WebSocket progress and event updates

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for Python dependency management
- Node.js 20+
- npm
- BitBrowser running locally or on a reachable host
- Playwright Chromium browser dependencies
- Optional: ipdata API key for proxy geo verification
- Optional: 2captcha API key for CAPTCHA challenge handling

## Install

Install backend dependencies from the repository root:

```bash
uv sync
```

Install Playwright Chromium:

```bash
uv run playwright install chromium
```

Install frontend dependencies:

```bash
cd frontend
npm install
```

Return to the repository root before running backend commands:

```bash
cd ..
```

## Configuration

Create a local `.env` file in the repository root:

```env
APP_NAME=PrimeBB Automation
DATABASE_PATH=data/primebb.sqlite3
BITBROWSER_URL=http://127.0.0.1:54345
IPDATA_API_KEY=
PROXY_USERNAME_PREFIX=
PROXY_PASSWORD=
PROXY_HOST=niceproxy.io
PROXY_PORT=17521
PROXY_SESSION_TTL=30
MAX_TASK_CONCURRENCY=3
TWOCAPTCHA_API_KEY=
DELETE_BROWSER_AFTER_COMPLETE=true
```

### Environment variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `APP_NAME` | No | `PrimeBB Automation` | Display/API app name. |
| `DATABASE_PATH` | No | `data/primebb.sqlite3` | SQLite database path. |
| `BITBROWSER_URL` | Yes | `http://127.0.0.1:54345` | BitBrowser API base URL. Use the reachable host/IP if BitBrowser runs on another machine. |
| `IPDATA_API_KEY` | No | empty | Enables proxy geo verification when configured. |
| `PROXY_USERNAME_PREFIX` | No | empty | Username prefix used when building proxy credentials. |
| `PROXY_PASSWORD` | No | empty | Proxy password used when building proxy credentials. |
| `PROXY_HOST` | No | `niceproxy.io` | Proxy host used for generated proxy URLs. |
| `PROXY_PORT` | No | `17521` | Proxy port used for generated proxy URLs. |
| `PROXY_SESSION_TTL` | No | `30` | Proxy session TTL in minutes. |
| `MAX_TASK_CONCURRENCY` | No | `3` | Maximum concurrent task workers. |
| `TWOCAPTCHA_API_KEY` | No | empty | Enables 2captcha-backed challenge handling when configured. |
| `DELETE_BROWSER_AFTER_COMPLETE` | No | `true` | Deletes temporary BitBrowser profiles after successful completion when enabled. |

Do not commit `.env`, SQLite databases, account exports, phone/SMS imports, proxy credentials, TOTP secrets, or CAPTCHA provider keys.

## Run the Backend

Start the FastAPI server from the repository root:

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check from the same machine:

```bash
curl http://127.0.0.1:8000/api/health
```

If you access the backend from another machine, replace `127.0.0.1` with the server IP or hostname.

## Run the Dashboard

Start the Vite development server from `frontend/`:

```bash
cd frontend
npm run dev -- --host 0.0.0.0
```

Open the dashboard:

```text
http://127.0.0.1:5173
```

If you access it remotely, replace `127.0.0.1` with the server IP or hostname.

The Vite dev server proxies `/api` and `/ws` to the backend at `http://127.0.0.1:8000`.

## BitBrowser Notes

- Keep BitBrowser running before starting automation tasks.
- Set `BITBROWSER_URL` to the BitBrowser API URL that the backend can reach.
- If BitBrowser runs on another machine, make sure its API and browser debug ports are reachable from the backend host.
- Some BitBrowser CDP URLs may point to `127.0.0.1`; the backend rewrites localhost CDP hosts to the host from `BITBROWSER_URL`.
- On Windows, remote BitBrowser access may require a firewall rule and a `netsh interface portproxy` mapping for localhost-only debug ports.

## Social Pumper Usage

Social Pumper account import is pipe-separated and expects exactly six fields:

```text
email|password|recovery_email|totp_secret|account_year|country
```

Example placeholder:

```text
user@example.com|password|recovery@example.com|BASE32TOTPSECRET|2024|United States
```

Supported service task types:

- `login_gmail`
- `login_service`
- `login_all_services`

Supported services:

- `youtube`
- `quora`
- `reddit`
- `x`
- `ebay`

Example task payload:

```json
{
  "type": "login_all_services",
  "account_ids": [1],
  "services": ["youtube", "quora", "reddit", "x", "ebay"],
  "concurrency": 1,
  "close_after": false,
  "template_browser_id": null,
  "proxy_urls": []
}
```

## Amazon Creation Usage

Amazon phone import is pipe-separated. Each line requires a phone number and SMS URL, with optional name and proxy region:

```text
phone|sms_url|name|state_abbreviation
```

Example placeholder:

```text
+15551234567|https://sms-provider.example/messages/abc|Jane Doe|CA
```

Notes:

- Empty lines and lines starting with `#` are ignored.
- `state_abbreviation` is optional. When present, the backend attempts to build a US regional proxy URL.
- You can also pass explicit proxy URLs when creating an Amazon task.

Example Amazon task payload:

```json
{
  "amazon_ids": [1, 2],
  "template_browser_id": null,
  "concurrency": 1,
  "proxy_urls": []
}
```

## Main API Endpoints

### Health and Config

- `GET /api/health`
- `GET /api/config`

### Social Pumper Accounts

- `GET /api/accounts`
- `POST /api/accounts`
- `POST /api/accounts/import`
- `GET /api/accounts/{account_id}`
- `PATCH /api/accounts/{account_id}`
- `DELETE /api/accounts/{account_id}`
- `POST /api/accounts/bulk-delete`
- `DELETE /api/accounts`

### Browsers

- `GET /api/browsers`
- `POST /api/browsers/ensure`
- `POST /api/browsers/{browser_id}/open`
- `POST /api/browsers/{browser_id}/close`

### Tasks

- `POST /api/tasks`
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `DELETE /api/tasks/{task_id}`

### Services

- `GET /api/services`
- `GET /api/accounts/{account_id}/services`

### Amazon

- `POST /api/amazon/phones/import`
- `GET /api/amazon/accounts`
- `PATCH /api/amazon/accounts/{account_id}`
- `DELETE /api/amazon/accounts/{account_id}`
- `POST /api/amazon/accounts/bulk-delete`
- `POST /api/amazon/tasks`

### WebSocket

- `WS /ws`

## Local Data

Runtime data is stored in SQLite by default:

```text
data/primebb.sqlite3
```

The `data/` directory is ignored by git because it may contain credentials, account status, proxy assignments, and service login state.

## Build

Build the frontend production assets:

```bash
cd frontend
npm run build
```

Preview the built frontend locally:

```bash
npm run preview -- --host 0.0.0.0
```

## Troubleshooting

- **Backend cannot connect to BitBrowser**: verify `BITBROWSER_URL`, firewall rules, and that BitBrowser is running.
- **Dashboard API calls fail**: confirm the backend is running on port `8000`; Vite proxies `/api` and `/ws` to that port.
- **Playwright/CDP connection fails**: confirm BitBrowser returned a valid Playwright websocket URL and that the debug port is reachable from the backend host.
- **Proxy geo lookup is empty**: set `IPDATA_API_KEY` and verify the proxy works from inside the opened browser profile.
- **CAPTCHA handling is skipped**: set `TWOCAPTCHA_API_KEY` and confirm the provider account has balance.

## Safety and Data Handling

- Use this project only with systems and accounts you are authorized to automate.
- Keep secrets in `.env` or another local secret store; never commit them.
- Do not log or publish account passwords, TOTP secrets, raw import lines, proxy credentials, CAPTCHA provider keys, or SMS URLs.
- Manual platform challenges should be handled by a human in the opened BitBrowser profile.
