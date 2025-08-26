"""
SOLR Client for MCP Server.

This module provides a comprehensive SOLR client with search, faceting, highlighting,
and other advanced SOLR features. It includes proper error handling, connection management,
and result processing.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import pysolr
from pydantic import BaseModel

from .config import SOLRConfig

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """Represents a single search result from SOLR."""

    id: str
    score: Optional[float] = None
    fields: Dict[str, Any] = {}
    highlighting: Optional[Dict[str, List[str]]] = None


class FacetValue(BaseModel):
    """Represents a facet value and its count."""

    value: str
    count: int


class FacetField(BaseModel):
    """Represents a facet field with its values."""

    name: str
    values: List[FacetValue]


class SearchResponse(BaseModel):
    """Comprehensive search response from SOLR."""

    results: List[SearchResult]
    total_found: int
    start: int
    rows: int
    query_time: Optional[int] = None
    facets: Optional[List[FacetField]] = None
    suggestions: Optional[Dict[str, List[str]]] = None


class SOLRClientError(Exception):
    """Base exception for SOLR client errors."""

    pass


class SOLRConnectionError(SOLRClientError):
    """Raised when connection to SOLR fails."""

    pass


class SOLRQueryError(SOLRClientError):
    """Raised when a SOLR query fails."""

    pass


class SOLRClient:
    """
    A comprehensive SOLR client that provides search functionality for the MCP server.

    This client handles connection management, query building, result processing,
    and error handling for SOLR operations.
    """

    def __init__(self, config: SOLRConfig):
        """
        Initialize the SOLR client.

        Args:
            config: SOLR configuration object.
        """
        self.config = config
        self._solr = None
        self._initialize_connection()

    def _initialize_connection(self) -> None:
        """Initialize the SOLR connection."""
        try:
            # Build the full URL to the collection
            collection_url = urljoin(
                f"{self.config.base_url}/", f"{self.config.collection}/"
            )

            # Set up authentication if provided
            auth = None
            if self.config.username and self.config.password:
                auth = (self.config.username, self.config.password)

            self._solr = pysolr.Solr(
                collection_url,
                auth=auth,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
                # Add connection pooling and keep-alive
                session=self._create_session(),
            )

            # Test the connection with retry
            self._ping_with_retry()
            logger.info(f"Successfully connected to SOLR at {collection_url}")

        except Exception as e:
            logger.error(f"Failed to connect to SOLR: {e}")
            raise SOLRConnectionError(f"Failed to connect to SOLR: {e}")

    def _create_session(self):
        """Create a requests session with connection pooling."""
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        # Configure connection adapter with pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy, pool_connections=10, pool_maxsize=20
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set keep-alive
        session.headers.update({"Connection": "keep-alive"})

        return session

    def _ping_with_retry(self, max_retries: int = 3) -> None:
        """Ping SOLR with retry logic."""
        import time

        for attempt in range(max_retries):
            try:
                self._solr.ping()
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(
                    f"SOLR ping attempt {attempt + 1} failed: {e}. Retrying..."
                )
                time.sleep(0.5 * (attempt + 1))  # Progressive backoff

    def ping(self) -> bool:
        """
        Test the SOLR connection.

        Returns:
            True if the connection is successful, False otherwise.
        """
        try:
            if self._solr:
                self._solr.ping()
                return True
        except Exception as e:
            logger.warning(f"SOLR ping failed: {e}")
        return False

    def search(
        self,
        query: str,
        default_field: Optional[str] = None,
        fields: Optional[List[str]] = None,
        start: int = 0,
        rows: Optional[int] = None,
        sort: Optional[str] = None,
        filters: Optional[List[str]] = None,
        facet_fields: Optional[List[str]] = None,
        highlight_fields: Optional[List[str]] = None,
        suggest: bool = False,
        **kwargs: Any,
    ) -> SearchResponse:
        """
        Perform a search query against SOLR.

        Args:
            query: The search query string.
            default_field: fields to search against (df parameter).
            fields: List of fields to return. If None, returns all fields.
            start: Starting offset for results (default: 0).
            rows: Number of results to return. If None, uses config default.
            sort: Sort specification (e.g., 'score desc', 'date asc').
            filters: List of filter queries (fq parameters).
            facet_fields: List of fields to facet on.
            highlight_fields: List of fields to highlight.
            suggest: Whether to include spelling suggestions.
            **kwargs: Additional SOLR parameters.

        Returns:
            SearchResponse object containing results and metadata.

        Raises:
            SOLRQueryError: If the query fails.
        """
        try:
            if rows is None:
                # Default to 100 if not specified
                rows = min(self.config.max_rows, 100)

            # Build search parameters
            search_params = {"q": query, "start": start, "rows": rows, **kwargs}

            # hangke search fields (qf)
            if default_field:
                search_params["df"] = default_field

            # Add field list if specified
            if fields:
                search_params["fl"] = ",".join(fields)

            # Add sort if specified
            if sort:
                search_params["sort"] = sort

            # Add filter queries
            if filters:
                search_params["fq"] = filters

            # Add faceting
            if facet_fields:
                search_params["facet"] = "true"
                search_params["facet.field"] = facet_fields
                search_params["facet.limit"] = self.config.facet_limit
                search_params["facet.mincount"] = 1

            # Add highlighting
            if highlight_fields and self.config.highlight_enabled:
                search_params["hl"] = "true"
                search_params["hl.fl"] = ",".join(highlight_fields)
                search_params["hl.simple.pre"] = "<mark>"
                search_params["hl.simple.post"] = "</mark>"
            elif self.config.highlight_enabled and not highlight_fields:
                # Enable highlighting on all fields if no specific fields requested
                search_params["hl"] = "true"
                search_params["hl.fl"] = "*"
                search_params["hl.simple.pre"] = "<mark>"
                search_params["hl.simple.post"] = "</mark>"

            # Add suggestions
            if suggest:
                search_params["spellcheck"] = "true"
                search_params["spellcheck.build"] = "true"
                search_params["spellcheck.collate"] = "true"

            logger.debug(f"Executing SOLR search with params: {search_params}")

            # Execute the search
            response = self._solr.search(**search_params)

            return self._process_search_response(response)

        except pysolr.SolrError as e:
            logger.error(f"SOLR query error: {e}")
            raise SOLRQueryError(f"SOLR query failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during search: {e}")
            raise SOLRQueryError(f"Unexpected error during search: {e}")

    def suggest_query(self, query: str, count: int = 5) -> Dict[str, List[str]]:
        """
        Get spelling suggestions for a query.

        Args:
            query: The query to get suggestions for.
            count: Maximum number of suggestions to return.

        Returns:
            Dictionary of suggestions.
        """
        try:
            response = self._solr.search(
                q=query,
                rows=0,  # We don't need results, just suggestions
                spellcheck="true",
                **{"spellcheck.count": count, "spellcheck.build": "true"},
            )

            suggestions = {}
            spellcheck = response.spellcheck or {}

            for word, suggestion_data in spellcheck.get("suggestions", {}).items():
                if (
                    isinstance(suggestion_data, dict)
                    and "suggestion" in suggestion_data
                ):
                    suggestions[word] = [
                        s for s in suggestion_data["suggestion"][:count]
                    ]

            return suggestions

        except Exception as e:
            logger.warning(f"Failed to get suggestions: {e}")
            return {}

    def get_schema_fields(self) -> List[str]:
        """
        Get the list of available fields in the SOLR schema.

        Returns:
            List of field names.
        """
        try:
            # This is a simplified approach - in a real implementation,
            # you might want to use the Schema API
            response = self._solr.search("*:*", rows=1, fl="*")
            if response.docs:
                return list(response.docs[0].keys())
            return []
        except Exception as e:
            logger.warning(f"Failed to get schema fields: {e}")
            return []

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get basic statistics about the collection.

        Returns:
            Dictionary with collection statistics.
        """
        try:
            response = self._solr.search("*:*", rows=0)
            return {
                "total_documents": response.hits,
                "collection_name": self.config.collection,
                "solr_url": self.config.base_url,
            }
        except Exception as e:
            logger.warning(f"Failed to get collection stats: {e}")
            return {}

    def _process_search_response(self, response: pysolr.Results) -> SearchResponse:
        """
        Process the raw SOLR response into a SearchResponse object.

        Args:
            response: Raw SOLR response.

        Returns:
            Processed SearchResponse object.
        """
        results = []

        # Process documents
        for doc in response.docs:
            doc_id = doc.get("id", str(hash(str(doc))))
            score = doc.get("score")

            # Remove special fields from the fields dict
            fields = {k: v for k, v in doc.items() if k not in ["id", "score"]}

            # Get highlighting for this document
            highlighting = None
            if hasattr(response, "highlighting") and response.highlighting:
                doc_highlighting = response.highlighting.get(doc_id, {})
                if doc_highlighting:
                    highlighting = doc_highlighting

            results.append(
                SearchResult(
                    id=doc_id, score=score, fields=fields, highlighting=highlighting
                )
            )

        # Process facets
        facets = []
        if hasattr(response, "facets") and response.facets:
            facet_fields = response.facets.get("facet_fields", {})
            for field_name, field_values in facet_fields.items():
                facet_values = []
                # SOLR returns facet values as [value1, count1, value2, count2, ...]
                for i in range(0, len(field_values), 2):
                    if i + 1 < len(field_values):
                        facet_values.append(
                            FacetValue(
                                value=str(field_values[i]), count=field_values[i + 1]
                            )
                        )

                if facet_values:
                    facets.append(FacetField(name=field_name, values=facet_values))

        # Process spelling suggestions
        suggestions = {}
        if hasattr(response, "spellcheck") and response.spellcheck:
            spellcheck_data = response.spellcheck.get("suggestions", {})
            for word, suggestion_data in spellcheck_data.items():
                if (
                    isinstance(suggestion_data, dict)
                    and "suggestion" in suggestion_data
                ):
                    suggestions[word] = suggestion_data["suggestion"]

        return SearchResponse(
            results=results,
            total_found=response.hits,
            start=getattr(response, "start", 0),
            rows=len(results),
            query_time=getattr(response, "qtime", None),
            facets=facets if facets else None,
            suggestions=suggestions if suggestions else None,
        )

    def close(self) -> None:
        """Close the SOLR connection."""
        if self._solr:
            # pysolr doesn't have an explicit close method, but we can clean up
            self._solr = None
            logger.info("SOLR connection closed")

    def __enter__(self) -> "SOLRClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
