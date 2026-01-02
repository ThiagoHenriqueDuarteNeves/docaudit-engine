"""
tools.py - Definições de ferramentas para busca semântica
DocumentSearchTool e MemorySearchTool retornam trechos relevantes.
"""
from typing import List, Dict

from document_manager import DocumentManager
from memory_manager import ConversationMemory


class DocumentSearchTool:
    """
    Tool de busca semântica em documentos.
    Input: {query: str, k: int}
    Output: {snippets: List[Dict[text, source, score]]}
    """

    def __init__(self, doc_manager: DocumentManager):
        self.doc_manager = doc_manager

    def invoke(self, query: str, k: int = 8) -> List[Dict]:
        return self.doc_manager.search_documents(query=query, k=k)


class MemorySearchTool:
    """
    Tool de busca semântica na memória de conversas.
    Input: {query: str, k: int}
    Output: {snippets: List[Dict[text, source, score]]}
    """

    def __init__(self, memory: ConversationMemory):
        self.memory = memory

    def invoke(self, query: str, k: int = 6) -> List[Dict]:
        return self.memory.search_memory_semantic(query=query, k=k)
