import sys
import os

# Add root
sys.path.append(os.getcwd())

# Add rag_retrieval folder to path (as per document_manager.py)
sys.path.append(os.path.join(os.getcwd(), 'rag_retrieval'))

try:
    from rag_retrieval.qdrant_store import QdrantStore
    print("Imported QdrantStore from rag_retrieval.qdrant_store")
except ImportError:
    print("Failed to import from rag_retrieval.qdrant_store, trying nested...")
    sys.path.append(os.path.join(os.getcwd(), 'rag_retrieval', 'rag_retrieval'))
    try:
        from qdrant_store import QdrantStore
        print("Imported QdrantStore from qdrant_store")
    except ImportError as e:
        print(f"CRITICAL: Could not import QdrantStore: {e}")
        sys.exit(1)

print("Connecting to Qdrant...")
try:
    store = QdrantStore(collection_name="default")
    client = store.client
    
    print(f"Deleting collection 'default'...")
    try:
        client.delete_collection("default")
        print("Collection deleted.")
    except Exception as e:
        print(f"Error deleting collection (might not exist): {e}")

    print("Re-initializing store...")
    store = QdrantStore(collection_name="default")
    print("Done.")

except Exception as e:
    print(f"General Error: {e}")
