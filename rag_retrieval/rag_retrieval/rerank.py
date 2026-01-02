"""
Reranking Module with CrossEncoder
Falls back to Bi-Encoder similarity if CrossEncoder unavailable
"""
from abc import ABC, abstractmethod
from typing import Optional
import numpy as np

from rag_retrieval.types import SearchHit
from rag_retrieval.config import get_settings


class Reranker(ABC):
    """Abstract base class for rerankers"""
    
    @abstractmethod
    def rerank(
        self,
        query: str,
        hits: list[SearchHit],
        top_k: int = 12
    ) -> list[SearchHit]:
        """
        Rerank hits based on query
        
        Args:
            query: Search query
            hits: Hits to rerank
            top_k: Number of results to return
        
        Returns:
            Reranked hits with updated scores
        """
        pass


class CrossEncoderReranker(Reranker):
    """Reranker using CrossEncoder model"""
    
    def __init__(self, model_name: Optional[str] = None):
        from sentence_transformers import CrossEncoder
        
        self.model_name = model_name or get_settings().cross_encoder_model
        self._model: Optional[CrossEncoder] = None
        self._fallback = False
    
    def _ensure_model(self):
        """Lazy load CrossEncoder model"""
        if self._model is not None:
            return
        
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
            print(f"✅ Loaded CrossEncoder: {self.model_name}")
        except Exception as e:
            print(f"⚠️ Failed to load CrossEncoder: {e}")
            self._fallback = True
    
    def rerank(
        self,
        query: str,
        hits: list[SearchHit],
        top_k: int = 12
    ) -> list[SearchHit]:
        """Rerank using CrossEncoder"""
        if not hits:
            return []
        
        self._ensure_model()
        
        if self._fallback or self._model is None:
            # Fallback: just return top_k by existing score
            sorted_hits = sorted(hits, key=lambda x: x.score, reverse=True)
            return sorted_hits[:top_k]
        
        # Prepare pairs for CrossEncoder
        pairs = [(query, hit.text) for hit in hits]
        
        # Get CrossEncoder scores
        try:
            scores = self._model.predict(pairs)
            
            # Normalize scores to 0-1 range
            if len(scores) > 1:
                min_score = min(scores)
                max_score = max(scores)
                if max_score > min_score:
                    scores = [(s - min_score) / (max_score - min_score) for s in scores]
            
            # Create reranked hits
            reranked = []
            for hit, score in zip(hits, scores):
                reranked_hit = SearchHit(
                    id=hit.id,
                    doc_id=hit.doc_id,
                    chunk_id=hit.chunk_id,
                    text=hit.text,
                    score=float(score),
                    source="reranked",
                    payload={
                        **hit.payload,
                        "rerank_score": float(score),
                        "pre_rerank_score": hit.score,
                    }
                )
                reranked.append(reranked_hit)
            
            # Sort by rerank score descending
            reranked.sort(key=lambda x: x.score, reverse=True)
            
            return reranked[:top_k]
            
        except Exception as e:
            print(f"⚠️ Rerank failed: {e}, using fallback")
            sorted_hits = sorted(hits, key=lambda x: x.score, reverse=True)
            return sorted_hits[:top_k]


class BiEncoderFallbackReranker(Reranker):
    """Fallback reranker using Bi-Encoder similarity"""
    
    def __init__(self, model_name: Optional[str] = None):
        from sentence_transformers import SentenceTransformer
        
        self.model_name = model_name or get_settings().embed_model
        self._model: Optional[SentenceTransformer] = None
    
    def _ensure_model(self):
        if self._model is not None:
            return
        
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self.model_name)
        print(f"✅ Loaded Bi-Encoder for fallback rerank: {self.model_name}")
    
    def rerank(
        self,
        query: str,
        hits: list[SearchHit],
        top_k: int = 12
    ) -> list[SearchHit]:
        """Rerank using cosine similarity with Bi-Encoder"""
        if not hits:
            return []
        
        self._ensure_model()
        
        # Encode query and passages
        query_emb = self._model.encode(query, convert_to_numpy=True)
        passages = [hit.text for hit in hits]
        passage_embs = self._model.encode(passages, convert_to_numpy=True)
        
        # Compute cosine similarities
        similarities = np.dot(passage_embs, query_emb) / (
            np.linalg.norm(passage_embs, axis=1) * np.linalg.norm(query_emb)
        )
        
        # Create reranked hits
        reranked = []
        for hit, sim in zip(hits, similarities):
            reranked_hit = SearchHit(
                id=hit.id,
                doc_id=hit.doc_id,
                chunk_id=hit.chunk_id,
                text=hit.text,
                score=float(sim),
                source="reranked",
                payload={
                    **hit.payload,
                    "rerank_score": float(sim),
                    "pre_rerank_score": hit.score,
                    "rerank_method": "bi-encoder-fallback"
                }
            )
            reranked.append(reranked_hit)
        
        # Sort by similarity descending
        reranked.sort(key=lambda x: x.score, reverse=True)
        
        return reranked[:top_k]


def get_reranker(prefer_cross_encoder: bool = True) -> Reranker:
    """Factory function to get appropriate reranker"""
    if prefer_cross_encoder:
        try:
            return CrossEncoderReranker()
        except Exception:
            pass
    
    return BiEncoderFallbackReranker()
