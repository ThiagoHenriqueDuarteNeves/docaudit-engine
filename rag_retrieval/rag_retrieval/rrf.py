"""
RRF (Reciprocal Rank Fusion) Implementation
Combines dense and sparse retrieval results
"""
from typing import Optional
from rag_retrieval.types import SearchHit


def rrf_fuse(
    dense_hits: list[SearchHit],
    sparse_hits: list[SearchHit],
    rrf_k: int = 60,
    top_k_fused: int = 80,
    dedupe: bool = True,
) -> list[SearchHit]:
    """
    Fuse dense and sparse results using Reciprocal Rank Fusion (RRF)
    
    RRF Score = Σ 1 / (k + rank_i)
    
    Args:
        dense_hits: Results from dense retrieval
        sparse_hits: Results from sparse retrieval
        rrf_k: RRF constant (default 60, as in original paper)
        top_k_fused: Number of results to return
        dedupe: Deduplicate by (doc_id, chunk_id)
    
    Returns:
        List of fused SearchHit with combined scores
    """
    # Dictionary to accumulate RRF scores
    # Key: (doc_id, chunk_id), Value: (accumulated_score, best_hit)
    score_map: dict[tuple[str, int], tuple[float, SearchHit]] = {}
    
    # Process dense hits
    for rank, hit in enumerate(dense_hits, start=1):
        key = (hit.doc_id, hit.chunk_id)
        rrf_score = 1.0 / (rrf_k + rank)
        
        if key in score_map:
            current_score, current_hit = score_map[key]
            score_map[key] = (current_score + rrf_score, current_hit)
        else:
            # Create new hit with source="fused"
            fused_hit = SearchHit(
                id=hit.id,
                doc_id=hit.doc_id,
                chunk_id=hit.chunk_id,
                text=hit.text,
                score=0.0,  # Will be set later
                source="fused",
                payload={
                    **hit.payload,
                    "dense_rank": rank,
                    "dense_score": hit.score,
                }
            )
            score_map[key] = (rrf_score, fused_hit)
    
    # Process sparse hits
    for rank, hit in enumerate(sparse_hits, start=1):
        key = (hit.doc_id, hit.chunk_id)
        rrf_score = 1.0 / (rrf_k + rank)
        
        if key in score_map:
            current_score, current_hit = score_map[key]
            # Update payload with sparse info
            current_hit.payload["sparse_rank"] = rank
            current_hit.payload["sparse_score"] = hit.score
            score_map[key] = (current_score + rrf_score, current_hit)
        else:
            # Create new hit with source="fused"
            fused_hit = SearchHit(
                id=hit.id,
                doc_id=hit.doc_id,
                chunk_id=hit.chunk_id,
                text=hit.text,
                score=0.0,
                source="fused",
                payload={
                    **hit.payload,
                    "sparse_rank": rank,
                    "sparse_score": hit.score,
                }
            )
            score_map[key] = (rrf_score, fused_hit)
    
    # Build final list with RRF scores
    fused_results = []
    for (doc_id, chunk_id), (rrf_score, hit) in score_map.items():
        hit.score = rrf_score
        hit.payload["rrf_score"] = rrf_score
        fused_results.append(hit)
    
    # Sort by RRF score descending
    fused_results.sort(key=lambda x: x.score, reverse=True)
    
    # Deduplicate if requested (should already be unique but just in case)
    if dedupe:
        seen = set()
        unique_results = []
        for hit in fused_results:
            key = (hit.doc_id, hit.chunk_id)
            if key not in seen:
                seen.add(key)
                unique_results.append(hit)
        fused_results = unique_results
    
    # Return top_k_fused
    return fused_results[:top_k_fused]


def rrf_score_single(rank: int, k: int = 60) -> float:
    """Calculate RRF score for a single rank"""
    return 1.0 / (k + rank)
