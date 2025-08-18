# SOLR MCP Server - System Architecture and Design

## Overview

The SOLR MCP Server is a Model Context Protocol (MCP) server that provides seamless integration between MCP clients and Apache SOLR search engine. It exposes SOLR's powerful search capabilities through a standardized MCP interface, enabling AI assistants and other MCP clients to perform sophisticated search operations on SOLR collections.

## Architecture

### High-Level Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   MCP Client    │────▶│  SOLR MCP       │────▶│  Apache SOLR    │
│  (AI Assistant) │     │    Server       │     │   Collection    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │
                              ▼
                        ┌─────────────────┐
                        │  Configuration  │
                        │   (.env file)   │
                        └─────────────────┘
```

### Component Architecture

The system is organized into several key components:

```
solr_mcp_server/
├── config.py          # Configuration management
├── solr_client.py     # SOLR client wrapper
├── server.py          # MCP server implementation
├── main.py            # Entry point and CLI
└── __init__.py        # Package initialization
```

## Core Components

### 1. Configuration Management (`config.py`)

The configuration system provides robust, validated configuration loading from environment variables and `.env` files.

**Key Classes:**
- `SOLRConfig`: SOLR-specific configuration (URL, collection, authentication, etc.)
- `MCPConfig`: MCP server configuration (host, port, logging)
- `OllamaConfig`: Optional Ollama integration configuration
- `Config`: Main configuration container

**Features:**
- Pydantic-based validation with clear error messages
- Support for both environment variables and `.env` files
- Type safety with automatic conversion and validation
- Comprehensive error handling for invalid configurations

**Environment Variables:**
```bash
# Required
SOLR_COLLECTION=your_collection_name

# Optional with defaults
SOLR_BASE_URL=http://localhost:8983/solr
SOLR_USERNAME=
SOLR_PASSWORD=
SOLR_TIMEOUT=30
SOLR_VERIFY_SSL=true
SOLR_MAX_ROWS=1000
SOLR_DEFAULT_SEARCH_FIELD=text
SOLR_FACET_LIMIT=100
SOLR_HIGHLIGHT_ENABLED=true

MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=8080
LOG_LEVEL=INFO

# Optional Ollama integration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2
```

### 2. SOLR Client (`solr_client.py`)

A comprehensive wrapper around the `pysolr` library that provides:

**Key Classes:**
- `SOLRClient`: Main client class with connection management
- `SearchResult`: Individual search result representation
- `SearchResponse`: Complete search response with metadata
- `FacetField`: Facet information container
- `FacetValue`: Individual facet value and count

**Features:**
- Connection management with authentication support
- Comprehensive search functionality:
  - Basic text search
  - Field-specific search
  - Filtered search (fq parameters)
  - Faceted search with configurable limits
  - Result highlighting with customizable markup
  - Spelling suggestions and corrections
  - Sorting and pagination
- Schema introspection
- Collection statistics
- Robust error handling and logging
- Context manager support for resource cleanup

**Search Capabilities:**
```python
# Basic search
response = client.search("search terms")

# Advanced search with all options
response = client.search(
    query="search terms",
    fields=["title", "content", "author"],
    start=0,
    rows=20,
    sort="score desc",
    filters=["status:published", "category:books"],
    facet_fields=["category", "author"],
    highlight_fields=["title", "content"],
    suggest=True
)
```

### 3. MCP Server (`server.py`)

The core MCP server implementation that exposes SOLR functionality through MCP tools.

**Available Tools:**

1. **search** - Basic search functionality
   - Parameters: query (required), rows, start
   - Returns: results with scores and fields

2. **advanced_search** - Advanced search with filtering and field selection
   - Parameters: query (required), fields, filters, sort, rows, start
   - Returns: filtered and sorted results

3. **faceted_search** - Search with facet aggregation
   - Parameters: query (required), facet_fields (required), filters, rows
   - Returns: results with facet counts

4. **search_with_highlighting** - Search with result highlighting
   - Parameters: query (required), highlight_fields, rows, start
   - Returns: results with highlighted matches

5. **get_suggestions** - Get spelling suggestions for queries
   - Parameters: query (required), count
   - Returns: spelling suggestions

6. **get_schema_fields** - Retrieve available schema fields
   - Parameters: none
   - Returns: list of available fields

7. **get_collection_stats** - Get collection statistics
   - Parameters: none
   - Returns: document count and collection info

8. **ping_solr** - Test SOLR connection health
   - Parameters: none
   - Returns: health status and connection info

**Error Handling:**
- Comprehensive error catching and reporting
- SOLR-specific error translation
- Proper MCP error code mapping
- Detailed logging for debugging

### 4. Main Entry Point (`main.py`)

The command-line interface and application entry point.

**Features:**
- Argument parsing with comprehensive help
- Configuration validation mode
- Graceful shutdown handling
- Logging setup and configuration
- Signal handling (SIGINT, SIGTERM)

**CLI Usage:**
```bash
# Basic usage
solr-mcp-server

# With custom configuration
solr-mcp-server --env-file /path/to/config.env

# Debug mode
solr-mcp-server --log-level DEBUG

# Validate configuration only
solr-mcp-server --validate-config
```

## Data Flow

### Request Processing Flow

```
1. MCP Client Request
   ↓
2. MCP Protocol Handling
   ↓
3. Tool Parameter Validation
   ↓
4. SOLR Client Method Call
   ↓
5. SOLR HTTP Request
   ↓
6. Response Processing
   ↓
7. Result Serialization
   ↓
8. MCP Response
```

### Search Request Flow

```
Client Search Request
├── Parameter Validation
├── Query Building
│   ├── Base Query (q parameter)
│   ├── Field List (fl parameter)
│   ├── Filters (fq parameters)
│   ├── Faceting (facet.* parameters)
│   ├── Highlighting (hl.* parameters)
│   └── Pagination (start, rows)
├── SOLR HTTP Request
├── Response Processing
│   ├── Document Results
│   ├── Facet Aggregation
│   ├── Highlighting Extraction
│   └── Metadata Collection
└── Structured Response
```

## Error Handling Strategy

### Error Hierarchy

```
Exception
└── SOLRClientError (Base SOLR error)
    ├── SOLRConnectionError (Connection issues)
    └── SOLRQueryError (Query execution issues)
```

### Error Flow

1. **Connection Errors**: Network issues, authentication failures
2. **Query Errors**: Invalid syntax, missing fields, SOLR-specific errors
3. **Configuration Errors**: Invalid settings, missing required values
4. **MCP Errors**: Protocol violations, invalid tool calls

### Error Responses

All errors are properly mapped to MCP error codes:
- `INVALID_PARAMS`: Invalid tool parameters
- `INTERNAL_ERROR`: SOLR or system errors

## Performance Considerations

### Connection Management
- Persistent connections to SOLR
- Connection pooling through pysolr
- Configurable timeouts
- Health checking with ping

### Query Optimization
- Configurable result limits (max 1000 rows)
- Efficient field selection
- Smart faceting limits
- Highlighting optimization

### Memory Management
- Streaming result processing
- Lazy evaluation where possible
- Proper resource cleanup
- Context manager patterns

## Security Features

### Authentication
- HTTP Basic Authentication support
- Username/password configuration
- SSL/TLS support with verification control

### Input Validation
- Pydantic-based validation
- SQL injection prevention (through SOLR's query parser)
- Parameter sanitization
- Configuration validation

### Logging Security
- No credential logging
- Configurable log levels
- Structured logging format
- Error message sanitization

## Integration Points

### SOLR Integration
- Compatible with SOLR 6.0+
- Support for SolrCloud and standalone
- Standard SOLR query syntax
- All major SOLR features supported

### MCP Integration
- MCP Protocol 2024-11-05
- Standard tool definitions
- Proper error handling
- Streaming support

### Optional Ollama Integration
- Configuration for local LLM integration
- Placeholder for future AI-enhanced search features
- Configurable model selection

## Monitoring and Observability

### Logging
- Structured logging with timestamps
- Configurable log levels
- Component-specific loggers
- Request/response logging

### Health Checks
- SOLR connection monitoring
- Collection accessibility verification
- Performance metrics (query time)
- Error rate tracking

### Metrics
- Search query count and timing
- Error rates by type
- Connection health status
- Resource utilization

## Deployment Architecture

### Standalone Deployment
```
┌─────────────────┐
│   MCP Client    │
└─────────┬───────┘
          │ stdio
┌─────────▼───────┐
│ SOLR MCP Server │
└─────────┬───────┘
          │ HTTP
┌─────────▼───────┐
│   Apache SOLR   │
└─────────────────┘
```

### Production Deployment
```
┌─────────────────┐
│   MCP Client    │
└─────────┬───────┘
          │ stdio/network
┌─────────▼───────┐
│ SOLR MCP Server │ (with logging, monitoring)
└─────────┬───────┘
          │ HTTP/HTTPS
┌─────────▼───────┐
│   Load Balancer │
└─────────┬───────┘
          │
    ┌─────┴─────┐
    ▼           ▼
┌─────────┐ ┌─────────┐
│ SOLR #1 │ │ SOLR #2 │ (SolrCloud cluster)
└─────────┘ └─────────┘
```

## Testing Strategy

### Unit Tests
- Configuration validation
- SOLR client functionality
- Server tool implementations
- Error handling scenarios
- Mock-based testing for isolation

### Functional Tests
- End-to-end workflows
- Real SOLR integration
- Performance benchmarking
- Error scenario testing
- Configuration validation

### Test Structure
```
tests/
├── unit/                 # Isolated component tests
│   ├── test_config.py   # Configuration tests
│   ├── test_solr_client.py  # Client tests
│   └── test_server.py   # Server tests
├── functional/          # Integration tests
│   └── test_integration.py  # End-to-end tests
└── conftest.py          # Test configuration
```

## Future Enhancements

### Planned Features
1. **Advanced Analytics**
   - Query performance analytics
   - Search result quality metrics
   - Usage pattern analysis

2. **Enhanced AI Integration**
   - Ollama-powered query enhancement
   - Semantic search capabilities
   - Automated query optimization

3. **Extended SOLR Features**
   - More Like This (MLT) queries
   - Clustering and classification
   - Streaming expressions
   - Update operations (if needed)

4. **Operational Improvements**
   - Health check endpoints
   - Prometheus metrics export
   - Distributed tracing
   - Auto-scaling support

### Extensibility Points
- Plugin system for custom tools
- Custom result processors
- Authentication backends
- Monitoring adapters

## Development Guidelines

### Code Style
- Python 3.8+ compatibility
- Type hints throughout
- Comprehensive docstrings
- Black code formatting
- isort import organization

### Testing Requirements
- Minimum 90% code coverage
- All public APIs tested
- Error conditions covered
- Performance benchmarks

### Documentation Standards
- API documentation for all public methods
- Configuration examples
- Deployment guides
- Troubleshooting guides

This architecture provides a robust, scalable, and maintainable foundation for SOLR-MCP integration while following best practices for both MCP servers and SOLR client applications.
