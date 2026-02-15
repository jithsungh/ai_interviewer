"""
Unit tests for Feature Flags

Tests feature flag creation, immutability, and access.
"""

import pytest
from dataclasses import FrozenInstanceError

from app.config.feature_flags import FeatureFlags, create_feature_flags
from app.config.settings import FeatureFlagsSettings


class TestFeatureFlags:
    """Test feature flags functionality"""
    
    def test_feature_flags_creation(self):
        """Test feature flags can be created from settings"""
        settings = FeatureFlagsSettings(
            enable_ai_evaluation=True,
            enable_proctoring=True,
            enable_audio_analysis=False,
            enable_code_execution=True,
            enable_practice_mode=False,
            enable_human_override=True,
            enable_resume_parsing=True
        )
        
        flags = FeatureFlags.from_settings(settings)
        
        assert flags.ENABLE_AI_EVALUATION is True
        assert flags.ENABLE_PROCTORING is True
        assert flags.ENABLE_AUDIO_ANALYSIS is False
        assert flags.ENABLE_CODE_EXECUTION is True
        assert flags.ENABLE_PRACTICE_MODE is False
        assert flags.ENABLE_HUMAN_OVERRIDE is True
        assert flags.ENABLE_RESUME_PARSING is True
    
    def test_feature_flags_immutable(self):
        """Test that feature flags are immutable"""
        settings = FeatureFlagsSettings()
        flags = FeatureFlags.from_settings(settings)
        
        with pytest.raises(FrozenInstanceError):
            flags.ENABLE_AI_EVALUATION = False  # type: ignore
    
    def test_feature_flags_boolean_types(self):
        """Test that all flags are boolean"""
        settings = FeatureFlagsSettings()
        flags = FeatureFlags.from_settings(settings)
        
        assert isinstance(flags.ENABLE_AI_EVALUATION, bool)
        assert isinstance(flags.ENABLE_PROCTORING, bool)
        assert isinstance(flags.ENABLE_AUDIO_ANALYSIS, bool)
        assert isinstance(flags.ENABLE_CODE_EXECUTION, bool)
        assert isinstance(flags.ENABLE_PRACTICE_MODE, bool)
        assert isinstance(flags.ENABLE_HUMAN_OVERRIDE, bool)
        assert isinstance(flags.ENABLE_RESUME_PARSING, bool)
    
    def test_create_feature_flags_factory(self):
        """Test factory function creates feature flags"""
        settings = FeatureFlagsSettings()
        flags = create_feature_flags(settings)
        
        assert isinstance(flags, FeatureFlags)
        assert isinstance(flags.ENABLE_AI_EVALUATION, bool)
    
    def test_feature_flags_all_enabled(self):
        """Test feature flags with all enabled"""
        settings = FeatureFlagsSettings(
            enable_ai_evaluation=True,
            enable_proctoring=True,
            enable_audio_analysis=True,
            enable_code_execution=True,
            enable_practice_mode=True,
            enable_human_override=True,
            enable_resume_parsing=True
        )
        
        flags = FeatureFlags.from_settings(settings)
        
        assert all([
            flags.ENABLE_AI_EVALUATION,
            flags.ENABLE_PROCTORING,
            flags.ENABLE_AUDIO_ANALYSIS,
            flags.ENABLE_CODE_EXECUTION,
            flags.ENABLE_PRACTICE_MODE,
            flags.ENABLE_HUMAN_OVERRIDE,
            flags.ENABLE_RESUME_PARSING
        ])
    
    def test_feature_flags_all_disabled(self):
        """Test feature flags with all disabled"""
        settings = FeatureFlagsSettings(
            enable_ai_evaluation=False,
            enable_proctoring=False,
            enable_audio_analysis=False,
            enable_code_execution=False,
            enable_practice_mode=False,
            enable_human_override=False,
            enable_resume_parsing=False
        )
        
        flags = FeatureFlags.from_settings(settings)
        
        assert not any([
            flags.ENABLE_AI_EVALUATION,
            flags.ENABLE_PROCTORING,
            flags.ENABLE_AUDIO_ANALYSIS,
            flags.ENABLE_CODE_EXECUTION,
            flags.ENABLE_PRACTICE_MODE,
            flags.ENABLE_HUMAN_OVERRIDE,
            flags.ENABLE_RESUME_PARSING
        ])
    
    def test_feature_flags_representation(self):
        """Test feature flags string representation"""
        settings = FeatureFlagsSettings()
        flags = FeatureFlags.from_settings(settings)
        
        repr_str = repr(flags)
        assert "FeatureFlags" in repr_str
        assert "ENABLE_AI_EVALUATION" in repr_str


# Run tests with pytest -v tests/unit/config/test_feature_flags.py
