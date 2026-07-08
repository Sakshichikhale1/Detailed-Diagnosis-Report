from google import genai
from google.genai import types
import json
import base64
import logging
import time
from config import settings

logger = logging.getLogger(__name__)

client = genai.Client(api_key=settings.GEMINI_API_KEY)

# Fallback model chain — tried in order when quota is exhausted
_MODEL_CHAIN = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

# Retry settings for 429 rate-limit errors
_MAX_RETRIES = 3
_RETRY_BACKOFF = 20  # seconds between retries


def _is_quota_error(exc: Exception) -> bool:
    """Returns True if the exception is a 429 / RESOURCE_EXHAUSTED error."""
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()


def _generate_with_fallback(contents, config: types.GenerateContentConfig) -> str:
    """
    Attempts generation across the model chain.
    For each model it retries up to _MAX_RETRIES times on 429 errors
    before moving on to the next model in the chain.
    Raises the last exception if all models are exhausted.
    """
    last_exc: Exception | None = None

    for model in _MODEL_CHAIN:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.info(f"Gemini call: model={model}, attempt={attempt}")
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                if attempt > 1 or model != _MODEL_CHAIN[0]:
                    logger.info(f"Succeeded with model={model} on attempt={attempt}")
                return response.text

            except Exception as exc:
                last_exc = exc
                if _is_quota_error(exc):
                    if attempt < _MAX_RETRIES:
                        wait = _RETRY_BACKOFF * attempt
                        logger.warning(
                            f"Quota exceeded for {model} (attempt {attempt}/{_MAX_RETRIES}). "
                            f"Retrying in {wait}s…"
                        )
                        time.sleep(wait)
                    else:
                        logger.warning(
                            f"Quota exhausted for {model} after {_MAX_RETRIES} retries. "
                            f"Trying next model in chain…"
                        )
                    continue  # retry or next model
                else:
                    # Non-quota error — don't retry, raise immediately
                    raise

    raise RuntimeError(
        f"All Gemini models exhausted quota or failed. Last error: {last_exc}"
    )


def call_gemini(prompt: str) -> dict | list:
    """
    Calls Gemini with a text-only prompt and returns parsed JSON.
    Automatically retries on 429 and falls back through the model chain.
    """
    try:
        config = types.GenerateContentConfig(response_mime_type="application/json")
        text = _generate_with_fallback(contents=prompt, config=config)
        return json.loads(text)
    except Exception as e:
        logger.exception(f"Gemini text call failed: {e}")
        raise


def call_gemini_multimodal(prompt: str, images_b64: list[dict]) -> dict | list:
    """
    Calls Gemini with a text prompt AND a list of base64-encoded images.
    Each item in images_b64 should be: {"base64": "...", "ext": "png"}
    Returns parsed JSON. Falls back to text-only if multimodal fails.
    """
    try:
        parts = []
        mime_map = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
            "bmp": "image/bmp",
        }

        for img in images_b64:
            b64_data = img.get("base64", "")
            ext = img.get("ext", "png").lower()
            mime_type = mime_map.get(ext, "image/png")
            if b64_data:
                parts.append(
                    types.Part.from_bytes(
                        data=base64.b64decode(b64_data),
                        mime_type=mime_type,
                    )
                )

        parts.append(types.Part.from_text(text=prompt))

        config = types.GenerateContentConfig(response_mime_type="application/json")
        contents = types.Content(parts=parts, role="user")
        text = _generate_with_fallback(contents=contents, config=config)
        return json.loads(text)

    except Exception as e:
        logger.exception(f"Gemini multimodal call failed: {e}")
        logger.warning("Falling back to text-only Gemini call.")
        return call_gemini(prompt)