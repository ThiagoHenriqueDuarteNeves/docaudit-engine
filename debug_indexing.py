
import sys
import os
import shutil
import time

# Add current dir to path
sys.path.append(os.getcwd())

from document_manager import DocumentManager
from core import config

pdf_path = "assets/demo/AuditDocEngine_Demo_SRS_QA_Requisitos.pdf"
target_path = "docs/AuditDocEngine_Demo_SRS_QA_Requisitos.pdf"
os.makedirs("docs", exist_ok=True)
if os.path.exists(pdf_path):
    shutil.copy(pdf_path, target_path)
    print(f"File copied to {target_path}, size: {os.stat(target_path).st_size}")
else:
    print(f"ERROR: Source file not found: {pdf_path}")
    sys.exit(1)

dm = DocumentManager()
print("Starting scan_and_index...")
stats = dm.scan_and_index()
print("Stats:", stats)

# check chunks
try:
    client = dm.vector_db.client
    col = dm.vector_db.collection_name
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    # Wait a bit for async commit if any
    time.sleep(2)

    count = client.count(
        collection_name=col,
        count_filter=Filter(
            should=[
                FieldCondition(key="doc_id", match=MatchValue(value="AuditDocEngine_Demo_SRS_QA_Requisitos.pdf")),
                FieldCondition(key="source", match=MatchValue(value="AuditDocEngine_Demo_SRS_QA_Requisitos.pdf"))
            ]
        )
    )
    print("Qdrant Count:", count.count)
except Exception as e:
    print(f"Error checking Qdrant: {e}")
