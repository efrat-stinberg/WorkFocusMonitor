"""
Client Service Configuration
Centralized management of all settings and constants.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# Server Settings
# =============================================================================
API_BASE_URL: str = os.getenv("API_BASE_URL", "https://privacymonitor.onrender.com")
API_KEY: str = os.getenv("API_KEY", "")
USER_ID: str = os.getenv("USER_ID", "")

# =============================================================================
# Screenshot Settings
# =============================================================================
SCREENSHOT_INTERVAL_MIN: float = float(os.getenv("SCREENSHOT_INTERVAL_MIN", "1"))
SCREENSHOT_INTERVAL_MAX: float = float(os.getenv("SCREENSHOT_INTERVAL_MAX", "15"))
SCREENSHOT_INTERVAL_MODE: float = float(os.getenv("SCREENSHOT_INTERVAL_MODE", "12"))
JPEG_QUALITY: int = int(os.getenv("JPEG_QUALITY", "70"))

# =============================================================================
# Browser Detection
# =============================================================================
BROWSER_PROCESSES: list[str] = [
    # Windows
    "chrome.exe",
    "firefox.exe",
    "msedge.exe",
    "brave.exe",
    "opera.exe",
    "iexplore.exe",
    "vivaldi.exe",
    "arc.exe",
    "waterfox.exe",
    "seamonkey.exe",
]

# Window titles to skip (case-insensitive substring match)
# Includes privacy-sensitive sites AND approved programming/dev sites
SKIP_WINDOW_TITLES: list[str] = [
    # Privacy-sensitive sites (existing)
    "gmail",
    "github",
    "stackoverflow",
    "docs.python",
    "mozilla",
    "leetcode",
    "chatgpt",
    "openai",
    "vscode.dev",
    "npmjs",
    "pypi",
    "docker",
    "kubernetes",
    "claude",
]

# =============================================================================
# Retry Settings
# =============================================================================
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF_FACTOR: int = int(os.getenv("RETRY_BACKOFF_FACTOR", "2"))
REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))

# Circuit breaker: stop hammering a dead server
CIRCUIT_BREAKER_THRESHOLD: int = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5"))
CIRCUIT_BREAKER_TIMEOUT: int = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "300"))  # seconds

# =============================================================================
# Logging Settings
# =============================================================================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = os.getenv("LOG_FILE", "client.log")
LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_MAX_BYTES: int = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10 MB
LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))


# =============================================================================
# Configuration Validation
# =============================================================================

def validate_config() -> tuple[list[str], list[str]]:
    """
    Validate configuration at startup.

    Returns:
        Tuple of (errors, warnings). Errors are fatal.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if API_BASE_URL and not API_BASE_URL.startswith("https://"):
        if "localhost" not in API_BASE_URL and "127.0.0.1" not in API_BASE_URL:
            warnings.append(
                f"API_BASE_URL uses insecure HTTP ({API_BASE_URL}). "
                "Use HTTPS in production to protect screenshot data in transit."
            )

    if SCREENSHOT_INTERVAL_MIN >= SCREENSHOT_INTERVAL_MAX:
        errors.append(
            f"SCREENSHOT_INTERVAL_MIN ({SCREENSHOT_INTERVAL_MIN}) must be less than "
            f"SCREENSHOT_INTERVAL_MAX ({SCREENSHOT_INTERVAL_MAX})"
        )

    if not (SCREENSHOT_INTERVAL_MIN <= SCREENSHOT_INTERVAL_MODE <= SCREENSHOT_INTERVAL_MAX):
        warnings.append(
            f"SCREENSHOT_INTERVAL_MODE ({SCREENSHOT_INTERVAL_MODE}) should be between "
            f"MIN ({SCREENSHOT_INTERVAL_MIN}) and MAX ({SCREENSHOT_INTERVAL_MAX})"
        )

    return errors, warnings
