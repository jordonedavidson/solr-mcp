"""
Pytest configuration and fixtures for SOLR MCP Server tests.
"""

import pytest
from pathlib import Path
import tempfile
import os

from solr_mcp_server.config import Config, SOLRConfig, MCPConfig


@pytest.fixture
def temp_env_file():
    """Create a temporary .env file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        env_content = """
SOLR_BASE_URL=http://localhost:8983/solr
SOLR_COLLECTION=test_collection
SOLR_USERNAME=test_user
SOLR_PASSWORD=test_pass
SOLR_TIMEOUT=30
SOLR_VERIFY_SSL=false
MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=8080
LOG_LEVEL=INFO
        """
        f.write(env_content.strip())
        temp_file = f.name

    yield Path(temp_file)

    # Cleanup
    os.unlink(temp_file)


@pytest.fixture
def test_config():
    """Provide a test configuration."""
    solr_config = SOLRConfig(
        base_url="http://localhost:8983/solr",
        collection="test_collection",
        username="test_user",
        password="test_pass",
        timeout=30,
        verify_ssl=False,
    )

    mcp_config = MCPConfig(host="localhost", port=8080, log_level="INFO")

    return Config(solr=solr_config, mcp=mcp_config)


@pytest.fixture
def mock_solr_response():
    """Mock SOLR response data for testing."""
    return {
        "responseHeader": {
            "status": 0,
            "QTime": 15,
            "params": {"q": "test query", "wt": "json"},
        },
        "response": {
            "numFound": 2,
            "start": 0,
            "docs": [
                {
                    "id": "doc1",
                    "score": 1.5,
                    "title": ["Test Document 1"],
                    "content": ["This is test content for document 1"],
                    "category": ["books"],
                    "author": ["John Doe"],
                },
                {
                    "id": "doc2",
                    "score": 1.2,
                    "title": ["Test Document 2"],
                    "content": ["This is test content for document 2"],
                    "category": ["articles"],
                    "author": ["Jane Smith"],
                },
            ],
        },
        "facet_counts": {
            "facet_fields": {
                "category": ["books", 5, "articles", 3, "papers", 1],
                "author": ["John Doe", 4, "Jane Smith", 2],
            }
        },
        "highlighting": {
            "doc1": {
                "title": ["<mark>Test</mark> Document 1"],
                "content": ["This is <mark>test</mark> content"],
            },
            "doc2": {
                "title": ["<mark>Test</mark> Document 2"],
                "content": ["This is <mark>test</mark> content"],
            },
        },
        "spellcheck": {
            "suggestions": {"tset": {"suggestion": ["test", "tests", "testing"]}}
        },
    }


@pytest.fixture(autouse=True)
def clean_env_vars():
    """Clean up environment variables before and after each test."""
    # Store original environment variables
    original_env = {}
    env_vars_to_clean = [
        "SOLR_BASE_URL",
        "SOLR_COLLECTION",
        "SOLR_USERNAME",
        "SOLR_PASSWORD",
        "SOLR_TIMEOUT",
        "SOLR_VERIFY_SSL",
        "SOLR_MAX_ROWS",
        "SOLR_DEFAULT_SEARCH_FIELD",
        "SOLR_FACET_LIMIT",
        "SOLR_HIGHLIGHT_ENABLED",
        "MCP_SERVER_HOST",
        "MCP_SERVER_PORT",
        "LOG_LEVEL",
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
    ]

    for var in env_vars_to_clean:
        if var in os.environ:
            original_env[var] = os.environ[var]
        os.environ.pop(var, None)

    yield

    # Restore original environment variables
    for var in env_vars_to_clean:
        os.environ.pop(var, None)

    for var, value in original_env.items():
        os.environ[var] = value
