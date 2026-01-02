"""
router.py - Roteador semântico
Se tools (function-calling) não forem suportadas, usa classificação LLM simples.
"""
from typing import Literal, List


RouteLabel = Literal["document_query", "memory_query", "chit_chat"]


def classify_query_simple(question: str) -> List[RouteLabel]:
    """
    Classificador básico: sempre retorna ['memory_query'] e decide 'document_query' por sinal semântico simples.
    Substituir por LLM router posteriormente.
    """
    q = (question or "").lower()
    labels: List[RouteLabel] = ["memory_query"]  # memória sempre ativa
    doc_hints = ["edital", "anbima", "certificação", "cpa", "exa", "documento", "regra", "taxa", "prazo"]
    if any(h in q for h in doc_hints):
        labels.append("document_query")
    else:
        labels.append("chit_chat")
    return labels
