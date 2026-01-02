"""
VectorStore Abstraction Layer
Supports ChromaDB and Qdrant backends with unified interface
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from pathlib import Path
from dataclasses import dataclass
import os


@dataclass
class SearchResult:
    """Resultado de busca vetorial"""
    text: str
    score: float
    metadata: Dict[str, Any]


class VectorStoreBackend(ABC):
    """Interface abstrata para backends de vectorstore"""
    
    @abstractmethod
    def add_documents(self, texts: List[str], metadatas: List[Dict], ids: List[str]) -> None:
        """Adiciona documentos ao índice"""
        pass
    
    @abstractmethod
    def search(self, query: str, k: int = 5, filters: Optional[Dict] = None) -> List[SearchResult]:
        """Busca semântica com filtros opcionais"""
        pass
    
    @abstractmethod
    def delete(self, ids: List[str]) -> None:
        """Remove documentos por ID"""
        pass
    
    @abstractmethod
    def count(self) -> int:
        """Retorna número de documentos"""
        pass


class ChromaBackend(VectorStoreBackend):
    """Backend ChromaDB (atual)"""
    
    def __init__(self, persist_directory: str, collection_name: str = "default"):
        try:
            from langchain_chroma import Chroma
        except ImportError:
            from langchain_community.vectorstores import Chroma
        
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings
        
        self.persist_dir = Path(persist_directory)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        offline_mode = os.getenv('TRANSFORMERS_OFFLINE', '0') == '1'
        self._embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu", "local_files_only": offline_mode},
            encode_kwargs={"normalize_embeddings": True}
        )
        
        self._vs = Chroma(
            persist_directory=str(self.persist_dir),
            embedding_function=self._embeddings,
            collection_name=collection_name
        )
        
        print(f"✅ [ChromaBackend] Inicializado: {persist_directory}")
    
    def add_documents(self, texts: List[str], metadatas: List[Dict], ids: List[str]) -> None:
        from langchain_core.documents import Document
        docs = [Document(page_content=t, metadata=m) for t, m in zip(texts, metadatas)]
        self._vs.add_documents(docs, ids=ids)
    
    def search(self, query: str, k: int = 5, filters: Optional[Dict] = None) -> List[SearchResult]:
        where = filters if filters else None
        results = self._vs.similarity_search_with_score(query, k=k, filter=where)
        
        return [
            SearchResult(
                text=doc.page_content,
                score=float(score),
                metadata=doc.metadata or {}
            )
            for doc, score in results
        ]
    
    def delete(self, ids: List[str]) -> None:
        try:
            self._vs.delete(ids=ids)
        except Exception as e:
            print(f"⚠️ [ChromaBackend] Erro ao deletar: {e}")
    
    def count(self) -> int:
        try:
            collection = self._vs._collection
            return collection.count() if collection else 0
        except:
            return 0


class QdrantBackend(VectorStoreBackend):
    """Backend Qdrant (suporta modo local e servidor Docker)"""
    
    def __init__(self, persist_directory: str, collection_name: str = "default"):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
        
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings
        
        self.persist_dir = Path(persist_directory)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        
        # Embeddings (mesmo modelo do Chroma para comparação justa)
        offline_mode = os.getenv('TRANSFORMERS_OFFLINE', '0') == '1'
        self._embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu", "local_files_only": offline_mode},
            encode_kwargs={"normalize_embeddings": True}
        )
        
        # Verificar se deve usar servidor (Docker) ou modo local
        qdrant_url = os.getenv("QDRANT_URL", "")
        
        if qdrant_url:
            # Modo servidor (Docker)
            self._client = QdrantClient(url=qdrant_url)
            print(f"✅ [QdrantBackend] Conectado ao servidor: {qdrant_url}")
        else:
            # Modo local (fallback - pode ter problemas no Windows)
            self._client = QdrantClient(path=str(self.persist_dir))
            print(f"✅ [QdrantBackend] Modo local: {persist_directory}")
        
        # Criar coleção se não existir
        self._ensure_collection()
        
        print(f"📦 [QdrantBackend] Coleção: {collection_name}")
    
    def _ensure_collection(self):
        from qdrant_client.models import Distance, VectorParams
        
        collections = self._client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            # all-MiniLM-L6-v2 produz vetores de 384 dimensões
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            print(f"📦 [QdrantBackend] Coleção '{self.collection_name}' criada")
    
    def add_documents(self, texts: List[str], metadatas: List[Dict], ids: List[str]) -> None:
        from qdrant_client.models import PointStruct
        
        # Gerar embeddings
        embeddings = self._embeddings.embed_documents(texts)
        
        # Converter IDs para inteiros (Qdrant prefere int)
        points = []
        for i, (text, emb, meta, doc_id) in enumerate(zip(texts, embeddings, metadatas, ids)):
            # Usar hash do ID como int
            point_id = abs(hash(doc_id)) % (10 ** 18)
            payload = {**meta, "text": text, "original_id": doc_id}
            points.append(PointStruct(id=point_id, vector=emb, payload=payload))
        
        self._client.upsert(collection_name=self.collection_name, points=points)
    
    def search(self, query: str, k: int = 5, filters: Optional[Dict] = None) -> List[SearchResult]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        # Gerar embedding da query
        query_embedding = self._embeddings.embed_query(query)
        
        # Construir filtro Qdrant
        qdrant_filter = None
        if filters:
            conditions = [
                FieldCondition(key=key, match=MatchValue(value=value))
                for key, value in filters.items()
            ]
            qdrant_filter = Filter(must=conditions)
        
        # Busca usando query_points (nova API qdrant-client 1.12+)
        try:
            results = self._client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                query_filter=qdrant_filter,
                limit=k,
                with_payload=True
            ).points
        except AttributeError:
            # Fallback para API antiga
            results = self._client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=qdrant_filter,
                limit=k
            )
        
        return [
            SearchResult(
                text=hit.payload.get("text", ""),
                score=float(hit.score) if hit.score else 0.0,
                metadata={k: v for k, v in hit.payload.items() if k != "text"}
            )
            for hit in results
        ]
    
    def delete(self, ids: List[str]) -> None:
        from qdrant_client.models import Filter, FieldCondition, MatchAny
        
        # Deletar por original_id
        self._client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="original_id", match=MatchAny(any=ids))]
            )
        )
    
    def count(self) -> int:
        try:
            info = self._client.get_collection(self.collection_name)
            return info.points_count
        except:
            return 0


def get_vectorstore_backend(persist_directory: str, collection_name: str = "default") -> VectorStoreBackend:
    """
    Factory function para criar o backend configurado.
    Usa variável de ambiente VECTORSTORE_BACKEND (padrão: chroma)
    """
    backend_type = os.getenv("VECTORSTORE_BACKEND", "chroma").lower()
    
    if backend_type == "qdrant":
        return QdrantBackend(persist_directory, collection_name)
    else:
        return ChromaBackend(persist_directory, collection_name)
