"""
Document Manager - Gerenciamento inteligente de PDFs
Indexação com detecção de duplicatas via MD5
"""
import hashlib
from pathlib import Path
from typing import List, Dict, Callable, Optional
import os
from datetime import datetime
import sys

# Fix for rag_retrieval import (module not installed as package)
sys.path.append(str(Path(__file__).parent / "rag_retrieval"))


from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
# Qdrant Import
from rag_retrieval.qdrant_store import QdrantStore
from qdrant_client.models import Filter, FieldCondition, MatchValue


class DocumentManager:
    def __init__(
        self,
        docs_dir: str = "docs",
        embedding_device: str = "cuda",
        max_file_size_mb: int = 50,
        max_total_files: int = 100
    ):
        self.docs_dir = Path(docs_dir)
        # self.persist_dir = persist_dir # Deprecated
        self.embedding_device = embedding_device
        self.max_file_size_mb = max_file_size_mb
        self.max_total_files = max_total_files
        
        # Criar diretórios
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        
        # Text splitter otimizado para documentos técnicos
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200,
            chunk_overlap=250,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Vector store (Qdrant)
        self._vector_db = None

    @property
    def vector_db(self) -> QdrantStore:
        """Lazy loading do QdrantStore"""
        if self._vector_db is None:
            try:
                # Usa variáveis de ambiente para config (definidas no run_backend_debug.bat)
                # COLLECTION_NAME=default, etc.
                self._vector_db = QdrantStore(collection_name="default")
                print("✅ QdrantStore inicializado (Collection: default)")
            except Exception as e:
                print(f"⚠️ Erro ao inicializar Qdrant: {e}")
                self._vector_db = None
        return self._vector_db

    def is_document_indexed(self, file_hash: str) -> bool:
        """Verifica se um arquivo com este hash já existe no Qdrant"""
        try:
            if not self.vector_db:
                return False
            
            # Busca por filtro exato no metadado file_hash
            # IMPORTANTE: QdrantStore não expõe busca de count por filtro fácil sem scroll
            # Vamos usar o client direto para count
            
            client = self.vector_db.client
            collection = self.vector_db.collection_name
            
            # Filtro: metadata.file_hash == file_hash
            # Como salvamos metadata dentro do payload como dicionário "metadata", 
            # a chave no Qdrant é "metadata.file_hash" ou "extra.file_hash" dependendo de como upsert_chunks salva
            # Olhando upsert_chunks: salva "metadata": doc.metadata
            # Então a chave é "metadata.file_hash"
            
            count_result = client.count(
                collection_name=collection,
                count_filter=Filter(
                    must=[
                        FieldCondition(
                            key="metadata.file_hash",
                            match=MatchValue(value=file_hash)
                        )
                    ]
                )
            )
            return count_result.count > 0
            
        except Exception as e:
            # print(f"⚠️ Erro ao verificar existência: {e}")
            return False
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """Calcula MD5 hash de um arquivo"""
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    
    def get_file_metadata(self, file_path: Path) -> Dict:
        """Extrai metadados de um arquivo PDF"""
        stats = file_path.stat()
        return {
            'filename': file_path.name,
            'size_bytes': stats.st_size,
            'size_mb': round(stats.st_size / (1024 * 1024), 2),
            'modified': datetime.fromtimestamp(stats.st_mtime).isoformat(),
            'hash': self.calculate_file_hash(file_path)
        }
    
    def list_documents(self) -> List[Dict]:
        """Lista todos os documentos suportados na pasta docs/"""
        # Suportar múltiplos formatos
        all_files = []
        for pattern in ["*.pdf", "*.txt", "*.md"]:
            all_files.extend(list(self.docs_dir.glob(pattern)))
        
        documents = []
        for file_path in all_files:
            try:
                metadata = self.get_file_metadata(file_path)
                documents.append(metadata)
            except Exception as e:
                print(f"⚠️ Erro ao ler {file_path.name}: {e}")
        
        return sorted(documents, key=lambda x: x['modified'], reverse=True)
    
    def validate_file(self, file_path: Path) -> tuple[bool, str]:
        """
        Valida se arquivo pode ser adicionado
        
        Returns:
            (is_valid, message)
        """
        # Verificar formato suportado
        allowed_extensions = ['.pdf', '.txt', '.md']
        if file_path.suffix.lower() not in allowed_extensions:
            return False, f"Apenas arquivos {', '.join(allowed_extensions)} são permitidos"
        
        # Verificar tamanho
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > self.max_file_size_mb:
            return False, f"Arquivo muito grande ({size_mb:.1f}MB). Máximo: {self.max_file_size_mb}MB"
        
        # Verificar limite total (contar todos os formatos)
        current_files = 0
        for pattern in ["*.pdf", "*.txt", "*.md"]:
            current_files += len(list(self.docs_dir.glob(pattern)))
        if current_files >= self.max_total_files:
            return False, f"Limite de {self.max_total_files} arquivos atingido"
        
        return True, "OK"
    
    def scan_and_index(
        self,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> Dict:
        """
        Escaneia pasta docs/ e indexa novos PDFs no Qdrant
        """
        # Garantir diretório de documentos
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.vector_db # Trigger init
        
        # Coletar todos os arquivos suportados
        all_files = []
        for pattern in ["*.pdf", "*.txt", "*.md"]:
            all_files.extend(list(self.docs_dir.glob(pattern)))
            
        # Limpeza de órfãos ignorada nesta versão por performance
        # self._prune_orphaned_documents(all_files)
        
        if not all_files:
            return {
                'indexed': 0, 'skipped': 0, 'errors': 0, 'total_chunks': 0,
                'message': 'Nenhum documento encontrado na pasta docs/'
            }
        
        stats = {
            'indexed': 0, 'skipped': 0, 'errors': 0, 'total_chunks': 0,
            'error_messages': []
        }
        
        total_files = len(all_files)
        
        for idx, file_path in enumerate(all_files):
            try:
                if progress_callback:
                    progress_callback(f"Processando {file_path.name}...", idx / total_files)
                
                # Calcular hash
                file_hash = self.calculate_file_hash(file_path)
                
                # Verificar se já está indexado no Qdrant
                if self.is_document_indexed(file_hash):
                    stats['skipped'] += 1
                    continue
                
                # Carregar Documento
                documents = self._load_file(file_path)
                if not documents:
                    # OCR fallback logic can be here or inside _load_file
                    if file_path.suffix.lower() == '.pdf':
                         if progress_callback: progress_callback(f"Tentando OCR em {file_path.name}...", idx / total_files)
                         documents = self._perform_ocr(file_path)

                if not documents:
                    err_msg = f"{file_path.name} não contém texto extraível"
                    print(f"⚠️ {err_msg}")
                    stats['errors'] += 1
                    stats['error_messages'].append(err_msg)
                    continue
                
                # Adicionar metadados bases
                for doc in documents:
                    doc.metadata['file_hash'] = file_hash
                    doc.metadata['filename'] = file_path.name
                    doc.metadata['indexed_at'] = datetime.now().isoformat()
                    # Ensure 'source' is set for compatibility
                    if 'source' not in doc.metadata:
                        doc.metadata['source'] = file_path.name
                
                # Split
                chunks = self.text_splitter.split_documents(documents)
                chunks = [c for c in chunks if getattr(c, "page_content", "").strip()]
                
                if not chunks:
                    stats['errors'] += 1
                    continue

                # Preparar para Qdrant (Upsert)
                q_chunks = []
                for i, doc in enumerate(chunks):
                    # ID Determinístico
                    combined_id = f"{doc.metadata.get('filename')}_{i}"
                    chunk_hash = abs(hash(combined_id)) % (10 ** 18)
                    
                    q_chunks.append({
                        "id": chunk_hash,
                        "text": doc.page_content,
                        "doc_id": doc.metadata.get('filename'),
                        "source": doc.metadata.get('filename'), # Para filtros
                        "source_id": doc.metadata.get('filename'),
                        "chunk_id": i,
                        "title": doc.metadata.get('filename'),
                        "created_at": datetime.now().isoformat(),
                        "metadata": doc.metadata # Importante salvar metadata completo
                    })

                # Enviar batch único por arquivo
                print(f"   📥 Enviando {len(q_chunks)} chunks para Qdrant...")
                self.vector_db.upsert_chunks(q_chunks)
                
                print(f"✅ Arquivo indexado: {file_path.name} ({len(chunks)} chunks)")
                stats['indexed'] += 1
                stats['total_chunks'] += len(chunks)
                
            except Exception as e:
                err_msg = f"Erro ao processar {file_path.name}: {e}"
                print(f"❌ {err_msg}")
                stats['errors'] += 1
                stats['error_messages'].append(err_msg)
        
        if progress_callback:
            progress_callback("Indexação concluída!", 1.0)
        
        stats['message'] = f"Indexados: {stats['indexed']}, Ignorados: {stats['skipped']}, Erros: {stats['errors']}"
        return stats

    def _load_file(self, file_path: Path) -> List:
        """Helper para carregar arquivo com retry de encoding"""
        file_ext = file_path.suffix.lower()
        if file_ext == '.pdf':
            return PyPDFLoader(str(file_path)).load()
        elif file_ext in ['.txt', '.md']:
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    return TextLoader(str(file_path), encoding=encoding).load()
                except: continue
        return []

    def _perform_ocr(self, pdf_path: Path) -> List:
        """Executa OCR em um PDF escaneado e retorna uma lista de Documents.
        Requer pacotes: pdf2image, pillow, pytesseract. Se não disponíveis, retorna []."""
        try:
            try:
                from pdf2image import convert_from_path
                import pytesseract
                from PIL import Image
            except Exception as e:
                print(f"⚠️ OCR indisponível (instale: pdf2image pillow pytesseract): {e}")
                return []
            # Converter páginas em imagens
            images = convert_from_path(str(pdf_path))
            full_text = ""
            # Usar idioma português quando disponível; sem limites de páginas
            for i, img in enumerate(images):
                try:
                    try:
                        text = pytesseract.image_to_string(img, lang="por")
                    except Exception:
                        # Fallback sem especificar idioma
                        text = pytesseract.image_to_string(img)
                    if text:
                        full_text += f"\n\n[Página {i+1}]\n" + text
                except Exception as e:
                    print(f"⚠️ OCR falhou na página {i+1}: {e}")
                    continue
            if not full_text.strip():
                return []
            # Montar Document único com metadados
            from langchain_core.documents import Document
            file_hash = self.calculate_file_hash(pdf_path)
            doc = Document(
                page_content=full_text,
                metadata={
                    'file_hash': file_hash,
                    'filename': pdf_path.name,
                    'indexed_at': datetime.now().isoformat(),
                    'source': 'ocr'
                }
            )
            return [doc]
        except Exception as e:
            print(f"❌ Erro no OCR de {pdf_path.name}: {e}")
            return []
    
    def delete_document(self, filename: str) -> tuple[bool, str]:
        """
        Remove um PDF e seus chunks do Qdrant
        """
        file_path = self.docs_dir / filename
        
        if not file_path.exists():
            return False, f"Arquivo {filename} não encontrado"
        
        try:
            # Remover do Qdrant por filtro (source = filename)
            if self.vector_db:
                client = self.vector_db.client
                collection = self.vector_db.collection_name
                
                # Apagar pontos onde doc_id == filename OU source == filename
                # Qdrant delete operation
                client.delete(
                    collection_name=collection,
                    points_selector=Filter(
                        should=[
                            FieldCondition(key="doc_id", match=MatchValue(value=filename)),
                            FieldCondition(key="source", match=MatchValue(value=filename))
                        ]
                    )
                )
            
            # Remover arquivo físico
            file_path.unlink()
            return True, f"✅ {filename} removido"

        except Exception as e:
            return False, f"❌ Erro ao deletar {filename}: {e}"
    
    def search_documents(self, query: str, k: int = 8) -> List[Dict]:
        """Busca semântica no Qdrant"""
        try:
            if not self.vector_db:
                return []
                
            results = self.vector_db.search_dense(query, top_k=k)
            snippets: List[Dict] = []
            
            for hit in results:
                snippets.append({
                    "text": hit.text,
                    "source": hit.payload.get("source") or hit.doc_id, # Fallback
                    "score": float(hit.score),
                    "page": hit.payload.get("metadata", {}).get("page", 0)
                })
            return snippets
        except Exception as e:
            print(f"❌ Erro em search_documents: {e}")
            return []


# Teste
if __name__ == "__main__":
    import torch
    
    # Verificar GPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🔧 Usando device: {device}")
    
    manager = DocumentManager(embedding_device=device)
    
    print(f"\n📁 Documentos em {manager.docs_dir}:")
    docs = manager.list_documents()
    
    if docs:
        for doc in docs:
            print(f"  - {doc['filename']} ({doc['size_mb']}MB)")
    else:
        print("  (vazio)")
    
    print("\n🔄 Iniciando indexação...")
    
    def progress(msg, pct):
        print(f"  [{pct*100:.0f}%] {msg}")
    
    stats = manager.scan_and_index(progress_callback=progress)
    print(f"\n✅ {stats['message']}")
    print(f"   Total de chunks: {stats['total_chunks']}")
