"""
Configuration management for the SOLR MCP Server.

This module handles loading and validating configuration from environment variables
and .env files using Pydantic for robust configuration management.
"""

import os
from pathlib import Path
from typing import Optional, Union

from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator


class SOLRConfig(BaseModel):
    """Configuration for SOLR connection and operations."""

    base_url: str = Field(
        default="http://localhost:8983/solr",
        description="Base URL for the SOLR instance",
    )
    collection: str = Field(description="Name of the SOLR collection to search")
    username: Optional[str] = Field(
        default=None, description="Username for SOLR authentication"
    )
    password: Optional[str] = Field(
        default=None, description="Password for SOLR authentication"
    )
    timeout: int = Field(default=30, description="Request timeout in seconds")
    verify_ssl: bool = Field(
        default=True, description="Whether to verify SSL certificates"
    )
    max_rows: int = Field(
        default=1000, description="Maximum number of rows to return in a single query"
    )
    default_search_field: str = Field(
        default="text", description="Default field to search when no field is specified"
    )
    facet_limit: int = Field(
        default=100, description="Maximum number of facet values to return"
    )
    highlight_enabled: bool = Field(
        default=True, description="Whether to enable result highlighting by default"
    )

    @validator("base_url")
    def validate_base_url(cls, v: str) -> str:
        """Validate that the base URL is properly formatted."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("SOLR base URL must start with http:// or https://")
        if v.endswith("/"):
            v = v.rstrip("/")
        return v

    @validator("timeout")
    def validate_timeout(cls, v: int) -> int:
        """Validate that timeout is positive."""
        if v <= 0:
            raise ValueError("Timeout must be positive")
        return v

    @validator("max_rows")
    def validate_max_rows(cls, v: int) -> int:
        """Validate that max_rows is positive and reasonable."""
        if v <= 0:
            raise ValueError("Max rows must be positive")
        if v > 10000:
            raise ValueError("Max rows should not exceed 10000 for performance reasons")
        return v


class MCPConfig(BaseModel):
    """Configuration for the MCP server."""

    host: str = Field(default="localhost", description="Host to bind the MCP server to")
    port: int = Field(default=8080, description="Port to bind the MCP server to")
    log_level: str = Field(default="INFO", description="Logging level")

    @validator("port")
    def validate_port(cls, v: int) -> int:
        """Validate that port is in valid range."""
        if not (1 <= v <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        return v

    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        """Validate that log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v_upper


class OllamaConfig(BaseModel):
    """Configuration for optional Ollama integration."""

    base_url: str = Field(
        default="http://localhost:11434", description="Base URL for Ollama API"
    )
    model: str = Field(
        default="llama2", description="Default model to use for LLM operations"
    )

    @validator("base_url")
    def validate_base_url(cls, v: str) -> str:
        """Validate that the base URL is properly formatted."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Ollama base URL must start with http:// or https://")
        if v.endswith("/"):
            v = v.rstrip("/")
        return v


class Config(BaseModel):
    """Main configuration class that combines all configuration sections."""

    solr: SOLRConfig
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    ollama: Optional[OllamaConfig] = Field(default=None)

    @classmethod
    def from_env(cls, env_file: Optional[Union[str, Path]] = None) -> "Config":
        """
        Load configuration from environment variables and optional .env file.

        Args:
            env_file: Optional path to .env file. If not provided, looks for .env
                     in the current directory.

        Returns:
            Configured Config instance.

        Raises:
            ValueError: If required configuration is missing or invalid.
        """
        # Load .env file if it exists
        if env_file is None:
            env_file = Path.cwd() / ".env"

        if isinstance(env_file, str):
            env_file = Path(env_file)

        if env_file.exists():
            load_dotenv(env_file)

        # Build SOLR config from environment variables
        solr_config = SOLRConfig(
            base_url=os.getenv("SOLR_BASE_URL", "http://localhost:8983/solr"),
            collection=os.getenv("SOLR_COLLECTION", ""),
            username=os.getenv("SOLR_USERNAME") or None,
            password=os.getenv("SOLR_PASSWORD") or None,
            timeout=int(os.getenv("SOLR_TIMEOUT", "30")),
            verify_ssl=os.getenv("SOLR_VERIFY_SSL", "true").lower() == "true",
            max_rows=int(os.getenv("SOLR_MAX_ROWS", "1000")),
            default_search_field=os.getenv("SOLR_DEFAULT_SEARCH_FIELD", "text"),
            facet_limit=int(os.getenv("SOLR_FACET_LIMIT", "100")),
            highlight_enabled=os.getenv("SOLR_HIGHLIGHT_ENABLED", "true").lower()
            == "true",
        )

        if not solr_config.collection:
            raise ValueError("SOLR_COLLECTION environment variable is required")

        # Build MCP config from environment variables
        mcp_config = MCPConfig(
            host=os.getenv("MCP_SERVER_HOST", "localhost"),
            port=int(os.getenv("MCP_SERVER_PORT", "8080")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

        # Build Ollama config if environment variables are present
        ollama_config = None
        ollama_base_url = os.getenv("OLLAMA_BASE_URL")
        ollama_model = os.getenv("OLLAMA_MODEL")

        if ollama_base_url or ollama_model:
            ollama_config = OllamaConfig(
                base_url=ollama_base_url or "http://localhost:11434",
                model=ollama_model or "llama2",
            )

        return cls(
            solr=solr_config,
            mcp=mcp_config,
            ollama=ollama_config,
        )


def get_config(env_file: Optional[Union[str, Path]] = None) -> Config:
    """
    Convenience function to get configuration.

    Args:
        env_file: Optional path to .env file.

    Returns:
        Configured Config instance.
    """
    return Config.from_env(env_file)
