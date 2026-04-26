"""
Client Service Main Entry Point
Manages scheduling and orchestrates screenshot capture, processing, and sending.
"""

import atexit
import ctypes
import io
import logging
import signal
import sys
import threading
from datetime import datetime

import psutil
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from api_client import APIClient
from config import (
    BROWSER_PROCESSES,
    JPEG_QUALITY,
    LOG_FORMAT,
    LOG_LEVEL,
    SCREENSHOT_INTERVAL_MAX,
    SCREENSHOT_INTERVAL_MIN,
    SCREENSHOT_INTERVAL_MODE,
    SKIP_WINDOW_TITLES,
    validate_config,
)
from logger import ServerLogHandler
from screenshot import ScreenshotCapture

# =============================================================================
# Logging Configuration
# =============================================================================

def setup_logging() -> logging.Logger:
    """
    Configure logging for the application.
    
    Sets up a console handler for local visibility and a remote server
    handler that sends all logs to the server for centralised storage.
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT)
    
    # Console handler - display in stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Remote server handler - send all logs to the server
    server_handler = ServerLogHandler()
    server_handler.setLevel(logging.DEBUG)
    server_handler.setFormatter(formatter)
    logger.addHandler(server_handler)
    
    return logger


# Initialize logging
logger = setup_logging()

# =============================================================================
# Shutdown Tracking
# =============================================================================

# Track the reason for shutdown
_shutdown_reason: str = "unknown"
_shutdown_lock = threading.Lock()

# =============================================================================
# Core Functions
# =============================================================================

def get_foreground_window_info() -> tuple[str | None, str | None, bool]:
    """
    Get the process name, title, and visibility state of the current foreground window.
    
    Uses Windows API to determine which window is currently active
    and retrieves its associated process name, window title, and whether it's visible.
    
    Returns:
        Tuple of (process_name, window_title, is_visible), or (None, None, False) if unavailable
    """
    if sys.platform != 'win32':
        logger.debug("Foreground window detection only supported on Windows")
        return None, None, False
    
    try:
        user32 = ctypes.windll.user32
        
        # Get the foreground window handle
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            logger.debug("No foreground window found")
            return None, None, False
        
        # Check if window is minimized (IsIconic returns non-zero if minimized)
        is_minimized = user32.IsIconic(hwnd) != 0
        
        # Check if window is visible
        is_window_visible = user32.IsWindowVisible(hwnd) != 0
        
        # Window is considered "visible in foreground" only if not minimized and visible
        is_visible = is_window_visible and not is_minimized
        
        if is_minimized:
            logger.debug("Foreground window is minimized")
        
        # Get window title
        title_length = user32.GetWindowTextLengthW(hwnd) + 1
        title_buffer = ctypes.create_unicode_buffer(title_length)
        user32.GetWindowTextW(hwnd, title_buffer, title_length)
        window_title = title_buffer.value
        
        # Get process ID from window handle
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        if not pid.value:
            logger.debug("Could not get process ID for foreground window")
            return None, window_title, is_visible
        
        # Get process name from PID
        try:
            process = psutil.Process(pid.value)
            process_name = process.name()
            return process_name, window_title, is_visible
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            logger.debug(f"Could not get process name for PID {pid.value}")
            return None, window_title, is_visible
            
    except Exception as e:
        logger.error(f"Error getting foreground window info: {e}")
        return None, None, False


def is_browser_in_foreground() -> tuple[bool, str | None]:
    """
    Check if the current foreground window is a browser and is visible (not minimized).
    
    Returns:
        Tuple of (is_browser, window_title)
        - is_browser: True if a browser is visible in the foreground (not minimized)
        - window_title: The title of the foreground window (or None)
    """
    process_name, window_title, is_visible = get_foreground_window_info()
    
    if not process_name:
        logger.debug("Could not determine foreground process")
        return False, window_title
    
    # Check if the window is actually visible (not minimized)
    if not is_visible:
        logger.debug(f"Foreground window is minimized or not visible: {process_name}")
        return False, window_title
    
    # Check if the process is a known browser
    browser_names = {name.lower() for name in BROWSER_PROCESSES}
    is_browser = process_name.lower() in browser_names
    
    if is_browser:
        logger.debug(f"Browser visible in foreground: {process_name} - '{window_title}'")
    else:
        logger.debug(f"Non-browser in foreground: {process_name}")
    
    return is_browser, window_title


def should_skip_window_title(window_title: str | None) -> bool:
    """
    Check if the window title matches any skip patterns.
    
    Args:
        window_title: The title of the window to check
        
    Returns:
        True if the capture should be skipped, False otherwise
    """
    if not window_title:
        return False
    
    title_lower = window_title.lower()
    
    for skip_pattern in SKIP_WINDOW_TITLES:
        if skip_pattern.lower() in title_lower:
            logger.info(f"Skipping capture: window title contains '{skip_pattern}'")
            return True
    
    return False


def capture_and_send(screenshot_capture, api_client) -> None:
    """
    Main function executed by the scheduler.
    
    Captures screenshots from all monitors and sends them to the server.
    """
    timestamp = datetime.now().isoformat()
    logger.info(f"Starting capture process at {timestamp}")
    
    # Step 1: Check if browser is in the foreground (not minimized)
    is_browser, window_title = is_browser_in_foreground()
    
    if not is_browser:
        logger.info("No browser in foreground, skipping capture")
        return
    
    logger.debug(f"Browser detected in foreground with title: '{window_title}'")
    
    # Step 2: Check if window title should be skipped (Gmail, Bank, etc.)
    if should_skip_window_title(window_title):
        logger.debug("Window title matched skip pattern, skipping capture")
        return
    
    # Step 3: Capture screenshots
    logger.info("Browser is active and title is allowed - proceeding with capture")
    screenshots = screenshot_capture.capture_all_screens()
    
    if not screenshots:
        logger.warning("No screenshots captured")
        return
    
    logger.info(f"Captured {len(screenshots)} screenshot(s)")
    
    # Step 3: Process and send each screenshot
    success_count = 0
    fail_count = 0
    
    for screenshot_info in screenshots:
        monitor_number = screenshot_info["monitor_number"]
        
        try:
            # Get image and compress directly (OCR disabled)
            image = screenshot_info["image"]
            
            # Compress image to JPEG bytes
            buffer = io.BytesIO()
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGB")
            image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            image_bytes = buffer.getvalue()
            
            metadata = {
                "monitor_number": monitor_number,
                "width": screenshot_info["width"],
                "height": screenshot_info["height"],
                "timestamp": timestamp,
                "left": screenshot_info["left"],
                "top": screenshot_info["top"],
            }
            
            # Send to server
            success = api_client.send_screenshot(
                image_bytes=image_bytes,
                metadata=metadata,
                monitor_number=monitor_number
            )
            
            if success:
                success_count += 1
            else:
                fail_count += 1
                
        except Exception as e:
            logger.error(
                f"Error processing monitor {monitor_number}: "
                f"{type(e).__name__}: {e}"
            )
            fail_count += 1
            continue
    
    # Step 4: Log summary
    logger.info(
        f"Capture complete: {success_count} succeeded, {fail_count} failed "
        f"out of {len(screenshots)} monitors"
    )


# =============================================================================
# Signal and Shutdown Handlers
# =============================================================================

def _set_shutdown_reason(reason: str) -> None:
    """Set the shutdown reason for logging."""
    global _shutdown_reason
    with _shutdown_lock:
        _shutdown_reason = reason


def _log_shutdown() -> None:
    """Log shutdown message with the appropriate reason."""
    with _shutdown_lock:
        reason = _shutdown_reason
    reason_messages = {
        "system_shutdown": "Service shutting down due to system shutdown",
        "system_logoff": "Service shutting down due to user logoff",
        "ctrl_c": "Service stopped via Ctrl+C (keyboard interrupt)",
        "ctrl_break": "Service stopped via Ctrl+Break",
        "console_close": "Service stopped via console window close",
        "signal_term": "Service stopped via SIGTERM signal (CMD/task kill)",
        "signal_int": "Service stopped via SIGINT signal",
        "task_manager": "Service stopped via Windows Task Manager or taskkill",
    }
    logger.info(reason_messages.get(reason, f"Service stopped (reason: {reason})"))
    logger.info("Privacy Monitor Client Service terminated")


def _signal_handler(signum: int, frame) -> None:
    """Handle Unix-style signals (SIGTERM, SIGINT, etc.)."""
    signal_names = {
        signal.SIGTERM: "signal_term",
        signal.SIGINT: "signal_int",
    }
    # On Windows, SIGBREAK is available
    if hasattr(signal, 'SIGBREAK'):
        signal_names[signal.SIGBREAK] = "ctrl_break"
    
    reason = signal_names.get(signum, f"signal_{signum}")
    _set_shutdown_reason(reason)
    logger.info(f"Received signal {signum}, initiating shutdown...")
    sys.exit(0)


def _setup_signal_handlers() -> None:
    """Set up signal handlers for graceful shutdown."""
    # Standard signals
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    
    # Windows-specific SIGBREAK (Ctrl+Break)
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, _signal_handler)


def _windows_console_ctrl_handler(ctrl_type: int) -> bool:
    """
    Handle Windows console control events.
    
    Args:
        ctrl_type: The type of control event:
            0 = CTRL_C_EVENT
            1 = CTRL_BREAK_EVENT
            2 = CTRL_CLOSE_EVENT
            5 = CTRL_LOGOFF_EVENT
            6 = CTRL_SHUTDOWN_EVENT
    
    Returns:
        True to indicate the event was handled
    """
    ctrl_type_names = {
        0: "ctrl_c",
        1: "ctrl_break",
        2: "console_close",
        5: "system_logoff",
        6: "system_shutdown",
    }
    
    reason = ctrl_type_names.get(ctrl_type, f"windows_ctrl_{ctrl_type}")
    _set_shutdown_reason(reason)
    
    # Log immediately for shutdown/logoff events as we may not get atexit
    if ctrl_type in (5, 6):  # LOGOFF or SHUTDOWN
        _log_shutdown()
    
    return True  # Indicate we handled the event


def _setup_windows_console_handler() -> None:
    """Set up Windows console control handler for shutdown events."""
    if sys.platform != 'win32':
        return
    
    try:
        # Define the handler function type
        HANDLER_ROUTINE = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)
        
        # Create a handler that won't be garbage collected
        handler = HANDLER_ROUTINE(_windows_console_ctrl_handler)
        
        # Store reference to prevent garbage collection
        _setup_windows_console_handler._handler = handler
        
        # Register the handler
        kernel32 = ctypes.windll.kernel32
        if not kernel32.SetConsoleCtrlHandler(handler, True):
            logger.warning("Failed to set Windows console control handler")
        else:
            logger.debug("Windows console control handler registered")
            
    except Exception as e:
        logger.warning(f"Could not set up Windows console handler: {e}")


def main() -> None:
    """
    Application entry point.
    
    Sets up the scheduler and starts the capture loop.
    """
    # Platform guard
    if sys.platform != "win32":
        logger.error("This application requires Windows (uses Win32 API).")
        sys.exit(1)

    # Validate configuration before starting
    errors, warnings = validate_config()
    for warning in warnings:
        logger.warning(f"Config: {warning}")
    if errors:
        for error in errors:
            logger.error(f"Config: {error}")
        logger.error("Configuration validation failed. Exiting.")
        sys.exit(1)

    # Register shutdown logging via atexit
    atexit.register(_log_shutdown)
    
    # Set up signal handlers
    _setup_signal_handlers()
    
    # Set up Windows-specific console handler
    _setup_windows_console_handler()

    # Create service instances
    screenshot_capture = ScreenshotCapture()
    api_client = APIClient()
    
    logger.info("=" * 60)
    logger.info("Privacy Monitor Client Service Starting")
    logger.info(f"Screenshot interval: random {SCREENSHOT_INTERVAL_MIN}-{SCREENSHOT_INTERVAL_MAX} min (mode={SCREENSHOT_INTERVAL_MODE})")
    logger.info("=" * 60)
    
    # Create scheduler
    scheduler = BlockingScheduler()

    # Use IntervalTrigger with jitter for stable, random-ish scheduling.
    # The base interval is the mode (most likely value), and jitter adds
    # uniform randomness of +/- jitter seconds around it.
    # This avoids the fragile pattern of removing and re-adding jobs.
    base_interval_sec = SCREENSHOT_INTERVAL_MODE * 60
    jitter_sec = int((SCREENSHOT_INTERVAL_MAX - SCREENSHOT_INTERVAL_MIN) / 2 * 60)

    def _job_wrapper() -> None:
        """Wrapper that logs execution boundaries around capture_and_send."""
        logger.info("Job started")
        capture_and_send(screenshot_capture, api_client)
        # Log next scheduled run time
        job = scheduler.get_job("screenshot_job")
        if job and job.next_run_time:
            logger.info(f"Next capture scheduled at {job.next_run_time.strftime('%H:%M:%S')}")
        logger.info("Job finished")

    scheduler.add_job(
        func=_job_wrapper,
        trigger=IntervalTrigger(seconds=base_interval_sec, jitter=jitter_sec),
        id="screenshot_job",
        name="Capture and Send Screenshots",
        replace_existing=True,
        misfire_grace_time=None,  # Always run missed jobs (e.g. after sleep/wake)
        coalesce=True,            # If multiple runs were missed, run only once
    )

    logger.info("Scheduler configured successfully")

    # Run first capture immediately (before the first interval elapses)
    logger.info("Running initial capture...")
    capture_and_send(screenshot_capture, api_client)
    job = scheduler.get_job("screenshot_job")
    if job and job.next_run_time:
        logger.info(f"Next capture scheduled at {job.next_run_time.strftime('%H:%M:%S')}")
    
    # Start the scheduler (blocking - runs forever)
    try:
        logger.info("Starting scheduler (press Ctrl+C to stop)...")
        scheduler.start()
    except KeyboardInterrupt:
        _set_shutdown_reason("ctrl_c")
        logger.info("Received keyboard interrupt")
        scheduler.shutdown(wait=False)
    except SystemExit:
        # Normal exit via signal handler
        scheduler.shutdown(wait=False)
    except Exception as e:
        _set_shutdown_reason(f"error: {e}")
        logger.error(f"Scheduler error: {e}")
        scheduler.shutdown(wait=False)
        raise


if __name__ == "__main__":
    main()
