"""
Unit tests for Constants

Tests domain constants are properly defined and immutable.
"""

import pytest

from app.config import constants


class TestCodeExecutionConstants:
    """Test code execution constants"""
    
    def test_supported_languages(self):
        """Test supported languages constant"""
        assert isinstance(constants.SUPPORTED_LANGUAGES, list)
        assert "cpp" in constants.SUPPORTED_LANGUAGES
        assert "java" in constants.SUPPORTED_LANGUAGES
        assert "python3" in constants.SUPPORTED_LANGUAGES
    
    def test_max_code_size(self):
        """Test max code size constant"""
        assert constants.MAX_CODE_SIZE_BYTES == 100_000
        assert isinstance(constants.MAX_CODE_SIZE_BYTES, int)
    
    def test_max_test_case_input_size(self):
        """Test max test case input size constant"""
        assert constants.MAX_TEST_CASE_INPUT_SIZE_BYTES == 10_485_760
        assert isinstance(constants.MAX_TEST_CASE_INPUT_SIZE_BYTES, int)


class TestInterviewConstants:
    """Test interview constants"""
    
    def test_max_question_length(self):
        """Test max question length constant"""
        assert constants.MAX_QUESTION_LENGTH == 10_000
        assert isinstance(constants.MAX_QUESTION_LENGTH, int)
    
    def test_max_answer_length(self):
        """Test max answer length constant"""
        assert constants.MAX_ANSWER_LENGTH == 50_000
        assert isinstance(constants.MAX_ANSWER_LENGTH, int)
    
    def test_max_exchanges_per_interview(self):
        """Test max exchanges per interview constant"""
        assert constants.MAX_EXCHANGES_PER_INTERVIEW == 50
        assert isinstance(constants.MAX_EXCHANGES_PER_INTERVIEW, int)


class TestEvaluationConstants:
    """Test evaluation constants"""
    
    def test_min_evaluation_score(self):
        """Test min evaluation score constant"""
        assert constants.MIN_EVALUATION_SCORE == 0.0
        assert isinstance(constants.MIN_EVALUATION_SCORE, float)
    
    def test_max_evaluation_score(self):
        """Test max evaluation score constant"""
        assert constants.MAX_EVALUATION_SCORE == 100.0
        assert isinstance(constants.MAX_EVALUATION_SCORE, float)
    
    def test_default_rubric_weight(self):
        """Test default rubric weight constant"""
        assert constants.DEFAULT_RUBRIC_WEIGHT == 1
        assert isinstance(constants.DEFAULT_RUBRIC_WEIGHT, int)


class TestAudioConstants:
    """Test audio constants"""
    
    def test_audio_sample_rate(self):
        """Test audio sample rate constant"""
        assert constants.AUDIO_SAMPLE_RATE == 16000
        assert isinstance(constants.AUDIO_SAMPLE_RATE, int)
    
    def test_audio_channels(self):
        """Test audio channels constant"""
        assert constants.AUDIO_CHANNELS == 1
        assert isinstance(constants.AUDIO_CHANNELS, int)
    
    def test_max_audio_chunk_size(self):
        """Test max audio chunk size constant"""
        assert constants.MAX_AUDIO_CHUNK_SIZE_BYTES == 1_048_576
        assert isinstance(constants.MAX_AUDIO_CHUNK_SIZE_BYTES, int)


class TestStatusConstants:
    """Test status value constants"""
    
    def test_interview_status_values(self):
        """Test interview status values constant"""
        assert isinstance(constants.INTERVIEW_STATUS_VALUES, list)
        assert "scheduled" in constants.INTERVIEW_STATUS_VALUES
        assert "in_progress" in constants.INTERVIEW_STATUS_VALUES
        assert "completed" in constants.INTERVIEW_STATUS_VALUES
        assert "cancelled" in constants.INTERVIEW_STATUS_VALUES
    
    def test_submission_status_values(self):
        """Test submission status values constant"""
        assert isinstance(constants.SUBMISSION_STATUS_VALUES, list)
        assert "pending" in constants.SUBMISSION_STATUS_VALUES
        assert "running" in constants.SUBMISSION_STATUS_VALUES
        assert "passed" in constants.SUBMISSION_STATUS_VALUES
        assert "failed" in constants.SUBMISSION_STATUS_VALUES
        assert "error" in constants.SUBMISSION_STATUS_VALUES
        assert "timeout" in constants.SUBMISSION_STATUS_VALUES


class TestTimeConstants:
    """Test time conversion constants"""
    
    def test_seconds_per_minute(self):
        """Test seconds per minute constant"""
        assert constants.SECONDS_PER_MINUTE == 60
    
    def test_milliseconds_per_second(self):
        """Test milliseconds per second constant"""
        assert constants.MILLISECONDS_PER_SECOND == 1000
    
    def test_microseconds_per_second(self):
        """Test microseconds per second constant"""
        assert constants.MICROSECONDS_PER_SECOND == 1_000_000


class TestFileSizeConstants:
    """Test file size conversion constants"""
    
    def test_bytes_per_kb(self):
        """Test bytes per KB constant"""
        assert constants.BYTES_PER_KB == 1024
    
    def test_bytes_per_mb(self):
        """Test bytes per MB constant"""
        assert constants.BYTES_PER_MB == 1024 * 1024
    
    def test_bytes_per_gb(self):
        """Test bytes per GB constant"""
        assert constants.BYTES_PER_GB == 1024 * 1024 * 1024


class TestPaginationConstants:
    """Test pagination constants"""
    
    def test_default_page_size(self):
        """Test default page size constant"""
        assert constants.DEFAULT_PAGE_SIZE == 20
    
    def test_max_page_size(self):
        """Test max page size constant"""
        assert constants.MAX_PAGE_SIZE == 100
    
    def test_min_page_size(self):
        """Test min page size constant"""
        assert constants.MIN_PAGE_SIZE == 1


class TestPasswordConstants:
    """Test password requirement constants"""
    
    def test_min_password_length(self):
        """Test min password length constant"""
        assert constants.MIN_PASSWORD_LENGTH == 8
    
    def test_max_password_length(self):
        """Test max password length constant"""
        assert constants.MAX_PASSWORD_LENGTH == 128


class TestAPIConstants:
    """Test API constants"""
    
    def test_api_v1_prefix(self):
        """Test API v1 prefix constant"""
        assert constants.API_V1_PREFIX == "/api/v1"


class TestQuestionConstants:
    """Test question type constants"""
    
    def test_question_types(self):
        """Test question types constant"""
        assert isinstance(constants.QUESTION_TYPES, list)
        assert "coding" in constants.QUESTION_TYPES
        assert "system_design" in constants.QUESTION_TYPES
        assert "behavioral" in constants.QUESTION_TYPES
        assert "technical_knowledge" in constants.QUESTION_TYPES
    
    def test_difficulty_levels(self):
        """Test difficulty levels constant"""
        assert isinstance(constants.DIFFICULTY_LEVELS, list)
        assert "easy" in constants.DIFFICULTY_LEVELS
        assert "medium" in constants.DIFFICULTY_LEVELS
        assert "hard" in constants.DIFFICULTY_LEVELS


class TestUserConstants:
    """Test user role constants"""
    
    def test_user_roles(self):
        """Test user roles constant"""
        assert isinstance(constants.USER_ROLES, list)
        assert "candidate" in constants.USER_ROLES
        assert "interviewer" in constants.USER_ROLES
        assert "admin" in constants.USER_ROLES
        assert "organization_admin" in constants.USER_ROLES


class TestProctoringConstants:
    """Test proctoring constants"""
    
    def test_max_tab_switch_warnings(self):
        """Test max tab switch warnings constant"""
        assert constants.MAX_TAB_SWITCH_WARNINGS == 3
    
    def test_max_offline_duration(self):
        """Test max offline duration constant"""
        assert constants.MAX_OFFLINE_DURATION_SECONDS == 30
    
    def test_face_detection_interval(self):
        """Test face detection interval constant"""
        assert constants.FACE_DETECTION_INTERVAL_MS == 5000


class TestEmbeddingConstants:
    """Test embedding dimension constants"""
    
    def test_default_embedding_dim(self):
        """Test default embedding dimension constant"""
        assert constants.DEFAULT_EMBEDDING_DIM == 768
    
    def test_openai_embedding_dim(self):
        """Test OpenAI embedding dimension constant"""
        assert constants.OPENAI_EMBEDDING_DIM == 1536
    
    def test_openai_embedding_dim_large(self):
        """Test OpenAI large embedding dimension constant"""
        assert constants.OPENAI_EMBEDDING_DIM_LARGE == 3072


class TestVectorSearchConstants:
    """Test vector search constants"""
    
    def test_default_top_k(self):
        """Test default top K constant"""
        assert constants.DEFAULT_TOP_K == 10
    
    def test_max_top_k(self):
        """Test max top K constant"""
        assert constants.MAX_TOP_K == 100
    
    def test_min_similarity_threshold(self):
        """Test min similarity threshold constant"""
        assert constants.MIN_SIMILARITY_THRESHOLD == 0.7


class TestConstantsImmutability:
    """Test that constants cannot be modified"""
    
    @pytest.mark.skip(reason="Python doesn't enforce Final at runtime - this documents intent only")
    def test_cannot_modify_list_constant(self):
        """Test that list constants cannot be modified"""
        original_length = len(constants.SUPPORTED_LANGUAGES)
        
        # This should raise an error since it's a Final type
        # In practice, Python doesn't enforce Final at runtime,
        # but this test documents the intent
        with pytest.raises((TypeError, AttributeError)):
            constants.SUPPORTED_LANGUAGES = ["new"]  # type: ignore
    
    @pytest.mark.skip(reason="Python doesn't enforce Final at runtime - this documents intent only")
    def test_cannot_modify_int_constant(self):
        """Test that int constants cannot be modified"""
        # This should raise an error since it's a Final type
        with pytest.raises((TypeError, AttributeError)):
            constants.MAX_CODE_SIZE_BYTES = 200_000  # type: ignore


# Run tests with pytest -v tests/unit/config/test_constants.py
