"""
Unit Tests for Redis Client

Tests client initialization, retry logic, and error handling.
Uses mocks to avoid actual Redis connections.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time

from app.config.settings import RedisSettings
from app.persistence.redis.client import (
    create_redis_client,
    init_redis_client,
    get_redis_client,
    cleanup_redis,
    RedisClientError,
)


@pytest.fixture
def test_config():
    """Fixture providing test configuration."""
    return RedisSettings(
        redis_url="redis://localhost:6379/0",
        redis_db=0,
        redis_password=None,
        redis_max_connections=50,
        redis_connection_timeout=10,
        redis_socket_timeout=5,
        redis_retry_on_timeout=True,
        redis_max_retries=3,
        redis_decode_responses=True,
        redis_session_ttl=3600,
        redis_lock_timeout=10,
        redis_health_check_interval=60,
    )


@pytest.fixture(autouse=True)
def reset_global_client():
    """Reset global client state before each test."""
    import app.persistence.redis.client as client_module
    client_module._client = None
    client_module._pool = None
    yield
    client_module._client = None
    client_module._pool = None


class TestClientCreation:
    """Test Redis client creation."""
    
    @patch('app.persistence.redis.client.ConnectionPool')
    @patch('app.persistence.redis.client.Redis')
    def test_create_client_success(self, mock_redis, mock_pool, test_config):
        """Test successful client creation."""
        # Mock client and ping response
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        mock_pool_instance = MagicMock()
        mock_pool.from_url.return_value = mock_pool_instance
        
        # Create client
        client = create_redis_client(test_config)
        
        # Verify client was created
        assert client is not None
        mock_pool.from_url.assert_called_once()
        mock_client.ping.assert_called_once()
    
    @patch('app.persistence.redis.client.ConnectionPool')
    @patch('app.persistence.redis.client.Redis')
    def test_create_client_with_password(self, mock_redis, mock_pool, test_config):
        """Test client creation with password."""
        test_config.redis_password = "test-password"
        
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        mock_pool_instance = MagicMock()
        mock_pool.from_url.return_value = mock_pool_instance
        
        # Create client
        client = create_redis_client(test_config)
        
        # Verify password was passed
        call_kwargs = mock_pool.from_url.call_args[1]
        assert call_kwargs["password"] == "test-password"
    
    @patch('app.persistence.redis.client.ConnectionPool')
    @patch('app.persistence.redis.client.Redis')
    @patch('app.persistence.redis.client.time.sleep')
    def test_create_client_retry_success(self, mock_sleep, mock_redis, mock_pool, test_config):
        """Test client creation succeeds after retry."""
        # First ping fails, second succeeds
        from redis.exceptions import ConnectionError as RedisConnectionError
        mock_client = MagicMock()
        mock_client.ping.side_effect = [
            RedisConnectionError("Connection refused"),
            True
        ]
        mock_redis.return_value = mock_client
        
        mock_pool_instance = MagicMock()
        mock_pool.from_url.return_value = mock_pool_instance
        
        # Create client (should succeed on retry)
        client = create_redis_client(test_config)
        
        assert client is not None
        assert mock_sleep.call_count >= 1
        assert mock_client.ping.call_count == 2
    
    @patch('app.persistence.redis.client.ConnectionPool')
    @patch('app.persistence.redis.client.Redis')
    @patch('app.persistence.redis.client.time.sleep')
    def test_create_client_all_retries_fail(self, mock_sleep, mock_redis, mock_pool, test_config):
        """Test client creation fails after all retries."""
        # All pings fail
        from redis.exceptions import ConnectionError as RedisConnectionError
        mock_client = MagicMock()
        mock_client.ping.side_effect = RedisConnectionError("Connection refused")
        mock_redis.return_value = mock_client
        
        mock_pool_instance = MagicMock()
        mock_pool.from_url.return_value = mock_pool_instance
        
        # Should raise RedisClientError after retries
        with pytest.raises(RedisClientError) as exc_info:
            create_redis_client(test_config)
        
        assert "unavailable" in str(exc_info.value).lower()
        assert exc_info.value.status_code == 503
        assert mock_client.ping.call_count == 3  # MAX_RETRIES
    
    @patch('app.persistence.redis.client.create_redis_client')
    def test_init_client(self, mock_create_client, test_config):
        """Test global client initialization."""
        mock_client = MagicMock()
        mock_client.connection_pool = MagicMock()
        mock_create_client.return_value = mock_client
        
        # Initialize client
        client = init_redis_client(test_config)
        
        assert client is not None
        assert client == mock_client
        mock_create_client.assert_called_once_with(test_config)
    
    @patch('app.persistence.redis.client.create_redis_client')
    def test_init_client_already_initialized(self, mock_create_client, test_config):
        """Test initializing client twice returns same instance."""
        mock_client = MagicMock()
        mock_client.connection_pool = MagicMock()
        mock_create_client.return_value = mock_client
        
        # First initialization
        client1 = init_redis_client(test_config)
        call_count_1 = mock_create_client.call_count
        
        # Second initialization (should not create new client)
        client2 = init_redis_client(test_config)
        call_count_2 = mock_create_client.call_count
        
        assert client1 == client2
        assert call_count_2 == call_count_1  # No new call
    
    def test_get_client_not_initialized(self):
        """Test get_redis_client raises error when not initialized."""
        with pytest.raises(RuntimeError) as exc_info:
            get_redis_client()
        
        assert "not initialized" in str(exc_info.value)
    
    @patch('app.persistence.redis.client.create_redis_client')
    def test_get_client_after_init(self, mock_create_client, test_config):
        """Test get_redis_client returns initialized client."""
        mock_client = MagicMock()
        mock_client.connection_pool = MagicMock()
        mock_create_client.return_value = mock_client
        
        # Initialize
        init_redis_client(test_config)
        
        # Get client
        client = get_redis_client()
        
        assert client == mock_client


class TestClientCleanup:
    """Test Redis client cleanup."""
    
    @patch('app.persistence.redis.client.create_redis_client')
    def test_cleanup(self, mock_create_client, test_config):
        """Test cleanup disconnects pool."""
        mock_client = MagicMock()
        mock_pool = MagicMock()
        mock_client.connection_pool = mock_pool
        mock_create_client.return_value = mock_client
        
        # Initialize client
        init_redis_client(test_config)
        
        # Cleanup
        cleanup_redis()
        
        # Verify pool disconnected
        mock_pool.disconnect.assert_called_once()
        
        # Verify client is uninitialized
        with pytest.raises(RuntimeError):
            get_redis_client()
    
    def test_cleanup_when_not_initialized(self):
        """Test cleanup does nothing when client not initialized."""
        # Should not raise error
        cleanup_redis()
    
    @patch('app.persistence.redis.client.create_redis_client')
    def test_cleanup_handles_error(self, mock_create_client, test_config):
        """Test cleanup handles errors gracefully."""
        mock_client = MagicMock()
        mock_pool = MagicMock()
        mock_pool.disconnect.side_effect = Exception("Disconnect error")
        mock_client.connection_pool = mock_pool
        mock_create_client.return_value = mock_client
        
        # Initialize client
        init_redis_client(test_config)
        
        # Cleanup should not raise error
        cleanup_redis()


class TestConnectionPoolConfig:
    """Test connection pool configuration."""
    
    @patch('app.persistence.redis.client.ConnectionPool')
    @patch('app.persistence.redis.client.Redis')
    def test_connection_pool_parameters(self, mock_redis, mock_pool, test_config):
        """Test connection pool is configured correctly."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        mock_pool_instance = MagicMock()
        mock_pool.from_url.return_value = mock_pool_instance
        
        # Create client
        create_redis_client(test_config)
        
        # Verify pool configuration
        call_kwargs = mock_pool.from_url.call_args[1]
        assert call_kwargs["max_connections"] == test_config.redis_max_connections
        assert call_kwargs["socket_connect_timeout"] == test_config.redis_connection_timeout
        assert call_kwargs["socket_timeout"] == test_config.redis_socket_timeout
        assert call_kwargs["retry_on_timeout"] == test_config.redis_retry_on_timeout
        assert call_kwargs["decode_responses"] == test_config.redis_decode_responses
        assert call_kwargs["db"] == test_config.redis_db
