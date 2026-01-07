import sys
import os
from pathlib import Path

# Add root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Hardcoded Config to avoid importing torch/core
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "default"

def diagnose_duplication():
    client = QdrantClient(url=QDRANT_URL)
    
    print(f"📊 Diagnosing duplication in collection: {COLLECTION_NAME}")
    
    # 1. Get all unique doc_ids by scrolling and aggregating
    # Since Qdrant doesn't have a "GROUP BY" aggregation easily accessible via python client for this,
    # we will scroll all points (assuming reasonable size) or use payload filtering.
    
    # Actually, let's use the scroll API to get all metadatas
    points = []
    next_offset = None
    
    print("⏳ Fetching all points (this might take a moment)...")
    while True:
        records, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            offset=next_offset,
            with_payload=True,
            with_vectors=False
        )
        points.extend(records)
        if not next_offset:
            break
            
    print(f"📦 Total points in collection: {len(points)}")
    
    # 2. Group by doc_id
    doc_counts = {}
    for p in points:
        doc_id = p.payload.get("doc_id", "UNKNOWN")
        doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1
        
    # 3. Report
    print("\n📋 Point Counts per Document:")
    print(f"{'DOC_ID':<50} | {'COUNT':<10}")
    print("-" * 65)
    
    points_to_delete = []
    
    for doc, count in doc_counts.items():
        print(f"{str(doc):<50} | {count:<10}")
        
        # Identify the PDF to clean
        if "AuditDoc" in str(doc) and ".pdf" in str(doc):
             # Collect IDs for this doc
             print(f"   ⚠️  Target for cleanup: {doc} ({count} points)")
             points_to_delete.extend([p.id for p in points if p.payload.get("doc_id") == doc])

    if points_to_delete:
        print(f"\n🧹 Cleaning {len(points_to_delete)} duplicate points for PDF...")
        batch_size = 1000
        for i in range(0, len(points_to_delete), batch_size):
            batch = points_to_delete[i:i + batch_size]
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=models.PointIdsList(points=batch)
            )
            print(f"   Deleted batch {i}-{i+len(batch)}")
        print("✅ Cleanup complete. Please re-index the document.")
    else:
        print("\n✅ No cleanup needed (Target PDF not found).")

    print("\n🔍 detailed analysis complete.")

if __name__ == "__main__":
    diagnose_duplication()
