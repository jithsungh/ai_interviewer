"""
Audio Ingestion API — Dependency Factories

Constructs the AudioIngestionService with configuration from settings.
Follows the same factory pattern as ``app.admin.api.dependencies``.
"""

from __future__ import annotations

from app.audio.ingestion.service import AudioIngestionService

# Module-level singleton — one service instance shared across requests
# since the service is stateless aside from the in-memory session registry.
_service_instance: AudioIngestionService | None = None


def get_audio_ingestion_service() -> AudioIngestionService:
    """
    Return the module-level AudioIngestionService singleton.

    Attempts to read audio settings from the app config.  Falls back
    to sensible defaults so that tests / dev environments work even
    when the full config stack is not loaded.
    """
    global _service_instance
    if _service_instance is not None:
        return _service_instance

    # Best-effort config loading
    silence_threshold_ms = 3000
    buffer_window_ms = 500
    max_buffer_duration_s = 30
    session_timeout_s = 10

    try:
        from app.config.settings import settings as global_settings

        if global_settings is not None:
            silence_threshold_ms = global_settings.audio.silence_threshold_ms
            buffer_window_ms = global_settings.audio.audio_chunk_size_ms
    except Exception:
        pass

    _service_instance = AudioIngestionService(
        silence_threshold_ms=silence_threshold_ms,
        buffer_window_ms=buffer_window_ms,
        max_buffer_duration_s=max_buffer_duration_s,
        session_timeout_s=session_timeout_s,
    )
    return _service_instance


def reset_audio_ingestion_service() -> None:
    """Reset the singleton (used in tests)."""
    global _service_instance
    _service_instance = None
