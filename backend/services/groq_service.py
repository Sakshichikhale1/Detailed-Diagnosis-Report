from groq import Groq
import json
import base64
import logging
import time
from config import settings

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.GROQ_API_KEY)

# Text-only model chain — tried in order when rate-limited
_TEXT_MODEL_CHAIN = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

# Vision-capable model (supports image inputs via base64)
_VISION_MODEL = "llama-3.2-11b-vision-preview"

# Retry settings for 429 rate-limit errors
_MAX_RETRIES = 3
_RETRY_BACKOFF = 15  # seconds between retries


def _is_rate_limit_error(exc: Exception) -> bool:
    """Returns True if the exception is a 429 / rate-limit error."""
    msg = str(exc)
    return "429" in msg or "rate_limit" in msg.lower() or "rate limit" in msg.lower()


def _parse_json_response(text: str) -> dict | list:
    """
    Tries to parse JSON from the model response.
    Handles cases where the model wraps the JSON in markdown code fences.
    """
    text = text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first and last fence lines
        inner = lines[1:] if lines[0].startswith("```") else lines
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
    return json.loads(text)


def _call_text_with_fallback(prompt: str) -> str:
    """
    Attempts text generation across the model chain.
    Retries up to _MAX_RETRIES times on rate-limit errors before moving to next model.
    Raises the last exception if all models are exhausted.
    """
    last_exc: Exception | None = None

    for model in _TEXT_MODEL_CHAIN:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.info(f"Groq text call: model={model}, attempt={attempt}")
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a property inspection AI assistant. "
                                "Always respond with valid JSON only — no extra text, no markdown fences."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=8192,
                )
                if attempt > 1 or model != _TEXT_MODEL_CHAIN[0]:
                    logger.info(f"Succeeded with model={model} on attempt={attempt}")
                return response.choices[0].message.content

            except Exception as exc:
                last_exc = exc
                if _is_rate_limit_error(exc):
                    if attempt < _MAX_RETRIES:
                        wait = _RETRY_BACKOFF * attempt
                        logger.warning(
                            f"Rate limit hit for {model} (attempt {attempt}/{_MAX_RETRIES}). "
                            f"Retrying in {wait}s…"
                        )
                        time.sleep(wait)
                    else:
                        logger.warning(
                            f"Rate limit exhausted for {model} after {_MAX_RETRIES} retries. "
                            f"Trying next model in chain…"
                        )
                    continue
                else:
                    raise

    raise RuntimeError(
        f"All Groq text models exhausted rate limits or failed. Last error: {last_exc}"
    )


def _call_vision(prompt: str, images_b64: list[dict]) -> str:
    """
    Calls the Groq vision model with text + base64 images.
    Falls back to text-only if vision call fails.
    """
    mime_map = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "bmp": "image/bmp",
    }

    # Build the multimodal message content
    content = []
    for img in images_b64:
        b64_data = img.get("base64", "")
        ext = img.get("ext", "png").lower()
        mime_type = mime_map.get(ext, "image/png")
        if b64_data:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{b64_data}",
                    },
                }
            )

    content.append({"type": "text", "text": prompt})

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.info(f"Groq vision call: model={_VISION_MODEL}, attempt={attempt}, images={len(images_b64)}")
            response = client.chat.completions.create(
                model=_VISION_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a property inspection AI assistant with vision capabilities. "
                            "Always respond with valid JSON only — no extra text, no markdown fences."
                        ),
                    },
                    {"role": "user", "content": content},
                ],
                temperature=0.1,
                max_tokens=8192,
            )
            return response.choices[0].message.content

        except Exception as exc:
            last_exc = exc
            if _is_rate_limit_error(exc):
                if attempt < _MAX_RETRIES:
                    wait = _RETRY_BACKOFF * attempt
                    logger.warning(
                        f"Rate limit hit for vision model (attempt {attempt}/{_MAX_RETRIES}). "
                        f"Retrying in {wait}s…"
                    )
                    time.sleep(wait)
                else:
                    logger.warning("Vision model rate limit exhausted. Raising.")
            else:
                raise

    raise RuntimeError(
        f"Vision model failed after {_MAX_RETRIES} retries. Last error: {last_exc}"
    )


# ─── Public API (drop-in replacements for call_gemini / call_gemini_multimodal) ───


def call_gemini(prompt: str) -> dict | list:
    """
    Text-only LLM call via Groq. Returns parsed JSON.
    Named call_gemini for backward compatibility with engine.py imports.
    """
    try:
        text = _call_text_with_fallback(prompt)
        return _parse_json_response(text)
    except Exception as e:
        logger.exception(f"Groq text call failed: {e}")
        raise


def call_gemini_multimodal(prompt: str, images_b64: list[dict]) -> dict | list:
    """
    Vision LLM call via Groq. Falls back to text-only if vision fails.
    Named call_gemini_multimodal for backward compatibility with engine.py imports.
    """
    if not images_b64:
        return call_gemini(prompt)

    try:
        text = _call_vision(prompt, images_b64)
        return _parse_json_response(text)
    except Exception as e:
        logger.exception(f"Groq vision call failed: {e}")
        logger.warning("Falling back to text-only Groq call.")
        return call_gemini(prompt)
