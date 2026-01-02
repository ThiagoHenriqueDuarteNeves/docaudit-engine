"""
FastAPI Endpoints for Hybrid Retrieval
Optional REST API for the retrieval pipeline
"""
from typing import Optional, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rag_retrieval.types import RetrievalFilters
from rag_retrieval.retriever import HybridRetriever, format_context_for_llm
from rag_retrieval.lmstudio import check_lmstudio_connection


app = FastAPI(
    title="RAG Hybrid Retrieval API",
    description="Dense + Sparse + RRF + Rerank retrieval pipeline",
    version="1.0.0"
)

# Singleton retriever (reused across requests)
_retriever: Optional[HybridRetriever] = None


def get_retriever() -> HybridRetriever:
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever


# Request/Response Models
class RetrieveRequest(BaseModel):
    """Request body for /retrieve endpoint"""
    query: str = Field(..., description="Search query")
    filters: Optional[dict] = Field(None, description="Metadata filters")
    topk: Optional[dict] = Field(
        None,
        description="Top-k config: {dense, sparse, fused, rerank}",
        example={"dense": 60, "sparse": 60, "fused": 80, "rerank": 12}
    )
    rrf_k: int = Field(60, description="RRF constant")
    max_iters: int = Field(2, description="Max iterations for weak evidence")
    diversity: Optional[dict] = Field(
        None,
        description="Diversity config: {max_per_doc, min_docs}",
        example={"max_per_doc": 3, "min_docs": 3}
    )
    max_chars_per_chunk: int = Field(1600, description="Max chars per chunk")
    format_for_llm: bool = Field(False, description="Return formatted context string")


class ChunkResponse(BaseModel):
    """Single chunk in response"""
    doc_id: str
    chunk_id: int
    text: str
    title: Optional[str]
    url: Optional[str]
    source_id: str
    score: float
    rank: int
    why_picked: str


class DebugResponse(BaseModel):
    """Debug info in response"""
    timings: dict[str, float]
    counts: dict[str, int]
    params: dict[str, Any]
    notes: list[str]


class RetrieveResponse(BaseModel):
    """Response from /retrieve endpoint"""
    chunks: list[ChunkResponse]
    context: Optional[str] = None
    debug: DebugResponse


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    qdrant_count: int
    bm25_count: int
    lmstudio: dict


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health and dependencies"""
    retriever = get_retriever()
    retriever._ensure_stores()
    
    return HealthResponse(
        status="ok",
        qdrant_count=retriever._qdrant.count() if retriever._qdrant else 0,
        bm25_count=retriever._bm25.count() if retriever._bm25 else 0,
        lmstudio=check_lmstudio_connection()
    )


@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(request: RetrieveRequest):
    """
    Hybrid retrieval endpoint
    
    Performs: Dense + Sparse + RRF Fusion + Rerank + Diversity
    """
    retriever = get_retriever()
    
    try:
        chunks, debug = retriever.retrieve_and_rerank(
            query=request.query,
            filters=request.filters,
            topk=request.topk,
            rrf_k=request.rrf_k,
            max_iters=request.max_iters,
            diversity=request.diversity,
            max_chars_per_chunk=request.max_chars_per_chunk
        )
        
        # Convert to response format
        chunk_responses = [
            ChunkResponse(
                doc_id=c.doc_id,
                chunk_id=c.chunk_id,
                text=c.text,
                title=c.title,
                url=c.url,
                source_id=c.source_id,
                score=c.score,
                rank=c.rank,
                why_picked=c.why_picked
            )
            for c in chunks
        ]
        
        context = None
        if request.format_for_llm:
            context = format_context_for_llm(chunks)
        
        return RetrieveResponse(
            chunks=chunk_responses,
            context=context,
            debug=DebugResponse(
                timings=debug.timings,
                counts=debug.counts,
                params=debug.params,
                notes=debug.notes
            )
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/index/rebuild")
async def rebuild_index():
    """Rebuild BM25 index from Qdrant"""
    retriever = get_retriever()
    retriever._ensure_stores()
    
    payloads = retriever._qdrant.get_all_payloads()
    retriever._bm25.build_from_payloads(payloads)
    
    return {
        "status": "ok",
        "indexed": len(payloads)
    }


# Run with: uvicorn rag_retrieval.api:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
