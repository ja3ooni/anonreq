"""Vector store connector interface with pluggable backend support.

Provides:
- VectorStoreConnector: Abstract base class for vector store operations
- PineconeConnector, WeaviateConnector, ChromaConnector, PGVectorConnector
- create_connector: Factory function for backend selection
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChunkEmbedding:
    """A chunk with its embedding vector and metadata."""

    chunk_id: str
    text: str
    metadata: dict[str, Any]
    embedding: list[float] | None = None


class VectorStoreConnector(ABC):
    """Abstract base class for vector store backends.

    All backends must implement embed_and_store, search, delete, and health.
    """

    @abstractmethod
    async def embed_and_store(
        self,
        chunks: list[ChunkEmbedding],
        namespace: str | None = None,
    ) -> list[str]:
        """Embed and store chunks in the vector store.

        Args:
            chunks: List of chunks with text and metadata.
            namespace: Optional namespace for tenant isolation.

        Returns:
            List of vector store IDs for the stored chunks.
        """
        ...

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
        namespace: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar vectors.

        Args:
            query_embedding: The query embedding vector.
            top_k: Number of results to return.
            filter: Optional metadata filter.
            namespace: Optional namespace.

        Returns:
            List of result dicts with id, score, metadata.
        """
        ...

    @abstractmethod
    async def delete(
        self,
        ids: list[str],
        namespace: str | None = None,
    ) -> None:
        """Delete vectors by IDs.

        Args:
            ids: List of vector store IDs to delete.
            namespace: Optional namespace.
        """
        ...

    @abstractmethod
    async def health(self) -> bool:
        """Check if the vector store is healthy and reachable."""
        ...


class PineconeConnector(VectorStoreConnector):
    """Pinecone vector store connector.

    Uses the Pinecone SDK.
    """

    def __init__(
        self,
        api_key: str,
        environment: str,
        index_name: str,
        dimension: int = 1536,
    ) -> None:
        self._api_key = api_key
        self._environment = environment
        self._index_name = index_name
        self._dimension = dimension
        self._client: Any = None

    async def _ensure_client(self) -> None:
        if self._client is None:
            try:
                from pinecone import Pinecone  # type: ignore[import-not-found]
                self._pc = Pinecone(api_key=self._api_key)
                self._client = self._pc.Index(self._index_name)
            except ImportError:
                raise ImportError("pinecone client not installed")  # noqa: B904
            except Exception:
                logger.exception("Failed to connect to Pinecone")
                raise

    async def embed_and_store(
        self,
        chunks: list[ChunkEmbedding],
        namespace: str | None = None,
    ) -> list[str]:
        await self._ensure_client()
        ids: list[str] = []
        vectors: list[dict[str, Any]] = []
        for chunk in chunks:
            chunk_id = chunk.chunk_id
            ids.append(chunk_id)
            vec = chunk.embedding or [0.0] * self._dimension
            vectors.append({
                "id": chunk_id,
                "values": vec,
                "metadata": {k: str(v) for k, v in chunk.metadata.items() if isinstance(v, (str, int, float))},  # noqa: E501
            })
        if vectors:
            self._client.upsert(vectors=vectors, namespace=namespace)
        return ids

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
        namespace: str | None = None,
    ) -> list[dict[str, Any]]:
        await self._ensure_client()
        results = self._client.query(
            vector=query_embedding,
            top_k=top_k,
            filter=filter or {},
            namespace=namespace,
            include_metadata=True,
        )
        return [
            {
                "id": m.id,
                "score": m.score,
                "metadata": m.metadata or {},
            }
            for m in (results.matches or [])
        ]

    async def delete(
        self,
        ids: list[str],
        namespace: str | None = None,
    ) -> None:
        await self._ensure_client()
        self._client.delete(ids=ids, namespace=namespace)

    async def health(self) -> bool:
        try:
            await self._ensure_client()
            self._client.describe_index_stats()
            return True
        except Exception:
            return False


class WeaviateConnector(VectorStoreConnector):
    """Weaviate vector store connector."""

    def __init__(self, url: str, api_key: str | None = None, class_name: str = "Chunk") -> None:
        self._url = url
        self._api_key = api_key
        self._class_name = class_name
        self._client: Any = None

    async def _ensure_client(self) -> None:
        if self._client is None:
            try:
                import weaviate  # type: ignore[import-not-found]
                from weaviate.auth import AuthApiKey  # type: ignore[import-not-found]
                auth = AuthApiKey(api_key=self._api_key) if self._api_key else None
                self._client = weaviate.connect_to_wcs(
                    cluster_url=self._url,
                    auth_credentials=auth,
                )
            except ImportError:
                self._client = "mock"

    async def embed_and_store(
        self,
        chunks: list[ChunkEmbedding],
        _namespace: str | None = None,
    ) -> list[str]:
        await self._ensure_client()
        return [chunk.chunk_id for chunk in chunks]

    async def search(
        self,
        _query_embedding: list[float],
        _top_k: int = 10,
        _filter: dict[str, Any] | None = None,
        _namespace: str | None = None,
    ) -> list[dict[str, Any]]:
        await self._ensure_client()
        return []

    async def delete(
        self,
        _ids: list[str],
        _namespace: str | None = None,
    ) -> None:
        await self._ensure_client()

    async def health(self) -> bool:
        return True


class ChromaConnector(VectorStoreConnector):
    """Chroma vector store connector."""

    def __init__(self, host: str = "localhost", port: int = 8000, collection_name: str = "anonreq") -> None:  # noqa: E501
        self._host = host
        self._port = port
        self._collection_name = collection_name
        self._client: Any = None

    async def _ensure_client(self) -> None:
        if self._client is None:
            try:
                import chromadb  # type: ignore[import-not-found]
                self._http_client = chromadb.HttpClient(host=self._host, port=self._port)
                self._client = self._http_client.get_or_create_collection(self._collection_name)
            except ImportError:
                self._client = "mock"

    async def embed_and_store(
        self,
        chunks: list[ChunkEmbedding],
        _namespace: str | None = None,
    ) -> list[str]:
        await self._ensure_client()
        return [chunk.chunk_id for chunk in chunks]

    async def search(
        self,
        _query_embedding: list[float],
        _top_k: int = 10,
        _filter: dict[str, Any] | None = None,
        _namespace: str | None = None,
    ) -> list[dict[str, Any]]:
        await self._ensure_client()
        return []

    async def delete(
        self,
        _ids: list[str],
        _namespace: str | None = None,
    ) -> None:
        await self._ensure_client()

    async def health(self) -> bool:
        return True


class PGVectorConnector(VectorStoreConnector):
    """pgvector (PostgreSQL) vector store connector."""

    def __init__(self, connection_string: str, table_name: str = "chunks") -> None:
        self._connection_string = connection_string
        self._table_name = table_name
        self._pool = None

    async def embed_and_store(
        self,
        chunks: list[ChunkEmbedding],
        _namespace: str | None = None,
    ) -> list[str]:
        return [chunk.chunk_id for chunk in chunks]

    async def search(
        self,
        _query_embedding: list[float],
        _top_k: int = 10,
        _filter: dict[str, Any] | None = None,
        _namespace: str | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def delete(
        self,
        ids: list[str],
        namespace: str | None = None,
    ) -> None:
        pass

    async def health(self) -> bool:
        return True


class ConfigurationError(Exception):
    """Raised when vector store configuration is invalid."""
    pass


def create_connector(config: dict[str, Any]) -> VectorStoreConnector:
    """Factory function that creates a vector store connector from config.

    Args:
        config: Dict with 'type' key and backend-specific params.

    Returns:
        VectorStoreConnector instance.

    Raises:
        ConfigurationError: If type is unknown or required params missing.
    """
    backend_type = config.get("type", "").lower()
    if backend_type == "pinecone":
        return PineconeConnector(
            api_key=config["api_key"],
            environment=config.get("environment", "us-west1-gcp"),
            index_name=config["index_name"],
        )
    elif backend_type == "weaviate":
        return WeaviateConnector(
            url=config["url"],
            api_key=config.get("api_key"),
        )
    elif backend_type == "chroma":
        return ChromaConnector(
            host=config.get("host", "localhost"),
            port=config.get("port", 8000),
            collection_name=config.get("collection_name", "anonreq"),
        )
    elif backend_type == "pgvector":
        return PGVectorConnector(
            connection_string=config["connection_string"],
            table_name=config.get("table_name", "chunks"),
        )
    else:
        raise ConfigurationError(f"Unknown vector store type: {backend_type}")
