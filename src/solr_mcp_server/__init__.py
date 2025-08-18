"""
SOLR MCP Server - A Model Context Protocol server for Apache SOLR search functionality.

This package provides an MCP server that exposes SOLR search capabilities to MCP clients,
allowing for rich search functionality including faceted search, highlighting, and more.
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .config import Config, get_config
from .solr_client import SOLRClient
from .server import SOLRMCPServer

__all__ = ["Config", "get_config", "SOLRClient", "SOLRMCPServer"]
