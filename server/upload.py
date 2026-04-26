"""
Public file-upload endpoint.

Accepts any file behind a fixed API key (no user login required).
The key is read from the UPLOAD_API_KEY environment variable.
Files are saved to an 'uploads/' directory with UUID-based filenames.
"""

import os
import secrets
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UPLOAD_API_KEY: str = os.getenv("UPLOAD_API_KEY", "")
UPLOADS_DIR: Path = Path(__file__).resolve().parent / "uploads"

# Ensure the upload directory exists at import time
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Maximum accepted file size (50 MB)
MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_upload_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    """Reject the request with 403 if the API key is missing or wrong."""
    if not UPLOAD_API_KEY:
        raise HTTPException(status_code=500, detail="Server upload key not configured")
    if not x_api_key or not secrets.compare_digest(x_api_key, UPLOAD_API_KEY):
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


def _safe_extension(filename: str | None) -> str:
    """Extract a sanitized file extension (e.g. '.png'), or empty string."""
    if not filename:
        return ""
    ext = Path(filename).suffix.lower()
    # Only keep simple alphanumeric extensions
    if ext and ext[1:].isalnum() and len(ext) <= 10:
        return ext
    return ""


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/api/v1/upload")
async def upload_file(
    file: UploadFile = File(...),
    x_api_key: str = Header(..., alias="X-API-Key"),
):
    """
    Upload a file with API-key authentication (no user login).

    Headers:
        X-API-Key: the fixed upload key.

    Body (multipart/form-data):
        file: the file to upload.

    Returns:
        JSON with the generated filename and byte size.
    """
    # --- Auth ---
    _verify_upload_key(x_api_key)

    # --- Read & validate ---
    contents = await file.read()

    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(contents)} bytes). Maximum is {MAX_UPLOAD_BYTES} bytes",
        )

    # --- Save with a unique name ---
    ext = _safe_extension(file.filename)
    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOADS_DIR / unique_name

    try:
        dest.write_bytes(contents)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to save file") from exc

    return {
        "status": "ok",
        "filename": unique_name,
        "size_bytes": len(contents),
    }
