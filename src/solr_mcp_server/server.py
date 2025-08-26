"""
MCP Server implementation for SOLR search functionality.

This module provides an MCP server that exposes SOLR search capabilities through
various tools including basic search, advanced search, faceted search, and more.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from mcp import McpError, Tool
from mcp.server import Server, InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    INVALID_PARAMS,
    INTERNAL_ERROR,
    ErrorData,
    TextContent,
    EmbeddedResource,
    Tool as ToolDefinition,
)

from .config import Config
from .solr_client import SOLRClient, SOLRClientError

logger = logging.getLogger(__name__)


class SOLRMCPServer:
    """
    MCP Server that provides SOLR search functionality.

    This server exposes various tools for searching SOLR collections,
    including basic search, advanced search with filters, faceted search,
    and schema introspection.
    """

    def __init__(self, config: Config):
        """
        Initialize the SOLR MCP Server.

        Args:
            config: Configuration object containing SOLR and MCP settings.
        """
        self.config = config
        self.solr_client = SOLRClient(config.solr)
        self.server = Server("solr-mcp-server")
        self._setup_tools()

    def _setup_tools(self) -> None:
        """Set up all available tools for the MCP server."""

        @self.server.list_tools()
        async def handle_list_tools() -> List[ToolDefinition]:
            """List all available tools."""
            return [
                ToolDefinition(
                    name="search",
                    description="Perform basic search in SOLR collection",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query string",
                            },
                            "rows": {
                                "type": "integer",
                                "description": "Number of results to return (max 1000)",
                                "minimum": 1,
                                "maximum": 1000,
                                "default": 10,
                            },
                            "start": {
                                "type": "integer",
                                "description": "Starting offset for pagination",
                                "minimum": 0,
                                "default": 0,
                            },
                        },
                        "required": ["query"],
                    },
                ),
                ToolDefinition(
                    name="advanced_search",
                    description="Perform advanced search with filters and field selection",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query string",
                            },
                            "query_fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of fields to search in (qf parameters)",
                            },
                            "fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of fields to return",
                            },
                            "filters": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of filter queries (fq parameters)",
                            },
                            "sort": {
                                "type": "string",
                                "description": "Sort specification (e.g., 'score desc', 'date asc')",
                            },
                            "rows": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 1000,
                                "default": 10,
                            },
                            "start": {"type": "integer", "minimum": 0, "default": 0},
                        },
                        "required": ["query"],
                    },
                ),
                ToolDefinition(
                    name="faceted_search",
                    description="Perform faceted search to get aggregated counts",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query string",
                            },
                            "facet_fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of fields to facet on",
                            },
                            "filters": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of filter queries",
                            },
                            "rows": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 1000,
                                "default": 10,
                            },
                        },
                        "required": ["query", "facet_fields"],
                    },
                ),
                ToolDefinition(
                    name="search_with_highlighting",
                    description="Search with result highlighting",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query string",
                            },
                            "highlight_fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Fields to highlight (empty for all fields)",
                            },
                            "rows": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 1000,
                                "default": 10,
                            },
                            "start": {"type": "integer", "minimum": 0, "default": 0},
                        },
                        "required": ["query"],
                    },
                ),
                ToolDefinition(
                    name="get_suggestions",
                    description="Get spelling suggestions for a query",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Query to get suggestions for",
                            },
                            "count": {
                                "type": "integer",
                                "description": "Maximum number of suggestions",
                                "minimum": 1,
                                "maximum": 20,
                                "default": 5,
                            },
                        },
                        "required": ["query"],
                    },
                ),
                ToolDefinition(
                    name="get_schema_fields",
                    description="Get available fields in the SOLR schema",
                    inputSchema={"type": "object", "properties": {}},
                ),
                ToolDefinition(
                    name="get_collection_stats",
                    description="Get basic statistics about the SOLR collection",
                    inputSchema={"type": "object", "properties": {}},
                ),
                ToolDefinition(
                    name="ping_solr",
                    description="Test SOLR connection",
                    inputSchema={"type": "object", "properties": {}},
                ),
            ]

        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> List[TextContent]:
            """Handle tool calls."""
            try:
                if name == "search":
                    return await self._handle_search(arguments)
                elif name == "advanced_search":
                    return await self._handle_advanced_search(arguments)
                elif name == "faceted_search":
                    return await self._handle_faceted_search(arguments)
                elif name == "search_with_highlighting":
                    return await self._handle_search_with_highlighting(arguments)
                elif name == "get_suggestions":
                    return await self._handle_get_suggestions(arguments)
                elif name == "get_schema_fields":
                    return await self._handle_get_schema_fields(arguments)
                elif name == "get_collection_stats":
                    return await self._handle_get_collection_stats(arguments)
                elif name == "ping_solr":
                    return await self._handle_ping_solr(arguments)
                else:
                    raise McpError(
                        ErrorData(code=INVALID_PARAMS, message=f"Unknown tool: {name}")
                    )
            except SOLRClientError as e:
                logger.error(f"SOLR error in tool {name}: {e}")
                raise McpError(
                    ErrorData(code=INTERNAL_ERROR, message=f"SOLR error: {str(e)}")
                )
            except Exception as e:
                logger.error(f"Unexpected error in tool {name}: {e}")
                raise McpError(
                    ErrorData(code=INTERNAL_ERROR, message=f"Internal error: {str(e)}")
                )

    async def _handle_search(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Handle basic search requests."""
        query = arguments.get("query")
        rows = arguments.get("rows", 10)
        start = arguments.get("start", 0)

        if not query:
            raise McpError(
                ErrorData(code=INVALID_PARAMS, message="Query parameter is required")
            )

        response = self.solr_client.search(query=query, rows=rows, start=start)

        result = {
            "total_found": response.total_found,
            "start": response.start,
            "rows": response.rows,
            "query_time": response.query_time,
            "results": [
                {"id": result.id, "score": result.score, "fields": result.fields}
                for result in response.results
            ],
        }

        return [
            TextContent(type="text", text=json.dumps(result, indent=2, default=str))
        ]

    async def _handle_advanced_search(
        self, arguments: Dict[str, Any]
    ) -> List[TextContent]:
        """Handle advanced search requests."""
        query = arguments.get("query")
        default_field = arguments.get("default_field")
        fields = arguments.get("fields")
        filters = arguments.get("filters")
        sort = arguments.get("sort")
        rows = arguments.get("rows", 10)
        start = arguments.get("start", 0)

        if not query:
            raise McpError(
                ErrorData(code=INVALID_PARAMS, message="Query parameter is required")
            )

        response = self.solr_client.search(
            query=query,
            default_field=default_field,
            fields=fields,
            filters=filters,
            sort=sort,
            rows=rows,
            start=start,
        )

        result = {
            "total_found": response.total_found,
            "start": response.start,
            "rows": response.rows,
            "query_time": response.query_time,
            "results": [
                {"id": result.id, "score": result.score, "fields": result.fields}
                for result in response.results
            ],
        }

        return [
            TextContent(type="text", text=json.dumps(result, indent=2, default=str))
        ]

    async def _handle_faceted_search(
        self, arguments: Dict[str, Any]
    ) -> List[TextContent]:
        """Handle faceted search requests."""
        query = arguments.get("query")
        facet_fields = arguments.get("facet_fields")
        filters = arguments.get("filters")
        rows = arguments.get("rows", 10)

        if not query or not facet_fields:
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message="Query and facet_fields parameters are required",
                )
            )

        response = self.solr_client.search(
            query=query, filters=filters, facet_fields=facet_fields, rows=rows
        )

        result = {
            "total_found": response.total_found,
            "query_time": response.query_time,
            "facets": [
                {
                    "field": facet.name,
                    "values": [
                        {"value": fv.value, "count": fv.count} for fv in facet.values
                    ],
                }
                for facet in response.facets or []
            ],
            "results": [
                {"id": result.id, "score": result.score, "fields": result.fields}
                for result in response.results
            ],
        }

        return [
            TextContent(type="text", text=json.dumps(result, indent=2, default=str))
        ]

    async def _handle_search_with_highlighting(
        self, arguments: Dict[str, Any]
    ) -> List[TextContent]:
        """Handle search with highlighting requests."""
        query = arguments.get("query")
        highlight_fields = arguments.get("highlight_fields")
        rows = arguments.get("rows", 10)
        start = arguments.get("start", 0)

        if not query:
            raise McpError(
                ErrorData(code=INVALID_PARAMS, message="Query parameter is required")
            )

        response = self.solr_client.search(
            query=query, highlight_fields=highlight_fields, rows=rows, start=start
        )

        result = {
            "total_found": response.total_found,
            "start": response.start,
            "rows": response.rows,
            "query_time": response.query_time,
            "results": [
                {
                    "id": result.id,
                    "score": result.score,
                    "fields": result.fields,
                    "highlighting": result.highlighting,
                }
                for result in response.results
            ],
        }

        return [
            TextContent(type="text", text=json.dumps(result, indent=2, default=str))
        ]

    async def _handle_get_suggestions(
        self, arguments: Dict[str, Any]
    ) -> List[TextContent]:
        """Handle suggestion requests."""
        query = arguments.get("query")
        count = arguments.get("count", 5)

        if not query:
            raise McpError(
                ErrorData(code=INVALID_PARAMS, message="Query parameter is required")
            )

        suggestions = self.solr_client.suggest_query(query, count)

        return [
            TextContent(
                type="text", text=json.dumps({"suggestions": suggestions}, indent=2)
            )
        ]

    async def _handle_get_schema_fields(
        self, arguments: Dict[str, Any]
    ) -> List[TextContent]:
        """Handle schema fields requests."""
        fields = self.solr_client.get_schema_fields()

        return [TextContent(type="text", text=json.dumps({"fields": fields}, indent=2))]

    async def _handle_get_collection_stats(
        self, arguments: Dict[str, Any]
    ) -> List[TextContent]:
        """Handle collection statistics requests."""
        stats = self.solr_client.get_collection_stats()

        return [TextContent(type="text", text=json.dumps(stats, indent=2))]

    async def _handle_ping_solr(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Handle SOLR ping requests."""
        is_healthy = self.solr_client.ping()

        result = {
            "status": "healthy" if is_healthy else "unhealthy",
            "collection": self.config.solr.collection,
            "solr_url": self.config.solr.base_url,
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def run(self) -> None:
        """Run the MCP server."""
        logger.info(
            f"Starting SOLR MCP Server for collection: {self.config.solr.collection}"
        )

        # Test SOLR connection before starting
        if not self.solr_client.ping():
            raise RuntimeError(
                "Failed to connect to SOLR. Please check your configuration."
            )

        # Check if STDIN is available for MCP communication
        import sys

        if sys.stdin.isatty():
            raise RuntimeError(
                "This MCP server requires STDIN for communication.\n"
                "It should be started by an MCP client (like Claude Desktop), not run directly.\n"
                "\n"
                "For testing purposes, you can pipe input:\n"
                "  echo '{}' | solr-mcp-server\n"
                "\n"
                "Or use it with an MCP client configuration."
            )

        async with stdio_server() as (read_stream, write_stream):
            logger.info("SOLR MCP Server is running...")

            # Create initialization options using the server's helper method
            initialization_options = self.server.create_initialization_options(
                notification_options=None,
                experimental_capabilities=None,
            )

            await self.server.run(
                read_stream, write_stream, initialization_options, False, True
            )

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.solr_client:
            self.solr_client.close()
            logger.info("SOLR MCP Server cleanup completed")


async def run_server(config: Config) -> None:
    """
    Run the SOLR MCP Server.

    Args:
        config: Configuration object.
    """
    server = SOLRMCPServer(config)
    try:
        await server.run()
    finally:
        server.cleanup()
