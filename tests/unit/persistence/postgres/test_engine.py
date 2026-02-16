"""
Unit Tests for Database Engine

Tests engine creation, retry logic, and error handling.
Uses mocks to avoid actual database connections.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.exc import OperationalError, DatabaseError

from app.config.settings import DatabaseSettings
from app.persistence.postgres.engine import (
    create_db_engine,
    init_engine,
    get_engine,
    cleanup_engine,
    get_pool_status,
)


@pytest.fixture
def test_config():
    """Fixture providing test configuration."""
    return DatabaseSettings(
        database_url="postgresql://user:pass@localhost/testdb",
        db_pool_size=10,
        db_max_overflow=5,
        db_pool_timeout=30,
        db_query_timeout=30,
    )


class TestEngineCreation:
    """Test database engine creation."""
    
    @patch('app.persistence.postgres.engine._register_pool_listeners')
    @patch('app.persistence.postgres.engine.create_engine')
    def test_create_engine_success(self, mock_create_engine, mock_register_listeners, test_config):
        """Test successful engine creation."""
        # Mock engine and connection
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value = mock_conn
        
        mock_create_engine.return_value = mock_engine
        
        # Create engine
        engine = create_db_engine(test_config)
        
        # Verify engine was created
        assert engine is not None
        mock_create_engine.assert_called_once()
        
        # Verify connection test was performed
        mock_engine.connect.assert_called_once()
    
    @patch('app.persistence.postgres.engine._register_pool_listeners')
    @patch('app.persistence.postgres.engine.create_engine')
    @patch('app.persistence.postgres.engine.time.sleep')  # Mock sleep to speed up test
    def test_create_engine_retry_success(self, mock_sleep, mock_create_engine, mock_register_listeners, test_config):
        """Test engine creation succeeds after retry."""
        # First two attempts fail, third succeeds
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_conn.execute.return_value = mock_result
        
        # First call raises error, second call succeeds
        mock_engine.connect.side_effect = [
            OperationalError("Connection refused", None, None),
            mock_conn
        ]
        mock_create_engine.return_value = mock_engine
        
        # Create engine (should succeed on retry)
        engine = create_db_engine(test_config)
        
        assert engine is not None
        # Should have retried once
        assert mock_sleep.call_count >= 1
    
    @patch('app.persistence.postgres.engine.create_engine')
    @patch('app.persistence.postgres.engine.time.sleep')
    def test_create_engine_all_retries_fail(self, mock_sleep, mock_create_engine, test_config):
        """Test engine creation fails after all retries."""
        # All attempts fail
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = OperationalError("Connection refused", None, None)
        mock_create_engine.return_value = mock_engine
        
        # Should raise OperationalError after retries
        with pytest.raises(OperationalError) as exc_info:
            create_db_engine(test_config)
        
        assert "Database unavailable" in str(exc_info.value)
        # Should have retried MAX_RETRIES times (3)
        assert mock_sleep.call_count == 2  # MAX_RETRIES - 1


class TestEngineInitialization:
    """Test global engine initialization."""
    
    def setup_method(self):
        """Reset global engine before each test."""
        # Import and reset the global _engine
        import app.persistence.postgres.engine as engine_module
        engine_module._engine = None
    
    @patch('app.persistence.postgres.engine.create_db_engine')
    def test_init_engine_first_call(self, mock_create_engine, test_config):
        """Test first initialization of global engine."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        engine = init_engine(test_config)
        
        assert engine == mock_engine
        mock_create_engine.assert_called_once()
    
    @patch('app.persistence.postgres.engine.create_db_engine')
    def test_init_engine_already_initialized(self, mock_create_engine, test_config):
        """Test init_engine returns existing engine if already initialized."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        # First call
        engine1 = init_engine(test_config)
        
        # Second call should return same engine
        engine2 = init_engine(test_config)
        
        assert engine1 == engine2
        # Should only create engine once
        mock_create_engine.assert_called_once()
    
    @patch('app.persistence.postgres.engine.create_db_engine')
    def test_get_engine_success(self, mock_create_engine, test_config):
        """Test get_engine returns initialized engine."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        # Initialize first
        init_engine(test_config)
        
        # Get engine
        engine = get_engine()
        
        assert engine == mock_engine
    
    def test_get_engine_not_initialized(self):
        """Test get_engine raises error if not initialized."""
        with pytest.raises(RuntimeError) as exc_info:
            get_engine()
        
        assert "not initialized" in str(exc_info.value)


class TestEngineCleanup:
    """Test engine cleanup and disposal."""
    
    @patch('app.persistence.postgres.engine.create_db_engine')
    def test_cleanup_engine(self, mock_create_engine, test_config):
        """Test cleanup disposes engine."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        # Initialize
        init_engine(test_config)
        
        # Cleanup
        cleanup_engine()
        
        # Should dispose engine
        mock_engine.dispose.assert_called_once()
    
    def test_cleanup_engine_not_initialized(self):
        """Test cleanup is safe when engine not initialized."""
        # Should not raise error
        cleanup_engine()


class TestPoolStatus:
    """Test connection pool status reporting."""
    
    @patch('app.persistence.postgres.engine.get_engine')
    def test_get_pool_status(self, mock_get_engine):
        """Test getting pool status."""
        # Mock pool
        mock_pool = MagicMock()
        mock_pool.size.return_value = 10
        mock_pool.checkedout.return_value = 3
        mock_pool.overflow.return_value = 2
        
        mock_engine = MagicMock()
        mock_engine.pool = mock_pool
        mock_get_engine.return_value = mock_engine
        
        status = get_pool_status()
        
        assert status["pool_size"] == 10
        assert status["checked_out"] == 3
        assert status["overflow"] == 2
        assert status["total_connections"] == 12  # size + overflow
    
    def test_get_pool_status_not_initialized(self):
        """Test get_pool_status raises error if engine not initialized."""
        # Reset engine
        import app.persistence.postgres.engine as engine_module
        engine_module._engine = None
        
        with pytest.raises(RuntimeError):
            get_pool_status()


class TestEventListeners:
    """Test pool event listener registration."""
    
    @patch('app.persistence.postgres.engine.create_engine')
    @patch('app.persistence.postgres.engine.event.listens_for')
    def test_event_listeners_registered(self, mock_listens_for, mock_create_engine, test_config):
        """Test that pool event listeners are registered."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value = mock_conn
        
        mock_create_engine.return_value = mock_engine
        
        create_db_engine(test_config)
        
        # Event listeners should be registered
        # (connect, checkout, checkin)
        assert mock_listens_for.call_count >= 3
