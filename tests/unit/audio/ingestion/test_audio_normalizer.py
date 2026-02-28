"""
Unit tests for AudioNormalizer.

Validates resampling, channel conversion, volume normalisation,
and silence detection — all pure computation, no mocks needed.
"""

import pytest
import numpy as np

from app.audio.ingestion.normalizer import AudioNormalizer


class TestResample:
    """Resampling from various source rates to 16 kHz."""

    def test_resample_48khz_to_16khz(self):
        normalizer = AudioNormalizer(target_sample_rate=16000)
        duration_s = 1.0
        source_rate = 48000
        audio_in = np.random.randn(int(duration_s * source_rate)).astype(np.float32)

        audio_out = normalizer.resample(audio_in, source_rate)

        assert len(audio_out) == 16000
        assert normalizer.output_sample_rate == 16000

    def test_resample_8khz_to_16khz(self):
        normalizer = AudioNormalizer(target_sample_rate=16000)
        audio_in = np.random.randn(8000).astype(np.float32)

        audio_out = normalizer.resample(audio_in, 8000)

        assert len(audio_out) == 16000

    def test_resample_noop_when_same_rate(self):
        normalizer = AudioNormalizer(target_sample_rate=16000)
        audio_in = np.random.randn(16000).astype(np.float32)

        audio_out = normalizer.resample(audio_in, 16000)

        assert len(audio_out) == 16000
        np.testing.assert_array_equal(audio_out, audio_in)

    def test_resample_invalid_source_rate(self):
        normalizer = AudioNormalizer()
        with pytest.raises(ValueError, match="positive"):
            normalizer.resample(np.zeros(100), 0)

    def test_resample_empty_audio(self):
        normalizer = AudioNormalizer()
        result = normalizer.resample(np.array([], dtype=np.float32), 48000)
        assert len(result) == 0


class TestMono:
    """Stereo-to-mono conversion."""

    def test_convert_stereo_to_mono(self):
        normalizer = AudioNormalizer(target_channels=1)
        stereo = np.random.randn(16000, 2).astype(np.float32)

        mono = normalizer.to_mono(stereo)

        assert mono.shape == (16000,)

    def test_mono_passthrough(self):
        normalizer = AudioNormalizer()
        mono = np.random.randn(16000).astype(np.float32)

        result = normalizer.to_mono(mono)

        np.testing.assert_array_equal(result, mono)

    def test_invalid_shape_raises(self):
        normalizer = AudioNormalizer()
        with pytest.raises(ValueError, match="Unexpected audio shape"):
            normalizer.to_mono(np.zeros((100, 2, 3)))


class TestNormalizeVolume:

    def test_peak_below_one(self):
        normalizer = AudioNormalizer()
        loud = np.random.randn(16000).astype(np.float32) * 10.0

        result = normalizer.normalize_volume(loud)

        assert float(np.max(np.abs(result))) <= 1.0 + 1e-7

    def test_silence_unchanged(self):
        normalizer = AudioNormalizer()
        silence = np.zeros(16000, dtype=np.float32)

        result = normalizer.normalize_volume(silence)

        np.testing.assert_array_equal(result, silence)


class TestIsSilence:

    def test_pure_silence_detected(self):
        normalizer = AudioNormalizer()
        silence = np.zeros(16000, dtype=np.float32)
        assert normalizer.is_silence(silence) is True

    def test_speech_not_silence(self):
        normalizer = AudioNormalizer()
        speech = np.random.randn(16000).astype(np.float32) * 0.5
        assert normalizer.is_silence(speech) is False

    def test_quiet_audio_is_silence(self):
        normalizer = AudioNormalizer()
        quiet = np.random.randn(16000).astype(np.float32) * 0.01
        assert normalizer.is_silence(quiet) is True

    def test_empty_audio_is_silence(self):
        normalizer = AudioNormalizer()
        assert normalizer.is_silence(np.array([], dtype=np.float32)) is True


class TestFullNormalize:

    def test_stereo_48khz_to_mono_16khz(self):
        normalizer = AudioNormalizer()
        stereo_48 = np.random.randn(48000, 2).astype(np.float32)

        result = normalizer.normalize(stereo_48, source_rate=48000, source_channels=2)

        assert result.ndim == 1
        assert len(result) == 16000
        assert float(np.max(np.abs(result))) <= 1.0 + 1e-7


class TestComputeDuration:

    def test_standard_duration(self):
        normalizer = AudioNormalizer()
        assert normalizer.compute_duration_ms(16000, 16000) == 1000

    def test_half_second(self):
        normalizer = AudioNormalizer()
        assert normalizer.compute_duration_ms(8000, 16000) == 500

    def test_zero_rate(self):
        normalizer = AudioNormalizer()
        assert normalizer.compute_duration_ms(100, 0) == 0
