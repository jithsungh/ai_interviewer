"""
Transcription Service

Orchestrates transcription requests through the provider abstraction:

  1. Select provider (primary or fallback chain)
  2. Execute batch or streaming transcription
  3. Retry on transient failures (exponential back-off)
  4. Log telemetry (provider, latency, cost estimate)

This is the **single public entry point** consumed by the ingestion
module (via callback), the orchestration module, and the API layer.

Invariants enforced:
  - Audio is NEVER written to disk (GDPR)
  - API keys are NEVER logged
  - TranscriptionResult is immutable (frozen dataclass)
  - Confidence scores are normalised to [0.0, 1.0]
"""

from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator, List, Optional, Sequence

from app.shared.observability import get_context_logger

from .contracts import TranscriptionConfig, TranscriptionRequest, TranscriptionResult
from .exceptions import (
    AllProvidersFailedError,
    TranscriptionError,
    TranscriptionTimeoutError,
)
from .provider_selector import TranscriptionProviderSelector

logger = get_context_logger(__name__)


class TranscriptionService:
    """
    Façade for speech-to-text transcription.

    Parameters
    ----------
    provider : str
        Primary provider name (``"whisper"``, ``"google"``, ``"local"``, …).
    api_key : str | None
        API key for the primary provider.
    config : TranscriptionConfig | None
        Provider-specific overrides.
    providers : list[str] | None
        Ordered fallback chain (used by ``transcribe_with_fallback``).
    fallback_api_keys : dict[str, str] | None
        Mapping of provider name → API key for fallback.
    fallback_enabled : bool
        Whether to attempt fallback providers on primary failure.
    max_retries : int
        Maximum retry attempts per provider.
    retry_delay_s : float
        Base delay between retries (doubles each attempt).
    timeout_s : float
        Per-call timeout in seconds.
    """

    def __init__(
        self,
        provider: str = "whisper",
        *,
        api_key: Optional[str] = None,
        config: Optional[TranscriptionConfig] = None,
        providers: Optional[List[str]] = None,
        fallback_api_keys: Optional[dict[str, str]] = None,
        fallback_enabled: bool = False,
        max_retries: int = 3,
        retry_delay_s: float = 2.0,
        timeout_s: float = 10.0,
    ) -> None:
        self._provider_name = provider
        self._api_key = api_key
        self._config = config
        self._providers = providers or [provider]
        self._fallback_api_keys = fallback_api_keys or {}
        self._fallback_enabled = fallback_enabled
        self._max_retries = max_retries
        self._retry_delay_s = retry_delay_s
        self._timeout_s = timeout_s
        self._selector = TranscriptionProviderSelector()

    # ------------------------------------------------------------------
    # Batch transcription
    # ------------------------------------------------------------------

    async def transcribe(
        self,
        request: TranscriptionRequest,
    ) -> TranscriptionResult:
        """
        Transcribe *request* using the primary provider with retry logic.

        Parameters
        ----------
        request : TranscriptionRequest
            Normalised audio data to transcribe.

        Returns
        -------
        TranscriptionResult
            Frozen result with transcript, confidence, and segments.

        Raises
        ------
        TranscriptionError
            If all retry attempts fail.
        TranscriptionTimeoutError
            If the operation exceeds ``timeout_s``.
        """
        transcriber = self._selector.get_provider(
            self._provider_name,
            api_key=self._api_key,
            config=self._config,
        )

        return await self._transcribe_with_retry(
            transcriber,
            request,
            provider_name=self._provider_name,
        )

    # ------------------------------------------------------------------
    # Streaming transcription
    # ------------------------------------------------------------------

    async def transcribe_streaming(
        self,
        request: TranscriptionRequest,
    ) -> AsyncIterator[TranscriptionResult]:
        """
        Yield partial transcription results for *request*.

        Only works with streaming-capable providers (e.g. Google).
        """
        transcriber = self._selector.get_provider(
            self._provider_name,
            api_key=self._api_key,
            config=self._config,
        )

        async for result in transcriber.transcribe_streaming(request):
            yield result

    # ------------------------------------------------------------------
    # Fallback transcription
    # ------------------------------------------------------------------

    async def transcribe_with_fallback(
        self,
        request: TranscriptionRequest,
    ) -> TranscriptionResult:
        """
        Try each provider in the fallback chain until one succeeds.

        Raises
        ------
        AllProvidersFailedError
            If every provider in the chain fails.
        """
        errors: list[str] = []

        for provider_name in self._providers:
            api_key = self._fallback_api_keys.get(provider_name, self._api_key)
            try:
                transcriber = self._selector.get_provider(
                    provider_name,
                    api_key=api_key,
                    config=self._config,
                )
                result = await self._transcribe_with_retry(
                    transcriber,
                    request,
                    provider_name=provider_name,
                )

                if provider_name != self._providers[0]:
                    logger.info(
                        "Transcription succeeded via fallback provider",
                        event_type="transcription.fallback.success",
                        metadata={"provider": provider_name},
                    )

                return result

            except Exception as exc:
                errors.append(f"{provider_name}: {exc}")
                logger.warning(
                    f"Transcription provider '{provider_name}' failed, "
                    f"trying next: {exc}",
                    event_type="transcription.fallback.attempt",
                    metadata={"provider": provider_name, "error": str(exc)},
                )

        raise AllProvidersFailedError(providers=list(self._providers))

    # ------------------------------------------------------------------
    # Retry engine
    # ------------------------------------------------------------------

    async def _transcribe_with_retry(
        self,
        transcriber,
        request: TranscriptionRequest,
        *,
        provider_name: str,
    ) -> TranscriptionResult:
        """Execute transcription with exponential back-off retry."""
        last_exc: Optional[Exception] = None
        delay = self._retry_delay_s

        for attempt in range(1, self._max_retries + 1):
            start = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    transcriber.transcribe(request),
                    timeout=self._timeout_s,
                )

                latency = time.monotonic() - start
                logger.info(
                    f"Transcription completed via {provider_name}",
                    event_type="transcription.completed",
                    latency_ms=latency * 1000,
                    metadata={
                        "provider": provider_name,
                        "attempt": attempt,
                        "confidence": result.confidence_score,
                        "transcript_length": len(result.transcript),
                    },
                )
                return result

            except asyncio.TimeoutError:
                last_exc = TranscriptionTimeoutError(
                    provider=provider_name,
                    timeout_s=self._timeout_s,
                )
                logger.warning(
                    f"Transcription attempt {attempt}/{self._max_retries} "
                    f"timed out for {provider_name}",
                    event_type="transcription.timeout",
                    metadata={
                        "provider": provider_name,
                        "attempt": attempt,
                        "timeout_s": self._timeout_s,
                    },
                )

            except Exception as exc:
                last_exc = exc
                logger.warning(
                    f"Transcription attempt {attempt}/{self._max_retries} "
                    f"failed for {provider_name}: {exc}",
                    event_type="transcription.retry",
                    metadata={
                        "provider": provider_name,
                        "attempt": attempt,
                        "error": str(exc),
                    },
                )

            # Exponential back-off (skip delay after last attempt)
            if attempt < self._max_retries:
                await asyncio.sleep(delay)
                delay *= 2

        # All retries exhausted
        if isinstance(last_exc, TranscriptionError):
            raise last_exc
        raise TranscriptionError(
            message=(
                f"Transcription via '{provider_name}' failed after "
                f"{self._max_retries} attempts: {last_exc}"
            ),
            metadata={"provider": provider_name},
        )
