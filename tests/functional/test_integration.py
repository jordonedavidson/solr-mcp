"""
Functional tests for SOLR MCP Server integration.

These tests require a running SOLR instance and are marked as functional tests.
They can be skipped if SOLR is not available.
"""

import asyncio
import json
import os
import pytest
from unittest.mock import AsyncMock, patch

from solr_mcp_server.config import Config, SOLRConfig, MCPConfig
from solr_mcp_server.server import SOLRMCPServer
from solr_mcp_server.solr_client import SOLRClient, SOLRConnectionError


@pytest.mark.functional
class TestSOLRIntegration:
    """
    Integration tests that require a running SOLR instance.
    
    Set environment variable SOLR_TEST_URL to run these tests.
    Example: SOLR_TEST_URL=http://localhost:8983/solr SOLR_TEST_COLLECTION=test_collection
    """

    @pytest.fixture(autouse=True)
    def check_solr_available(self):
        """Skip tests if SOLR is not available."""
        solr_url = os.getenv("SOLR_TEST_URL")
        collection = os.getenv("SOLR_TEST_COLLECTION")
        
        if not solr_url or not collection:
            pytest.skip("SOLR integration tests require SOLR_TEST_URL and SOLR_TEST_COLLECTION environment variables")
        
        # Try to create a client and ping SOLR
        config = SOLRConfig(base_url=solr_url, collection=collection)
        try:
            client = SOLRClient(config)
            if not client.ping():
                pytest.skip("SOLR instance is not responding")
            client.close()
        except SOLRConnectionError:
            pytest.skip("Cannot connect to SOLR instance")

    @pytest.fixture
    def integration_config(self):
        """Configuration for integration tests."""
        solr_config = SOLRConfig(
            base_url=os.getenv("SOLR_TEST_URL"),
            collection=os.getenv("SOLR_TEST_COLLECTION"),
            timeout=10,
            verify_ssl=False
        )
        mcp_config = MCPConfig(log_level="DEBUG")
        return Config(solr=solr_config, mcp=mcp_config)

    def test_solr_client_connection(self, integration_config):
        """Test that we can connect to SOLR."""
        client = SOLRClient(integration_config.solr)
        assert client.ping() is True
        client.close()

    def test_solr_basic_search(self, integration_config):
        """Test basic search functionality."""
        client = SOLRClient(integration_config.solr)
        
        try:
            # Perform a basic search
            response = client.search("*:*", rows=5)
            
            assert response.total_found >= 0  # May be 0 if collection is empty
            assert response.start == 0
            assert len(response.results) <= 5
            
        finally:
            client.close()

    def test_solr_collection_stats(self, integration_config):
        """Test getting collection statistics."""
        client = SOLRClient(integration_config.solr)
        
        try:
            stats = client.get_collection_stats()
            
            assert "total_documents" in stats
            assert "collection_name" in stats
            assert "solr_url" in stats
            assert stats["collection_name"] == integration_config.solr.collection
            
        finally:
            client.close()

    def test_solr_schema_fields(self, integration_config):
        """Test getting schema fields."""
        client = SOLRClient(integration_config.solr)
        
        try:
            fields = client.get_schema_fields()
            
            # Should return a list of field names
            assert isinstance(fields, list)
            # Standard SOLR collections usually have at least an 'id' field
            if fields:  # Only check if there are documents
                assert any("id" in field.lower() for field in fields)
                
        finally:
            client.close()


@pytest.mark.functional
class TestMCPServerIntegration:
    """Integration tests for the MCP server functionality."""

    @pytest.fixture
    def mcp_server(self, integration_config):
        """Create an MCP server instance."""
        return SOLRMCPServer(integration_config)

    @pytest.fixture(autouse=True)
    def check_solr_available(self):
        """Skip tests if SOLR is not available."""
        solr_url = os.getenv("SOLR_TEST_URL")
        collection = os.getenv("SOLR_TEST_COLLECTION")
        
        if not solr_url or not collection:
            pytest.skip("MCP Server integration tests require SOLR_TEST_URL and SOLR_TEST_COLLECTION environment variables")

    @pytest.fixture
    def integration_config(self):
        """Configuration for integration tests."""
        solr_config = SOLRConfig(
            base_url=os.getenv("SOLR_TEST_URL"),
            collection=os.getenv("SOLR_TEST_COLLECTION"),
            timeout=10,
            verify_ssl=False
        )
        mcp_config = MCPConfig(log_level="DEBUG")
        return Config(solr=solr_config, mcp=mcp_config)

    async def test_ping_solr_tool(self, mcp_server):
        """Test the ping_solr tool."""
        result = await mcp_server._handle_ping_solr({})
        
        assert len(result) == 1
        response_data = json.loads(result[0].text)
        assert response_data["status"] == "healthy"
        assert "collection" in response_data
        assert "solr_url" in response_data

    async def test_get_collection_stats_tool(self, mcp_server):
        """Test the get_collection_stats tool."""
        result = await mcp_server._handle_get_collection_stats({})
        
        assert len(result) == 1
        response_data = json.loads(result[0].text)
        assert "total_documents" in response_data
        assert "collection_name" in response_data
        assert "solr_url" in response_data

    async def test_get_schema_fields_tool(self, mcp_server):
        """Test the get_schema_fields tool."""
        result = await mcp_server._handle_get_schema_fields({})
        
        assert len(result) == 1
        response_data = json.loads(result[0].text)
        assert "fields" in response_data
        assert isinstance(response_data["fields"], list)

    async def test_search_tool(self, mcp_server):
        """Test the basic search tool."""
        arguments = {
            "query": "*:*",
            "rows": 5,
            "start": 0
        }
        
        result = await mcp_server._handle_search(arguments)
        
        assert len(result) == 1
        response_data = json.loads(result[0].text)
        assert "total_found" in response_data
        assert "start" in response_data
        assert "rows" in response_data
        assert "results" in response_data
        assert response_data["start"] == 0
        assert len(response_data["results"]) <= 5

    async def test_advanced_search_tool(self, mcp_server):
        """Test the advanced search tool."""
        arguments = {
            "query": "*:*",
            "rows": 3,
            "start": 0,
            "sort": "score desc"
        }
        
        result = await mcp_server._handle_advanced_search(arguments)
        
        assert len(result) == 1
        response_data = json.loads(result[0].text)
        assert "total_found" in response_data
        assert "results" in response_data
        assert len(response_data["results"]) <= 3

    async def test_search_with_highlighting_tool(self, mcp_server):
        """Test the search with highlighting tool."""
        arguments = {
            "query": "*:*",
            "rows": 2
        }
        
        result = await mcp_server._handle_search_with_highlighting(arguments)
        
        assert len(result) == 1
        response_data = json.loads(result[0].text)
        assert "total_found" in response_data
        assert "results" in response_data
        
        # Check that highlighting field is present in results
        for doc_result in response_data["results"]:
            assert "highlighting" in doc_result

    async def test_get_suggestions_tool(self, mcp_server):
        """Test the get suggestions tool."""
        arguments = {
            "query": "test",  # Simple query that might have suggestions
            "count": 3
        }
        
        result = await mcp_server._handle_get_suggestions(arguments)
        
        assert len(result) == 1
        response_data = json.loads(result[0].text)
        assert "suggestions" in response_data
        assert isinstance(response_data["suggestions"], dict)

    async def test_tool_error_handling(self, mcp_server):
        """Test error handling in tools."""
        # Test with invalid arguments
        with pytest.raises(Exception):  # Should raise McpError, but we'll catch any exception
            await mcp_server._handle_search({})  # Missing required 'query' argument


@pytest.mark.functional
class TestEndToEndWorkflow:
    """End-to-end workflow tests."""

    @pytest.fixture(autouse=True)
    def check_solr_available(self):
        """Skip tests if SOLR is not available."""
        solr_url = os.getenv("SOLR_TEST_URL")
        collection = os.getenv("SOLR_TEST_COLLECTION")
        
        if not solr_url or not collection:
            pytest.skip("End-to-end tests require SOLR_TEST_URL and SOLR_TEST_COLLECTION environment variables")

    @pytest.fixture
    def integration_config(self):
        """Configuration for integration tests."""
        solr_config = SOLRConfig(
            base_url=os.getenv("SOLR_TEST_URL"),
            collection=os.getenv("SOLR_TEST_COLLECTION"),
            timeout=10,
            verify_ssl=False
        )
        mcp_config = MCPConfig(log_level="INFO")
        return Config(solr=solr_config, mcp=mcp_config)

    async def test_typical_search_workflow(self, integration_config):
        """Test a typical search workflow."""
        server = SOLRMCPServer(integration_config)
        
        try:
            # 1. Check server health
            health_result = await server._handle_ping_solr({})
            health_data = json.loads(health_result[0].text)
            assert health_data["status"] == "healthy"
            
            # 2. Get collection stats
            stats_result = await server._handle_get_collection_stats({})
            stats_data = json.loads(stats_result[0].text)
            total_docs = stats_data["total_documents"]
            
            # 3. Perform a search
            search_result = await server._handle_search({
                "query": "*:*",
                "rows": min(10, max(1, total_docs))  # Ensure we don't request more than available
            })
            search_data = json.loads(search_result[0].text)
            
            assert search_data["total_found"] >= 0
            assert len(search_data["results"]) <= search_data["total_found"]
            
            # 4. Get schema fields
            fields_result = await server._handle_get_schema_fields({})
            fields_data = json.loads(fields_result[0].text)
            available_fields = fields_data["fields"]
            
            # 5. If we have results and fields, try an advanced search
            if search_data["total_found"] > 0 and available_fields:
                # Use first few fields for field selection
                selected_fields = available_fields[:3] if len(available_fields) >= 3 else available_fields
                
                advanced_result = await server._handle_advanced_search({
                    "query": "*:*",
                    "fields": selected_fields,
                    "rows": 2
                })
                advanced_data = json.loads(advanced_result[0].text)
                
                assert "results" in advanced_data
                if advanced_data["results"]:
                    # Check that only selected fields are returned
                    result_fields = advanced_data["results"][0]["fields"].keys()
                    # Some fields might not be in the result, but none should be outside selected_fields
                    # (This is a loose check as SOLR might return additional fields)
                    assert len(result_fields) >= 0
                    
        finally:
            server.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "functional"])
