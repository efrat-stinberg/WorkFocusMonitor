"""
Screenshot storage - saves uploaded images to disk organized by user and date.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from config import SCREENSHOTS_DIR

logger = logging.getLogger(__name__)

_BASE_DIR = Path(SCREENSHOTS_DIR).resolve()


def save_screenshot(
    user_id: str,
    monitor_number: int,
    image_bytes: bytes,
    metadata: dict,
) -> Path:
    """
    Save a screenshot to disk.

    Storage layout: screenshots/<user_id>/<YYYY-MM-DD>/<timestamp>_monitor_<N>.jpg

    Returns:
        Path to the saved file.
    """
    now = datetime.now()
    date_folder = now.strftime("%Y-%m-%d")
    timestamp_str = now.strftime("%H-%M-%S") + f"_{now.microsecond // 1000:03d}"

    user_dir = (Path(SCREENSHOTS_DIR) / user_id / date_folder).resolve()
    if not str(user_dir).startswith(str(_BASE_DIR)):
        raise ValueError(f"Invalid user directory: {user_dir}")
    user_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{timestamp_str}_monitor_{monitor_number}.jpg"
    filepath = user_dir / filename

    try:
        filepath.write_bytes(image_bytes)
    except OSError as e:
        logger.error(f"Failed to write screenshot: {e}")
        raise
    logger.info(f"Saved screenshot: {filepath} ({len(image_bytes)} bytes)")

    # Save metadata alongside the image
    meta_path = filepath.with_suffix(".json")
    meta_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")

    return filepath
