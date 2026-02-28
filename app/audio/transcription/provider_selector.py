"""
Transcription Provider Selector

Factory that instantiates the correct ``Transcriber`` implementation
from a provider name string + optional configuration overrides.

Follows the DI-factory pattern used by ``audio.ingestion.api.dependencies``.
"""

from __future__ import annotations

from typing import Optional

from app.shared.observability import get_context_logger

from .contracts import TranscriptionConfig
from .exceptions import ProviderConfigurationError, ProviderNotFoundError

logger = get_context_logger(__name__)

# Supported provider names
_EXTERNAL_PROVIDERS = {"whisper", "google", "azure", "assemblyai"}
_LOCAL_PROVIDERS = {"local"}
_ALL_PROVIDERS = _EXTERNAL_PROVIDERS | _LOCAL_PROVIDERS


class TranscriptionProviderSelector:
    """
    Resolves a provider name to a concrete ``Transcriber`` instance.

    External providers require an API key; local providers do not.
    """

    def get_provider(
        self,
        provider: str,
        *,
        api_key: Optional[str] = None,
        config: Optional[TranscriptionConfig] = None,
    ):
        """
        Build and return a ``Transcriber`` implementation.

        Parameters
        ----------
        provider : str
            One of ``"whisper"``, ``"google"``, ``"azure"``,
            ``"assemblyai"``, ``"local"``.
        api_key : str | None
            Required for external providers.
        config : TranscriptionConfig | None
            Optional overrides (model name, language, etc.).

        Returns
        -------
        Transcriber
            A concrete provider instance.

        Raises
        ------
        ProviderNotFoundError
            If ``provider`` is not recognised.
        ProviderConfigurationError
            If a required setting (e.g. API key) is missing.
        """
        provider = provider.lower().strip()

        if provider not in _ALL_PROVIDERS:
            raise ProviderNotFoundError(provider)

        # External providers need an API key
        if provider in _EXTERNAL_PROVIDERS and not api_key:
            raise ProviderConfigurationError(
                provider=provider,
                detail="API key is required for external providers",
            )

        model = (config.model if config else None) or None
        language = (config.language if config else None) or None

        if provider == "whisper":
            from .providers.whisper import WhisperTranscriber

            return WhisperTranscriber(
                api_key=api_key,  # type: ignore[arg-type]
                model=model or "whisper-1",
                language=language,
            )

        if provider == "google":
            from .providers.google_speech import GoogleSpeechTranscriber

            return GoogleSpeechTranscriber(
                api_key=api_key,
                language_code=language or "en-US",
            )

        if provider == "azure":
            # Azure provider is a future enhancement stub.
            # For now, raise an explicit error rather than silently failing.
            raise ProviderNotFoundError(
                f"azure (not yet implemented — planned for future release)"
            )

        if provider == "assemblyai":
            raise ProviderNotFoundError(
                f"assemblyai (not yet implemented — planned for future release)"
            )

        if provider == "local":
            from .providers.local_whisper import LocalWhisperTranscriber

            return LocalWhisperTranscriber(model=model or "base.en")

        # Unreachable — but satisfies exhaustiveness for type checkers
        raise ProviderNotFoundError(provider)  # pragma: no cover
