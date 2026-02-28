"""
Audio Transcription API — Dependency Factories

Constructs the TranscriptionService with configuration from settings.
Follows the same singleton-factory pattern as
``audio.ingestion.api.dependencies``.
"""

from __future__ import annotations

from typing import Optional

from app.audio.transcription.service import TranscriptionService

# Module-level singleton
_service_instance: Optional[TranscriptionService] = None


def get_transcription_service() -> TranscriptionService:
    """
    Return the module-level ``TranscriptionService`` singleton.

    Reads audio / LLM settings from the global config on first call.
    Falls back to sensible defaults for test / dev environments.
    """
    global _service_instance
    if _service_instance is not None:
        return _service_instance

    # Defaults (overridden by settings if available)
    provider = "whisper"
    api_key: Optional[str] = None
    max_retries = 3
    retry_delay_s = 2.0
    timeout_s = 10.0

    try:
        from app.config.settings import settings as global_settings

        if global_settings is not None:
            provider = global_settings.audio.audio_transcription_provider
            # Reuse OpenAI key for Whisper provider
            if provider == "whisper":
                api_key = global_settings.llm.openai_api_key
    except Exception:
        pass

    _service_instance = TranscriptionService(
        provider=provider,
        api_key=api_key,
        max_retries=max_retries,
        retry_delay_s=retry_delay_s,
        timeout_s=timeout_s,
    )
    return _service_instance


def reset_transcription_service() -> None:
    """Reset the singleton (used in tests)."""
    global _service_instance
    _service_instance = None
