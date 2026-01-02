"""
Memory Manager - Sistema de memória persistente com SQLite
Gerencia conversas ativas e arquivadas
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import json
from pathlib import Path


class ConversationMemory:
    # Mensagens muito curtas ou genéricas que não devem ser indexadas semanticamente
    # Isso evita poluir o vectorstore com "ruído" sem valor informativo
    IGNORED_MESSAGES = {
        "ok", "beleza", "valeu", "obrigado", "obrigada", 
        "sim", "não", "nao", "tchau", "oi", "olá", "ola",
        "entendo", "certo", "claro", "legal", "bacana"
    }
    
    # Tamanho mínimo para indexar mensagem (caracteres)
    MIN_INDEX_LENGTH = 20
    
    def __init__(self, user_id: str = "default"):
        self.user_id = self._sanitize_user_id(user_id)
        
        # Caminhos base
        self.base_dir = Path("memory")
        self.user_dir = self.base_dir / self.user_id
        self.db_path = self.user_dir / "conversations.db"
        
        # Criar diretório do usuário
        self.user_dir.mkdir(parents=True, exist_ok=True)
        
        # Tentar migrar dados legados (root -> user) se for o primeiro acesso
        self._migrate_legacy_data()
        
        self._init_database()
        # Vetorstore semântico (lazy)
        self._vs = None

    def _sanitize_user_id(self, user_id: str) -> str:
        """Sanitiza o ID do usuário para ser usado como nome de pasta seguro"""
        import re
        # Manter apenas letras, números, hífens e underscores
        safe_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(user_id)).lower()
        return safe_id if safe_id else "default"

    def _migrate_legacy_data(self):
        """
        Move dados legados (da raiz memory/conversations.db) para o diretório do usuário atual.
        Isso garante que o primeiro usuário a logar 'herda' o histórico antigo.
        """
        import shutil
        legacy_db = self.base_dir / "conversations.db"
        legacy_vs = self.base_dir / "vectorstore"
        
        # Apenas migrar se o diretório do usuário estiver 'vazio' (sem db) e legado existir
        if not self.db_path.exists() and legacy_db.exists():
            print(f"📦 Migrando dados legados para usuário '{self.user_id}'...")
            try:
                # Migrar SQLite
                shutil.move(str(legacy_db), str(self.db_path))
                print("   ✅ Banco de dados migrado.")
                
                # Migrar Vectorstore (se existir)
                user_vs_dir = self.user_dir / "vectorstore"
                if legacy_vs.exists() and not user_vs_dir.exists():
                    shutil.move(str(legacy_vs), str(user_vs_dir))
                    print("   ✅ Vectorstore migrado.")
                    
            except Exception as e:
                print(f"❌ Erro na migração de dados legados: {e}")
    
    def _init_database(self):
        """Inicializa tabelas do banco de dados"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabela de mensagens ativas (conversa atual)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabela de conversas arquivadas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS archived_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                archive_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                conversation_data TEXT NOT NULL,
                message_count INTEGER NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_message(self, role: str, content: str):
        """
        Salva uma mensagem na conversa ativa e indexa semanticamente se relevante.
        
        Filtros aplicados antes da indexação semântica:
        1. Remove mensagens muito curtas (< MIN_INDEX_LENGTH chars)
        2. Remove mensagens genéricas/irrelevantes (IGNORED_MESSAGES)
        3. Remove contadores de contexto [Contexto: ...]
        
        Args:
            role: 'user' ou 'assistant'
            content: conteúdo da mensagem
        """
        # SEMPRE salvar no SQLite (histórico completo)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO active_messages (role, content)
            VALUES (?, ?)
        """, (role, content))
        
        conn.commit()
        conn.close()
        
        # FILTRO: Decidir se deve indexar semanticamente
        # Remove contador de contexto que é adicionado no final da resposta
        import re
        cleaned = re.sub(r'\n\n\[Contexto: memória \d+, documentos \d+\]$', '', content)
        cleaned = cleaned.strip()
        
        # Verificar se mensagem é relevante para indexação
        should_index = (
            cleaned  # Não vazio
            and len(cleaned) >= self.MIN_INDEX_LENGTH  # Tamanho mínimo
            and cleaned.lower() not in self.IGNORED_MESSAGES  # Não é genérica
        )
        
        if should_index:
            self._index_message_semantic(role, cleaned)
            print(f"✅ Mensagem indexada semanticamente: {role} ({len(cleaned)} chars)")
        else:
            print(f"⏭️ Mensagem NÃO indexada (muito curta ou irrelevante): {role} ({len(cleaned)} chars)")
    
    def load_active_history(self, limit: int = 10) -> List[Dict[str, str]]:
        """
        Carrega últimas N mensagens da conversa ativa
        
        Args:
            limit: número máximo de mensagens a retornar
            
        Returns:
            Lista de dicts com keys: role, content, timestamp
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT role, content, timestamp
            FROM active_messages
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Retornar em ordem cronológica
        return list(reversed(messages))
    
    def get_full_active_history(self) -> List[Dict[str, str]]:
        """Retorna TODO o histórico ativo (sem limite)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT role, content, timestamp
            FROM active_messages
            ORDER BY id ASC
        """)
        
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return messages
    
    def archive_and_clear(self) -> int:
        """
        Arquiva a conversa atual e limpa active_messages
        
        Returns:
            ID do arquivo criado
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Buscar todas as mensagens ativas
        cursor.execute("SELECT role, content, timestamp FROM active_messages ORDER BY id ASC")
        messages = [dict(zip(['role', 'content', 'timestamp'], row)) for row in cursor.fetchall()]
        
        if not messages:
            conn.close()
            return -1  # Nada para arquivar
        
        # Salvar no arquivo
        conversation_json = json.dumps(messages, ensure_ascii=False, indent=2)
        cursor.execute("""
            INSERT INTO archived_conversations (conversation_data, message_count)
            VALUES (?, ?)
        """, (conversation_json, len(messages)))
        
        archive_id = cursor.lastrowid
        
        # Limpar mensagens ativas
        cursor.execute("DELETE FROM active_messages")
        
        conn.commit()
        conn.close()
        
        return archive_id
    
    def list_archives(self) -> List[Dict]:
        """
        Lista todas as conversas arquivadas
        
        Returns:
            Lista de dicts com id, data, número de mensagens
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, archive_date, message_count
            FROM archived_conversations
            ORDER BY archive_date DESC
        """)
        
        archives = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return archives
    
    def load_archive(self, archive_id: int) -> Optional[List[Dict[str, str]]]:
        """
        Carrega uma conversa arquivada específica
        
        Args:
            archive_id: ID do arquivo
            
        Returns:
            Lista de mensagens ou None se não encontrado
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT conversation_data
            FROM archived_conversations
            WHERE id = ?
        """, (archive_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return json.loads(result[0])
        return None
    
    def get_message_count(self) -> int:
        """Retorna número de mensagens na conversa ativa"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM active_messages")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def _ensure_vectorstore(self):
        """Inicializa o backend Qdrant unificado (via rag_retrieval)"""
        if self._vs is not None:
            return
        try:
            # Usar Qdrant centralizado do rag_retrieval
            from rag_retrieval.qdrant_store import QdrantStore
            self._vs = QdrantStore()
            print(f"✅ [MEMORY] Usando Qdrant unificado para usuário '{self.user_id}'")
        except ImportError:
            # Fallback para vectorstore local se rag_retrieval não disponível
            try:
                from core.vectorstore import get_vectorstore_backend
                mem_dir = self.user_dir / "vectorstore"
                mem_dir.mkdir(parents=True, exist_ok=True)
                self._vs = get_vectorstore_backend(
                    persist_directory=str(mem_dir),
                    collection_name=f"memory_{self.user_id}"
                )
                print(f"⚠️ [MEMORY] Fallback para vectorstore local: {mem_dir}")
            except Exception as e2:
                print(f"⚠️ Falha ao iniciar vectorstore de memória: {e2}")
                self._vs = None
        except Exception as e:
            print(f"⚠️ Falha ao conectar Qdrant unificado: {e}")
            import traceback
            traceback.print_exc()
            self._vs = None

    def _index_message_semantic(self, role: str, content: str):
        """Indexa mensagem no Qdrant unificado"""
        try:
            self._ensure_vectorstore()
            if self._vs is None:
                return
            
            # Adicionar metadados completos para busca híbrida
            timestamp = datetime.now().isoformat()
            doc_id = f"memory_{self.user_id}"
            chunk_id = hash(f"{timestamp}_{content}") % 10000000
            
            # Verificar se é QdrantStore ou backend antigo
            if hasattr(self._vs, 'upsert_chunks'):
                # Qdrant unificado - usar upsert_chunks
                chunk = {
                    "id": f"{doc_id}_{chunk_id}",
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "text": content,
                    "source_id": f"memory_{role}",  # memory_user ou memory_assistant
                    "title": f"Conversa {role}",
                    "tags": ["memory", role, self.user_id],
                    "tenant_id": self.user_id,
                    "created_at": timestamp,
                }
                self._vs.upsert_chunks([chunk])
                print(f"✅ Mensagem indexada semanticamente: {role} ({len(content)} chars)")
            else:
                # Backend antigo (ChromaDB) - compatibilidade
                self._vs.add_documents(
                    texts=[content],
                    metadatas=[{"role": role, "timestamp": timestamp}],
                    ids=[f"{role}_{timestamp}_{hash(content) % 10000}"]
                )
        except Exception as e:
            print(f"⚠️ Erro indexando memória semântica: {e}")
            import traceback
            traceback.print_exc()
    
    def search_in_memory(self, query: str, limit: int = 20) -> List[Dict[str, str]]:
        """
        Busca mensagens relevantes na memória (busca textual simples)
        
        Args:
            query: texto a buscar (vazio retorna todas)
            limit: número máximo de resultados
            
        Returns:
            Lista de mensagens que contém o termo buscado
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if query:
            # Busca case-insensitive
            cursor.execute("""
                SELECT role, content, timestamp
                FROM active_messages
                WHERE LOWER(content) LIKE LOWER(?)
                ORDER BY id DESC
                LIMIT ?
            """, (f'%{query}%', limit))
        else:
            # Retorna todas as mensagens recentes
            cursor.execute("""
                SELECT role, content, timestamp
                FROM active_messages
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
        
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return list(reversed(messages))

    def search_memory_semantic(self, query: str, k: int = 6) -> List[Dict[str, str]]:
        """
        Busca semântica na memória usando Qdrant unificado.
        
        Args:
            query: texto da busca
            k: número máximo de resultados a retornar
            
        Returns:
            Lista de snippets {text, source, score} ordenados por relevância
        """
        try:
            self._ensure_vectorstore()
            if self._vs is None:
                return []
            
            # Detectar tipo de backend e buscar
            if hasattr(self._vs, 'search_dense'):
                # QdrantStore (rag_retrieval) - usa search_dense
                from rag_retrieval.types import RetrievalFilters
                
                # Filtrar apenas memória deste usuário
                filters = RetrievalFilters(tenant_id=self.user_id)
                
                raw_results = self._vs.search_dense(
                    query=query,
                    top_k=k * 3,
                    filters=filters
                )
                
                if not raw_results:
                    return []
                
                # Converter SearchHit para formato esperado
                # Filtrar duplicatas exatas (score > 0.95)
                seen_texts = set()
                snippets = []
                for hit in raw_results:
                    if hit.score > 0.95:  # Duplicata exata
                        continue
                    if hit.text in seen_texts:
                        continue
                    seen_texts.add(hit.text)
                    
                    snippets.append({
                        "text": hit.text,
                        "source": hit.payload.get("source_id", "").replace("memory_", "") or "unknown",
                        "score": hit.score,
                        "timestamp": hit.payload.get("created_at", "")
                    })
                    
                    if len(snippets) >= k:
                        break
                
                print(f"🔍 Busca semântica (qdrant): {len(raw_results)} brutos → {len(snippets)} finais")
                return snippets
                
            else:
                # Backend antigo (ChromaDB) - compatibilidade
                results = self._vs.search(query, k=k * 3)
                
                if not results:
                    return []
                
                # Filtrar e deduplicar
                seen_texts = set()
                snippets = []
                for r in results:
                    if r.score >= 0.05 and r.text not in seen_texts:  # Chroma: menor = melhor
                        seen_texts.add(r.text)
                        snippets.append({
                            "text": r.text,
                            "source": r.metadata.get("role", "unknown"),
                            "score": r.score,
                            "timestamp": r.metadata.get("timestamp", "")
                        })
                
                print(f"🔍 Busca semântica (chroma): {len(results)} brutos → {len(snippets[:k])} finais")
                return snippets[:k]
            
        except Exception as e:
            print(f"❌ Erro em search_memory_semantic: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def format_for_langchain(self, limit: int = 10) -> str:
        """
        Formata histórico de curto prazo para inclusão no prompt LangChain.
        
        Remove automaticamente:
        - Contadores de contexto [Contexto: memória X, documentos Y]
        - Mensagens vazias
        
        Args:
            limit: número de mensagens recentes a incluir
            
        Returns:
            String formatada com histórico limpo
        """
        messages = self.load_active_history(limit)
        
        if not messages:
            return "(Sem histórico recente)"
        
        import re
        formatted_lines = []
        
        for msg in messages:
            # Limpar contador de contexto do final da mensagem
            content = re.sub(r'\n\n\[Contexto: memória \d+, documentos \d+\]$', '', msg['content'])
            content = content.strip()
            
            if content:  # Só adicionar se tiver conteúdo
                role_display = "Usuário" if msg['role'] == 'user' else "Assistente"
                formatted_lines.append(f"{role_display}: {content}")
        
        return "\n".join(formatted_lines) if formatted_lines else "(Sem histórico recente)"


# Teste rápido
if __name__ == "__main__":
    memory = ConversationMemory()
    
    # Teste básico
    memory.save_message("user", "Olá, teste do sistema de memória")
    memory.save_message("assistant", "Sistema funcionando perfeitamente!")
    
    print("Mensagens ativas:", memory.get_message_count())

    print("\nHistórico:")
    for msg in memory.load_active_history():
        print(f"  {msg['role']}: {msg['content']}")
    
    print("\nArquivando conversa...")
    archive_id = memory.archive_and_clear()
    print(f"Arquivado com ID: {archive_id}")
    print(f"Mensagens ativas após arquivar: {memory.get_message_count()}")
