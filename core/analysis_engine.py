
"""
Analysis Engine
Unified pipeline for Document Analysis (Scan All & Hybrid Modes).
"""
import logging
import json
import time
from typing import List, Optional, Dict, Callable
from datetime import datetime

from core.llm import llm
from core.strategies import get_strategy
from core.normalizer import sanitize_llm_json_output, normalize_adt_output
from core.documents import get_doc_manager
from core.hybrid_adapter import hybrid_search, format_hybrid_snips_for_context
from langsmith import traceable

# Qdrant Models
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

logger = logging.getLogger("aurora.engine")

# Resource Map (Prompts/Schemas) - Copied from ADT to keep here
ANALYSIS_RESOURCES = {
    "default": {
        "prompt": "prompts/aurora_adt_system_prompt.txt",
        "schema": "schemas/aurora_adt_output.schema.json"
    },
    "risk_detection": {
        "prompt": "prompts/risk_detection.txt",
        "schema": "schemas/risk_detection.schema.json"
    },
    "ambiguity_detection": {
        "prompt": "prompts/ambiguity_detection_system_v1.txt",
        "schema": "schemas/ambiguity_detection.schema.json"
    },
    "qa_requirements_audit": {
        "prompt": "prompts/qa_requirements_audit_system_v1.txt",
        "prompt_v2": "prompts/qa_requirements_audit_system_v2.txt",
        "schema": "schemas/qa_requirements_audit_output.schema.json"
    }
}

def load_resources(analysis_type: str, variant: str = "v1"):
    """Load prompt and schema."""
    config = ANALYSIS_RESOURCES.get(analysis_type, ANALYSIS_RESOURCES["default"])
    p_file = config["prompt"]
    if variant == "v2" and "prompt_v2" in config: p_file = config["prompt_v2"]
    
    try:
        with open(p_file, "r", encoding="utf-8") as f: prompt = f.read()
        with open(config["schema"], "r", encoding="utf-8") as f: schema = json.load(f)
        return prompt, schema
    except Exception as e:
        logger.error(f"Failed to load resources: {e}")
        return "You are an analyzer.", {}

class AnalysisEngine:
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.debug_capture = {}

    @traceable(name="Run Analysis Pipeline")
    def run(self, 
            document_ids: List[str], 
            analysis_type: str, 
            question: Optional[str] = None,
            mode: str = "scan_all", # scan_all | hybrid
            batch_size: int = 12,
            prompt_variant: str = "v1",
            on_progress: Optional[Callable] = None
        ) -> Dict:
        
        start_time = time.time()
        logger.info(f"🚀 [Engine] Starting {analysis_type} (Mode: {mode}) on {len(document_ids)} docs.")
        
        # 1. Strategy Setup
        strategy = get_strategy(analysis_type)
        system_prompt, schema = load_resources(analysis_type, prompt_variant)
        
        # 2. Retrieval Phase
        chunks = []
        doc_context_str = ""
        
        if mode == "scan_all":
            chunks = self._fetch_all_chunks(document_ids)
            total_items = len(chunks)
            if not chunks:
                 return {"error": "NO_CHUNKS", "message": "No chunks found for documents."}
        else:
            # Hybrid Mode
            query = question or f"Análise de {analysis_type}"
            chunks, doc_context_str = self._fetch_hybrid_context(document_ids, query)
            total_items = len(chunks) # Virtual chunks (snips)
            # For Hybrid, we treat the unified context as a SINGLE batch usually, 
            # OR we can treat snips as chunks.
            # ADT Pattern: Use unified string for single LLM call.
            # We will adapt: Make a single "virtual chunk" with full text?
            # Or pass chunks list.
            # To unify logic: Map-Reduce works for 1 batch too.
            if chunks:
                # If we have chunks from hybrid search, use them as batch
                pass
            elif doc_context_str:
                 # Fallback if only string returned (legacy adapter)
                 chunks = [{"text": doc_context_str, "chunk_id": 0, "doc_id": "hybrid_ctx"}]
        
        # 3. Processing Phase (Map)
        batch_results = []
        
        # Hybrid mode usually does 1 pass on ALL retrieved context.
        # Scan mode does N passes.
        
        current_batch_size = batch_size if mode == "scan_all" else 100 # Hybrid fits in context usually
        
        batches = [chunks[i:i + current_batch_size] for i in range(0, len(chunks), current_batch_size)]
        total_batches = len(batches)
        
        logger.info(f"⚡ [Engine] Processing {total_batches} batches...")
        
        for i, batch in enumerate(batches):
            batch_num = i + 1
            if on_progress: on_progress(batch_num, total_batches)
            
            # Prepare Text
            batch_text = "\n---\n".join([f"{c['text']}" for c in batch])
            
            # Call LLM
            logger.info(f"🤖 [Engine] LLM Call Batch {batch_num}/{total_batches}")
            try:
                # Prompt Construction
                user_prompt = f"""
ANÁLISE PARCIAL (Lote {batch_num}/{total_batches}):
Tipo: {analysis_type}
Pergunta: {question if question else 'N/A'}

<context>
{batch_text[:25000]} 
</context>

<instruction>
{system_prompt}
Analise o texto acima e extraia itens conforme o schema.
Retorne JSON.
</instruction>
"""
                # Simplified Invoke
                msgs = [("system", "Você é um analista especialista. Responda apenas JSON."), ("user", user_prompt)]
                resp = llm.invoke(msgs)
                content = sanitize_llm_json_output(resp.content)
                
                data = json.loads(content)
                if data: batch_results.append(data)
                
            except Exception as e:
                logger.error(f"❌ Batch {batch_num} failed: {e}")
                self.debug_capture[f"batch_{batch_num}_error"] = str(e)

        # 4. Aggregation Phase (Reduce)
        logger.info("🔄 [Engine] Merging results...")
        merged_data = strategy.merge_batch_results(batch_results)
        
        # 5. Post-Processing & Fallback
        full_text_ref = "\n".join([c["text"] for c in chunks])
        merged_data = strategy.apply_fallbacks(merged_data, full_text_ref)
        
        if hasattr(strategy, "post_process"):
             merged_data = strategy.post_process(merged_data, self.debug_capture)
        
        if hasattr(strategy, "reindex"):
             merged_data = strategy.reindex(merged_data)
             
        # 6. Final Metadata
        merged_data["meta"] = {
            "analysis_type": analysis_type,
            "mode": mode,
            "duration": time.time() - start_time,
            "batches_processed": total_batches,
            "model": getattr(llm, "model_name", "unknown")
        }
        
        if self.debug:
            merged_data["meta"]["debug"] = self.debug_capture
            
        return merged_data

    def _fetch_all_chunks(self, doc_ids: List[str]) -> List[Dict]:
        doc_manager = get_doc_manager()
        client = doc_manager.vector_db.client
        collection = doc_manager.vector_db.collection_name
        
        chunks = []
        try:
             # Using MatchAny for robustness
            q_filter = Filter(must=[FieldCondition(key="doc_id", match=MatchAny(any=doc_ids))])
            offset = None
            while True:
                recs, offset = client.scroll(
                    collection_name=collection, scroll_filter=q_filter, limit=100, with_payload=True, offset=offset
                )
                for r in recs:
                    if "text" in r.payload:
                        chunks.append({
                            "text": r.payload["text"], 
                            "doc_id": r.payload.get("doc_id"),
                            "chunk_id": r.payload.get("chunk_id", 0)
                        })
                if offset is None: break
        except Exception as e:
            logger.error(f"Fetch Error: {e}")
        
        # Sort
        chunks.sort(key=lambda x: (x['doc_id'], x['chunk_id']))
        return chunks

    def _fetch_hybrid_context(self, doc_ids: List[str], query: str) -> tuple:
        # Use existing hybrid logic
        ret = hybrid_search(query=query, filters={"source": doc_ids}, k_docs=20)
        snips = ret.get("doc_snips", [])
        formatted_text, _ = format_hybrid_snips_for_context(snips, [])
        
        # Convert snips to dict chunks like Qdrant
        chunks = []
        for s in snips:
            chunks.append({"text": s.text, "doc_id": s.metadata.get("doc_id"), "chunk_id": 0})
            
        return chunks, formatted_text
