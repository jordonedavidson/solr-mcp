"""
Unit tests for the configuration module.
"""

import os
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from solr_mcp_server.config import Config, SOLRConfig, MCPConfig, OllamaConfig, get_config


class TestSOLRConfig:
    """Test cases for SOLR configuration."""

    def test_solr_config_valid(self):
        """Test valid SOLR configuration."""
        config = SOLRConfig(
            base_url="http://localhost:8983/solr",
            collection="test_collection",
            username="user",
            password="pass",
            timeout=30,
            verify_ssl=True
        )
        assert config.base_url == "http://localhost:8983/solr"
        assert config.collection == "test_collection"
        assert config.username == "user"
        assert config.password == "pass"
        assert config.timeout == 30
        assert config.verify_ssl is True

    def test_solr_config_url_validation(self):
        """Test SOLR URL validation."""
        # Test trailing slash removal
        config = SOLRConfig(
            base_url="http://localhost:8983/solr/",
            collection="test"
        )
        assert config.base_url == "http://localhost:8983/solr"

        # Test invalid URL scheme
        with pytest.raises(ValidationError):
            SOLRConfig(base_url="ftp://localhost:8983/solr", collection="test")

    def test_solr_config_timeout_validation(self):
        """Test timeout validation."""
        # Test negative timeout
        with pytest.raises(ValidationError):
            SOLRConfig(base_url="http://localhost:8983/solr", collection="test", timeout=-1)

        # Test zero timeout
        with pytest.raises(ValidationError):
            SOLRConfig(base_url="http://localhost:8983/solr", collection="test", timeout=0)

    def test_solr_config_max_rows_validation(self):
        """Test max_rows validation."""
        # Test negative max_rows
        with pytest.raises(ValidationError):
            SOLRConfig(base_url="http://localhost:8983/solr", collection="test", max_rows=-1)

        # Test zero max_rows
        with pytest.raises(ValidationError):
            SOLRConfig(base_url="http://localhost:8983/solr", collection="test", max_rows=0)

        # Test excessive max_rows
        with pytest.raises(ValidationError):
            SOLRConfig(base_url="http://localhost:8983/solr", collection="test", max_rows=20000)


class TestMCPConfig:
    """Test cases for MCP configuration."""

    def test_mcp_config_valid(self):
        """Test valid MCP configuration."""
        config = MCPConfig(host="0.0.0.0", port=8080, log_level="DEBUG")
        assert config.host == "0.0.0.0"
        assert config.port == 8080
        assert config.log_level == "DEBUG"

    def test_mcp_config_port_validation(self):
        """Test port validation."""
        # Test invalid port ranges
        with pytest.raises(ValidationError):
            MCPConfig(port=0)

        with pytest.raises(ValidationError):
            MCPConfig(port=65536)

        with pytest.raises(ValidationError):
            MCPConfig(port=-1)

    def test_mcp_config_log_level_validation(self):
        """Test log level validation."""
        # Test valid log levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = MCPConfig(log_level=level)
            assert config.log_level == level

        # Test case insensitive
        config = MCPConfig(log_level="debug")
        assert config.log_level == "DEBUG"

        # Test invalid log level
        with pytest.raises(ValidationError):
            MCPConfig(log_level="INVALID")


class TestOllamaConfig:
    """Test cases for Ollama configuration."""

    def test_ollama_config_valid(self):
        """Test valid Ollama configuration."""
        config = OllamaConfig(
            base_url="http://localhost:11434",
            model="llama2"
        )
        assert config.base_url == "http://localhost:11434"
        assert config.model == "llama2"

    def test_ollama_config_url_validation(self):
        """Test Ollama URL validation."""
        # Test trailing slash removal
        config = OllamaConfig(base_url="http://localhost:11434/")
        assert config.base_url == "http://localhost:11434"

        # Test invalid URL scheme
        with pytest.raises(ValidationError):
            OllamaConfig(base_url="ftp://localhost:11434")


class TestConfig:
    """Test cases for main configuration class."""

    def test_config_creation(self):
        """Test basic config creation."""
        solr_config = SOLRConfig(
            base_url="http://localhost:8983/solr",
            collection="test"
        )
        config = Config(solr=solr_config)
        
        assert config.solr.collection == "test"
        assert config.mcp.host == "localhost"
        assert config.mcp.port == 8080
        assert config.ollama is None

    def test_config_with_ollama(self):
        """Test config creation with Ollama."""
        solr_config = SOLRConfig(
            base_url="http://localhost:8983/solr",
            collection="test"
        )
        ollama_config = OllamaConfig(
            base_url="http://localhost:11434",
            model="llama2"
        )
        config = Config(solr=solr_config, ollama=ollama_config)
        
        assert config.ollama is not None
        assert config.ollama.base_url == "http://localhost:11434"
        assert config.ollama.model == "llama2"


class TestConfigFromEnv:
    """Test cases for loading config from environment variables."""

    def test_config_from_env_minimal(self, monkeypatch):
        """Test loading minimal config from environment."""
        monkeypatch.setenv("SOLR_COLLECTION", "test_collection")
        
        config = Config.from_env()
        assert config.solr.collection == "test_collection"
        assert config.solr.base_url == "http://localhost:8983/solr"

    def test_config_from_env_complete(self, monkeypatch):
        """Test loading complete config from environment."""
        monkeypatch.setenv("SOLR_BASE_URL", "https://solr.example.com:8443/solr")
        monkeypatch.setenv("SOLR_COLLECTION", "prod_collection")
        monkeypatch.setenv("SOLR_USERNAME", "solr_user")
        monkeypatch.setenv("SOLR_PASSWORD", "solr_pass")
        monkeypatch.setenv("SOLR_TIMEOUT", "60")
        monkeypatch.setenv("SOLR_VERIFY_SSL", "false")
        monkeypatch.setenv("MCP_SERVER_HOST", "0.0.0.0")
        monkeypatch.setenv("MCP_SERVER_PORT", "9090")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        monkeypatch.setenv("OLLAMA_MODEL", "llama3")
        
        config = Config.from_env()
        
        assert config.solr.base_url == "https://solr.example.com:8443/solr"
        assert config.solr.collection == "prod_collection"
        assert config.solr.username == "solr_user"
        assert config.solr.password == "solr_pass"
        assert config.solr.timeout == 60
        assert config.solr.verify_ssl is False
        assert config.mcp.host == "0.0.0.0"
        assert config.mcp.port == 9090
        assert config.mcp.log_level == "DEBUG"
        assert config.ollama is not None
        assert config.ollama.base_url == "http://localhost:11434"
        assert config.ollama.model == "llama3"

    def test_config_from_env_missing_collection(self, monkeypatch):
        """Test that missing collection raises error."""
        # Clear any existing SOLR_COLLECTION
        monkeypatch.delenv("SOLR_COLLECTION", raising=False)
        
        with pytest.raises(ValueError, match="SOLR_COLLECTION environment variable is required"):
            Config.from_env()

    def test_config_from_env_file(self, tmp_path):
        """Test loading config from .env file."""
        env_file = tmp_path / ".env"
        env_content = """
SOLR_BASE_URL=http://test.example.com:8983/solr
SOLR_COLLECTION=env_test_collection
SOLR_USERNAME=env_user
SOLR_PASSWORD=env_pass
MCP_SERVER_PORT=7070
LOG_LEVEL=WARNING
        """
        env_file.write_text(env_content.strip())
        
        config = Config.from_env(env_file)
        
        assert config.solr.base_url == "http://test.example.com:8983/solr"
        assert config.solr.collection == "env_test_collection"
        assert config.solr.username == "env_user"
        assert config.solr.password == "env_pass"
        assert config.mcp.port == 7070
        assert config.mcp.log_level == "WARNING"

    def test_config_from_nonexistent_env_file(self, tmp_path):
        """Test loading config when .env file doesn't exist."""
        nonexistent_file = tmp_path / "nonexistent.env"
        
        # Should not raise an error, just use environment variables
        # But we need SOLR_COLLECTION set
        os.environ["SOLR_COLLECTION"] = "test_collection"
        try:
            config = Config.from_env(nonexistent_file)
            assert config.solr.collection == "test_collection"
        finally:
            del os.environ["SOLR_COLLECTION"]

    def test_get_config_function(self, monkeypatch):
        """Test the convenience get_config function."""
        monkeypatch.setenv("SOLR_COLLECTION", "convenience_test")
        
        config = get_config()
        assert config.solr.collection == "convenience_test"


if __name__ == "__main__":
    pytest.main([__file__])
