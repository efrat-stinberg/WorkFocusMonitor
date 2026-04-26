# WorkFocusMonitor

A self-hosted screen monitor that uses OpenAI Vision to detect off-task browsing during coding sessions and sends an email alert when non-development content is detected.

## Architecture

```
┌──────────────────┐         HTTPS          ┌──────────────────┐
│     Client       │  ───────────────────►  │     Server       │
│  (Windows agent) │   screenshot + meta    │  (FastAPI + AI)  │
└──────────────────┘                        └──────────────────┘
   • Screenshot capture                       • Authentication
   • Browser detection                        • OpenAI Vision analysis
   • Window-title filtering                   • SendGrid email alerts
   • Randomized scheduling                    • Disk storage (user/date)
   • Retry + circuit breaker                  • Daily API-call limits
```

The **client** runs silently on a Windows machine and periodically captures the active browser window. Each screenshot is uploaded to the **server**, which uses OpenAI Vision to determine whether the screen content is related to programming or software development. If it is **not** work-related, an email alert with the screenshot is sent to the configured recipient.

---

## Client

Windows desktop agent that captures, filters, and uploads screenshots.

### Features

| Feature | Description |
|---------|-------------|
| **Browser Detection** | Only captures when a supported browser is active and visible (not minimized) |
| **Allowed Dev Sites** | Skips capture automatically when a known dev site is open (GitHub, Stack Overflow, docs, etc.) |
| **Locked Screen Detection** | Avoids capture when the workstation is locked |
| **Randomized Scheduling** | Capture intervals use a fixed base (mode) with uniform jitter derived from min/max range |
| **Retry + Circuit Breaker** | Exponential backoff on failures; stops hammering after repeated errors |
| **Multi-Monitor Support** | Captures all connected physical monitors |
| **Graceful Shutdown** | Handles Ctrl+C, SIGTERM, logoff, and system shutdown events |

### Supported Browsers

Chrome, Firefox, Edge, Brave, Opera, Vivaldi, Arc, Waterfox, SeaMonkey, Internet Explorer.

### Allowed Dev Sites (no screenshot taken when open)

GitHub, Stack Overflow, docs.python.org, MDN, LeetCode, ChatGPT, OpenAI, vscode.dev, npmjs, PyPI, Docker, Kubernetes, Claude.

### Setup

```bash
cd client
pip install -r requirements.txt
# Create a .env file and fill in: API_BASE_URL, API_KEY, USER_ID
python main.py
```

### Client Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `https://...` | Server URL |
| `API_KEY` | — | Shared authentication key |
| `USER_ID` | — | Identifier for this machine |
| `SCREENSHOT_INTERVAL_MIN` | `1` | Min seconds between captures |
| `SCREENSHOT_INTERVAL_MAX` | `15` | Max seconds between captures |
| `JPEG_QUALITY` | `70` | JPEG compression quality (1–95) |

---

## Server

FastAPI backend that authenticates uploads, runs AI analysis, and sends email alerts.

### Setup

```bash
cd server
pip install -r requirements.txt
# Create a .env file and fill in: API_KEY, ALLOWED_USER_IDS, OPENAI_API_KEY, SENDGRID_API_KEY, EMAIL_RECIPIENT
python main.py
```

### Server Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Bind port |
| `API_KEY` | — | Shared authentication key |
| `ALLOWED_USER_IDS` | — | Comma-separated list of allowed user IDs |
| `SCREENSHOTS_DIR` | `screenshots` | Storage directory |
| `MAX_FILE_SIZE_MB` | `20` | Max upload size |
| `OPENAI_API_KEY` | — | OpenAI API key for image analysis |
| `OPENAI_MODEL` | `gpt-4o` | Vision model to use |
| `OPENAI_MAX_DAILY_CALLS` | `100` | Daily cap on AI analysis calls |
| `SENDGRID_API_KEY` | — | SendGrid API key for email alerts |
| `EMAIL_RECIPIENT` | — | Address to receive off-task alerts |
| `EMAIL_SENDER` | — | Verified SendGrid sender address |
| `EMAIL_SUBJECT` | `Work Monitor - Off-Task Activity Detected` | Email subject line |

---

## Requirements

- **Client:** Windows 10+, Python 3.10+
- **Server:** Any OS, Python 3.10+

### Client Dependencies

APScheduler, mss, Pillow, psutil, requests, python-dotenv

### Server Dependencies

FastAPI, uvicorn, python-multipart, python-dotenv, openai, sendgrid
