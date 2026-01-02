"""
Main Hybrid Retrieval Pipeline
Dense + Sparse + RRF Fusion + Rerank + Diversity Selection
"""
import time
from typing import Optional, Any
from dataclasses import dataclass

from rag_retrieval.types import SearchHit, ContextChunk, DebugInfo, RetrievalFilters
from rag_retrieval.config import get_settings
from rag_retrieval.text_utils import (
    extract_dense_query, extract_sparse_query, must_have_terms,
    check_term_coverage, truncate_text
)
from rag_retrieval.qdrant_store import QdrantStore
from rag_retrieval.bm25_index import BM25Index
from rag_retrieval.rrf import rrf_fuse
from rag_retrieval.rerank import get_reranker, Reranker


@dataclass
class TopKConfig:
    """Configuration for top-k at each stage"""
    dense: int = 60
    sparse: int = 60
    fused: int = 80
    rerank: int = 12


@dataclass
class DiversityConfig:
    """Configuration for result diversity"""
    max_per_doc: int = 3
    min_docs: int = 3


class HybridRetriever:
    """
    Hybrid Retrieval Pipeline
    
    Pipeline:
    1. Extract dense and sparse queries
    2. Dense search in Qdrant
    3. Sparse search with BM25
    4. Fuse results using RRF
    5. Rerank top_fused using CrossEncoder
    6. Apply diversity constraints
    7. Return final context chunks with debug info
    """
    
    def __init__(
        self,
        qdrant_store: Optional[QdrantStore] = None,
        bm25_index: Optional[BM25Index] = None,
        reranker: Optional[Reranker] = None,
    ):
        self._qdrant = qdrant_store
        self._bm25 = bm25_index
        self._reranker = reranker
    
    def _ensure_stores(self):
        """Lazy initialization of stores"""
        if self._qdrant is None:
            self._qdrant = QdrantStore()
        
        if self._bm25 is None:
            self._bm25 = BM25Index()
            
            # If BM25 index is empty, try to build from Qdrant
            if not self._bm25.is_ready():
                print("📊 Building BM25 index from Qdrant...")
                payloads = self._qdrant.get_all_payloads()
                if payloads:
                    self._bm25.build_from_payloads(payloads)
        
        if self._reranker is None:
            self._reranker = get_reranker()
    
    def retrieve_and_rerank(
        self,
        query: str,
        filters: Optional[dict | RetrievalFilters] = None,
        topk: Optional[dict | TopKConfig] = None,
        rrf_k: int = 60,
        max_iters: int = 2,
        diversity: Optional[dict | DiversityConfig] = None,
        max_chars_per_chunk: int = 1600,
    ) -> tuple[list[ContextChunk], DebugInfo]:
        """
        Main retrieval function with full pipeline
        
        Args:
            query: User query
            filters: Optional metadata filters
            topk: Top-k at each stage (dense, sparse, fused, rerank)
            rrf_k: RRF constant
            max_iters: Max iterations if evidence is weak
            diversity: Diversity constraints
            max_chars_per_chunk: Max chars per chunk in output
        
        Returns:
            Tuple of (final_chunks, debug_info)
        """
        start_time = time.time()
        debug = DebugInfo()
        
        # Initialize
        self._ensure_stores()
        
        # Parse configs
        if isinstance(topk, dict):
            topk = TopKConfig(**topk)
        elif topk is None:
            topk = TopKConfig()
        
        if isinstance(diversity, dict):
            diversity = DiversityConfig(**diversity)
        elif diversity is None:
            diversity = DiversityConfig()
        
        if isinstance(filters, dict):
            filters = RetrievalFilters(**filters)
        
        # Store params for debug
        debug.params = {
            "topk": {"dense": topk.dense, "sparse": topk.sparse, "fused": topk.fused, "rerank": topk.rerank},
            "rrf_k": rrf_k,
            "max_iters": max_iters,
            "diversity": {"max_per_doc": diversity.max_per_doc, "min_docs": diversity.min_docs},
            "filters": filters.to_dict() if filters else {}
        }
        
        # Step 1: Extract queries
        dense_query = extract_dense_query(query)
        sparse_query = extract_sparse_query(query)
        must_terms = must_have_terms(query)
        
        if must_terms:
            debug.add_note(f"Must-have terms: {must_terms}")
        
        # Iteration loop
        current_iter = 0
        final_reranked = []
        
        while current_iter < max_iters:
            current_iter += 1
            
            # Step 2: Dense search
            t0 = time.time()
            query_vector = self._qdrant.embed_text(dense_query)
            debug.timings["embed_ms"] = (time.time() - t0) * 1000
            
            t0 = time.time()
            dense_hits = self._qdrant.search_dense(
                query=dense_query,
                top_k=topk.dense,
                filters=filters,
                query_vector=query_vector
            )
            debug.timings["dense_ms"] = (time.time() - t0) * 1000
            debug.counts["dense_n"] = len(dense_hits)
            
            # Step 3: Sparse search
            t0 = time.time()
            sparse_hits = self._bm25.search_sparse(
                query=sparse_query,
                top_k=topk.sparse,
                filters=filters
            )
            debug.timings["sparse_ms"] = (time.time() - t0) * 1000
            debug.counts["sparse_n"] = len(sparse_hits)
            
            # Step 4: RRF Fusion
            t0 = time.time()
            fused_hits = rrf_fuse(
                dense_hits=dense_hits,
                sparse_hits=sparse_hits,
                rrf_k=rrf_k,
                top_k_fused=topk.fused
            )
            debug.timings["fuse_ms"] = (time.time() - t0) * 1000
            debug.counts["fused_n"] = len(fused_hits)
            
            # Step 5: Rerank (ONLY the fused shortlist!)
            t0 = time.time()
            reranked_hits = self._reranker.rerank(
                query=query,
                hits=fused_hits,
                top_k=topk.rerank
            )
            debug.timings["rerank_ms"] = (time.time() - t0) * 1000
            debug.counts["reranked_n"] = len(reranked_hits)
            
            # Check term coverage
            if must_terms and reranked_hits:
                covered = 0
                for hit in reranked_hits[:5]:
                    found, total = check_term_coverage(hit.text, must_terms)
                    if found > 0:
                        covered += 1
                
                coverage_ratio = covered / min(5, len(reranked_hits))
                
                if coverage_ratio < 0.4 and current_iter < max_iters:
                    # Weak evidence, try again with expanded search
                    debug.add_note(f"Iteration {current_iter}: weak coverage ({coverage_ratio:.1%}), expanding search")
                    topk.dense = int(topk.dense * 1.2)
                    topk.sparse = int(topk.sparse * 1.2)
                    continue
            
            final_reranked = reranked_hits
            break
        
        if current_iter > 1:
            debug.add_note(f"Used {current_iter} iterations")
        
        # Step 6: Apply diversity constraints
        final_chunks = self._apply_diversity(
            hits=final_reranked,
            max_per_doc=diversity.max_per_doc,
            min_docs=diversity.min_docs,
            max_chars_per_chunk=max_chars_per_chunk,
            query=query
        )
        
        debug.counts["final_n"] = len(final_chunks)
        debug.timings["total_ms"] = (time.time() - start_time) * 1000
        
        return final_chunks, debug
    
    def _apply_diversity(
        self,
        hits: list[SearchHit],
        max_per_doc: int,
        min_docs: int,
        max_chars_per_chunk: int,
        query: str
    ) -> list[ContextChunk]:
        """Apply diversity constraints and convert to ContextChunk"""
        doc_counts: dict[str, int] = {}
        docs_seen: set[str] = set()
        result: list[ContextChunk] = []
        
        for rank, hit in enumerate(hits, start=1):
            doc_id = hit.doc_id
            
            # Check max per doc
            current_count = doc_counts.get(doc_id, 0)
            if current_count >= max_per_doc:
                continue
            
            # Update counts
            doc_counts[doc_id] = current_count + 1
            docs_seen.add(doc_id)
            
            # Generate why_picked
            why_parts = []
            if hit.payload.get("dense_rank"):
                why_parts.append(f"dense #{hit.payload['dense_rank']}")
            if hit.payload.get("sparse_rank"):
                why_parts.append(f"sparse #{hit.payload['sparse_rank']}")
            why_parts.append(f"rerank score {hit.score:.3f}")
            why_picked = ", ".join(why_parts)
            
            chunk = ContextChunk(
                doc_id=doc_id,
                chunk_id=hit.chunk_id,
                text=truncate_text(hit.text, max_chars_per_chunk),
                title=hit.payload.get("title"),
                url=hit.payload.get("url"),
                source_id=hit.payload.get("source_id", ""),
                score=hit.score,
                rank=len(result) + 1,
                why_picked=why_picked
            )
            result.append(chunk)
        
        # Check min_docs constraint
        if len(docs_seen) < min_docs:
            # Try to add more docs from remaining hits
            for hit in hits:
                if hit.doc_id not in docs_seen:
                    docs_seen.add(hit.doc_id)
                    doc_counts[hit.doc_id] = 1
                    
                    chunk = ContextChunk(
                        doc_id=hit.doc_id,
                        chunk_id=hit.chunk_id,
                        text=truncate_text(hit.text, max_chars_per_chunk),
                        title=hit.payload.get("title"),
                        url=hit.payload.get("url"),
                        source_id=hit.payload.get("source_id", ""),
                        score=hit.score,
                        rank=len(result) + 1,
                        why_picked="added for diversity"
                    )
                    result.append(chunk)
                    
                    if len(docs_seen) >= min_docs:
                        break
        
        return result


# Convenience function
def retrieve_and_rerank(
    query: str,
    filters: Optional[dict] = None,
    topk: Optional[dict] = None,
    rrf_k: int = 60,
    max_iters: int = 2,
    diversity: Optional[dict] = None,
    max_chars_per_chunk: int = 1600,
) -> tuple[list[ContextChunk], DebugInfo]:
    """
    Convenience function for hybrid retrieval
    
    Creates a HybridRetriever instance and runs the pipeline.
    For repeated calls, consider reusing a HybridRetriever instance.
    """
    retriever = HybridRetriever()
    return retriever.retrieve_and_rerank(
        query=query,
        filters=filters,
        topk=topk,
        rrf_k=rrf_k,
        max_iters=max_iters,
        diversity=diversity,
        max_chars_per_chunk=max_chars_per_chunk
    )


def format_context_for_llm(chunks: list[ContextChunk]) -> str:
    """Format context chunks for LLM prompt"""
    if not chunks:
        return "(Nenhum contexto encontrado)"
    
    parts = []
    for chunk in chunks:
        parts.append(chunk.to_context_string())
    
    return "\n\n---\n\n".join(parts)
