"""
BM25 Index for Sparse Retrieval
Implements BM25Okapi with persistence and filtering
"""
import json
import pickle
from pathlib import Path
from typing import Optional, Any
from rank_bm25 import BM25Okapi

from rag_retrieval.config import get_index_path
from rag_retrieval.types import SearchHit, RetrievalFilters
from rag_retrieval.text_utils import tokenize_ptbr


class BM25Index:
    """BM25 sparse retrieval index with persistence"""
    
    def __init__(self, index_path: Optional[Path] = None):
        self.index_path = index_path or get_index_path()
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        self._bm25: Optional[BM25Okapi] = None
        self._corpus: list[list[str]] = []  # Tokenized documents
        self._payloads: list[dict] = []  # Original payloads
        self._key_to_idx: dict[str, int] = {}  # (doc_id, chunk_id) -> index
        
        # Try to load existing index
        self._load_if_exists()
    
    def _make_key(self, doc_id: str, chunk_id: int) -> str:
        """Create unique key from doc_id and chunk_id"""
        return f"{doc_id}::{chunk_id}"
    
    def _load_if_exists(self):
        """Load index from disk if it exists"""
        bm25_path = self.index_path / "bm25.pkl"
        meta_path = self.index_path / "bm25_meta.json"
        
        if bm25_path.exists() and meta_path.exists():
            try:
                with open(bm25_path, "rb") as f:
                    data = pickle.load(f)
                    self._bm25 = data["bm25"]
                    self._corpus = data["corpus"]
                
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    self._payloads = meta["payloads"]
                    self._key_to_idx = meta["key_to_idx"]
                
                print(f"✅ Loaded BM25 index: {len(self._payloads)} documents")
            except Exception as e:
                print(f"⚠️ Failed to load BM25 index: {e}")
                self._reset()
    
    def _reset(self):
        """Reset index to empty state"""
        self._bm25 = None
        self._corpus = []
        self._payloads = []
        self._key_to_idx = {}
    
    def save(self):
        """Save index to disk"""
        if not self._bm25:
            print("⚠️ No index to save")
            return
        
        bm25_path = self.index_path / "bm25.pkl"
        meta_path = self.index_path / "bm25_meta.json"
        
        with open(bm25_path, "wb") as f:
            pickle.dump({
                "bm25": self._bm25,
                "corpus": self._corpus
            }, f)
        
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "payloads": self._payloads,
                "key_to_idx": self._key_to_idx
            }, f, ensure_ascii=False)
        
        print(f"💾 Saved BM25 index: {len(self._payloads)} documents")
    
    def build_from_payloads(self, payloads: list[dict], save: bool = True):
        """
        Build BM25 index from list of payloads
        
        Each payload should have:
        - doc_id: str
        - chunk_id: int
        - text: str
        """
        self._reset()
        
        for i, payload in enumerate(payloads):
            doc_id = payload.get("doc_id") or payload.get("source") or f"doc_{i}"
            chunk_id = payload.get("chunk_id", i)
            text = payload.get("text", "")
            
            key = self._make_key(doc_id, chunk_id)
            
            # Tokenize
            tokens = tokenize_ptbr(text, remove_stopwords=True)
            
            self._corpus.append(tokens)
            self._payloads.append(payload)
            self._key_to_idx[key] = len(self._corpus) - 1
        
        # Build BM25
        if self._corpus:
            self._bm25 = BM25Okapi(self._corpus)
            print(f"📊 Built BM25 index: {len(self._corpus)} documents")
        
        if save:
            self.save()
    
    def _matches_filters(self, payload: dict, filters: Optional[RetrievalFilters]) -> bool:
        """Check if payload matches filters"""
        if not filters or filters.is_empty():
            return True
        
        if filters.tenant_id and payload.get("tenant_id") != filters.tenant_id:
            return False
        
        if filters.source_id and payload.get("source_id") != filters.source_id:
            return False
        
        if filters.doc_id:
            if isinstance(filters.doc_id, list):
                if payload.get("doc_id") not in filters.doc_id and payload.get("source") not in filters.doc_id:
                    return False
            elif payload.get("doc_id") != filters.doc_id and payload.get("source") != filters.doc_id:
                return False
        
        if filters.tags:
            payload_tags = set(payload.get("tags", []) or [])
            if not payload_tags.intersection(filters.tags):
                return False
        
        if filters.date_from:
            created = payload.get("created_at", "")
            if created and created < filters.date_from:
                return False
        
        if filters.date_to:
            created = payload.get("created_at", "")
            if created and created > filters.date_to:
                return False
        
        return True
    
    def search_sparse(
        self,
        query: str,
        top_k: int = 60,
        filters: Optional[RetrievalFilters] = None,
    ) -> list[SearchHit]:
        """
        Sparse BM25 search
        
        Args:
            query: Search query
            top_k: Number of results
            filters: Optional filters
        
        Returns:
            List of SearchHit with source="sparse"
        """
        if not self._bm25 or not self._corpus:
            print("⚠️ BM25 index not built")
            return []
        
        # Tokenize query
        query_tokens = tokenize_ptbr(query, remove_stopwords=True)
        
        if not query_tokens:
            return []
        
        # Get BM25 scores for all documents
        scores = self._bm25.get_scores(query_tokens)
        
        # Build candidate list with filters
        candidates = []
        for idx, score in enumerate(scores):
            if score <= 0:
                continue
            
            payload = self._payloads[idx]
            
            # Apply filters
            if not self._matches_filters(payload, filters):
                continue
            
            candidates.append((idx, score, payload))
        
        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Take top_k
        top_candidates = candidates[:top_k]
        
        # Convert to SearchHit
        hits = []
        for idx, score, payload in top_candidates:
            hits.append(SearchHit(
                id=payload.get("_point_id", idx),
                doc_id=payload.get("doc_id") or payload.get("source") or "",
                chunk_id=payload.get("chunk_id", 0),
                text=payload.get("text", ""),
                score=float(score),
                source="sparse",
                payload=payload
            ))
        
        return hits
    
    def count(self) -> int:
        """Get number of indexed documents"""
        return len(self._payloads)
    
    def is_ready(self) -> bool:
        """Check if index is ready for search"""
        return self._bm25 is not None and len(self._corpus) > 0
