from qdrant_client import QdrantClient
from qdrant_client.http import models

# Hardcoded Config
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "default"

def clean_duplicates():
    client = QdrantClient(url=QDRANT_URL)
    
    target_doc_id = "AuditDocEngine_Demo_SRS_QA_Requisitos.pdf"
    
    print(f"🧹 Scanning for points with doc_id: {target_doc_id}")
    
    # Scroll to get all IDs
    points_to_delete = []
    next_offset = None
    
    print(f"DEBUG: Starting scroll on '{COLLECTION_NAME}'...")
    found_doc_ids = set()
    
    while True:
        records, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=1000,
            offset=next_offset,
            with_payload=True,
            with_vectors=False
        )
        
        print(f"DEBUG: Fetched {len(records)} records. Offset: {next_offset}")
        
        for r in records:
            if r.payload:
                d_id = r.payload.get("doc_id", "UNKNOWN")
                found_doc_ids.add(str(d_id))
                
                # Debug counts
                # if "AuditDoc" in str(d_id):
                #    print(f"   -> Saw {d_id}")
                
                # Fuzzy match to find the actual ID
                if d_id and "AuditDoc" in str(d_id) and ".pdf" in str(d_id):
                    if len(points_to_delete) == 0:
                        print(f"🎯 FOUND MATCH! Actual doc_id: '{d_id}'")
                    points_to_delete.append(r.id)
        
        if not next_offset:
            break
            
    print(f"DEBUG: Found Doc IDs in DB: {found_doc_ids}")
            
    if not points_to_delete:
        print("⚠️ No points found for this doc_id.")
        return

    print(f"found {len(points_to_delete)} points. Deleting...")
    
    # Delete in batches
    batch_size = 1000
    for i in range(0, len(points_to_delete), batch_size):
        batch_ids = points_to_delete[i:i + batch_size]
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.PointIdsList(points=batch_ids)
        )
        print(f"   Deleted batch {i}-{i+len(batch_ids)}")
    
    print(f"✅ Deleted all {len(points_to_delete)} points.")

if __name__ == "__main__":
    clean_duplicates()
