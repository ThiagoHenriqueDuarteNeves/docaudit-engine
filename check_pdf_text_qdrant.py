import sys
import os
import json
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Setup paths
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'rag_retrieval'))

# Use DocumentManager to get client configuration or connect directly
# Assuming default local connection
client = QdrantClient(url="http://localhost:6333") 

# Or use existing logic
from rag_retrieval.qdrant_store import QdrantStore
store = QdrantStore(collection_name="default")
client = store.client

doc_id = "AuditDocEngine_Demo_SRS_QA_Requisitos.pdf"

print(f"Fetching chunks for {doc_id}...")

q_filter = Filter(
    should=[
        FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
        FieldCondition(key="source", match=MatchValue(value=doc_id))
    ]
)

records, _ = client.scroll(
    collection_name="default",
    scroll_filter=q_filter,
    limit=100,
    with_payload=True,
    with_vectors=False
)

print(f"Found {len(records)} chunks.")

with open("pdf_content.txt", "w", encoding="utf-8") as f:
    for r in records:
        text = r.payload.get("text", "")
        chunk_id = r.payload.get("chunk_id", "?")
        f.write(f"--- Chunk {chunk_id} ---\n")
        f.write(text)
        f.write("\n\n")

print("Saved to pdf_content.txt")
