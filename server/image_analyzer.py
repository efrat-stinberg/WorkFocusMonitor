"""
Image Analyzer Module
Uses OpenAI Vision API to analyze screenshots for appropriateness.
"""

import base64
import logging
import threading
from datetime import date

from openai import APIConnectionError, AuthenticationError, OpenAI, RateLimitError

from config import OPENAI_API_KEY, OPENAI_MAX_DAILY_CALLS, OPENAI_MODEL, OPENAI_IMAGE_CHECK_PROMPT

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """
    Analyzes images using OpenAI's Vision API to determine appropriateness.
    """

    def __init__(self):
        """Initialize the OpenAI client."""
        if not OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured - image analysis will be disabled")
            self.client = None
        else:
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        self._daily_calls = 0
        self._last_reset_date = date.today()
        self._lock = threading.Lock()

    def _image_to_base64(self, image_bytes: bytes) -> str:
        """Convert image bytes to base64 string."""
        return base64.b64encode(image_bytes).decode("utf-8")

    def is_appropriate(self, image_bytes: bytes) -> bool:
        """
        Analyze image to determine if it's appropriate.

        Returns:
            True if image is appropriate, False otherwise.
            Returns False if API is not configured (fail-closed).
        """
        if not self.client:
            logger.warning("OpenAI client not initialized - defaulting to not appropriate")
            return False

        # Rate limiting: reset counter daily, reject if over limit (thread-safe)
        with self._lock:
            today = date.today()
            if today != self._last_reset_date:
                self._daily_calls = 0
                self._last_reset_date = today
            if self._daily_calls >= OPENAI_MAX_DAILY_CALLS:
                logger.warning(f"OpenAI daily call limit reached ({OPENAI_MAX_DAILY_CALLS}) - skipping analysis")
                return False
            self._daily_calls += 1

        try:
            image_base64 = self._image_to_base64(image_bytes)
            logger.debug("Sending image to OpenAI for analysis...")

            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": OPENAI_IMAGE_CHECK_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}",
                                    "detail": "low",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=10,
            )

            result_text = response.choices[0].message.content.strip().lower()
            logger.debug(f"OpenAI response: {result_text}")

            if "true" in result_text:
                logger.info("Image analysis: APPROPRIATE")
                return True
            elif "false" in result_text:
                logger.info("Image analysis: NOT APPROPRIATE")
                return False
            else:
                logger.warning(f"Unexpected OpenAI response: {result_text} - defaulting to not appropriate")
                return False

        except AuthenticationError:
            logger.critical("OpenAI API key is invalid - disabling image analysis")
            self.client = None
            return False
        except (APIConnectionError, RateLimitError) as e:
            logger.warning(f"OpenAI transient error: {e}")
            return False
        except Exception as e:
            logger.error(f"OpenAI image analysis failed: {type(e).__name__}: {e}", exc_info=True)
            return False
