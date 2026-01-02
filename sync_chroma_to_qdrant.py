import os
import sys
from pathlib import Path
from datetime import datetime

# Setup paths
sys.path.append(str(Path(__file__).parent / "rag_retrieval"))
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["EMBED_MODEL"] = "sentence-transformers/all-MiniLM-L6-v2"
os.environ["EMBED_DIM"] = "384"
os.environ["COLLECTION_NAME"] = "default"

# Mock imports
try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    from langchain_community.embeddings import HuggingFaceEmbeddings

# Fix import path
from rag_retrieval.qdrant_store import QdrantStore

def sync_data():
    print("🚀 Iniciando Sincronização Chroma -> Qdrant...")
    
    # 1. Connect to Chroma (Source)
    embedding_device = "cpu" # Safe default
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': embedding_device},
        encode_kwargs={"normalize_embeddings": True}
    )
    
    persist_dir = "db"
    vector_db = Chroma(
        persist_directory=persist_dir,
        embedding_function=embeddings
    )
    
    # 2. Connect to Qdrant (Destination)
    # Force collection name to 'default' as per debug config
    qdrant = QdrantStore(collection_name="default")
    
    # 3. Fetch all docs from Chroma
    print("📦 Lendo documentos do ChromaDB...")
    collection = vector_db._collection
    data = collection.get(include=['documents', 'metadatas'])
    
    total = len(data['ids'])
    print(f"📊 Encontrados {total} chunks no Chroma.")
    
    if total == 0:
        print("⚠️ Nada para sincronizar.")
        return

    # 4. Prepare for Qdrant
    q_chunks = []
    
    for i in range(total):
        doc_text = data['documents'][i]
        meta = data['metadatas'][i] or {}
        
        filename = meta.get('filename') or meta.get('source', 'unknown')
        
        # Consistent ID generation
        combined_id = f"{filename}_{i}"
        chunk_hash = abs(hash(combined_id)) % (10 ** 18)
        
        q_chunks.append({
            "id": chunk_hash,
            "text": doc_text,
            "doc_id": filename,
            "source": filename, # Critical for ADT filter
            "source_id": filename,
            "chunk_id": i,
            "title": filename,
            "created_at": datetime.now().isoformat(),
            "metadata": meta
        })
    
    # 5. Upsert
    print(f"📤 Enviando {len(q_chunks)} chunks para o Qdrant...")
    qdrant.upsert_chunks(q_chunks, batch_size=100)
    print("✅ Sincronização concluída!")

if __name__ == "__main__":
    sync_data()
