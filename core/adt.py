
"""
Aurora ADT (Analista de Documentos Técnicos)
Wrapper simplificado usando o Unified Analysis Engine.
"""
import logging
from typing import List, Optional
from langsmith import traceable

from core.analysis_engine import AnalysisEngine

logger = logging.getLogger("aurora.adt")

@traceable(name="Analyze Documents (Unified)")
def analyze_documents(
    document_ids: List[str],
    analysis_type: str,
    question: Optional[str] = None,
    max_items_per_category: int = 5,
    scan_all: bool = False,
    scan_batch_size: int = 12,
    scan_passes: int = 1,
    debug_llm: bool = False
) -> dict:
    """Entry point legado mantido para compatibilidade."""
    return _internal_analyze_pipeline(
        document_ids, analysis_type, question, 
        scan_all=scan_all, scan_batch_size=scan_batch_size, 
        debug_llm=debug_llm
    )

@traceable(name="Analyze Pipeline (Core)")
def _internal_analyze_pipeline(
    document_ids: List[str],
    analysis_type: str,
    question: Optional[str] = None,
    max_items_per_category: int = 5,
    scan_all: bool = False,
    scan_batch_size: int = 12,
    scan_passes: int = 1,
    debug_llm: bool = False,
    prompt_variant: str = "v1",
    on_progress: Optional[callable] = None
) -> dict:
    """
    Roteia para o Engine Unificado.
    """
    engine = AnalysisEngine(debug=debug_llm)
    
    # Determinar modo
    mode = "scan_all" if scan_all else "hybrid"
    
    try:
        result = engine.run(
            document_ids=document_ids,
            analysis_type=analysis_type,
            question=question,
            mode=mode,
            batch_size=scan_batch_size,
            prompt_variant=prompt_variant,
            on_progress=on_progress
        )
        return result
    except Exception as e:
        logger.error(f"❌ ADT Error: {e}")
        return {"error": str(e), "items": {}}

# Helper wrapper para polling
def analyze_documents_with_progress(
    document_ids: List[str],
    analysis_type: str,
    question: Optional[str] = None,
    max_items_per_category: int = 5, # Ignored by engine, controlled by strategies
    scan_all: bool = False,
    scan_batch_size: int = 6,
    scan_passes: int = 1,
    debug_llm: bool = False,
    on_progress: Optional[callable] = None
) -> dict:
    return _internal_analyze_pipeline(
        document_ids, analysis_type, question, 
        scan_all=scan_all, scan_batch_size=scan_batch_size, 
        debug_llm=debug_llm, on_progress=on_progress
    )

# Re-exportar constants se necessário para api.py (nada crítico por enquanto)
