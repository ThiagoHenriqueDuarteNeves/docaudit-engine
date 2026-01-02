"""
Configuration for RAG Retrieval Pipeline
Loads from environment variables with sensible defaults
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configuration loaded from environment variables"""
    
    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    collection_name: str = "rag_chunks"
    
    # Embedding Model (Bi-Encoder) - Multilingual for better PT-BR
    embed_model: str = "intfloat/multilingual-e5-base"
    embed_dim: int = 768
    
    # CrossEncoder for Reranking
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    # BM25 Index persistence
    index_path: Path = Path("./bm25_index")
    
    # Retrieval defaults
    default_dense_k: int = 60
    default_sparse_k: int = 60
    default_fused_k: int = 80
    default_rerank_k: int = 12
    default_rrf_k: int = 60
    
    # Diversity
    max_chunks_per_doc: int = 3
    min_docs_in_result: int = 3
    
    # Limits
    max_chars_per_chunk: int = 1600
    max_iterations: int = 2
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Convenience accessors
def get_qdrant_url() -> str:
    return get_settings().qdrant_url

def get_qdrant_api_key() -> str | None:
    return get_settings().qdrant_api_key

def get_collection_name() -> str:
    return get_settings().collection_name

def get_embed_model() -> str:
    return get_settings().embed_model

def get_cross_encoder_model() -> str:
    return get_settings().cross_encoder_model

def get_index_path() -> Path:
    path = get_settings().index_path
    path.mkdir(parents=True, exist_ok=True)
    return path
