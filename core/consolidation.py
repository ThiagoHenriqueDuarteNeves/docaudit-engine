import hashlib
import json
import logging
import re
from typing import List, Dict, Any, Optional

from core.llm import llm
from core.normalizer import normalize_adt_output

logger = logging.getLogger("aurora.consolidation")

VALID_PREFIXES = [
    "[PRAZOS/RECURSOS]", 
    "[ELIMINATÓRIO]", 
    "[DOCUMENTAÇÃO]", 
    "[DISCRICIONARIEDADE]"
]

def _normalize_string(text: str) -> str:
    """Normaliza whitespace e casing para comparação/hash"""
    if not text: return ""
    return re.sub(r'\s+', ' ', text.strip()).lower()

def _get_evidence_hash(evidence: str) -> str:
    norm = _normalize_string(evidence)
    return hashlib.sha1(norm.encode('utf-8')).hexdigest()

def _fallback_consolidation(group: List[Dict]) -> Dict:
    """
    Consolidação determinística (maior impacto, texto mais longo).
    """
    # Ordem de prioridade de impacto
    impact_weight = {"alto": 3, "medio": 2, "baixo": 1, "": 0}
    
    # Ordenar por impacto (desc) e tamanho da descrição (desc)
    sorted_group = sorted(
        group, 
        key=lambda x: (
            impact_weight.get(_normalize_string(x.get("impact", "")), 0),
            len(x.get("description", ""))
        ), 
        reverse=True
    )
    
    selected = sorted_group[0]
    # Garantir que prefixo existe (ou adicionar genérico se solicitado, mas fallback mantém original)
    return selected

import os

# Carregar prompt do arquivo
PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "risk_consolidator_system_v1.txt")
try:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT_TEMPLATE = f.read()
except Exception as e:
    logger.error(f"❌ Falha ao carregar prompt de consolidação: {e}")
    SYSTEM_PROMPT_TEMPLATE = "ERROR_LOADING_PROMPT"

def build_risk_consolidator_user_prompt(evidence: str, group: List[Dict]) -> str:
    """Monta o USER template dinâmico com os candidatos."""
    candidates_formatted = []
    for i, item in enumerate(group, 1):
        candidates_formatted.append(f"""
ITEM #{i}:
- Description: {item.get('description', '')}
- Type: {item.get('risk_type', '')}
- Impact: {item.get('impact', '')}
- Justification: {item.get('justification', '')}
- Mitigation: {item.get('mitigation_question', '')}
""".strip())
    
    candidates_block = "\n\n".join(candidates_formatted)
    
    return f"""
EVIDÊNCIA ÚNICA (use exatamente este texto no campo evidence):
<<<EVIDENCE_TEXT>>>
{evidence}
<<<EVIDENCE_TEXT>>>

CANDIDATOS PARA CONSOLIDAÇÃO:
{candidates_block}

INSTRUÇÃO FINAL:
Gere 1 ÚNICO item final consolidado. Preserve o melhor conteúdo dos candidatos, sem inventar nada além da evidência. Escolha o prefixo mais apropriado da lista permitida.
"""

def _call_llm_consolidation(evidence: str, group: List[Dict]) -> Optional[Dict]:
    """
    Chama LLM para fundir múltiplos riscos em um só.
    """
    if not llm: return None

    prompt = build_risk_consolidator_user_prompt(evidence, group)
    
    try:
        messages = [
            ("system", SYSTEM_PROMPT_TEMPLATE),
            ("user", prompt)
        ]
        resp = llm.invoke(messages)
        content = resp.content.strip()
        
        # Clean markdown
        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        
        return json.loads(content.strip())
    except Exception as e:
        logger.warning(f"⚠️ Falha na consolidação LLM: {e}")
        return None

def consolidate_risks(
    items: List[Dict], 
    max_llm_calls: int = 10,
    debug_stats: Dict = None
) -> List[Dict]:
    """
    Agrupa riscos por evidência idêntica e consolida duplicados.
    """
    if not items: return []
    
    # 1. Agrupar
    groups: Dict[str, List[Dict]] = {}
    
    for item in items:
        # Apenas processa se tiver evidência
        evidence = item.get("evidence", "")
        if not evidence or len(evidence) < 10: 
            key = f"no_evidence_{id(item)}"
        else:
            key = _get_evidence_hash(evidence)
            
        if key not in groups:
            groups[key] = []
        groups[key].append(item)
        
    final_items = []
    
    unique_groups = [g for k, g in groups.items() if not k.startswith("no_evidence")]
    no_evidence_items = [item for k, g in groups.items() if k.startswith("no_evidence") for item in g]
    
    # Stats vars
    total_groups = len(unique_groups)
    consolidated_llm = 0
    fallback_det = 0
    already_unique = 0
    
    # Sample hashes for audit (up to 3)
    sample_hashes = []
    
    calls_made = 0
    
    # 2. Processar Grupos
    for group in unique_groups:
        evidence_txt = group[0].get("evidence")
        group_hash = _get_evidence_hash(evidence_txt)
        
        if len(group) == 1:
            final_items.append(group[0])
            already_unique += 1
            continue
            
        # Add to samples if budget allows
        if len(sample_hashes) < 3:
            sample_hashes.append(group_hash)
            
        # Precisa consolidar
        consolidated = None
        
        # Tentar LLM se tiver budget
        if calls_made < max_llm_calls:
            consolidated = _call_llm_consolidation(evidence_txt, group)
            if consolidated:
                calls_made += 1
                consolidated_llm += 1
        
        # Fallback se LLM falhou ou budget estourou
        if not consolidated:
            consolidated = _fallback_consolidation(group)
            fallback_det += 1
            
        final_items.append(consolidated)
        
    # Adicionar itens sem evidencias (não consolidados)
    final_items.extend(no_evidence_items)
    
    # Atualizar stats se fornecido
    if debug_stats is not None:
        if "consolidation" not in debug_stats: debug_stats["consolidation"] = {}
        debug_stats["consolidation"].update({
            "groups_total": total_groups,
            "groups_single": already_unique,
            "groups_consolidated_by_llm": consolidated_llm,
            "groups_fallback_deterministic": fallback_det,
            "sample_hashes": sample_hashes
        })
        
    logger.info(f"🧩 [Consolidation] {len(items)} -> {len(final_items)} items. (LLM: {consolidated_llm}, Fallback: {fallback_det})")
    
    return final_items
