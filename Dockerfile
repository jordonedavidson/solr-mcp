# Multi-stage build for SOLR MCP Server
FROM python:3.11-slim as builder

# Set build arguments
ARG BUILD_DATE
ARG VERSION=1.0.0
ARG VCS_REF

# Labels
LABEL maintainer="Your Name <your.email@example.com>"
LABEL org.label-schema.build-date=$BUILD_DATE
LABEL org.label-schema.name="SOLR MCP Server"
LABEL org.label-schema.description="Model Context Protocol server for Apache SOLR"
LABEL org.label-schema.url="https://github.com/your-repo/solr-mcp-server"
LABEL org.label-schema.vcs-ref=$VCS_REF
LABEL org.label-schema.vcs-url="https://github.com/your-repo/solr-mcp-server"
LABEL org.label-schema.version=$VERSION
LABEL org.label-schema.schema-version="1.0"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up Python environment
WORKDIR /build
COPY pyproject.toml .
COPY src/ src/
COPY README.md .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -e .

# Production stage
FROM python:3.11-slim as production

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r solrmcp \
    && useradd -r -g solrmcp -d /app -s /sbin/nologin solrmcp

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/solr-mcp-server /usr/local/bin/

# Set up application directory
WORKDIR /app
RUN mkdir -p /app/logs && chown -R solrmcp:solrmcp /app

# Copy source code
COPY --from=builder /build/src/solr_mcp_server /usr/local/lib/python3.11/site-packages/solr_mcp_server/

# Switch to non-root user
USER solrmcp

# Environment variables
ENV PYTHONPATH=/usr/local/lib/python3.11/site-packages
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD solr-mcp-server --validate-config || exit 1

# Expose port
EXPOSE 8080

# Default command
CMD ["solr-mcp-server"]

# Development stage
FROM production as development

USER root

# Install development tools
RUN apt-get update && apt-get install -y \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Install development dependencies
RUN pip install --no-cache-dir pytest pytest-cov pytest-asyncio black isort mypy

USER solrmcp

# Override CMD for development
CMD ["solr-mcp-server", "--log-level", "DEBUG"]
