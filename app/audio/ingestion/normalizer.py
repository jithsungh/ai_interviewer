"""
Audio Normalizer

Responsible for resampling, channel conversion, and volume normalisation
so that all audio forwarded to transcription is **16 kHz mono PCM**.

Pure computation — no I/O, no side-effects, no database access.
"""

from __future__ import annotations

import numpy as np
from typing import Optional

# Target format for speech-to-text engines
TARGET_SAMPLE_RATE = 16_000
TARGET_CHANNELS = 1


class AudioNormalizer:
    """
    Transforms raw audio to a canonical format.

    Parameters
    ----------
    target_sample_rate : int
        Output sample rate in Hz (default 16 000).
    target_channels : int
        Output channel count (default 1 = mono).
    silence_rms_threshold : float
        RMS amplitude below which a chunk is considered silence.
    """

    def __init__(
        self,
        target_sample_rate: int = TARGET_SAMPLE_RATE,
        target_channels: int = TARGET_CHANNELS,
        silence_rms_threshold: float = 0.02,
    ):
        self.output_sample_rate = target_sample_rate
        self.output_channels = target_channels
        self.silence_rms_threshold = silence_rms_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resample(self, audio: np.ndarray, source_rate: int) -> np.ndarray:
        """
        Resample 1-D audio from *source_rate* to *self.output_sample_rate*.

        Uses linear interpolation — good enough for speech; avoids heavy
        dependencies like ``librosa`` or ``scipy.signal``.
        """
        if source_rate == self.output_sample_rate:
            return audio

        if source_rate <= 0:
            raise ValueError(f"source_rate must be positive, got {source_rate}")

        duration_s = len(audio) / source_rate
        target_len = int(duration_s * self.output_sample_rate)
        if target_len == 0:
            return np.array([], dtype=audio.dtype)

        indices = np.linspace(0, len(audio) - 1, num=target_len)
        return np.interp(indices, np.arange(len(audio)), audio).astype(audio.dtype)

    def to_mono(self, audio: np.ndarray) -> np.ndarray:
        """
        Down-mix multi-channel audio to mono by averaging channels.

        Expects shape ``(samples,)`` (already mono) or ``(samples, channels)``.
        """
        if audio.ndim == 1:
            return audio
        if audio.ndim == 2:
            return audio.mean(axis=1)
        raise ValueError(f"Unexpected audio shape: {audio.shape}")

    def normalize_volume(self, audio: np.ndarray) -> np.ndarray:
        """
        Peak-normalize audio so that the maximum absolute value is ≤ 1.0.
        """
        peak = np.max(np.abs(audio))
        if peak == 0:
            return audio
        return audio / peak

    def is_silence(self, audio: np.ndarray) -> bool:
        """
        Return ``True`` if the RMS energy of *audio* is below
        *self.silence_rms_threshold*.
        """
        if len(audio) == 0:
            return True
        rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
        return rms < self.silence_rms_threshold

    def decode_opus(self, opus_data: bytes) -> np.ndarray:
        """
        Decode Opus-encoded audio to PCM float32 ndarray.

        Currently a **placeholder** — real implementation would use
        ``opuslib`` or ``pyogg``.  Returns an empty array if the codec
        is unavailable.
        """
        # TODO: integrate opuslib when codec library is in requirements.txt
        return np.array([], dtype=np.float32)

    def normalize(
        self,
        raw_audio: np.ndarray,
        source_rate: int,
        source_channels: int = 1,
    ) -> np.ndarray:
        """
        Full normalisation pipeline: mono → resample → volume normalisation.
        """
        audio = raw_audio.copy()

        # Channel conversion
        if source_channels > 1:
            audio = self.to_mono(audio)

        # Resample
        audio = self.resample(audio, source_rate)

        # Volume normalisation
        audio = self.normalize_volume(audio)

        return audio

    def compute_duration_ms(self, sample_count: int, sample_rate: int) -> int:
        """Return duration in ms for a given number of samples."""
        if sample_rate <= 0:
            return 0
        return int((sample_count / sample_rate) * 1000)
