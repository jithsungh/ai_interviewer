"""
Integration Tests for Connection Pool

Tests connection pool behavior, monitoring, and resource management.
"""

import pytest
import time
import threading
from sqlalchemy import text

from app.config.settings import DatabaseSettings
from app.persistence.postgres import (
    init_postgres,
    cleanup_postgres,
    get_engine,
    get_pool_status,
    log_pool_stats,
)



@pytest.fixture(scope="module")
def postgres_config():
    """Create test PostgreSQL configuration with small pool."""
    import os
    database_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://postgres:interviewer%40password@100.95.213.103/interviewer"
    )
    return DatabaseSettings(
        database_url=database_url,
        db_pool_size=3,  # Small pool for testing
        db_max_overflow=2,
        db_pool_timeout=5,
        db_echo=False,
    )


@pytest.fixture(scope="module")
def initialized_postgres(postgres_config):
    """Initialize PostgreSQL with small pool."""
    init_postgres(postgres_config)
    yield
    cleanup_postgres()


class TestPoolStatus:
    """Test connection pool status reporting."""
    
    def test_initial_pool_status(self, initialized_postgres):
        """Test pool status after initialization."""
        status = get_pool_status()
        
        assert "pool_size" in status
        assert "checked_out" in status
        assert "overflow" in status
        assert "total_connections" in status
        
        # Initially no connections checked out
        assert status["checked_out"] == 0
        assert status["pool_size"] > 0
    
    def test_pool_status_changes_with_checkout(self, initialized_postgres):
        """Test pool status reflects checked out connections."""
        engine = get_engine()
        
        # Get initial status
        initial_status = get_pool_status()
        initial_checked_out = initial_status["checked_out"]
        
        # Check out connection
        conn = engine.connect()
        
        try:
            # Status should show connection checked out
            during_status = get_pool_status()
            assert during_status["checked_out"] == initial_checked_out + 1
        finally:
            conn.close()
        
        # Status should return to initial
        final_status = get_pool_status()
        assert final_status["checked_out"] == initial_checked_out


class TestPoolCheckoutCheckin:
    """Test connection checkout and checkin."""
    
    def test_single_connection_lifecycle(self, initialized_postgres):
        """Test single connection checkout and return."""
        engine = get_engine()
        
        # Checkout
        conn = engine.connect()
        status_during = get_pool_status()
        assert status_during["checked_out"] > 0
        
        # Use connection
        result = conn.execute(text("SELECT 1"))
        assert result.fetchone()[0] == 1
        
        # Checkin
        conn.close()
        status_after = get_pool_status()
        assert status_after["checked_out"] < status_during["checked_out"]
    
    def test_multiple_connections_sequential(self, initialized_postgres):
        """Test multiple connections checked out sequentially."""
        engine = get_engine()
        
        for i in range(5):
            conn = engine.connect()
            try:
                result = conn.execute(text(f"SELECT {i}"))
                assert result.fetchone()[0] == i
            finally:
                conn.close()
        
        # All should be returned
        final_status = get_pool_status()
        assert final_status["checked_out"] == 0
    
    def test_multiple_connections_concurrent(self, initialized_postgres):
        """Test multiple connections checked out concurrently."""
        engine = get_engine()
        config = engine.pool.size()
        
        connections = []
        try:
            # Check out up to pool size
            for _ in range(min(config, 3)):
                conn = engine.connect()
                connections.append(conn)
            
            # All should work
            for i, conn in enumerate(connections):
                result = conn.execute(text(f"SELECT {i}"))
                assert result.fetchone()[0] == i
            
            # Pool should show connections checked out
            status = get_pool_status()
            assert status["checked_out"] > 0
        finally:
            # Return all
            for conn in connections:
                conn.close()


class TestPoolOverflow:
    """Test pool overflow behavior."""
    
    def test_overflow_when_pool_exhausted(self, initialized_postgres):
        """Test overflow connections created when pool exhausted."""
        engine = get_engine()
        pool_size = engine.pool.size()
        max_overflow = engine.pool.overflow()
        
        connections = []
        try:
            # Exhaust pool + some overflow
            num_connections = min(pool_size + 2, pool_size + max_overflow)
            
            for _ in range(num_connections):
                conn = engine.connect()
                connections.append(conn)
            
            # Check status
            status = get_pool_status()
            assert status["checked_out"] == num_connections
            
            # If we exceeded pool_size, overflow should be > 0
            if num_connections > pool_size:
                assert status["overflow"] > 0
        finally:
            # Return all connections
            for conn in connections:
                conn.close()


class TestPoolTimeout:
    """Test pool timeout behavior."""
    
    def test_timeout_when_pool_exhausted(self, initialized_postgres):
        """Test timeout occurs when waiting for connection."""
        from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
        
        engine = get_engine()
        pool_size = engine.pool.size()
        max_overflow = engine.pool._max_overflow  # Max overflow capacity, not current
        
        # Exhaust pool + overflow
        connections = []
        try:
            for _ in range(pool_size + max_overflow):
                conn = engine.connect()
                connections.append(conn)
            
            # Next checkout should timeout after db_pool_timeout seconds
            with pytest.raises((SQLAlchemyTimeoutError, TimeoutError)):
                # This will block for pool_timeout (5 seconds) then raise TimeoutError
                engine.connect()
        finally:
            # Return connections
            for conn in connections:
                conn.close()


class TestPoolRecycling:
    """Test connection recycling."""
    
    def test_connection_works_after_recycle_time(self, initialized_postgres):
        """Test connections still work after recycle time."""
        engine = get_engine()
        
        # Get connection
        conn1 = engine.connect()
        conn1.close()
        
        # Wait a bit (not full recycle time, but simulate)
        time.sleep(0.1)
        
        # Get new connection (may be recycled)
        conn2 = engine.connect()
        try:
            result = conn2.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1
        finally:
            conn2.close()


class TestConcurrentAccess:
    """Test concurrent pool access."""
    
    def test_concurrent_checkout_safe(self, initialized_postgres):
        """Test concurrent connection checkout is thread-safe."""
        engine = get_engine()
        results = []
        errors = []
        
        def worker(worker_id):
            try:
                conn = engine.connect()
                try:
                    result = conn.execute(text(f"SELECT {worker_id}"))
                    value = result.fetchone()[0]
                    results.append(value)
                finally:
                    conn.close()
            except Exception as e:
                errors.append(str(e))
        
        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all
        for t in threads:
            t.join()
        
        # All should succeed
        assert len(errors) == 0
        assert len(results) == 5
        assert sorted(results) == [0, 1, 2, 3, 4]


class TestPoolMonitoring:
    """Test pool monitoring functions."""
    
    def test_log_pool_stats(self, initialized_postgres, caplog):
        """Test logging pool statistics."""
        import logging
        caplog.set_level(logging.INFO)
        
        log_pool_stats()
        
        # Should have logged something
        assert len(caplog.records) > 0
        
        # Log should contain pool info
        log_text = " ".join([r.message for r in caplog.records])
        assert "Pool Stats" in log_text or "size=" in log_text
    
    def test_pool_status_accuracy(self, initialized_postgres):
        """Test pool status accurately reflects state."""
        engine = get_engine()
        
        # Check out known number of connections
        connections = []
        num_connections = 2
        
        try:
            for _ in range(num_connections):
                conn = engine.connect()
                connections.append(conn)
            
            # Verify status
            status = get_pool_status()
            assert status["checked_out"] >= num_connections
        finally:
            for conn in connections:
                conn.close()


class TestConnectionLeakDetection:
    """Test connection leak scenarios."""
    
    def test_unclosed_connection_detection(self, initialized_postgres):
        """Test that unclosed connections are detectable."""
        engine = get_engine()
        
        initial_status = get_pool_status()
        initial_checked_out = initial_status["checked_out"]
        
        # Check out connection but don't close
        conn = engine.connect()
        
        # Status should show it
        during_status = get_pool_status()
        assert during_status["checked_out"] > initial_checked_out
        
        # Cleanup for test
        conn.close()
