"""
Type definitions for RAG Retrieval Pipeline
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SearchHit:
    """Result from a single retrieval method (dense or sparse)"""
    id: str | int
    doc_id: str
    chunk_id: int
    text: str
    score: float
    source: str  # "dense" | "sparse" | "fused" | "reranked"
    payload: dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash((self.doc_id, self.chunk_id))
    
    def __eq__(self, other):
        if not isinstance(other, SearchHit):
            return False
        return self.doc_id == other.doc_id and self.chunk_id == other.chunk_id


@dataclass
class ContextChunk:
    """Final chunk selected for LLM context"""
    doc_id: str
    chunk_id: int
    text: str
    title: Optional[str]
    url: Optional[str]
    source_id: str
    score: float
    rank: int
    why_picked: str  # 1-line explanation
    
    def to_context_string(self, max_chars: int = 1600) -> str:
        """Format chunk for LLM context"""
        header = f"[{self.rank}] {self.title or self.source_id}"
        if self.url:
            header += f" ({self.url})"
        text = self.text[:max_chars] if len(self.text) > max_chars else self.text
        return f"{header}\n{text}"


@dataclass
class DebugInfo:
    """Observability data for retrieval pipeline"""
    # Timings in milliseconds
    timings: dict[str, float] = field(default_factory=lambda: {
        "embed_ms": 0.0,
        "dense_ms": 0.0,
        "sparse_ms": 0.0,
        "fuse_ms": 0.0,
        "rerank_ms": 0.0,
        "total_ms": 0.0,
    })
    
    # Counts at each stage
    counts: dict[str, int] = field(default_factory=lambda: {
        "dense_n": 0,
        "sparse_n": 0,
        "fused_n": 0,
        "reranked_n": 0,
        "final_n": 0,
    })
    
    # Parameters used
    params: dict[str, Any] = field(default_factory=dict)
    
    # Notes/warnings
    notes: list[str] = field(default_factory=list)
    
    def add_note(self, note: str):
        self.notes.append(note)
    
    def to_dict(self) -> dict:
        return {
            "timings": self.timings,
            "counts": self.counts,
            "params": self.params,
            "notes": self.notes,
        }


@dataclass
class RetrievalFilters:
    """Filters for retrieval queries"""
    tenant_id: Optional[str] = None
    tags: Optional[list[str]] = None
    source_id: Optional[str] = None
    doc_id: Optional[str] = None
    date_from: Optional[str] = None  # ISO format
    date_to: Optional[str] = None    # ISO format
    
    def to_dict(self) -> dict:
        result = {}
        if self.tenant_id:
            result["tenant_id"] = self.tenant_id
        if self.tags:
            result["tags"] = self.tags
        if self.source_id:
            result["source_id"] = self.source_id
        if self.doc_id:
            result["doc_id"] = self.doc_id
        if self.date_from:
            result["date_from"] = self.date_from
        if self.date_to:
            result["date_to"] = self.date_to
        return result
    
    def is_empty(self) -> bool:
        return not any([
            self.tenant_id, self.tags, self.source_id, 
            self.doc_id, self.date_from, self.date_to
        ])
