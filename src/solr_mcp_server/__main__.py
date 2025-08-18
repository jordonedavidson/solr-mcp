"""
Entry point for running solr_mcp_server as a module.

This allows the package to be executed with:
    python -m src.solr_mcp_server
"""

from .main import main

if __name__ == "__main__":
    main()
