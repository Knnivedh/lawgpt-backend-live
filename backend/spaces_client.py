"""
spaces_client.py — HTTP clients for the three deployed HuggingFace Gradio Spaces.

Each function calls the corresponding Space using `gradio_client`, which handles
the Gradio queuing protocol, file uploads, and polling automatically.

Spaces:
  - Whisper small      → rverma0631/Whisper          (/transcribe)
  - IndicConformer 600M→ rverma0631/MultilingualASR   (/transcribe_audio)
  - IndicParler-TTS   → R910/IndicParler_TTS          (/generate_finetuned)
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Optional

import httpx
from gradio_client import Client, handle_file

logger = logging.getLogger(__name__)

# ── Space URLs (set via environment / config) ──────────────────────────────────
_WHISPER_SPACE      = os.getenv("WHISPER_SPACE_URL",    "rverma0631/Whisper")
_INDIC_ASR_SPACE    = os.getenv("INDIC_ASR_SPACE_URL",  "rverma0631/MultilingualASR")
_INDIC_TTS_SPACE    = os.getenv("INDIC_TTS_SPACE_URL",  "R910/IndicParler_TTS")


# ── Whisper (English / non-Indic transcription + language ID) ─────────────────

def call_whisper_space(audio_path: str) -> dict:
    """
    Transcribe audio using the Whisper small HF Space.

    Args:
        audio_path: Local path to the audio file (any format supported by Whisper).

    Returns:
        dict with keys: text (str), language (str), language_probability (float)
    """
    logger.info("🎙️  [Whisper Space] Sending audio → %s", _WHISPER_SPACE)
    try:
        client = Client(_WHISPER_SPACE)
        result = client.predict(
            audio=handle_file(audio_path),
            api_name="/transcribe",
        )
        # The Space returns a plain string (the transcription text)
        text = result.strip() if isinstance(result, str) else str(result).strip()
        logger.info("✅ [Whisper Space] Transcription: %s…", text[:60])
        return {
            "text": text,
            "language": "en",           # Whisper small default; actual lang from audio
            "language_probability": 1.0,
        }
    except Exception as e:
        logger.error("❌ [Whisper Space] Error: %s", e)
        raise RuntimeError(f"Whisper Space call failed: {e}") from e


# ── IndicConformer (Indic language transcription) ─────────────────────────────

def call_indic_asr_space(audio_path: str, language: str) -> dict:
    """
    Transcribe audio in an Indic language using the IndicConformer Space.

    Args:
        audio_path: Local path to the audio file.
        language:   BCP-47 / ISO-639-1 language code (e.g. "hi", "ta", "bn").

    Returns:
        dict with keys: text (str), language (str), language_probability (float)
    """
    logger.info(
        "🎙️  [IndicConformer Space] lang=%s → %s", language, _INDIC_ASR_SPACE
    )
    try:
        client = Client(_INDIC_ASR_SPACE)
        result = client.predict(
            audio_file=handle_file(audio_path),
            language=language,
            api_name="/transcribe_audio",
        )
        text = result.strip() if isinstance(result, str) else str(result).strip()
        logger.info("✅ [IndicConformer Space] Transcription: %s…", text[:60])
        return {
            "text": text,
            "language": language,
            "language_probability": 1.0,
        }
    except Exception as e:
        logger.error("❌ [IndicConformer Space] Error: %s", e)
        raise RuntimeError(f"IndicConformer Space call failed: {e}") from e


# ── Auto-detect (Whisper for language ID, then IndicConformer if Indic) ────────

def call_auto_detect_space(
    audio_path: str,
    indic_languages: list[str],
) -> dict:
    """
    Detect language using Whisper, then transcribe with IndicConformer if Indic.

    The Whisper Space transcribes with language detection as a by-product;
    we parse the BCP-47 code and route to IndicConformer for Indic languages.

    Args:
        audio_path:       Local audio file path.
        indic_languages:  List of Indic BCP-47 codes supported by IndicConformer.

    Returns:
        dict with keys: text, language, language_probability
    """
    logger.info("🔍 [Auto-detect] Running Whisper for language ID …")
    whisper_result = call_whisper_space(audio_path)
    detected_lang  = whisper_result.get("language", "en")

    if detected_lang in indic_languages:
        logger.info(
            "🔍 [Auto-detect] Detected Indic lang=%s — routing to IndicConformer", detected_lang
        )
        try:
            indic_result = call_indic_asr_space(audio_path, detected_lang)
            indic_result["language_probability"] = whisper_result["language_probability"]
            return indic_result
        except Exception as e:
            logger.warning(
                "⚠️  [Auto-detect] IndicConformer failed (%s) — falling back to Whisper", e
            )

    return whisper_result


# ── IndicParler-TTS ────────────────────────────────────────────────────────────

def call_tts_space(text: str, voice_description: str) -> bytes:
    """
    Synthesize speech using the IndicParler-TTS HF Space.

    The Space exposes two endpoints:
      /generate_finetuned  — fine-tuned multilingual model (preferred)
      /generate_pretrained — base pretrained model (fallback)

    Returns:
        Raw WAV audio bytes.
    """
    logger.info(
        "🔊 [TTS Space] text=%d chars → %s", len(text), _INDIC_TTS_SPACE
    )
    try:
        client = Client(_INDIC_TTS_SPACE)
        result = client.predict(
            text=text,
            description=voice_description,
            api_name="/generate_finetuned",
        )
        # Gradio returns a FileData dict with a 'url' key pointing to the audio
        audio_url: Optional[str] = None
        if isinstance(result, dict):
            audio_url = result.get("url") or result.get("path")
        elif isinstance(result, str):
            audio_url = result

        if not audio_url:
            raise ValueError(f"TTS Space returned unexpected result: {result!r}")

        # Fetch the audio bytes from the returned URL
        with httpx.Client(timeout=60) as http:
            resp = http.get(audio_url)
            resp.raise_for_status()
            audio_bytes = resp.content

        logger.info("✅ [TTS Space] Synthesized %d bytes", len(audio_bytes))
        return audio_bytes

    except Exception as e:
        logger.error("❌ [TTS Space] Error: %s", e)
        raise RuntimeError(f"IndicParler-TTS Space call failed: {e}") from e
