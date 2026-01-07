from core.document_manager import DocumentManager
from core import config

# Singleton DocumentManager
doc_manager = DocumentManager(
    embedding_device=config.EMBEDDING_DEVICE,
    max_file_size_mb=config.MAX_FILE_SIZE_MB,
    max_total_files=config.MAX_TOTAL_FILES
)

def get_doc_manager():
    return doc_manager
