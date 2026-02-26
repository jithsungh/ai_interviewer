"""
Pytest configuration for bootstrap integration tests

Provides fixtures specific to bootstrap testing.
"""

import pytest
import os
from pathlib import Path
from dotenv import load_dotenv


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Load environment variables from .env file for integration tests"""
    # Find the .env file in the project root
    project_root = Path(__file__).parent.parent.parent.parent
    env_file = project_root / ".env"
    
    if env_file.exists():
        # Load .env file - this will populate os.environ
        load_dotenv(env_file, override=False)
    else:
        pytest.fail(f".env file not found at {env_file}. Integration tests require real environment variables.")
    
    yield
    
    # No cleanup needed - we're using real environment
