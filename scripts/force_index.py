from core.documents import get_doc_manager
import time

def index_now():
    dm = get_doc_manager()
    print("🔄 Forcing scan_and_index...")
    stats = dm.scan_and_index()
    print(f"✅ Indexing result: {stats}")

if __name__ == "__main__":
    index_now()
