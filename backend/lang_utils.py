"""
lang_utils.py - Shared language detection utilities.

Used by generator, information_gatherer, and query_analyzer nodes to detect
the language of the user's query so the LLM can respond in the same language.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ISO 639-1 code → human-readable language name for LLM prompt injection.
# Covers all 22 scheduled Indian languages + English.
LANGUAGE_NAMES: dict = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "te": "Telugu",
    "mr": "Marathi",
    "ta": "Tamil",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
    "as": "Assamese",
    "ur": "Urdu",
    "ne": "Nepali",
    "sa": "Sanskrit",
    "sd": "Sindhi",
    "ks": "Kashmiri",
    "mai": "Maithili",
    "kok": "Konkani",
    "mni": "Manipuri",
    "doi": "Dogri",
    "bho": "Bhojpuri",
    "raj": "Rajasthani",
    "awa": "Awadhi",
}


def detect_language(text: str) -> str:
    """
    Detect the ISO 639-1 language code of *text*.

    Returns the detected code (e.g. "hi" for Hindi) or "en" if
    detection fails or the text is too short to be reliable.
    """
    if not text or len(text.strip()) < 5:
        return "en"

    try:
        from langdetect import detect, LangDetectException
        code = detect(text)
        logger.debug(f"[lang_utils] detected language: {code!r} for text: {text[:60]!r}")
        return code
    except Exception as e:
        logger.warning(f"[lang_utils] language detection failed: {e}")
        return "en"


def get_language_name(code: str) -> str:
    """Return a human-readable name for *code*, falling back to the code itself."""
    return LANGUAGE_NAMES.get(code, code.upper())


def build_language_instruction(detected_code: str) -> str:
    """
    Return a concise instruction string to inject into LLM prompts so the
    model responds in the same language as the user query.

    Returns an empty string when the detected language is English (default).
    """
    if detected_code == "en":
        return ""

    lang_name = get_language_name(detected_code)
    return (
        f"\n\nCRITICAL LANGUAGE INSTRUCTION: The user's query is written in {lang_name}. "
        f"You MUST respond ENTIRELY in {lang_name}. "
        f"Do NOT switch to English at any point. "
        f"Legal terms may be briefly clarified in brackets, but the response body must be in {lang_name}."
    )
