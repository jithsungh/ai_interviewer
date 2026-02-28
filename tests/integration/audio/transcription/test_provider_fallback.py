"""
Integration tests for the provider fallback chain.

Validates:
  - Primary provider failure triggers fallback
  - Correct provider order honoured
  - Fallback API keys routed correctly
  - All-providers-failed error raised when chain is exhausted
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.audio.transcription.contracts import TranscriptionRequest, TranscriptionResult
from app.audio.transcription.exceptions import AllProvidersFailedError
from app.audio.transcription.service import TranscriptionService


@pytest.fixture
def audio_request():
    return TranscriptionRequest(audio_data=b"\x00" * 500, sample_rate=16000)


class TestProviderFallback:
    """Fallback chain integration tests."""

    @pytest.mark.asyncio
    async def test_primary_succeeds_no_fallback(self, audio_request):
        """When primary succeeds, fallback is never invoked."""
        success = TranscriptionResult(
            transcript="Primary result",
            confidence_score=0.95,
            provider_metadata={"provider": "whisper"},
        )

        mock_primary = AsyncMock()
        mock_primary.transcribe = AsyncMock(return_value=success)
        mock_secondary = AsyncMock()
        mock_secondary.transcribe = AsyncMock()

        def select(name, **kw):
            return mock_primary if name == "whisper" else mock_secondary

        with patch(
            "app.audio.transcription.service.TranscriptionProviderSelector"
        ) as Mock:
            Mock.return_value.get_provider.side_effect = select

            svc = TranscriptionService(
                provider="whisper",
                api_key="k1",
                providers=["whisper", "local"],
                fallback_enabled=True,
                max_retries=1,
                retry_delay_s=0.01,
                timeout_s=5.0,
            )
            result = await svc.transcribe_with_fallback(audio_request)

            assert result.transcript == "Primary result"
            mock_secondary.transcribe.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_order_preserved(self, audio_request):
        """Providers are tried in the order specified."""
        call_order = []

        async def fail_transcriber(name):
            async def _transcribe(req):
                call_order.append(name)
                raise Exception(f"{name} failed")
            return _transcribe

        def select(name, **kw):
            t = AsyncMock()
            async def _t(req):
                call_order.append(name)
                raise Exception(f"{name} failed")
            t.transcribe = _t
            return t

        with patch(
            "app.audio.transcription.service.TranscriptionProviderSelector"
        ) as Mock:
            Mock.return_value.get_provider.side_effect = select

            svc = TranscriptionService(
                provider="whisper",
                providers=["whisper", "google", "local"],
                fallback_api_keys={"whisper": "k1", "google": "k2"},
                fallback_enabled=True,
                max_retries=1,
                retry_delay_s=0.01,
                timeout_s=5.0,
            )

            with pytest.raises(AllProvidersFailedError):
                await svc.transcribe_with_fallback(audio_request)

            assert call_order == ["whisper", "google", "local"]

    @pytest.mark.asyncio
    async def test_fallback_api_keys_routed(self, audio_request):
        """Each provider in the chain receives its own API key."""
        received_keys = {}

        def select(name, api_key=None, **kw):
            received_keys[name] = api_key
            t = AsyncMock()
            t.transcribe = AsyncMock(side_effect=Exception("fail"))
            return t

        with patch(
            "app.audio.transcription.service.TranscriptionProviderSelector"
        ) as Mock:
            Mock.return_value.get_provider.side_effect = select

            svc = TranscriptionService(
                provider="whisper",
                api_key="default_key",
                providers=["whisper", "google"],
                fallback_api_keys={"google": "google_specific_key"},
                fallback_enabled=True,
                max_retries=1,
                retry_delay_s=0.01,
                timeout_s=5.0,
            )

            with pytest.raises(AllProvidersFailedError):
                await svc.transcribe_with_fallback(audio_request)

            # Whisper should fall back to default_key
            assert received_keys["whisper"] == "default_key"
            # Google should use its specific key
            assert received_keys["google"] == "google_specific_key"
