"""
Qdrant Vector Store for Dense Retrieval
Handles connection, upsert, and search with filters
"""
from typing import Optional, Any
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue, MatchAny, Range,
    SearchParams, ScoredPoint
)
from sentence_transformers import SentenceTransformer

from rag_retrieval.config import get_settings
from rag_retrieval.types import SearchHit, RetrievalFilters


class QdrantStore:
    """Qdrant vector store for dense retrieval"""
    
    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection_name: Optional[str] = None,
        embed_model: Optional[str] = None,
    ):
        settings = get_settings()
        
        self.url = url or settings.qdrant_url
        self.api_key = api_key or settings.qdrant_api_key
        self.collection_name = collection_name or settings.collection_name
        self.embed_dim = settings.embed_dim
        
        # Initialize Qdrant client
        self.client = QdrantClient(
            url=self.url,
            api_key=self.api_key,
        )
        
        # Initialize embedding model
        model_name = embed_model or settings.embed_model
        self._encoder = SentenceTransformer(model_name)
        
        # Ensure collection exists
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embed_dim,
                    distance=Distance.COSINE
                )
            )
            print(f"✅ Created Qdrant collection: {self.collection_name}")
    
    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for text"""
        return self._encoder.encode(text, convert_to_numpy=True).tolist()
    
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts"""
        return self._encoder.encode(texts, convert_to_numpy=True).tolist()
    
    def upsert_chunks(
        self,
        chunks: list[dict[str, Any]],
        batch_size: int = 100
    ) -> int:
        """
        Upsert chunks to Qdrant
        
        Each chunk should have:
        - id: unique identifier
        - text: content to embed
        - doc_id, chunk_id, source_id, title, url, tenant_id, tags, created_at, extra
        """
        total = 0
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            # Generate embeddings
            texts = [c["text"] for c in batch]
            embeddings = self.embed_texts(texts)
            
            # Build points
            points = []
            for chunk, embedding in zip(batch, embeddings):
                # Generate composite point_id to avoid collisions between documents
                # Format: tenant_id:doc_id:chunk_id (hashed to int for Qdrant)
                tenant_id = chunk.get("tenant_id", "default") or "default"
                doc_id = chunk.get("doc_id", "unknown")
                chunk_id = chunk.get("chunk_id", 0)
                composite_id = f"{tenant_id}:{doc_id}:{chunk_id}"
                
                # Convert to int hash (Qdrant requires int or UUID for point id)
                point_id = abs(hash(composite_id)) % (10 ** 18)
                
                payload = {
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "source_id": chunk.get("source_id", ""),
                    "title": chunk.get("title"),
                    "url": chunk.get("url"),
                    "text": chunk.get("text", ""),
                    "tenant_id": tenant_id,
                    "tags": chunk.get("tags", []),
                    "created_at": chunk.get("created_at"),
                    "extra": chunk.get("extra", {}),
                }
                
                points.append(PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload
                ))
            
            # Upsert batch
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            total += len(batch)
            print(f"📦 Upserted {total}/{len(chunks)} chunks")
        
        return total
    
    def _build_filter(self, filters: Optional[RetrievalFilters]) -> Optional[Filter]:
        """Build Qdrant filter from RetrievalFilters"""
        if not filters or filters.is_empty():
            return None
        
        conditions = []
        
        if filters.tenant_id:
            conditions.append(
                FieldCondition(key="tenant_id", match=MatchValue(value=filters.tenant_id))
            )
        
        if filters.source_id:
            conditions.append(
                FieldCondition(key="source_id", match=MatchValue(value=filters.source_id))
            )
        
        if filters.doc_id:
            if isinstance(filters.doc_id, list):
                conditions.append(
                    FieldCondition(key="source", match=MatchAny(any=filters.doc_id))
                )
            else:
                conditions.append(
                    FieldCondition(key="source", match=MatchValue(value=filters.doc_id))
                )
        
        if filters.tags:
            conditions.append(
                FieldCondition(key="tags", match=MatchAny(any=filters.tags))
            )

        if filters.source:
             if isinstance(filters.source, list):
                 conditions.append(
                     FieldCondition(key="source", match=MatchAny(any=filters.source))
                 )
             else:
                 conditions.append(
                     FieldCondition(key="source", match=MatchValue(value=filters.source))
                 )
        
        if filters.date_from or filters.date_to:
            range_filter = {}
            if filters.date_from:
                range_filter["gte"] = filters.date_from
            if filters.date_to:
                range_filter["lte"] = filters.date_to
            conditions.append(
                FieldCondition(key="created_at", range=Range(**range_filter))
            )
        
        if not conditions:
            return None
        
        return Filter(must=conditions)
    
    def search_dense(
        self,
        query: str,
        top_k: int = 60,
        filters: Optional[RetrievalFilters] = None,
        query_vector: Optional[list[float]] = None,
    ) -> list[SearchHit]:
        """
        Dense vector search in Qdrant
        
        Args:
            query: Search query (used if query_vector not provided)
            top_k: Number of results
            filters: Optional filters
            query_vector: Pre-computed query embedding
        
        Returns:
            List of SearchHit with source="dense"
        """
        # Get query vector
        if query_vector is None:
            query_vector = self.embed_text(query)
        
        # Build filter
        qdrant_filter = self._build_filter(filters)
        
        # Search using query_points (new API in qdrant-client 1.12+)
        try:
            # Try new API first
            from qdrant_client.models import QueryResponse
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=qdrant_filter,
                limit=top_k,
                with_payload=True
            ).points
        except AttributeError:
            # Fallback to old API
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=qdrant_filter,
                limit=top_k,
            )
        
        # Convert to SearchHit
        hits = []
        for result in results:
            payload = result.payload or {}
            hits.append(SearchHit(
                id=result.id,
                doc_id=payload.get("doc_id") or payload.get("source") or "",
                chunk_id=payload.get("chunk_id", 0),
                text=payload.get("text", ""),
                score=float(result.score) if result.score else 0.0,
                source="dense",
                payload=payload
            ))
        
        return hits
    
    def get_all_payloads(
        self,
        filters: Optional[RetrievalFilters] = None,
        limit: int = 10000
    ) -> list[dict]:
        """
        Get all payloads from collection (for BM25 index building)
        """
        qdrant_filter = self._build_filter(filters)
        
        # Scroll through all points
        payloads = []
        offset = None
        
        while True:
            results, offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=qdrant_filter,
                limit=min(100, limit - len(payloads)),
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            for point in results:
                if point.payload:
                    payload = dict(point.payload)
                    payload["_point_id"] = point.id
                    payloads.append(payload)
            
            if offset is None or len(payloads) >= limit:
                break
        
        return payloads
    
    def count(self) -> int:
        """Get number of points in collection"""
        try:
            info = self.client.get_collection(self.collection_name)
            return info.points_count
        except:
            return 0
