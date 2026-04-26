"""
Privacy Monitor Server Configuration
"""

import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# Server Settings
# =============================================================================
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))

# =============================================================================
# Authentication
# =============================================================================
API_KEY: str = os.getenv("API_KEY", "")
ALLOWED_USER_IDS: list[str] = [
    uid.strip()
    for uid in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if uid.strip()
]

# =============================================================================
# Storage
# =============================================================================
SCREENSHOTS_DIR: str = os.getenv("SCREENSHOTS_DIR", "screenshots")
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "20"))

# =============================================================================
# Logging
# =============================================================================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = os.getenv("LOG_FILE", "server.log")

# =============================================================================
# OpenAI Settings
# =============================================================================
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_MAX_DAILY_CALLS: int = int(os.getenv("OPENAI_MAX_DAILY_CALLS", "100"))

OPENAI_IMAGE_CHECK_PROMPT: str = """
You are a workplace productivity monitor that classifies screen content.

Your task: determine whether the screen content is related to programming or software development work.

Programming/work-related content includes:
- Code editors, IDEs, terminals, command prompts
- Technical documentation, Stack Overflow, GitHub, developer forums
- Databases, developer tools, debugging output, build logs
- Design tools used for software development (Figma, draw.io, etc.)
- Professional communication about software (emails, Slack, Jira about dev tasks)

NOT work-related content includes:
- Social media, news, entertainment, video/streaming sites
- Shopping, games, personal messaging unrelated to work
- Any content clearly outside the scope of software development

Decision:
- Return TRUE if the screen is NOT related to programming or software development work.
- Return FALSE if the screen IS related to programming or software development work.

Return ONLY one word: TRUE or FALSE. No explanation, no formatting."""

# =============================================================================
# Email Settings (SendGrid)
# =============================================================================
EMAIL_ENABLED: bool = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
EMAIL_RECIPIENT: str = os.getenv("EMAIL_RECIPIENT", "")
EMAIL_SENDER: str = os.getenv("EMAIL_SENDER", "")
SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
EMAIL_SUBJECT: str = os.getenv("EMAIL_SUBJECT", "Work Monitor - Off-Task Activity Detected")


def validate_config() -> list[str]:
    """Validate required configuration. Returns list of errors."""
    errors = []
    if not API_KEY:
        errors.append("API_KEY is not set")
    if not ALLOWED_USER_IDS:
        errors.append("ALLOWED_USER_IDS is not set (comma-separated list of user IDs)")
    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY is not set - image analysis cannot function")
    if EMAIL_ENABLED:
        if not SENDGRID_API_KEY:
            errors.append("SENDGRID_API_KEY is required when EMAIL_ENABLED=true")
        if not EMAIL_SENDER:
            errors.append("EMAIL_SENDER is required when EMAIL_ENABLED=true")
        if not EMAIL_RECIPIENT:
            errors.append("EMAIL_RECIPIENT is required when EMAIL_ENABLED=true")
    return errors
