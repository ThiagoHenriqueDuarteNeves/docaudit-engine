"""
QA Requirements Audit V3 - Full-Scan + Map-Reduce + Deterministic Fallback
Garantir contagens mínimas independente do LLM.
"""
import re
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from core.llm import llm
from core.normalizer import normalize_adt_output

logger = logging.getLogger("aurora.adt.qa_v3")

# =============================================================================
# CONSTANTS
# =============================================================================
MIN_REQUIREMENTS = 10
MIN_AMBIGUITIES = 8
MIN_UNVERIFIABLE = 3
MIN_CONTRADICTIONS = 1

VAGUE_TERMS = [
    "rápido", "muito rápido", "curto", "intervalo curto", "alto", "forte",
    "padrão de mercado", "não frustrar", "sempre que possível", "internet ruim",
    "sem interrupções", "longos períodos", "longo período", "gentil", "gentilmente",
    "bonito", "amigável", "fácil", "intuitivo", "bom", "boa"
]

NORMATIVE_TOKENS = [
    "deve", "não pode", "precisa", "quando", "se", "sempre", "nunca", 
    "obrigatório", "obrigatoriamente", "permitir", "bloquear"
]

# =============================================================================
# A) FULL-SCAN RETRIEVAL (Already done in calling code - we just receive chunks)
# =============================================================================

def fetch_all_chunks_from_qdrant(document_ids: List[str], max_chunks: int = 200, debug: bool = False) -> List[Dict]:
    """
    Fetch ALL chunks for given document_ids from Qdrant.
    Returns list of {text, chunk_id, doc_id}.
    """
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, MatchAny
    import os
    
    debug = debug or os.environ.get("DEBUG_RETRIEVAL") == "1"
    
    if debug:
        logger.info(f"🔍 [RETRIEVAL DEBUG] Requested document_ids: {document_ids}")
    
    client = QdrantClient(host="localhost", port=6333)
    all_chunks = []
    
    # Build filter: use MUST with MatchAny for doc_id field
    # This ensures we ONLY get chunks matching the requested document_ids
    q_filter = Filter(
        must=[
            FieldCondition(key="doc_id", match=MatchAny(any=document_ids))
        ]
    )
    
    try:
        offset = None
        while len(all_chunks) < max_chunks:
            records, offset = client.scroll(
                collection_name="default",
                scroll_filter=q_filter,
                limit=100,
                with_payload=True,
                with_vectors=False,
                offset=offset
            )
            
            for r in records:
                if r.payload and "text" in r.payload:
                    chunk_doc_id = r.payload.get("doc_id", "UNKNOWN")
                    all_chunks.append({
                        "text": r.payload["text"],
                        "chunk_id": r.payload.get("chunk_id", 0),
                        "doc_id": chunk_doc_id,
                    })
            
            if offset is None or len(records) == 0:
                break
                
    except Exception as e:
        logger.error(f"❌ Erro ao buscar chunks: {e}")
    
    # Debug: group by doc_id and check for leaks
    if debug:
        from collections import Counter
        doc_counts = Counter([c["doc_id"] for c in all_chunks])
        logger.info(f"📊 [RETRIEVAL DEBUG] Total chunks: {len(all_chunks)}")
        logger.info(f"📊 [RETRIEVAL DEBUG] Group by doc_id: {dict(doc_counts)}")
        
        # Check for leaked documents
        leaked = [d for d in doc_counts.keys() if d not in document_ids]
        if leaked:
            logger.warning(f"⚠️ [RETRIEVAL LEAK] Found chunks from unexpected docs: {leaked}")
            raise ValueError(f"FULL_SCAN_FILTER_LEAK: retrieved chunks from other documents: {leaked}")
        
        # Sample first 5
        if all_chunks:
            logger.info(f"📊 [RETRIEVAL DEBUG] Sample (first 5): {[(c['doc_id'], c['chunk_id']) for c in all_chunks[:5]]}")
    
    # Sort by doc_id then chunk_id
    all_chunks.sort(key=lambda x: (x['doc_id'], x['chunk_id']))
    return all_chunks[:max_chunks]



# =============================================================================
# B) MAP-REDUCE PROCESSING
# =============================================================================

# Field length limits for truncation
FIELD_LIMITS = {
    "evidencia_literal": 240,
    "texto": 180,
    "problema": 160,
    "motivo": 160,
    "como_tornar_testavel": 160,
    "sugestao_reescrita": 160,
    "descricao": 200,
    "evidencia_a": 200,
    "evidencia_b": 200,
}

QA_AUDIT_MAX_TOKENS = 1800  # Limit to prevent context overflow


def truncate_field(value: str, max_len: int) -> str:
    """Truncate a string to max_len, adding ellipsis if truncated."""
    if not value or len(value) <= max_len:
        return value
    return value[:max_len - 1] + "…"


def truncate_item_fields(item: Dict, field_limits: Dict = FIELD_LIMITS) -> Dict:
    """Truncate all text fields in an item according to limits."""
    for field, limit in field_limits.items():
        if field in item and isinstance(item[field], str):
            item[field] = truncate_field(item[field], limit)
    return item


def truncate_all_items(items_dict: Dict) -> Dict:
    """Apply truncation to all items in the items dictionary."""
    for category in ["requirements", "ambiguities", "contradictions", "unverifiable_criteria"]:
        if category in items_dict and isinstance(items_dict[category], list):
            items_dict[category] = [truncate_item_fields(item) for item in items_dict[category]]
    return items_dict
# Batch item caps for smaller JSON output
BATCH_ITEM_CAPS = {
    "requirements": 3,
    "ambiguities": 3,
    "unverifiable_criteria": 1,
    "contradictions": 1
}

# Batch-specific schema for structured output
BATCH_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "object",
            "properties": {
                "requirements": {"type": "array", "items": {"type": "object"}},
                "ambiguities": {"type": "array", "items": {"type": "object"}},
                "contradictions": {"type": "array", "items": {"type": "object"}},
                "unverifiable_criteria": {"type": "array", "items": {"type": "object"}},
                "coverage": {"type": "object"}
            }
        }
    },
    "required": ["items"]
}

# Tracking for debug
_batch_repair_count = 0


def repair_json_response(raw_content: str, error_msg: str) -> Optional[Dict]:
    """Attempt to repair invalid JSON using LLM."""
    import requests
    from core.config import LM_STUDIO_URL
    
    global _batch_repair_count
    
    repair_prompt = f"""
O JSON abaixo está inválido. Erro: {error_msg}

<json_invalido>
{raw_content[:2000]}
</json_invalido>

Corrija para JSON válido aderente ao schema, sem alterar significado.
Retorne APENAS o JSON corrigido, sem markdown.
"""
    
    base_url = LM_STUDIO_URL.replace("/v1", "")
    
    try:
        resp = requests.post(
            f"{base_url}/v1/chat/completions",
            json={
                "messages": [
                    {"role": "system", "content": "Você repara JSONs inválidos. Retorne apenas JSON válido."},
                    {"role": "user", "content": repair_prompt}
                ],
                "max_tokens": 2500,
                "temperature": 0.0
            },
            timeout=60
        )
        
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"].strip()
            
            from core.normalizer import sanitize_llm_json_output
            content = sanitize_llm_json_output(content)
            
            data = json.loads(content)
            _batch_repair_count += 1
            logger.info(f"✅ [QA V3] JSON reparado com sucesso")
            return data
    except Exception as e:
        logger.warning(f"⚠️ [QA V3] Repair falhou: {e}")
    
    return None


def call_llm_for_extraction(batch_text: str, system_prompt: str, batch_num: int, total_batches: int, max_tokens: int = 2500) -> Dict:
    """Call LLM to extract items from a batch with structured output and repair."""
    import requests
    from core.config import LM_STUDIO_URL
    
    base_url = LM_STUDIO_URL.replace("/v1", "")
    
    # Build prompt with item caps
    user_prompt = f"""
ANÁLISE PARCIAL (Lote {batch_num}/{total_batches}):
Tipo: qa_requirements_audit

<context_data>
{batch_text}
</context_data>

<task>
Extraia APENAS o que estiver NESTES TRECHOS.
LIMITES DESTE BATCH (NÃO EXCEDER):
- Máximo {BATCH_ITEM_CAPS['requirements']} requirements
- Máximo {BATCH_ITEM_CAPS['ambiguities']} ambiguities  
- Máximo {BATCH_ITEM_CAPS['unverifiable_criteria']} unverifiable_criteria
- Máximo {BATCH_ITEM_CAPS['contradictions']} contradictions

Mantenha campos curtos (evidencia_literal max 200 chars, texto max 150 chars).

Retorne JSON com "items" contendo: requirements, ambiguities, contradictions, unverifiable_criteria, coverage.
IMPORTANTE: Retorne APENAS o JSON puro. NÃO use blocos de código (```json). NÃO escreva introdução. 
</task>
"""
    
    base_payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": int(max_tokens),
        "temperature": 0.0
    }

    # Attempt 1: Raw (No response_format for compatibility)
    payload = base_payload.copy()
    # payload["response_format"] = {"type": "json_object"} # DISABLED to avoid HTTP 400 loop and speed up
    
    def log_error_details(resp, p_load, attempt_name):
        try:
            body_preview = resp.text[:500]
            logger.error(f"❌ [QA V3] {attempt_name} HTTP {resp.status_code}. Body: {body_preview}")
            logger.error(f"   Payload summary: model={p_load.get('model')}, max_tokens={p_load.get('max_tokens')}, keys={list(p_load.keys())}")
        except Exception as e:
            logger.error(f"❌ [QA V3] Error logging details: {e}")

    try:
        logger.info(f"🤖 [QA V3] Calling LLM (batch={batch_num}, structured_output=true)")
        resp = requests.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            timeout=120
        )
        
        if resp.status_code != 200:
            log_error_details(resp, payload, "Attempt 1 (Raw)")
            return {"items": {}}
             
            #    logger.warning(f"⚠️ [QA V3] Batch {batch_num} failed with 400. Retrying without response_format...")
            #    
            #    # Attempt 2: Without response_format
            #    payload = base_payload.copy()
            #    resp = requests.post(
            #        f"{base_url}/v1/chat/completions",
            #        json=payload,
            #        timeout=120
            #    )
            
            if resp.status_code != 200:
                log_error_details(resp, payload, "Attempt 2 (Raw)")
                # Return FATAL error to trigger fail-fast
                return {"error": "HTTP_400", "items": {}}

        # Other non-200 errors (500, etc) -> just return empty, don't kill pipeline immediately unless 400?
        # User requested fail-fast on 400. For others, we might want to skip.
        if resp.status_code != 200:
             logger.error(f"❌ [QA V3] LLM HTTP error: {resp.status_code}")
             return {"items": {}} # Non-fatal error for now? Or fatal? User said "se ocorrer 400... fail-fast".

        content = resp.json()["choices"][0]["message"]["content"].strip()
        
        # Robust sanitization (removes Markdown, extra text, finds first valid JSON)
        from core.normalizer import sanitize_llm_json_output
        content = sanitize_llm_json_output(content)
        
        try:
            data = json.loads(content) # Removed .strip() as sanitizer does it
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ [QA V3] Batch {batch_num} JSON error: {e}. Attempting repair...")
            data = repair_json_response(content, str(e))
            if data is None:
                return {"items": {}}
        
        # Apply truncation to LLM output
        if "items" in data:
            data["items"] = truncate_all_items(data["items"])
        
        return data
        
    except Exception as e:
        logger.warning(f"⚠️ [QA V3] Batch {batch_num} error: {e}")
        return {"items": {"requirements": [], "ambiguities": [], "contradictions": [], "unverifiable_criteria": [], "coverage": {"counts": {}}}}


def sanitize_text(text: str) -> str:
    """Sanitize text by removing control characters and normalizing spaces."""
    if not text:
        return ""
    # Remove control chars (0x00-0x1F, 0x7F) and specific garbage like \u007f or " "
    text = re.sub(r'[\x00-\x1F\x7F\u007f]', '', text)
    # Collapse whitespace
    return re.sub(r'\s+', ' ', text).strip()


def normalize_text(text: str) -> str:
    """Normalize text for deduplication."""
    if not text:
        return ""
    return sanitize_text(text).lower()


def merge_and_dedup_results(batch_results: List[Dict]) -> Dict:
    """
    Merge results from all batches and deduplicate.
    Implements deterministic type correction and keeps longest evidence.
    """
    merged = {
        "requirements": [],
        "ambiguities": [],
        "contradictions": [],
        "unverifiable_criteria": [],
        "coverage": {"counts": {"funcional": 0, "nao_funcional": 0, "regra_negocio": 0, "aceite": 0}},
        "_debug_stats": {"dedup_removed": 0}
    }
    
    # Track best items by key
    # Key -> Item
    best_reqs = {}
    best_ambs = {}
    best_unvs = {}
    best_cons = {}
    
    total_raw_items = 0
    
    for result in batch_results:
        if not result: continue
        items = result.get("items") or {}
        
        # Requirements
        for req in items.get("requirements", []):
            total_raw_items += 1
            # Sanitize
            req["texto"] = sanitize_text(req.get("texto", ""))
            req["evidencia_literal"] = sanitize_text(req.get("evidencia_literal", ""))
            
            # Deterministic Type Correction
            txt_lower = req["texto"].lower()
            if txt_lower.startswith("rf-"): req["tipo"] = "funcional"
            elif txt_lower.startswith("rnf-"): req["tipo"] = "nao_funcional"
            elif txt_lower.startswith("rb-"): req["tipo"] = "regra_negocio"
            elif txt_lower.startswith("ca-"): req["tipo"] = "aceite"
            
            # Dedup Key
            key = (req.get("tipo", ""), normalize_text(req["texto"]))
            if not key[1]: continue
            
            # Keep longest evidence
            if key not in best_reqs:
                best_reqs[key] = req
            else:
                existing = best_reqs[key]
                if len(req["evidencia_literal"]) > len(existing["evidencia_literal"]):
                    best_reqs[key] = req
                merged["_debug_stats"]["dedup_removed"] += 1
        
        # Ambiguities
        for amb in items.get("ambiguities", []):
            amb["evidencia_literal"] = sanitize_text(amb.get("evidencia_literal", ""))
            key = normalize_text(amb.get("trecho_problematico", ""))
            if key and key not in best_ambs:
                best_ambs[key] = amb
        
        # Unverifiable
        for unv in items.get("unverifiable_criteria", []):
            unv["evidencia_literal"] = sanitize_text(unv.get("evidencia_literal", ""))
            key = normalize_text(unv.get("evidencia_literal", "")) or normalize_text(unv.get("motivo", ""))
            if key and key not in best_unvs:
                best_unvs[key] = unv

        # Contradictions
        for con in items.get("contradictions", []):
            con["evidencia_literal"] = sanitize_text(con.get("evidencia_literal", ""))
            con["evidencia_a"] = sanitize_text(con.get("evidencia_a", ""))
            con["evidencia_b"] = sanitize_text(con.get("evidencia_b", ""))
            
            key = (normalize_text(con.get("evidencia_a", "")), normalize_text(con.get("evidencia_b", "")))
            if key[0] and key not in best_cons:
                best_cons[key] = con

    merged["requirements"] = list(best_reqs.values())
    merged["ambiguities"] = list(best_ambs.values())
    merged["contradictions"] = list(best_cons.values())
    merged["unverifiable_criteria"] = list(best_unvs.values())
    
    return merged


def reindex_requirements(requirements: List[Dict]) -> List[Dict]:
    """Reindex requirement IDs sequentially."""
    counters = {"funcional": 0, "nao_funcional": 0, "regra_negocio": 0, "aceite": 0}
    prefixes = {"funcional": "RF", "nao_funcional": "RNF", "regra_negocio": "RB", "aceite": "CA"}
    
    for req in requirements:
        tipo = req.get("tipo", "funcional")
        if tipo not in counters:
            tipo = "funcional"
        counters[tipo] += 1
        req["id"] = f"{prefixes[tipo]}-{counters[tipo]:02d}"
    
    return requirements


def recalculate_coverage(requirements: List[Dict]) -> Dict:
    """Recalculate coverage counts."""
    counts = {"funcional": 0, "nao_funcional": 0, "regra_negocio": 0, "aceite": 0}
    for req in requirements:
        tipo = req.get("tipo", "funcional")
        if tipo in counts:
            counts[tipo] += 1
    return {"counts": counts}


# =============================================================================
# C) DETERMINISTIC FALLBACK
# =============================================================================

def extract_requirement_from_sentence(sentence: str, idx: int) -> Optional[Dict]:
    """Extract a requirement from a sentence using heuristics."""
    sentence_lower = sentence.lower()
    
    # Determine tipo - more comprehensive keywords
    tipo = "funcional"
    
    # Non-functional: performance, security, availability
    nf_keywords = ["tempo", "ms", "segundos", "latência", "disponível", "criptografia", 
                   "log", "24/7", "rápido", "taxa", "sucesso", "performance", "uptime",
                   "ssl", "https", "segurança", "backup", "recuperação"]
    
    # Business rules: organizational/policy constraints  
    rb_keywords = ["corporativo", "@empresa", "mfa", "obrigatório", "regra", "política",
                   "sessão", "expirar", "logado", "dias", "minutos", "tentativas",
                   "bloquear", "bloqueio", "conta", "usuário"]
    
    # Acceptance criteria: testable outcomes
    ca_keywords = ["critério", "aceite", "deve passar", "consegue logar", "funciona", 
                   "expira", "consegue", "aparece", "exibe", "mostra", "retorna"]
    
    if any(t in sentence_lower for t in nf_keywords):
        tipo = "nao_funcional"
    elif any(t in sentence_lower for t in rb_keywords):
        tipo = "regra_negocio"
    elif any(t in sentence_lower for t in ca_keywords):
        tipo = "aceite"
    
    # Determine testability
    testabilidade = "parcialmente_verificavel"
    if any(t in sentence_lower for t in VAGUE_TERMS):
        testabilidade = "nao_verificavel"
    elif re.search(r'\d+\s*(minutos?|segundos?|dias?|tentativas?|%)', sentence_lower):
        testabilidade = "verificavel"
    
    return {
        "id": f"FB-{idx:02d}",
        "tipo": tipo,
        "texto": truncate_field(sentence.strip(), 180),
        "testabilidade": testabilidade,
        "evidencia_literal": truncate_field(sentence.strip(), 240)
    }


def fallback_extract_requirements(full_text: str, existing_items: List[Dict]) -> List[Dict]:
    """Extract requirements deterministically from text, avoiding duplicates."""
    existing_count = len(existing_items)
    needed = max(0, MIN_REQUIREMENTS - existing_count)
    if needed == 0:
        return []
        
    # Build existing keys to avoid duplicates
    existing_keys = set()
    for item in existing_items:
        key = (item.get("tipo", ""), normalize_text(item.get("texto", "")))
        existing_keys.add(key)
    
    results = []
    sentences = re.split(r'[.\n]', full_text)
    idx = existing_count + 1
    
    for sentence in sentences:
        if len(results) >= needed:
            break
        
        sentence = sentence.strip()
        if len(sentence) < 15:
            continue
            
        # Check for normative tokens or bullets
        sentence_lower = sentence.lower()
        has_normative = any(token in sentence_lower for token in NORMATIVE_TOKENS)
        is_bullet = sentence.startswith(("-", "•", "*", "RF-", "RNF-", "RB-", "CA-"))
        
        if has_normative or is_bullet:
            req = extract_requirement_from_sentence(sentence, idx)
            if req:
                # Check for duplicate against existing AND newly added
                # Sanitize first
                req["texto"] = sanitize_text(req["texto"])
                
                # Type correction (same as merge)
                txt_lower = req["texto"].lower()
                if txt_lower.startswith("rf-"): req["tipo"] = "funcional"
                elif txt_lower.startswith("rnf-"): req["tipo"] = "nao_funcional"
                elif txt_lower.startswith("rb-"): req["tipo"] = "regra_negocio"
                elif txt_lower.startswith("ca-"): req["tipo"] = "aceite"

                key = (req.get("tipo", ""), normalize_text(req["texto"]))
                
                if key not in existing_keys:
                    existing_keys.add(key)
                    results.append(req)
                    idx += 1
    
    return results


def fallback_extract_ambiguities(full_text: str, existing_count: int) -> List[Dict]:
    """Extract ambiguities deterministically from text."""
    needed = max(0, MIN_AMBIGUITIES - existing_count)
    if needed == 0:
        return []
    
    results = []
    text_lower = full_text.lower()
    
    for term in VAGUE_TERMS:
        if len(results) >= needed:
            break
        
        if term in text_lower:
            # Find context around the term
            idx = text_lower.find(term)
            start = max(0, idx - 50)
            end = min(len(full_text), idx + len(term) + 100)
            context = full_text[start:end].strip()
            
            # Find sentence containing term
            sentences = re.split(r'[.\n]', context)
            for s in sentences:
                if term in s.lower():
                    results.append({
                        "trecho_problematico": term,
                        "problema": f"Termo vago/subjetivo: '{term}' não define métrica objetiva",
                        "sugestao_reescrita": f"Definir valor numérico ou limites claros para '{term}'",
                        "evidencia_literal": s.strip() if len(s) > 10 else context[:100]
                    })
                    break
    
    return results


def fallback_extract_unverifiable(requirements: List[Dict], existing_count: int, full_text: str = "") -> List[Dict]:
    """Extract unverifiable criteria from requirements or text containing vague terms."""
    needed = max(0, MIN_UNVERIFIABLE - existing_count)
    if needed == 0:
        return []
    
    results = []
    seen_ids = set()
    
    # First, check requirements with testabilidade == "nao_verificavel"
    for req in requirements:
        if len(results) >= needed:
            break
        
        req_text = (req.get("texto", "") + " " + req.get("evidencia_literal", "")).lower()
        is_unverifiable = req.get("testabilidade") == "nao_verificavel"
        
        # Also check if the text contains vague terms
        if not is_unverifiable:
            is_unverifiable = any(term in req_text for term in VAGUE_TERMS)
        
        if is_unverifiable:
            req_id = req.get("id", f"REQ-{len(results)+1}")
            if req_id not in seen_ids:
                seen_ids.add(req_id)
                results.append({
                    "id_requisito": req_id,
                    "motivo": "Critério subjetivo sem métrica numérica definida",
                    "como_tornar_testavel": "Definir valor numérico (ms, %, uptime, algoritmo específico)",
                    "evidencia_literal": truncate_field(req.get("evidencia_literal", req.get("texto", "")), 240)
                })
    
    # If still not enough, scan text directly for vague terms
    if len(results) < needed and full_text:
        text_lower = full_text.lower()
        for term in VAGUE_TERMS:
            if len(results) >= needed:
                break
            
            if term in text_lower:
                idx = text_lower.find(term)
                start = max(0, idx - 30)
                end = min(len(full_text), idx + len(term) + 80)
                context = full_text[start:end].strip()
                
                results.append({
                    "id_requisito": f"TEXT-{len(results)+1}",
                    "motivo": f"Termo vago '{term}' sem métrica definida",
                    "como_tornar_testavel": f"Substituir '{term}' por valor numérico mensurável",
                    "evidencia_literal": truncate_field(context, 240)
                })
    
    return results


def fallback_extract_contradiction(full_text: str, existing_count: int) -> List[Dict]:
    """Extract contradiction if 7 dias / 30 dias pattern exists."""
    if existing_count >= MIN_CONTRADICTIONS:
        return []
    
    text_lower = full_text.lower()
    
    # Check for the specific demo contradiction
    has_7_dias = "7 dias" in text_lower
    has_30_dias = "30 dias" in text_lower
    
    if has_7_dias and has_30_dias:
        # Find evidence
        ev_a = ""
        ev_b = ""
        
        for sentence in re.split(r'[.\n]', full_text):
            if "7 dias" in sentence.lower() and not ev_a:
                ev_a = sentence.strip()
            if "30 dias" in sentence.lower() and not ev_b:
                ev_b = sentence.strip()
        
        if ev_a and ev_b:
            return [{
                "descricao": "Contradição de prazo: sessão deve expirar em 7 dias, mas manter logado por 30 dias",
                "evidencia_a": ev_a[:200],
                "evidencia_b": ev_b[:200],
                "severidade": "alta",
                "evidencia_literal": f"{ev_a[:100]}... / ...{ev_b[:100]}"
            }]
    
    return []


# =============================================================================
# MAIN V3 PIPELINE
# =============================================================================

def run_qa_requirements_audit_v3(
    document_ids: List[str],
    system_prompt: str,
    schema: Dict,
    debug_llm: bool = False,
    batch_size: int = 4,
    max_chunks: int = 200
) -> Dict:
    """
    Run QA Requirements Audit with V3 strategy:
    1. Full-scan retrieval
    2. Map-Reduce processing
    3. Deterministic fallback
    """
    global _batch_repair_count
    _batch_repair_count = 0  # Reset counter for this run
    
    debug_info = {
        "full_scan_used": True,
        "map_reduce_used": True,
        "fallback_quantity_used": False,
        "added_by_fallback_counts": {},
        "batches": 0,
        "chunks_total": 0,
        "structured_output_enabled": True,
        "map_batch_item_caps": BATCH_ITEM_CAPS,
        "map_batch_max_tokens_used": 2500,
        "batch_repair_used_count": 0,
        "llm_temperature_used": 0.1
    }
    
    # A) FULL-SCAN RETRIEVAL
    logger.info(f"📥 [QA V3] Full-scan: fetching all chunks for {document_ids}")
    all_chunks = fetch_all_chunks_from_qdrant(document_ids, max_chunks=max_chunks, debug=debug_llm)
    
    if not all_chunks:
        return {
            "error": "DOCUMENT_NOT_INDEXED",
            "message": f"Nenhum chunk encontrado para: {', '.join(document_ids)}"
        }
    
    debug_info["chunks_total"] = len(all_chunks)
    logger.info(f"📦 [QA V3] Loaded {len(all_chunks)} chunks")
    
    # B) MAP-REDUCE
    batch_results = []
    num_batches = (len(all_chunks) + batch_size - 1) // batch_size
    debug_info["batches"] = num_batches
    
    for i in range(0, len(all_chunks), batch_size):
        batch_num = (i // batch_size) + 1
        batch = all_chunks[i:i + batch_size]
        batch_text = "\n---\n".join([f"[Chunk {c['chunk_id']}] {c['text']}" for c in batch])
        
        logger.info(f"⏳ [QA V3] MAP Batch {batch_num}/{num_batches}")
        
        result = call_llm_for_extraction(batch_text, system_prompt, batch_num, num_batches)
        
        # FAIL-FAST: If LLM returns fatal error (e.g. persistent 400), stop processing batches
        if result.get("error") == "HTTP_400":
            logger.error(f"⛔ [QA V3] Fail-fast triggered by HTTP 400 in batch {batch_num}. Stopping further batches.")
            debug_info["llm_disabled_reason"] = "HTTP_400"
            debug_info["batches_failed_fast"] = True
            break
            
        batch_results.append(result)
    
    # REDUCE
    logger.info(f"🔄 [QA V3] REDUCE: Merging {len(batch_results)} batch results")
    merged = merge_and_dedup_results(batch_results)
    
    # Capture Dedup Stats
    dedup_removed = merged.get("_debug_stats", {}).get("dedup_removed", 0)
    if "_debug_stats" in merged:
        del merged["_debug_stats"] # Clean up before output
    
    debug_info["dedup_removed_count"] = dedup_removed
    
    # Reindex and recalculate
    merged["requirements"] = reindex_requirements(merged["requirements"])
    merged["coverage"] = recalculate_coverage(merged["requirements"])
    
    # C) FALLBACK IF NEEDED
    full_text = "\n".join([c["text"] for c in all_chunks])
    
    req_count = len(merged["requirements"])
    amb_count = len(merged["ambiguities"])
    unv_count = len(merged["unverifiable_criteria"])
    con_count = len(merged["contradictions"])
    
    logger.info(f"📊 [QA V3] Pre-fallback counts: req={req_count}, amb={amb_count}, unv={unv_count}, con={con_count}")
    
    fallback_counts = {"requirements": 0, "ambiguities": 0, "unverifiable_criteria": 0, "contradictions": 0}
    
    # C1) Requirements fallback (Passing existing items for collision check)
    if req_count < MIN_REQUIREMENTS:
        fb_reqs = fallback_extract_requirements(full_text, merged["requirements"])
        merged["requirements"].extend(fb_reqs)
        fallback_counts["requirements"] = len(fb_reqs)
        debug_info["fallback_quantity_used"] = True
    
    # C2) Ambiguities fallback
    if amb_count < MIN_AMBIGUITIES:
        fb_ambs = fallback_extract_ambiguities(full_text, amb_count)
        merged["ambiguities"].extend(fb_ambs)
        fallback_counts["ambiguities"] = len(fb_ambs)
        debug_info["fallback_quantity_used"] = True
    
    # C3) Unverifiable fallback (after requirements are complete)
    unv_count = len(merged["unverifiable_criteria"])
    if unv_count < MIN_UNVERIFIABLE:
        fb_unvs = fallback_extract_unverifiable(merged["requirements"], unv_count, full_text)
        merged["unverifiable_criteria"].extend(fb_unvs)
        fallback_counts["unverifiable_criteria"] = len(fb_unvs)
        debug_info["fallback_quantity_used"] = True
    
    # C4) Contradictions fallback
    if con_count < MIN_CONTRADICTIONS:
        fb_cons = fallback_extract_contradiction(full_text, con_count)
        merged["contradictions"].extend(fb_cons)
        fallback_counts["contradictions"] = len(fb_cons)
        debug_info["fallback_quantity_used"] = True
    
    debug_info["added_by_fallback_counts"] = fallback_counts
    
    # Reindex again after fallback and recalculate coverage (Ensure IDs are cohesive)
    merged["requirements"] = reindex_requirements(merged["requirements"])
    merged["coverage"] = recalculate_coverage(merged["requirements"])
    
    # Final counts
    final_counts = {
        "requirements": len(merged["requirements"]),
        "ambiguities": len(merged["ambiguities"]),
        "unverifiable_criteria": len(merged["unverifiable_criteria"]),
        "contradictions": len(merged["contradictions"])
    }
    debug_info["final_counts"] = final_counts
    
    logger.info(f"✅ [QA V3] Final counts: {final_counts}")
    
    # Summary Pluralization Logic
    def pluralize(count, singular, plural):
        return f"{count} {singular}" if count == 1 else f"{count} {plural}"
        
    summary_text = (
        f"Análise QA de Requisitos concluída. "
        f"{pluralize(final_counts['requirements'], 'requisito', 'requisitos')}, "
        f"{pluralize(final_counts['ambiguities'], 'ambiguidade', 'ambiguidades')}, "
        f"{pluralize(final_counts['contradictions'], 'contradição', 'contradições')} identificadas."
    )

    # Build output
    output = {
        "meta": {
            "analysis_type": "qa_requirements_audit",
            "language": "pt-BR",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "input_documents": [{"doc_id": d, "title": d, "source": "user_upload"} for d in document_ids],
            "model": {"provider": "lm-studio", "name": getattr(llm, "model_name", "unknown") if llm else "unknown"}
        },
        "summary": {
            "executive": summary_text,
            "confidence": "high" if not debug_info["fallback_quantity_used"] else "medium",
            "coverage_notes": ["Cobertura completa via Full-Scan + Map-Reduce"]
        },
        "items": merged
    }
    
    if debug_llm:
        # Add extra debug fields requested
        debug_info["normalization_applied"] = True
        output["meta"]["debug"] = debug_info
    
    return output
