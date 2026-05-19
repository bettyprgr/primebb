# PrimeBB Automation

PrimeBB Automation is a local automation workspace for managing BitBrowser-backed browser profiles from a FastAPI backend and a React dashboard.

The current dashboard includes two tools:

- **Social Pumper**: imports Gmail accounts, authenticates Gmail, and connects supported services through Google OAuth.
- **Amazon Creation**: imports phone/SMS records and runs Amazon account creation flows with BitBrowser profiles.

This project is intended only for accounts, phone numbers, browsers, proxies, and third-party services that you are authorized to use. Manual platform challenges may require human action in the opened browser profile.

## Features

- FastAPI backend with SQLite persistence
- React + Vite dashboard (served by FastAPI — no separate frontend server needed)
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

- Python 3.11+ (https://python.org — check "Add Python to PATH" during install)
- BitBrowser running locally or on a reachable host

No Node.js or frontend build tools needed on the machine that runs the app.

## Quick Start (Windows)

1. Install Python 3.11+ from https://python.org (check "Add Python to PATH")
2. Clone or download this repository
3. Double-click `setup.bat` — installs all dependencies and opens `.env` for configuration
4. Edit `.env` — at minimum set `BITBROWSER_URL`
5. Double-click `start.bat` — starts the server
6. Open http://localhost:8000 in your browser

Run `setup.bat` only once. After that, use `start.bat` every time.

## Configuration

`setup.bat` creates `.env` from `.env.example` automatically. Key settings:

| Variable | Default | Description |
| --- | --- | --- |
| `BITBROWSER_URL` | `http://127.0.0.1:54345` | BitBrowser API URL. Change host/IP if BitBrowser runs on another machine. |
| `TWOCAPTCHA_API_KEY` | empty | 2captcha key for auto-solving CAPTCHAs. Leave empty to solve manually. |
| `PROXY_USERNAME_PREFIX` | empty | Proxy credential username prefix. |
| `PROXY_PASSWORD` | empty | Proxy credential password. |
| `PROXY_HOST` | `niceproxy.io` | Proxy host. |
| `PROXY_PORT` | `17521` | Proxy port. |
| `MAX_TASK_CONCURRENCY` | `3` | Max accounts processed at the same time. |
| `DELETE_BROWSER_AFTER_COMPLETE` | `true` | Delete BitBrowser profile after successful account creation. |
| `IPDATA_API_KEY` | empty | ipdata.co key for proxy geo lookup (optional). |

## Manual Install (Linux / Mac)

```bash
# Install uv (Python package manager)
pip install uv

# Install dependencies
uv sync

# Install Playwright browser
uv run playwright install chromium

# Copy and edit config
cp .env.example .env
# edit .env

# Run
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## BitBrowser Notes

- Keep BitBrowser running before starting automation tasks.
- Set `BITBROWSER_URL` to the BitBrowser API URL reachable from this machine.
- If BitBrowser runs on another machine, ensure its API port (54345) and browser debug ports are accessible.
- On Windows, remote BitBrowser access may require a firewall rule and a `netsh interface portproxy` mapping for localhost-only debug ports.

## Social Pumper Usage

Account import format (pipe-separated, one per line):

```text
email|password|recovery_email|totp_secret|account_year|country
```

Supported service task types: `login_gmail`, `login_service`, `login_all_services`

Supported services: `youtube`, `quora`, `reddit`, `x`, `ebay`

## Amazon Creation Usage

Phone import format (pipe-separated, one per line):

```text
phone|sms_url|name|state_abbreviation
```

- `name` and `state_abbreviation` are optional.
- Empty lines and lines starting with `#` are ignored.

## Local Data

Runtime data is stored in SQLite:

```text
data/primebb.sqlite3
```

The `data/` directory is not committed to git as it may contain credentials and account state.

## Troubleshooting

- **Cannot connect to BitBrowser**: verify `BITBROWSER_URL`, that BitBrowser is running, and firewall rules.
- **Playwright/CDP fails**: confirm BitBrowser returned a valid websocket URL and the debug port is reachable.
- **Proxy geo lookup empty**: set `IPDATA_API_KEY` and verify proxy connectivity.
- **CAPTCHA not auto-solved**: set `TWOCAPTCHA_API_KEY` and confirm account balance.

## Safety and Data Handling

- Use only with systems and accounts you are authorized to automate.
- Never commit `.env`, SQLite databases, proxy credentials, TOTP secrets, or API keys.
- Manual platform challenges should be handled by a human in the opened BitBrowser profile.

