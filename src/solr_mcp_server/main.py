"""
Main entry point for the SOLR MCP Server.

This module provides the command-line interface and main function for running
the SOLR MCP server with proper logging setup and configuration.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

import argparse

from .config import get_config
from .server import run_server


def setup_logging(log_level: str) -> None:
    """
    Set up logging configuration.
    
    Args:
        log_level: The logging level to use.
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set specific loggers to appropriate levels
    logging.getLogger('pysolr').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)


def create_arg_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description="SOLR MCP Server - Model Context Protocol server for Apache SOLR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Use default .env file
  %(prog)s --env-file /path/to/config.env    # Use specific config file
  %(prog)s --log-level DEBUG                 # Enable debug logging
  %(prog)s --validate-config                 # Validate configuration and exit

Environment Variables:
  SOLR_BASE_URL          - SOLR base URL (default: http://localhost:8983/solr)
  SOLR_COLLECTION        - SOLR collection name (required)
  SOLR_USERNAME          - SOLR username (optional)
  SOLR_PASSWORD          - SOLR password (optional)
  SOLR_TIMEOUT           - Request timeout in seconds (default: 30)
  SOLR_VERIFY_SSL        - Verify SSL certificates (default: true)
  MCP_SERVER_HOST        - MCP server host (default: localhost)
  MCP_SERVER_PORT        - MCP server port (default: 8080)
  LOG_LEVEL              - Logging level (default: INFO)
        """
    )
    
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Path to .env file (default: .env in current directory)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Override log level from configuration"
    )
    
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate configuration and exit"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0"
    )
    
    return parser


async def main_async(
    env_file: Optional[Path] = None,
    log_level_override: Optional[str] = None,
    validate_only: bool = False
) -> int:
    """
    Async main function.
    
    Args:
        env_file: Optional path to .env file.
        log_level_override: Optional log level override.
        validate_only: If True, validate configuration and exit.
    
    Returns:
        Exit code (0 for success, non-zero for error).
    """
    try:
        # Load configuration
        config = get_config(env_file)
        
        # Override log level if specified
        if log_level_override:
            config.mcp.log_level = log_level_override.upper()
        
        # Set up logging
        setup_logging(config.mcp.log_level)
        logger = logging.getLogger(__name__)
        
        if validate_only:
            logger.info("Configuration validation successful!")
            logger.info(f"SOLR Collection: {config.solr.collection}")
            logger.info(f"SOLR URL: {config.solr.base_url}")
            logger.info(f"MCP Server: {config.mcp.host}:{config.mcp.port}")
            if config.ollama:
                logger.info(f"Ollama: {config.ollama.base_url} ({config.ollama.model})")
            return 0
        
        logger.info("Starting SOLR MCP Server...")
        logger.info(f"SOLR Collection: {config.solr.collection}")
        logger.info(f"SOLR URL: {config.solr.base_url}")
        
        # Set up graceful shutdown
        shutdown_event = asyncio.Event()
        
        def signal_handler(signum: int, frame) -> None:
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            shutdown_event.set()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run the server
        server_task = asyncio.create_task(run_server(config))
        shutdown_task = asyncio.create_task(shutdown_event.wait())
        
        # Wait for either the server to complete or shutdown signal
        done, pending = await asyncio.wait(
            [server_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Check if server completed with an error
        if server_task in done:
            try:
                await server_task
            except Exception as e:
                logger.error(f"Server error: {e}")
                return 1
        
        logger.info("SOLR MCP Server shutdown completed")
        return 0
        
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main() -> None:
    """Main entry point for the command-line interface."""
    parser = create_arg_parser()
    args = parser.parse_args()
    
    # Run the async main function
    exit_code = asyncio.run(main_async(
        env_file=args.env_file,
        log_level_override=args.log_level,
        validate_only=args.validate_config
    ))
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
