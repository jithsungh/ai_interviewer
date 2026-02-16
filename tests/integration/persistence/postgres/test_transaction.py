"""
Integration Tests for Transaction Management

Tests complex transaction scenarios including savepoints and nested transactions.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.config.settings import DatabaseSettings
from app.persistence.postgres import (
    init_postgres,
    cleanup_postgres,
    get_engine,
    db_session_context,
)


@pytest.fixture(scope="module")
def postgres_config():
    """Create test PostgreSQL configuration."""
    import os
    database_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://postgres:interviewer%40password@100.95.213.103/interviewer"
    )
    return DatabaseSettings(
        database_url=database_url,
        db_pool_size=5,
        db_max_overflow=2,
        db_echo=False,
    )


@pytest.fixture(scope="module")
def initialized_postgres(postgres_config):
    """Initialize PostgreSQL for tests."""
    init_postgres(postgres_config)
    yield
    cleanup_postgres()


@pytest.fixture
def test_table_name():
    """Generate unique test table name."""
    import uuid
    return f"test_transactions_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_table(initialized_postgres, test_table_name):
    """Create and cleanup test table."""
    engine = get_engine()
    
    # Create table
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {test_table_name} (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                value INTEGER
            )
        """))
    
    yield test_table_name
    
    # Cleanup
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {test_table_name}"))


class TestBasicTransactions:
    """Test basic transaction operations."""
    
    def test_commit_persists_data(self, test_table):
        """Test committed transaction persists data."""
        engine = get_engine()
        
        # Insert with commit
        with engine.begin() as conn:
            conn.execute(
                text(f"INSERT INTO {test_table} (name, value) VALUES (:name, :value)"),
                {"name": "test1", "value": 100}
            )
        
        # Verify persisted
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT value FROM {test_table} WHERE name = :name"),
                {"name": "test1"}
            )
            row = result.fetchone()
            assert row[0] == 100
    
    def test_rollback_discards_data(self, test_table):
        """Test rolled back transaction discards data."""
        engine = get_engine()
        
        # Insert and rollback
        conn = engine.connect()
        trans = conn.begin()
        try:
            conn.execute(
                text(f"INSERT INTO {test_table} (name, value) VALUES (:name, :value)"),
                {"name": "test_rollback", "value": 200}
            )
            trans.rollback()
        finally:
            conn.close()
        
        # Verify not persisted
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT COUNT(*) FROM {test_table} WHERE name = :name"),
                {"name": "test_rollback"}
            )
            count = result.fetchone()[0]
            assert count == 0
    
    def test_multiple_operations_in_transaction(self, test_table):
        """Test multiple operations in single transaction."""
        engine = get_engine()
        
        # Multiple inserts in one transaction
        with engine.begin() as conn:
            conn.execute(
                text(f"INSERT INTO {test_table} (name, value) VALUES (:name, :value)"),
                {"name": "multi1", "value": 1}
            )
            conn.execute(
                text(f"INSERT INTO {test_table} (name, value) VALUES (:name, :value)"),
                {"name": "multi2", "value": 2}
            )
            conn.execute(
                text(f"INSERT INTO {test_table} (name, value) VALUES (:name, :value)"),
                {"name": "multi3", "value": 3}
            )
        
        # Verify all persisted
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT COUNT(*) FROM {test_table} WHERE name LIKE 'multi%'")
            )
            count = result.fetchone()[0]
            assert count == 3


class TestSavepoints:
    """Test nested transactions using savepoints."""
    
    def test_savepoint_rollback_partial(self, test_table):
        """Test rolling back to savepoint keeps earlier changes."""
        engine = get_engine()
        
        with engine.begin() as conn:
            # Insert first record
            conn.execute(
                text(f"INSERT INTO {test_table} (name, value) VALUES (:name, :value)"),
                {"name": "save1", "value": 1}
            )
            
            # Create savepoint
            savepoint = conn.begin_nested()
            
            # Insert second record
            conn.execute(
                text(f"INSERT INTO {test_table} (name, value) VALUES (:name, :value)"),
                {"name": "save2", "value": 2}
            )
            
            # Rollback savepoint (discards save2, keeps save1)
            savepoint.rollback()
            
            # Transaction commits (save1 persisted, save2 discarded)
        
        # Verify only first record persisted
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT name FROM {test_table} WHERE name LIKE 'save%' ORDER BY name")
            )
            names = [row[0] for row in result.fetchall()]
            assert names == ["save1"]
    
    def test_savepoint_commit_all(self, test_table):
        """Test committing savepoint persists all changes."""
        engine = get_engine()
        
        with engine.begin() as conn:
            # Insert first record
            conn.execute(
                text(f"INSERT INTO {test_table} (name, value) VALUES (:name, :value)"),
                {"name": "commit1", "value": 1}
            )
            
            # Create savepoint
            savepoint = conn.begin_nested()
            
            # Insert second record
            conn.execute(
                text(f"INSERT INTO {test_table} (name, value) VALUES (:name, :value)"),
                {"name": "commit2", "value": 2}
            )
            
            # Commit savepoint
            savepoint.commit()
            
            # Transaction commits
        
        # Verify both records persisted
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT COUNT(*) FROM {test_table} WHERE name LIKE 'commit%'")
            )
            count = result.fetchone()[0]
            assert count == 2


class TestConstraintViolations:
    """Test handling of constraint violations in transactions."""
    
    def test_unique_constraint_violation_rolls_back(self, test_table):
        """Test unique constraint violation triggers rollback."""
        engine = get_engine()
        
        # Insert first record
        with engine.begin() as conn:
            conn.execute(
                text(f"INSERT INTO {test_table} (name, value) VALUES (:name, :value)"),
                {"name": "unique_test", "value": 1}
            )
        
        # Attempt to insert duplicate (should fail)
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(
                    text(f"INSERT INTO {test_table} (name, value) VALUES (:name, :value)"),
                    {"name": "unique_test", "value": 2}  # Duplicate name
                )
        
        # Verify original record still exists
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT value FROM {test_table} WHERE name = :name"),
                {"name": "unique_test"}
            )
            row = result.fetchone()
            assert row[0] == 1  # Original value


class TestContextManager:
    """Test db_session_context context manager."""
    
    def test_context_manager_commits(self, test_table):
        """Test context manager commits on success."""
        with db_session_context() as session:
            session.execute(
                text(f"INSERT INTO {test_table} (name, value) VALUES (:name, :value)"),
                {"name": "ctx_test", "value": 999}
            )
        
        # Verify committed
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT value FROM {test_table} WHERE name = :name"),
                {"name": "ctx_test"}
            )
            row = result.fetchone()
            assert row[0] == 999
    
    def test_context_manager_rollback_on_error(self, test_table):
        """Test context manager rolls back on exception."""
        with pytest.raises(ValueError):
            with db_session_context() as session:
                session.execute(
                    text(f"INSERT INTO {test_table} (name, value) VALUES (:name, :value)"),
                    {"name": "error_test", "value": 888}
                )
                raise ValueError("Test error")
        
        # Verify not committed
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT COUNT(*) FROM {test_table} WHERE name = :name"),
                {"name": "error_test"}
            )
            count = result.fetchone()[0]
            assert count == 0


class TestConcurrentTransactions:
    """Test concurrent transaction behavior."""
    
    def test_concurrent_inserts_isolated(self, test_table):
        """Test concurrent transactions are isolated."""
        import threading
        import time
        
        engine = get_engine()
        results = []
        
        def insert_data(name, value):
            try:
                with engine.begin() as conn:
                    # Simulate some processing time
                    time.sleep(0.1)
                    conn.execute(
                        text(f"INSERT INTO {test_table} (name, value) VALUES (:name, :value)"),
                        {"name": name, "value": value}
                    )
                results.append("success")
            except Exception as e:
                results.append(f"error: {e}")
        
        # Start two concurrent inserts
        thread1 = threading.Thread(target=insert_data, args=("concurrent1", 1))
        thread2 = threading.Thread(target=insert_data, args=("concurrent2", 2))
        
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()
        
        # Both should succeed
        assert len([r for r in results if r == "success"]) == 2
        
        # Verify both records exist
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT COUNT(*) FROM {test_table} WHERE name LIKE 'concurrent%'")
            )
            count = result.fetchone()[0]
            assert count == 2
