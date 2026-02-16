"""
Unit Tests for Session Management

Tests session factory initialization and lifecycle management.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, IntegrityError

from app.persistence.postgres.session import (
    init_session_factory,
    get_session_factory,
    get_db_session,
    get_db_session_with_commit,
    db_session_context,
    execute_with_retry,
)


class TestSessionFactoryInitialization:
    """Test session factory initialization."""
    
    def setup_method(self):
        """Reset session factory before each test."""
        import app.persistence.postgres.session as session_module
        session_module.SessionLocal = None
    
    @patch('app.persistence.postgres.session.get_engine')
    @patch('app.persistence.postgres.session.sessionmaker')
    def test_init_session_factory(self, mock_sessionmaker, mock_get_engine):
        """Test session factory initialization."""
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine
        mock_factory = MagicMock()
        mock_sessionmaker.return_value = mock_factory
        
        init_session_factory()
        
        # Should create sessionmaker with engine
        mock_sessionmaker.assert_called_once()
        call_kwargs = mock_sessionmaker.call_args[1]
        assert call_kwargs["bind"] == mock_engine
        assert call_kwargs["autocommit"] is False
        assert call_kwargs["autoflush"] is True
    
    @patch('app.persistence.postgres.session.get_engine')
    @patch('app.persistence.postgres.session.sessionmaker')
    def test_init_session_factory_already_initialized(self, mock_sessionmaker, mock_get_engine):
        """Test initialization when already initialized."""
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine
        mock_factory = MagicMock()
        mock_sessionmaker.return_value = mock_factory
        
        # First initialization
        init_session_factory()
        call_count_1 = mock_sessionmaker.call_count
        
        # Second initialization should log warning but not create new factory
        init_session_factory()
        call_count_2 = mock_sessionmaker.call_count
        
        # Should still only be called once
        assert call_count_2 == call_count_1
    
    @patch('app.persistence.postgres.session.get_engine')
    @patch('app.persistence.postgres.session.sessionmaker')
    def test_get_session_factory(self, mock_sessionmaker, mock_get_engine):
        """Test getting session factory."""
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine
        mock_factory = MagicMock()
        mock_sessionmaker.return_value = mock_factory
        
        init_session_factory()
        factory = get_session_factory()
        
        assert factory == mock_factory
    
    def test_get_session_factory_not_initialized(self):
        """Test get_session_factory raises error when not initialized."""
        with pytest.raises(RuntimeError) as exc_info:
            get_session_factory()
        
        assert "not initialized" in str(exc_info.value)


class TestSessionContextManager:
    """Test db_session_context context manager."""
    
    @patch('app.persistence.postgres.session.SessionLocal')
    def test_session_context_success(self, mock_session_local):
        """Test context manager commits on success."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        with db_session_context() as session:
            assert session == mock_session
            # Perform some operation
            pass
        
        # Should commit and close
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.rollback.assert_not_called()
    
    @patch('app.persistence.postgres.session.SessionLocal')
    def test_session_context_rollback_on_error(self, mock_session_local):
        """Test context manager rolls back on exception."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        with pytest.raises(ValueError):
            with db_session_context() as session:
                raise ValueError("Test error")
        
        # Should rollback and close, not commit
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.commit.assert_not_called()
    
    @patch('app.persistence.postgres.session.SessionLocal')
    def test_session_context_always_closes(self, mock_session_local):
        """Test context manager always closes session."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        # Test with exception
        try:
            with db_session_context():
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Should always close
        mock_session.close.assert_called()


class TestFastAPIDependencies:
    """Test FastAPI dependency injection functions."""
    
    @patch('app.persistence.postgres.session.SessionLocal')
    def test_get_db_session(self, mock_session_local):
        """Test get_db_session dependency."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        # Get session generator
        session_gen = get_db_session()
        
        # Get session
        session = next(session_gen)
        assert session == mock_session
        
        # Complete generator (simulates request end)
        try:
            next(session_gen)
        except StopIteration:
            pass
        
        # Should close session
        mock_session.close.assert_called_once()
    
    @patch('app.persistence.postgres.session.SessionLocal')
    def test_get_db_session_with_commit_success(self, mock_session_local):
        """Test get_db_session_with_commit commits on success."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        session_gen = get_db_session_with_commit()
        session = next(session_gen)
        
        # Complete normally
        try:
            next(session_gen)
        except StopIteration:
            pass
        
        # Should commit and close
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
    
    @patch('app.persistence.postgres.session.SessionLocal')
    def test_get_db_session_with_commit_rollback_on_error(self, mock_session_local):
        """Test get_db_session_with_commit rolls back on error."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        session_gen = get_db_session_with_commit()
        next(session_gen)
        
        # Throw error into generator
        try:
            session_gen.throw(ValueError("Test error"))
        except ValueError:
            pass
        
        # Should rollback and close, not commit
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


class TestExecuteWithRetry:
    """Test execute_with_retry utility."""
    
    def test_execute_with_retry_success_first_attempt(self):
        """Test operation succeeds on first attempt."""
        mock_session = MagicMock()
        mock_operation = Mock(return_value="success")
        
        result = execute_with_retry(mock_session, mock_operation, max_retries=3)
        
        assert result == "success"
        mock_operation.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
    
    def test_execute_with_retry_success_after_retry(self):
        """Test operation succeeds after retry."""
        mock_session = MagicMock()
        
        # First call fails, second succeeds
        mock_operation = Mock(side_effect=[
            OperationalError("Deadlock", None, None),
            "success"
        ])
        
        result = execute_with_retry(mock_session, mock_operation, max_retries=3)
        
        assert result == "success"
        assert mock_operation.call_count == 2
        # Should rollback once (for failure), then commit (for success)
        assert mock_session.rollback.call_count == 1
        assert mock_session.commit.call_count == 1
    
    def test_execute_with_retry_all_retries_fail(self):
        """Test operation fails after all retries."""
        mock_session = MagicMock()
        mock_operation = Mock(side_effect=OperationalError("Deadlock", None, None))
        
        with pytest.raises(OperationalError):
            execute_with_retry(mock_session, mock_operation, max_retries=3)
        
        # Should attempt max_retries times
        assert mock_operation.call_count == 3
        assert mock_session.rollback.call_count == 3
    
    def test_execute_with_retry_non_retryable_error(self):
        """Test non-retryable error (IntegrityError) fails immediately."""
        mock_session = MagicMock()
        mock_operation = Mock(side_effect=IntegrityError("Duplicate key", None, None))
        
        with pytest.raises(IntegrityError):
            execute_with_retry(mock_session, mock_operation, max_retries=3)
        
        # Should NOT retry on IntegrityError
        mock_operation.assert_called_once()
        mock_session.rollback.assert_called_once()


class TestSessionLifecycle:
    """Test session lifecycle management."""
    
    @patch('app.persistence.postgres.session.SessionLocal')
    def test_session_closes_on_exception_in_dependency(self, mock_session_local):
        """Test session closes even when exception occurs during request."""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        session_gen = get_db_session()
        session = next(session_gen)
        
        # Simulate exception in request handler
        try:
            session_gen.throw(RuntimeError("Request failed"))
        except RuntimeError:
            pass
        
        # Session should still be closed
        mock_session.close.assert_called_once()
