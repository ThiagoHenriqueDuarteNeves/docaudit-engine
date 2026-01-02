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
try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma  # fallback
try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    from langchain_community.embeddings import HuggingFaceEmbeddings  # fallback


class DocumentManager:
    def __init__(
        self,
        docs_dir: str = "docs",
        persist_dir: str = "db",
        embedding_device: str = "cuda",
        max_file_size_mb: int = 50,
        max_total_files: int = 100
    ):
        self.docs_dir = Path(docs_dir)
        self.persist_dir = persist_dir
        self.embedding_device = embedding_device
        self.max_file_size_mb = max_file_size_mb
        self.max_total_files = max_total_files
        
        # Criar diretórios
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicializar embeddings
        import os
        # Tentar usar cache local primeiro, mas permitir download se necessário
        offline_mode = os.getenv('TRANSFORMERS_OFFLINE', '0') == '1'
        
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': embedding_device, 'local_files_only': offline_mode},
            encode_kwargs={"normalize_embeddings": True}
        )
        
        # Text splitter otimizado para documentos técnicos
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200,
            chunk_overlap=250,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Vector store (será carregado quando necessário)
        self._vector_db = None

    def _persist_if_supported(self):
        """Chama persist() se o backend suportar; caso contrário, ignora."""
        try:
            persist = getattr(self.vector_db, "persist", None)
            if callable(persist):
                persist()
        except Exception as e:
            # Apenas loga; alguns backends persistem automaticamente
            print(f"⚠️ Persist não suportado: {e}")
    
    @property
    def vector_db(self):
        """Lazy loading do vector database"""
        if self._vector_db is None:
            # Garantir diretório de persistência
            persist_path = Path(self.persist_dir)
            persist_path.mkdir(parents=True, exist_ok=True)
            # Inicializar/abrir coleção com tratamento de erro
            try:
                self._vector_db = Chroma(
                    persist_directory=str(persist_path),
                    embedding_function=self.embeddings
                )
            except Exception as e:
                # Log mais amigável e fallback para None
                print(f"⚠️ Erro ao inicializar Vector DB (Chroma): {e}")
                print("   Será desativado acesso semântico a documentos até correção.")
                self._vector_db = None
        return self._vector_db
    
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
    
    def get_indexed_hashes(self) -> set:
        """Retorna set de hashes já indexados no ChromaDB"""
        try:
            # ChromaDB armazena metadados com os documentos
            collection = self.vector_db._collection
            all_docs = collection.get()
            
            hashes = set()
            if all_docs and 'metadatas' in all_docs:
                for metadata in all_docs['metadatas']:
                    if metadata and 'file_hash' in metadata:
                        hashes.add(metadata['file_hash'])
            
            return hashes
        except Exception as e:
            print(f"⚠️ Erro ao buscar hashes indexados: {e}")
            return set()
    
    def _prune_orphaned_documents(self, current_files: List[Path]) -> int:
        """Remove do vector DB documentos que não existem mais no disco"""
        try:
            # Acesso direto à collection do Chroma
            if not self.vector_db:
                return 0
                
            print("🧹 Verificando documentos órfãos...")
            collection = self.vector_db._collection
            
            # Pegar todos metadados
            data = collection.get(include=['metadatas'])
            
            if not data['ids']:
                return 0
                
            ids_to_delete = []
            
            # Criar conjunto de nomes de arquivos existentes
            existing_filenames = {f.name for f in current_files}
            
            for i, meta in enumerate(data['metadatas']):
                if not meta:
                    continue
                
                # Priorizar metadado 'filename' que nós adicionamos na indexação
                filename = meta.get('filename')
                if not filename:
                    # Fallback para 'source' (padrão LangChain)
                    source = meta.get('source')
                    if source:
                        filename = Path(source).name
                
                # Se identificamos um arquivo de origem e ele não está na lista atual
                if filename and filename not in existing_filenames:
                    ids_to_delete.append(data['ids'][i])
                
            if ids_to_delete:
                print(f"⚠️ Removendo {len(ids_to_delete)} chunks órfãos do ChromaDB...")
                collection.delete(ids=ids_to_delete)
                print("✅ Limpeza concluída.")
                return len(ids_to_delete)
            
            return 0
            
        except Exception as e:
            print(f"❌ Erro ao limpar órfãos: {e}")
            return 0

    def scan_and_index(
        self,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> Dict:
        """
        Escaneia pasta docs/ e indexa novos PDFs
        
        Args:
            progress_callback: função(mensagem, progresso_0_a_1)
        
        Returns:
            Dict com estatísticas: {indexed, skipped, errors, total_chunks}
        """
        # Garantir diretório de documentos
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        
        # Coletar todos os arquivos suportados
        all_files = []
        for pattern in ["*.pdf", "*.txt", "*.md"]:
            all_files.extend(list(self.docs_dir.glob(pattern)))
            
        # Limpar documentos órfãos (que foram deletados do disco)
        self._prune_orphaned_documents(all_files)
        
        if not all_files:
            return {
                'indexed': 0,
                'skipped': 0,
                'errors': 0,
                'total_chunks': 0,
                'message': 'Nenhum documento encontrado na pasta docs/'
            }
        
        indexed_hashes = self.get_indexed_hashes()
        
        stats = {
            'indexed': 0,
            'skipped': 0,
            'errors': 0,
            'total_chunks': 0,
            'error_messages': []
        }
        
        total_files = len(all_files)
        
        for idx, file_path in enumerate(all_files):
            try:
                if progress_callback:
                    progress_callback(
                        f"Processando {file_path.name}...",
                        idx / total_files
                    )
                
                # Calcular hash
                file_hash = self.calculate_file_hash(file_path)
                
                # Verificar se já está indexado
                if file_hash in indexed_hashes:
                    stats['skipped'] += 1
                    continue
                
                # Escolher loader baseado na extensão
                file_ext = file_path.suffix.lower()
                if file_ext == '.pdf':
                    loader = PyPDFLoader(str(file_path))
                    documents = loader.load()
                elif file_ext in ['.txt', '.md']:
                    # Tentar múltiplos encodings para arquivos de texto
                    documents = None
                    for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                        try:
                            loader = TextLoader(str(file_path), encoding=encoding)
                            documents = loader.load()
                            print(f"   ✅ {file_path.name} carregado com encoding: {encoding}")
                            break
                        except Exception as e:
                            continue
                    
                    if documents is None:
                        err_msg = f"{file_path.name}: Não foi possível detectar encoding correto"
                        print(f"❌ {err_msg}")
                        stats['errors'] += 1
                        stats['error_messages'].append(err_msg)
                        continue
                else:
                    print(f"⚠️ Formato não suportado: {file_path.name}")
                    stats['errors'] += 1
                    continue
                
                if not documents:
                    print(f"⚠️ {file_path.name} não contém texto extraível")
                    stats['errors'] += 1
                    continue
                
                # Adicionar hash aos metadados
                for doc in documents:
                    doc.metadata['file_hash'] = file_hash
                    doc.metadata['filename'] = file_path.name
                    doc.metadata['indexed_at'] = datetime.now().isoformat()
                
                # Dividir em chunks
                chunks = self.text_splitter.split_documents(documents)
                # Filtrar chunks vazios
                chunks = [c for c in chunks if getattr(c, "page_content", "").strip()]
                if not chunks:
                    # Tentar OCR apenas para PDFs
                    if file_ext == '.pdf':
                        if progress_callback:
                            progress_callback(f"Aplicando OCR em {file_path.name}...", idx / total_files)
                        ocr_docs = self._perform_ocr(file_path)
                        if not ocr_docs:
                            err_msg = f"{file_path.name} não possui texto extraível (0 chunks)."
                            print(f"⚠️ {err_msg}")
                            stats['errors'] += 1
                            stats['error_messages'].append(err_msg)
                            continue
                        # Dividir OCR em chunks
                        chunks = self.text_splitter.split_documents(ocr_docs)
                        chunks = [c for c in chunks if getattr(c, "page_content", "").strip()]
                    
                    if not chunks:
                        err_msg = f"{file_path.name} não possui texto extraível."
                        print(f"⚠️ {err_msg}")
                        stats['errors'] += 1
                        stats['error_messages'].append(err_msg)
                        continue
                
                # Adicionar ao vector store
                # Adicionar ao vector store em lotes (batching) para evitar limites do ChromaDB
                # Limite padrão do SQLite é variável, 5461 foi o erro relatado. Usaremos 2000 para segurança.
                BATCH_SIZE = 2000
                total_chunks = len(chunks)
                
                for i in range(0, total_chunks, BATCH_SIZE):
                    batch = chunks[i:i + BATCH_SIZE]
                    self.vector_db.add_documents(batch)
                    print(f"   📥 Indexando lote {i//BATCH_SIZE + 1} de {(total_chunks-1)//BATCH_SIZE + 1} ({len(batch)} chunks)...")

                    # ---------------------------------------------------------
                    # DUAL WRITE: Sincronizar com Qdrant (para Hybrid Retrieval)
                    # ---------------------------------------------------------
                    if os.getenv("QDRANT_URL"):
                        try:
                            # Lazy import para evitar erros se pacote faltando
                            from rag_retrieval.rag_retrieval.qdrant_store import QdrantStore
                            
                            # Singleton do QdrantStore no DocumentManager
                            if not hasattr(self, '_qdrant_sync'):
                                print("   🔄 [SYNC] Inicializando conexão com Qdrant...")
                                self._qdrant_sync = QdrantStore()
                            
                            # Converter docs para formato de chunks do Qdrant
                            q_chunks = []
                            for q_idx, doc in enumerate(batch):
                                # Gerar ID determinístico
                                combined_id = f"{doc.metadata.get('filename')}_{i+q_idx}"
                                chunk_hash = abs(hash(combined_id)) % (10 ** 18)
                                
                                q_chunks.append({
                                    "id": chunk_hash,
                                    "text": doc.page_content,
                                    "doc_id": doc.metadata.get('filename'),   # ID principal
                                    "source": doc.metadata.get('filename'),   # Fallback/Compatibilidade
                                    "source_id": doc.metadata.get('filename'),# Fallback
                                    "chunk_id": i + q_idx,
                                    "title": doc.metadata.get('filename'),
                                    "created_at": datetime.now().isoformat(),
                                    "metadata": doc.metadata
                                })
                            
                            # Enviar para Qdrant
                            self._qdrant_sync.upsert_chunks(q_chunks)
                            print(f"   ✅ [SYNC] {len(q_chunks)} chunks enviados para Qdrant")
                            
                        except Exception as e:
                            print(f"   ⚠️ [SYNC] Erro ao sincronizar com Qdrant: {e}")
                    # ---------------------------------------------------------

                print(f"✅ Arquivo indexado com sucesso!")
                
                # DEBUG: Log de indexação
                print(f"✅ Arquivo indexado: {file_path.name} ({len(chunks)} chunks)")
                
                stats['indexed'] += 1
                stats['total_chunks'] += len(chunks)
                
                print(f"✅ Indexado: {file_path.name} ({len(chunks)} chunks)")
                
            except Exception as e:
                err_msg = f"Erro ao processar {file_path.name}: {e}"
                print(f"❌ {err_msg}")
                stats['errors'] += 1
                stats['error_messages'].append(err_msg)
        
        if progress_callback:
            progress_callback("Indexação concluída!", 1.0)
        
        # Persistir mudanças (se suportado)
        self._persist_if_supported()
        
        if stats['errors']:
            last_err = stats['error_messages'][-1] if stats['error_messages'] else "Erro desconhecido"
            stats['message'] = (
                f"Indexados: {stats['indexed']}, Ignorados: {stats['skipped']}, Erros: {stats['errors']}\n"
                f"Último erro: {last_err}"
            )
        else:
            stats['message'] = f"Indexados: {stats['indexed']}, Ignorados: {stats['skipped']}, Erros: {stats['errors']}"
        return stats

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
        Remove um PDF e seus chunks do vector store
        
        Args:
            filename: nome do arquivo
        
        Returns:
            (sucesso, mensagem)
        """
        file_path = self.docs_dir / filename
        
        if not file_path.exists():
            return False, f"Arquivo {filename} não encontrado"
        
        try:
            # Calcular hash para remoção
            file_hash = self.calculate_file_hash(file_path)

            # Remover chunks via filtro (mais robusto)
            try:
                # Chroma community API aceita where na coleção
                collection = self.vector_db._collection
                collection.delete(where={"file_hash": file_hash})
            except Exception:
                # Fallback: buscar ids manualmente
                collection = self.vector_db._collection
                all_docs = collection.get()
                ids_to_delete = []
                if all_docs and 'metadatas' in all_docs:
                    for idx, metadata in enumerate(all_docs['metadatas']):
                        if metadata and metadata.get('file_hash') == file_hash:
                            ids_to_delete.append(all_docs['ids'][idx])
                if ids_to_delete:
                    collection.delete(ids=ids_to_delete)
            # Persistir remoções (se suportado)
            self._persist_if_supported()

            # Remover arquivo físico
            file_path.unlink()

            return True, f"✅ {filename} removido"

        except Exception as e:
            return False, f"❌ Erro ao deletar {filename}: {e}"
    
    def get_retriever(self, k: int = 4):
        """Retorna retriever configurado"""
        return self.vector_db.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k}
        )

    def search_documents(self, query: str, k: int = 8) -> List[Dict]:
        """Busca semântica nos documentos e retorna snippets estruturados"""
        try:
            results = self.vector_db.similarity_search_with_score(query, k=k)
            snippets: List[Dict] = []
            for doc, score in results:
                meta = doc.metadata or {}
                snippets.append({
                    "text": doc.page_content,
                    "source": meta.get("filename", "desconhecido"),
                    "score": float(score)
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
