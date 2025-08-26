"""
Unit tests for the SOLR client module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

import pysolr

from solr_mcp_server.config import SOLRConfig
from solr_mcp_server.solr_client import (
    SOLRClient,
    SOLRClientError,
    SOLRConnectionError,
    SOLRQueryError,
    SearchResult,
    SearchResponse,
    FacetField,
    FacetValue,
)


@pytest.fixture
def solr_config():
    """Fixture providing a basic SOLR configuration."""
    return SOLRConfig(
        base_url="http://localhost:8983/solr",
        collection="test_collection",
        timeout=30,
        verify_ssl=True,
    )


@pytest.fixture
def mock_solr():
    """Fixture providing a mock SOLR instance."""
    mock = Mock(spec=pysolr.Solr)
    mock.ping.return_value = True
    return mock


class TestSOLRClient:
    """Test cases for SOLR client."""

    @patch("solr_mcp_server.solr_client.pysolr.Solr")
    def test_init_success(self, mock_solr_class, solr_config):
        """Test successful SOLR client initialization."""
        mock_solr_instance = Mock()
        mock_solr_instance.ping.return_value = True
        mock_solr_class.return_value = mock_solr_instance

        client = SOLRClient(solr_config)

        mock_solr_class.assert_called_once_with(
            "http://localhost:8983/solr/test_collection/",
            auth=None,
            timeout=30,
            verify=True,
        )
        mock_solr_instance.ping.assert_called_once()
        assert client.config == solr_config

    @patch("solr_mcp_server.solr_client.pysolr.Solr")
    def test_init_with_auth(self, mock_solr_class, solr_config):
        """Test SOLR client initialization with authentication."""
        solr_config.username = "test_user"
        solr_config.password = "test_pass"

        mock_solr_instance = Mock()
        mock_solr_instance.ping.return_value = True
        mock_solr_class.return_value = mock_solr_instance

        client = SOLRClient(solr_config)

        mock_solr_class.assert_called_once_with(
            "http://localhost:8983/solr/test_collection/",
            auth=("test_user", "test_pass"),
            timeout=30,
            verify=True,
        )

    @patch("solr_mcp_server.solr_client.pysolr.Solr")
    def test_init_connection_failure(self, mock_solr_class, solr_config):
        """Test SOLR client initialization with connection failure."""
        mock_solr_instance = Mock()
        mock_solr_instance.ping.side_effect = Exception("Connection failed")
        mock_solr_class.return_value = mock_solr_instance

        with pytest.raises(SOLRConnectionError, match="Failed to connect to SOLR"):
            SOLRClient(solr_config)

    def test_ping_success(self, solr_config, mock_solr):
        """Test successful ping."""
        with patch("solr_mcp_server.solr_client.pysolr.Solr", return_value=mock_solr):
            client = SOLRClient(solr_config)
            result = client.ping()
            assert result is True

    def test_ping_failure(self, solr_config, mock_solr):
        """Test ping failure."""
        mock_solr.ping.side_effect = Exception("Ping failed")

        with patch("solr_mcp_server.solr_client.pysolr.Solr", return_value=mock_solr):
            client = SOLRClient(solr_config)
            mock_solr.ping.side_effect = Exception(
                "Ping failed"
            )  # Reset for second call
            result = client.ping()
            assert result is False

    def test_basic_search(self, solr_config, mock_solr):
        """Test basic search functionality."""
        # Mock SOLR response
        mock_response = Mock()
        mock_response.docs = [
            {
                "id": "doc1",
                "score": 1.5,
                "title": "Test Document 1",
                "content": "Some content",
            },
            {
                "id": "doc2",
                "score": 1.2,
                "title": "Test Document 2",
                "content": "More content",
            },
        ]
        mock_response.hits = 2
        mock_response.start = 0
        mock_response.qtime = 15
        mock_response.highlighting = None
        mock_response.facets = None
        mock_response.spellcheck = None

        mock_solr.search.return_value = mock_response

        with patch("solr_mcp_server.solr_client.pysolr.Solr", return_value=mock_solr):
            client = SOLRClient(solr_config)
            response = client.search("test query")

            assert len(response.results) == 2
            assert response.total_found == 2
            assert response.start == 0
            assert response.query_time == 15

            # Check first result
            assert response.results[0].id == "doc1"
            assert response.results[0].score == 1.5
            assert response.results[0].fields["title"] == "Test Document 1"
            assert response.results[0].fields["content"] == "Some content"

    def test_search_with_parameters(self, solr_config, mock_solr):
        """Test search with various parameters."""
        mock_response = Mock()
        mock_response.docs = []
        mock_response.hits = 0
        mock_response.start = 10
        mock_response.qtime = 5
        mock_response.highlighting = None
        mock_response.facets = None
        mock_response.spellcheck = None

        mock_solr.search.return_value = mock_response

        with patch("solr_mcp_server.solr_client.pysolr.Solr", return_value=mock_solr):
            client = SOLRClient(solr_config)

            response = client.search(
                query="advanced query",
                fields=["title", "content"],
                start=10,
                rows=20,
                sort="score desc",
                filters=["type:document", "status:published"],
            )

            mock_solr.search.assert_called_once()
            call_args = mock_solr.search.call_args[1]

            assert call_args["q"] == "advanced query"
            assert call_args["fl"] == "title,content"
            assert call_args["start"] == 10
            assert call_args["rows"] == 20
            assert call_args["sort"] == "score desc"
            assert call_args["fq"] == ["type:document", "status:published"]

    def test_faceted_search(self, solr_config, mock_solr):
        """Test faceted search functionality."""
        mock_response = Mock()
        mock_response.docs = []
        mock_response.hits = 0
        mock_response.highlighting = None
        mock_response.spellcheck = None

        # Mock facet response
        mock_response.facets = {
            "facet_fields": {
                "category": ["books", 5, "articles", 3, "papers", 1],
                "author": ["smith", 4, "jones", 2],
            }
        }

        mock_solr.search.return_value = mock_response

        with patch("solr_mcp_server.solr_client.pysolr.Solr", return_value=mock_solr):
            client = SOLRClient(solr_config)

            response = client.search(query="*:*", facet_fields=["category", "author"])

            assert response.facets is not None
            assert len(response.facets) == 2

            # Check category facet
            category_facet = next(f for f in response.facets if f.name == "category")
            assert len(category_facet.values) == 3
            assert category_facet.values[0].value == "books"
            assert category_facet.values[0].count == 5

    def test_search_with_highlighting(self, solr_config, mock_solr):
        """Test search with highlighting."""
        mock_response = Mock()
        mock_response.docs = [{"id": "doc1", "title": "Test Document"}]
        mock_response.hits = 1
        mock_response.highlighting = {
            "doc1": {
                "title": ["<mark>Test</mark> Document"],
                "content": ["This is a <mark>test</mark> document"],
            }
        }
        mock_response.facets = None
        mock_response.spellcheck = None

        mock_solr.search.return_value = mock_response

        with patch("solr_mcp_server.solr_client.pysolr.Solr", return_value=mock_solr):
            client = SOLRClient(solr_config)

            response = client.search(
                query="test", highlight_fields=["title", "content"]
            )

            assert len(response.results) == 1
            assert response.results[0].highlighting is not None
            assert "title" in response.results[0].highlighting
            assert (
                "<mark>Test</mark> Document"
                in response.results[0].highlighting["title"]
            )

    def test_suggest_query(self, solr_config, mock_solr):
        """Test query suggestions."""
        mock_response = Mock()
        mock_response.spellcheck = {
            "suggestions": {"documnt": {"suggestion": ["document", "documents"]}}
        }

        mock_solr.search.return_value = mock_response

        with patch("solr_mcp_server.solr_client.pysolr.Solr", return_value=mock_solr):
            client = SOLRClient(solr_config)

            suggestions = client.suggest_query("documnt")

            assert "documnt" in suggestions
            assert "document" in suggestions["documnt"]
            assert "documents" in suggestions["documnt"]

    def test_get_schema_fields(self, solr_config, mock_solr):
        """Test getting schema fields."""
        mock_response = Mock()
        mock_response.docs = [
            {"id": "doc1", "title": "Test", "content": "Content", "category": "book"}
        ]

        mock_solr.search.return_value = mock_response

        with patch("solr_mcp_server.solr_client.pysolr.Solr", return_value=mock_solr):
            client = SOLRClient(solr_config)

            fields = client.get_schema_fields()

            assert "id" in fields
            assert "title" in fields
            assert "content" in fields
            assert "category" in fields

    def test_get_collection_stats(self, solr_config, mock_solr):
        """Test getting collection statistics."""
        mock_response = Mock()
        mock_response.hits = 1000

        mock_solr.search.return_value = mock_response

        with patch("solr_mcp_server.solr_client.pysolr.Solr", return_value=mock_solr):
            client = SOLRClient(solr_config)

            stats = client.get_collection_stats()

            assert stats["total_documents"] == 1000
            assert stats["collection_name"] == "test_collection"
            assert stats["solr_url"] == "http://localhost:8983/solr"

    def test_search_solr_error(self, solr_config, mock_solr):
        """Test search with SOLR error."""
        mock_solr.search.side_effect = pysolr.SolrError("SOLR query failed")

        with patch("solr_mcp_server.solr_client.pysolr.Solr", return_value=mock_solr):
            client = SOLRClient(solr_config)

            with pytest.raises(SOLRQueryError, match="SOLR query failed"):
                client.search("test query")

    def test_search_unexpected_error(self, solr_config, mock_solr):
        """Test search with unexpected error."""
        mock_solr.search.side_effect = Exception("Unexpected error")

        with patch("solr_mcp_server.solr_client.pysolr.Solr", return_value=mock_solr):
            client = SOLRClient(solr_config)

            with pytest.raises(SOLRQueryError, match="Unexpected error during search"):
                client.search("test query")

    def test_context_manager(self, solr_config, mock_solr):
        """Test using SOLR client as context manager."""
        with patch("solr_mcp_server.solr_client.pysolr.Solr", return_value=mock_solr):
            with SOLRClient(solr_config) as client:
                assert client.config == solr_config
            # Should not raise any errors

    def test_close(self, solr_config, mock_solr):
        """Test closing SOLR client."""
        with patch("solr_mcp_server.solr_client.pysolr.Solr", return_value=mock_solr):
            client = SOLRClient(solr_config)
            client.close()
            assert client._solr is None


class TestSearchResultModels:
    """Test cases for search result models."""

    def test_search_result_creation(self):
        """Test SearchResult creation."""
        result = SearchResult(
            id="doc1",
            score=1.5,
            fields={"title": "Test", "content": "Content"},
            highlighting={"title": ["<mark>Test</mark>"]},
        )

        assert result.id == "doc1"
        assert result.score == 1.5
        assert result.fields["title"] == "Test"
        assert result.highlighting["title"] == ["<mark>Test</mark>"]

    def test_facet_value_creation(self):
        """Test FacetValue creation."""
        facet_value = FacetValue(value="books", count=5)

        assert facet_value.value == "books"
        assert facet_value.count == 5

    def test_facet_field_creation(self):
        """Test FacetField creation."""
        facet_values = [
            FacetValue(value="books", count=5),
            FacetValue(value="articles", count=3),
        ]
        facet_field = FacetField(name="category", values=facet_values)

        assert facet_field.name == "category"
        assert len(facet_field.values) == 2
        assert facet_field.values[0].value == "books"

    def test_search_response_creation(self):
        """Test SearchResponse creation."""
        results = [SearchResult(id="doc1", fields={"title": "Test"})]
        facets = [
            FacetField(name="category", values=[FacetValue(value="books", count=5)])
        ]

        response = SearchResponse(
            results=results,
            total_found=1,
            start=0,
            rows=1,
            query_time=15,
            facets=facets,
            suggestions={"test": ["tests", "testing"]},
        )

        assert len(response.results) == 1
        assert response.total_found == 1
        assert response.query_time == 15
        assert len(response.facets) == 1
        assert "test" in response.suggestions


if __name__ == "__main__":
    pytest.main([__file__])
