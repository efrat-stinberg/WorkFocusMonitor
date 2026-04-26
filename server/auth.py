"""
Authentication middleware for API key and user ID validation.
"""

import logging
import secrets

from fastapi import Header, HTTPException

from config import API_KEY, ALLOWED_USER_IDS

logger = logging.getLogger(__name__)


def _sanitize_for_log(value: str, max_len: int = 100) -> str:
    """Strip control characters and truncate for safe logging."""
    return value.replace("\n", "").replace("\r", "").replace("\x1b", "")[:max_len]


async def verify_auth(
    x_api_key: str = Header(..., alias="X-API-Key"),
    x_user_id: str = Header(..., alias="X-User-Id"),
) -> str:
    """
    Validate API key and user ID from request headers.

    Returns:
        The validated user_id.

    Raises:
        HTTPException 401 if API key is invalid.
        HTTPException 403 if user ID is not allowed.
    """
    if not x_api_key or not secrets.compare_digest(x_api_key, API_KEY):
        logger.warning("Invalid API key attempt")
        raise HTTPException(status_code=401, detail="Invalid API key")

    if ALLOWED_USER_IDS and x_user_id not in ALLOWED_USER_IDS:
        logger.warning(f"Unauthorized user ID: {_sanitize_for_log(x_user_id)}")
        raise HTTPException(status_code=403, detail="User not authorized")

    return x_user_id
