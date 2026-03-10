"""
Feature Flags

Immutable feature flags for runtime feature toggling.
Centralized access - no scattered string checks.
"""

from dataclasses import dataclass
from app.config.settings import FeatureFlagsSettings


@dataclass(frozen=True)
class FeatureFlags:
    """
    Immutable feature flags.
    
    Use this object to check feature availability throughout the application.
    Flags are loaded from environment variables at startup and cannot be changed.
    """
    
    # Core features
    ENABLE_AI_EVALUATION: bool
    ENABLE_PROCTORING: bool
    ENABLE_AUDIO_ANALYSIS: bool
    ENABLE_CODE_EXECUTION: bool
    
    # Optional features
    ENABLE_PRACTICE_MODE: bool
    ENABLE_HUMAN_OVERRIDE: bool
    ENABLE_RESUME_PARSING: bool
    ENABLE_MOCK_DATA: bool
    
    @classmethod
    def from_settings(cls, settings: FeatureFlagsSettings) -> "FeatureFlags":
        """Create FeatureFlags from FeatureFlagsSettings"""
        return cls(
            ENABLE_AI_EVALUATION=settings.enable_ai_evaluation,
            ENABLE_PROCTORING=settings.enable_proctoring,
            ENABLE_AUDIO_ANALYSIS=settings.enable_audio_analysis,
            ENABLE_CODE_EXECUTION=settings.enable_code_execution,
            ENABLE_PRACTICE_MODE=settings.enable_practice_mode,
            ENABLE_HUMAN_OVERRIDE=settings.enable_human_override,
            ENABLE_RESUME_PARSING=settings.enable_resume_parsing,
            ENABLE_MOCK_DATA=settings.enable_mock_data
        )


def create_feature_flags(settings: FeatureFlagsSettings) -> FeatureFlags:
    """Factory function to create feature flags from settings"""
    return FeatureFlags.from_settings(settings)
