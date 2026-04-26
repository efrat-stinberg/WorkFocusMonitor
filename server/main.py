"""
Privacy Monitor Server
FastAPI application that receives and stores screenshots from clients.
"""

import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
import uvicorn

from auth import verify_auth
from config import HOST, LOG_FILE, LOG_LEVEL, MAX_FILE_SIZE_MB, PORT, validate_config
from email_sender import EmailSender
from image_analyzer import ImageAnalyzer
from log_receiver import router as log_router
from storage import save_screenshot
from upload import router as upload_router

JPEG_MAGIC = b"\xff\xd8\xff"


# =============================================================================
# Logging
# =============================================================================

def setup_logging() -> logging.Logger:
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # File handler (skipped when LOG_FILE is empty, e.g. on Render/cloud)
    if LOG_FILE:
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


logger = setup_logging()


# =============================================================================
# App
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    errors = validate_config()
    if errors:
        for e in errors:
            logger.error(f"Config: {e}")
        raise RuntimeError("Server configuration invalid: " + "; ".join(errors))
    app.state.image_analyzer = ImageAnalyzer()
    app.state.email_sender = EmailSender()
    if os.getenv("RENDER"):
        logger.warning("Running on Render — local file storage is ephemeral. "
                        "Screenshots and uploads will be lost on redeploy.")
    logger.info(f"Privacy Monitor Server starting on {HOST}:{PORT}")
    yield
    logger.info("Privacy Monitor Server shutting down")


app = FastAPI(
    title="Privacy Monitor Server",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(upload_router)
app.include_router(log_router)


# =============================================================================
# Routes
# =============================================================================

@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/v1/screenshot")
async def upload_screenshot(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    monitor_number: str = Form(...),
    metadata: str = Form("{}"),
    user_id: str = Depends(verify_auth),
):
    """
    Receive a screenshot from a client.

    Expects multipart form data:
      - file: JPEG image
      - monitor_number: monitor index (string)
      - metadata: JSON string with capture metadata
    """
    # Read and validate size
    image_bytes = await file.read()
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(image_bytes)} bytes). Max: {max_bytes} bytes",
        )

    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    # Validate JPEG magic bytes
    if not image_bytes[:3] == JPEG_MAGIC:
        raise HTTPException(status_code=400, detail="File is not a valid JPEG image")

    # Validate metadata size
    if len(metadata) > 10_000:
        raise HTTPException(status_code=400, detail="Metadata too large")

    # Parse metadata
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid metadata JSON")

    # Parse and bound monitor number
    try:
        mon_num = int(monitor_number)
    except ValueError:
        raise HTTPException(status_code=400, detail="monitor_number must be an integer")
    if not (0 <= mon_num <= 20):
        raise HTTPException(status_code=400, detail="monitor_number out of range")

    # Store
    meta["user_id"] = user_id
    save_screenshot(
        user_id=user_id,
        monitor_number=mon_num,
        image_bytes=image_bytes,
        metadata=meta,
    )

    logger.info(f"Screenshot received from user={user_id} monitor={mon_num}")

    # Defer heavy work (OpenAI analysis + email) to a background task
    # so the client gets an immediate 200 response and doesn't time out.
    background_tasks.add_task(
        _analyze_and_notify,
        request.app,
        image_bytes,
        meta,
        user_id,
        mon_num,
    )

    return {"status": "ok"}


def _analyze_and_notify(app, image_bytes: bytes, meta: dict, user_id: str, mon_num: int):
    """Background task: run OpenAI analysis and send email if appropriate."""
    try:
        analyzer = app.state.image_analyzer
        is_appropriate = False
        if analyzer:
            logger.info(f"Analyzing screenshot from user={user_id} monitor={mon_num}...")
            is_appropriate = analyzer.is_appropriate(image_bytes)
        else:
            logger.warning("Image analyzer not available - skipping analysis")

        sender = app.state.email_sender
        if is_appropriate and sender:
            logger.info(f"Image appropriate - sending email alert for user={user_id} monitor={mon_num}")
            email_sent = sender.send_screenshot(
                image_bytes=image_bytes,
                monitor_number=mon_num,
                timestamp=meta.get("timestamp"),
                user_id=user_id,
            )
            if email_sent:
                logger.info(f"Email sent for user={user_id} monitor={mon_num}")
            else:
                logger.warning(f"Failed to send email for user={user_id} monitor={mon_num}")
        elif not is_appropriate:
            logger.info(f"Image not appropriate or analysis failed - no email for user={user_id} monitor={mon_num}")
    except Exception as e:
        logger.error(f"Background analysis/notify failed for user={user_id} monitor={mon_num}: {e}", exc_info=True)


# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
