"""Debug script to inspect Qdrant payload fields."""
import sys
sys.path.insert(0, ".")

from qdrant_client import QdrantClient
from collections import Counter

client = QdrantClient(host="localhost", port=6333)

# Get all records (first 100)
records, _ = client.scroll(
    collection_name="default",
    limit=100,
    with_payload=True,
    with_vectors=False
)

print(f"Total records retrieved: {len(records)}")
print()

# Show first 5 payload structures
print("=== FIRST 5 PAYLOAD KEYS ===")
for i, r in enumerate(records[:5]):
    print(f"{i+1}. Keys: {list(r.payload.keys())}")
    print(f"   doc_id: {r.payload.get('doc_id', 'N/A')}")
    print(f"   source: {r.payload.get('source', 'N/A')}")
    print(f"   chunk_id: {r.payload.get('chunk_id', 'N/A')}")
    print()

# Count by doc_id
print("=== GROUP BY doc_id ===")
doc_ids = [r.payload.get('doc_id', 'MISSING') for r in records]
for doc_id, count in Counter(doc_ids).most_common():
    print(f"  {doc_id}: {count} chunks")

# Count by source
print("\n=== GROUP BY source ===")
sources = [r.payload.get('source', 'MISSING') for r in records]
for source, count in Counter(sources).most_common():
    print(f"  {source}: {count} chunks")
