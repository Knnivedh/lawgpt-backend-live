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
import inspect
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from gradio_client import Client, handle_file

logger = logging.getLogger(__name__)

# ── Space URLs (set via environment / config) ──────────────────────────────────
_WHISPER_SPACE      = os.getenv("WHISPER_SPACE_URL",    "rverma0631/Whisper")
_INDIC_ASR_SPACE    = os.getenv("INDIC_ASR_SPACE_URL",  "rverma0631/MultilingualASR")
_INDIC_TTS_SPACE    = os.getenv("INDIC_TTS_SPACE_URL",  "R910/IndicParler_TTS")


def _space_client(space: str, **kwargs) -> Client:
    """Authenticate Space calls with the configured backend HF account."""
    from config import get_settings

    # Gradio 2.x uses token; older supported clients use hf_token.
    token_parameter = "token" if "token" in inspect.signature(Client).parameters else "hf_token"
    return Client(space, **{token_parameter: get_settings().huggingface_api_key}, **kwargs)


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
        client = _space_client(_WHISPER_SPACE)
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
        client = _space_client(_INDIC_ASR_SPACE)
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

def _read_tts_audio(result: object) -> bytes:
    """Read a Gradio download, or fetch an explicit HTTP(S) audio URL."""
    candidates = (
        [result.get("path"), result.get("url")]
        if isinstance(result, dict) else [result]
    )
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate:
            continue
        if urlsplit(candidate).scheme in ("http", "https"):
            with httpx.Client(timeout=60, follow_redirects=True) as http:
                response = http.get(candidate)
                response.raise_for_status()
                return response.content
        if Path(candidate).is_file():
            return Path(candidate).read_bytes()
    raise ValueError("TTS Space returned no readable audio file or HTTP(S) URL")


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
        # Gradio downloads file outputs locally. Read them before cleaning up
        # this request's directory so generated audio does not accumulate.
        with tempfile.TemporaryDirectory(prefix="tts-") as output_dir:
            client = _space_client(_INDIC_TTS_SPACE, download_files=output_dir)
            result = client.predict(
                text=text,
                description=voice_description,
                api_name="/generate_finetuned",
            )
            audio_bytes = _read_tts_audio(result)

        logger.info("✅ [TTS Space] Synthesized %d bytes", len(audio_bytes))
        return audio_bytes

    except Exception as e:
        logger.error("❌ [TTS Space] Error: %s", e)
        raise RuntimeError(f"IndicParler-TTS Space call failed: {e}") from e
