"""
Log Receiver Module
FastAPI router that accepts and serves log entries from remote clients.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth import verify_auth

logger = logging.getLogger(__name__)

# File where received client logs are appended
CLIENT_LOG_FILE = os.getenv("CLIENT_LOG_FILE", "server.log")

router = APIRouter()


class LogEntry(BaseModel):
    """Schema for incoming log entries from clients."""
    level: str = Field(..., max_length=20)
    message: str = Field(..., max_length=5000)
    client_id: str = Field(..., max_length=200)


# Valid log level names
_VALID_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


@router.post("/api/logs")
async def receive_log(entry: LogEntry, _user_id: str = Depends(verify_auth)):
    """
    Receive a log entry from a client and append it to the server log file.

    The log is written in the format:
        [timestamp] [client_id] [level] message
    """
    # Validate log level
    level = entry.level.upper().strip()
    if level not in _VALID_LEVELS:
        raise HTTPException(status_code=400, detail="Invalid log level")

    # Sanitize inputs to prevent log injection (strip newlines / control chars)
    client_id = entry.client_id.replace("\n", "").replace("\r", "").replace("\x00", "")
    message = entry.message.replace("\n", " ").replace("\r", "").replace("\x00", "")

    # Build formatted log line
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{client_id}] [{level}] {message}\n"

    try:
        with open(CLIENT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line)
    except OSError as e:
        logger.error("Failed to write client log to %s: %s", CLIENT_LOG_FILE, e)
        raise HTTPException(status_code=500, detail="Failed to store log entry")

    return {"status": "ok"}


@router.get("/api/logs")
async def get_logs(
    _user_id: str = Depends(verify_auth),
    lines: int = Query(100, ge=1, le=5000, description="Number of most recent lines to return"),
    level: Optional[str] = Query(None, description="Filter by log level (e.g. ERROR)"),
    client_id: Optional[str] = Query(None, description="Filter by client_id"),
):
    """
    Retrieve the most recent client log entries from the server log file.

    Supports optional filtering by level and client_id.
    Returns the last N lines (default 100).
    """
    if not os.path.isfile(CLIENT_LOG_FILE):
        return {"logs": [], "total": 0}

    try:
        with open(CLIENT_LOG_FILE, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
    except OSError as e:
        logger.error("Failed to read log file %s: %s", CLIENT_LOG_FILE, e)
        raise HTTPException(status_code=500, detail="Failed to read log file")

    # Optional filtering
    if level:
        level_upper = level.upper().strip()
        all_lines = [ln for ln in all_lines if f"[{level_upper}]" in ln]

    if client_id:
        all_lines = [ln for ln in all_lines if f"[{client_id}]" in ln]

    # Return the last N lines
    recent = all_lines[-lines:]

    return {"logs": [ln.rstrip("\n") for ln in recent], "total": len(recent)}
