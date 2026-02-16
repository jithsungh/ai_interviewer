"""
Integration Tests for PostgreSQL Connection

Tests actual database connectivity, connection pooling, and retry logic.
Requires a running PostgreSQL instance (configured via env vars or test config).
"""

import pytest
import os
from sqlalchemy import text

from app.config.settings import DatabaseSettings
from app.persistence.postgres import (
    init_postgres,
    get_engine,
    get_db_session,
    cleanup_postgres,
    check_postgres_connectivity,
    check_postgres_health,
)


@pytest.fixture(scope="module")
def test_database_url():
    """
    Get test database URL from environment or use default.
    
    Set TEST_DATABASE_URL environment variable to override.
    """
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://postgres:interviewer%40password@100.95.213.103/interviewer"
    )


@pytest.fixture(scope="module")
def postgres_config(test_database_url):
    """Create test PostgreSQL configuration."""
    return DatabaseSettings(
        database_url=test_database_url,
        db_pool_size=5,  # Smaller pool for testing
        db_max_overflow=2,
        db_pool_timeout=10,
        db_query_timeout=30,
        db_echo=False,  # Set to True for debugging
    )


@pytest.fixture(scope="module")
def initialized_postgres(postgres_config):
    """
    Initialize PostgreSQL for integration tests.
    
    Runs once per test module.
    """
    # Initialize
    init_postgres(postgres_config)
    
    yield
    
    # Cleanup
    cleanup_postgres()


class TestDatabaseConnection:
    """Test actual database connectivity."""
    
    def test_connection_successful(self, initialized_postgres):
        """Test successful connection to database."""
        engine = get_engine()
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 AS test"))
            row = result.fetchone()
            assert row[0] == 1
    
    def test_query_execution(self, initialized_postgres):
        """Test executing a simple query."""
        engine = get_engine()
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            assert "PostgreSQL" in version
    
    def test_multiple_connections(self, initialized_postgres):
        """Test opening multiple connections."""
        engine = get_engine()
        
        connections = []
        try:
            # Open multiple connections
            for _ in range(3):
                conn = engine.connect()
                connections.append(conn)
                
                # Execute query on each
                result = conn.execute(text("SELECT 1"))
                assert result.fetchone()[0] == 1
        finally:
            # Close all connections
            for conn in connections:
                conn.close()


class TestSessionManagement:
    """Test session factory and lifecycle."""
    
    def test_session_creation(self, initialized_postgres):
        """Test creating a session via dependency."""
        session_gen = get_db_session()
        session = next(session_gen)
        
        try:
            # Execute query
            result = session.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1
        finally:
            # Complete generator to close session
            try:
                next(session_gen)
            except StopIteration:
                pass
    
    def test_session_isolation(self, initialized_postgres):
        """Test that sessions are isolated."""
        # Create two sessions
        session_gen_1 = get_db_session()
        session_1 = next(session_gen_1)
        
        session_gen_2 = get_db_session()
        session_2 = next(session_gen_2)
        
        try:
            # Sessions should be different instances
            assert session_1 is not session_2
        finally:
            # Close both sessions
            for gen in [session_gen_1, session_gen_2]:
                try:
                    next(gen)
                except StopIteration:
                    pass


class TestTransactionManagement:
    """Test transaction commit and rollback."""
    
    @pytest.fixture
    def test_table_name(self):
        """Unique test table name per test."""
        import uuid
        return f"test_table_{uuid.uuid4().hex[:8]}"
    
    def test_transaction_commit(self, initialized_postgres, test_table_name):
        """Test transaction commits changes."""
        engine = get_engine()
        
        # Create test table
        with engine.begin() as conn:
            conn.execute(text(f"""
                CREATE TABLE {test_table_name} (
                    id SERIAL PRIMARY KEY,
                    value TEXT
                )
            """))
        
        try:
            # Insert data with commit
            with engine.begin() as conn:
                conn.execute(
                    text(f"INSERT INTO {test_table_name} (value) VALUES (:value)"),
                    {"value": "test_value"}
                )
            
            # Verify data persisted
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT value FROM {test_table_name}"))
                rows = result.fetchall()
                assert len(rows) == 1
                assert rows[0][0] == "test_value"
        finally:
            # Cleanup
            with engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {test_table_name}"))
    
    def test_transaction_rollback(self, initialized_postgres, test_table_name):
        """Test transaction rollback discards changes."""
        engine = get_engine()
        
        # Create test table
        with engine.begin() as conn:
            conn.execute(text(f"""
                CREATE TABLE {test_table_name} (
                    id SERIAL PRIMARY KEY,
                    value TEXT
                )
            """))
        
        try:
            # Start transaction and insert data
            conn = engine.connect()
            trans = conn.begin()
            
            try:
                conn.execute(
                    text(f"INSERT INTO {test_table_name} (value) VALUES (:value)"),
                    {"value": "test_value"}
                )
                
                # Rollback instead of commit
                trans.rollback()
            finally:
                conn.close()
            
            # Verify no data persisted
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {test_table_name}"))
                count = result.fetchone()[0]
                assert count == 0
        finally:
            # Cleanup
            with engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {test_table_name}"))


class TestConnectionPooling:
    """Test connection pool behavior."""
    
    def test_pool_checkout_checkin(self, initialized_postgres):
        """Test connections are checked out and returned to pool."""
        from app.persistence.postgres import get_pool_status
        
        # Get initial pool status
        initial_status = get_pool_status()
        initial_checked_out = initial_status["checked_out"]
        
        # Check out connection
        engine = get_engine()
        conn = engine.connect()
        
        # Should have one more checked out
        during_status = get_pool_status()
        assert during_status["checked_out"] == initial_checked_out + 1
        
        # Return connection
        conn.close()
        
        # Should be back to initial
        final_status = get_pool_status()
        assert final_status["checked_out"] == initial_checked_out
    
    def test_pool_does_not_exhaust(self, initialized_postgres):
        """Test pool handles multiple concurrent connections."""
        from app.persistence.postgres import get_pool_status
        
        engine = get_engine()
        pool_status = get_pool_status()
        pool_size = pool_status["pool_size"]
        
        connections = []
        try:
            # Check out up to pool_size connections
            for _ in range(min(pool_size, 5)):  # Don't exhaust entire pool
                conn = engine.connect()
                connections.append(conn)
            
            # Should not block or raise error
            status = get_pool_status()
            assert status["checked_out"] > 0
        finally:
            # Return all connections
            for conn in connections:
                conn.close()


class TestHealthChecks:
    """Test health check integration."""
    
    def test_connectivity_check_success(self, initialized_postgres):
        """Test connectivity check succeeds with healthy database."""
        result = check_postgres_connectivity()
        assert result is True
    
    def test_health_check_returns_healthy(self, initialized_postgres):
        """Test health check returns healthy status."""
        health = check_postgres_health()
        
        assert health["status"] in ["healthy", "degraded"]  # May be degraded if latency high
        assert health["latency_ms"] is not None
        assert health["latency_ms"] > 0
        assert health["pool"] is not None
    
    def test_health_check_measures_latency(self, initialized_postgres):
        """Test health check measures query latency."""
        health = check_postgres_health()
        
        # Latency should be measured
        assert "latency_ms" in health
        assert health["latency_ms"] is not None
        
        # Should be reasonable (< 1 second for local DB)
        assert health["latency_ms"] < 1000
    
    def test_health_check_includes_pool_status(self, initialized_postgres):
        """Test health check includes pool metrics."""
        health = check_postgres_health()
        
        assert "pool" in health
        assert health["pool"] is not None
        assert "pool_size" in health["pool"]
        assert "checked_out" in health["pool"]


class TestQueryTimeout:
    """Test query timeout enforcement."""
    
    @pytest.mark.slow
    def test_query_timeout_enforced(self, initialized_postgres):
        """Test long-running queries are terminated."""
        engine = get_engine()
        
        with pytest.raises(Exception):  # Will raise OperationalError or similar
            with engine.connect() as conn:
                # This query will sleep for longer than timeout
                conn.execute(text("SELECT pg_sleep(60)"))


class TestErrorHandling:
    """Test error handling in database operations."""
    
    def test_invalid_query_raises_error(self, initialized_postgres):
        """Test invalid SQL raises appropriate error."""
        engine = get_engine()
        
        with pytest.raises(Exception):  # ProgrammingError
            with engine.connect() as conn:
                conn.execute(text("INVALID SQL SYNTAX"))
    
    def test_connection_close_is_safe(self, initialized_postgres):
        """Test closing connection twice is safe."""
        engine = get_engine()
        conn = engine.connect()
        
        # Close once
        conn.close()
        
        # Close again should not raise error
        conn.close()
