from core.documents import get_doc_manager
from qdrant_client.models import Filter, FieldCondition, MatchValue

def debug_qdrant():
    print("🔍 Inspecting Qdrant Content...")
    dm = get_doc_manager()
    client = dm.vector_db.client
    collection_name = dm.vector_db.collection_name
    
    print(f"Collection: {collection_name}")
    
    # 1. Count Total
    info = client.get_collection(collection_name)
    print(f"Total Points: {info.points_count}")
    
    # 2. List some points to see metadata structure
    print("\n--- Sample Points ---")
    res, _ = client.scroll(
        collection_name=collection_name,
        limit=5,
        with_payload=True
    )
    
    for r in res:
        p = r.payload
        print(f"ID: {r.id}")
        print(f"DocID: {p.get('doc_id')}")
        print(f"Source: {p.get('source')}")
        print(f"Metadata: {p.get('metadata')}")
        print("-" * 20)

    # 3. Check specifically for FEATURES.md
    print("\n--- Check FEATURES.md ---")
    filename = "FEATURES.md"
    
    # Try doc_id
    res_doc, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=filename))]
        ),
        limit=1
    )
    print(f"Found via doc_id={filename}: {len(res_doc)}")

    # Try source
    res_src, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(
            must=[FieldCondition(key="source", match=MatchValue(value=filename))]
        ),
        limit=1
    )
    print(f"Found via source={filename}: {len(res_src)}")

if __name__ == "__main__":
    debug_qdrant()
