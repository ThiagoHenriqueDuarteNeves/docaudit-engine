"""
Aurora ADT (Analista de Documentos Técnicos)
Módulo core para análise técnica de documentos usando LLM e Retrieval.
"""
import json
import logging
from typing import List, Optional
from datetime import datetime

from core.llm import llm
from core.hybrid_adapter import hybrid_search, format_hybrid_snips_for_context
from core.normalizer import normalize_adt_output
from core.consolidation import consolidate_risks

# Configurar logger
logger = logging.getLogger("aurora.adt")

from qdrant_client.models import Filter, FieldCondition, MatchValue

# Mapa de recursos por tipo de análise
ANALYSIS_RESOURCES = {
    "default": {
        "prompt": "prompts/aurora_adt_system_prompt.txt",
        "schema": "schemas/aurora_adt_output.schema.json"
    },
    "risk_detection": {
        "prompt": "prompts/risk_detection.txt",
        "schema": "schemas/risk_detection.schema.json"
    }
}

def load_resources(analysis_type: str = "default"):
    """Carrega prompt e schema baseados no tipo de análise"""
    res_config = ANALYSIS_RESOURCES.get(analysis_type, ANALYSIS_RESOURCES["default"])
    
    try:
        with open(res_config["prompt"], "r", encoding="utf-8") as f:
            prompt = f.read()
            
        with open(res_config["schema"], "r", encoding="utf-8") as f:
            schema = json.load(f)
            
            # Resolver herança simplificada (Risk Detection herda de Base)
            if analysis_type != "default":
                try:
                    with open(ANALYSIS_RESOURCES["default"]["schema"], "r", encoding="utf-8") as f_base:
                        base_schema = json.load(f_base)
                        
                        # 1. Copiar Definitions ($defs ou definitions)
                        base_defs = base_schema.get("$defs", base_schema.get("definitions", {}))
                        if "$defs" not in schema: schema["$defs"] = {}
                        schema["$defs"].update(base_defs)
                        
                        # 2. Resolver External Refs em 'properties' (Copiar estrutura Meta e Summary)
                        # O schema de risco usa "$ref": "aurora_adt_output.schema.json#/properties/meta"
                        # Vamos substituir esses refs remotos pela definição local do base_schema
                        if "properties" in schema:
                            for key in ["meta", "summary"]:
                                if key in schema["properties"] and "$ref" in schema["properties"][key]:
                                    ref_str = schema["properties"][key]["$ref"]
                                    if "aurora_adt_output" in ref_str:
                                        # Injetar a definição real do Base Schema
                                        schema["properties"][key] = base_schema["properties"][key]
                except Exception as merge_err:
                     logger.warning(f"⚠️ Erro ao mesclar schemas: {merge_err}")

        return prompt, schema
    except Exception as e:
        logger.error(f"⚠️ Erro ao carregar recursos para {analysis_type}: {e}")
        return "Responda em JSON.", {}

# Carregar Default inicialmente (para retrocompatibilidade)
ADT_SYSTEM_PROMPT, ADT_SCHEMA = load_resources("default")

def validate_against_schema(data: dict, schema: dict = None, path: str = "") -> List[str]:
    """
    Validação simplificada recursiva contra o schema JSON.
    Verifica campos obrigatórios e tipos básicos.
    """
    errors = []
    if schema is None:
        schema = ADT_SCHEMA
        if not schema:
            return ["Schema não carregado"]

    # 1. Verificar Required
    if "required" in schema:
        for req in schema["required"]:
            if req not in data:
                errors.append(f"Campo obrigatório ausente: {path + '.' + req if path else req}")
    
    # 2. Verificar Properties (Recursão)
    if "properties" in schema:
        for prop, prop_schema in schema["properties"].items():
            if prop in data:
                # Type check simples
                val = data[prop]
                expected_type = prop_schema.get("type")
                
                # Mapeamento tipos JSON -> Python
                type_map = {
                    "string": str,
                    "number": (int, float),
                    "integer": int, 
                    "boolean": bool,
                    "array": list,
                    "object": dict
                }
                
                if expected_type in type_map:
                     if not isinstance(val, type_map[expected_type]):
                         # Permitir float onde pede integer se for .0
                         if expected_type == "integer" and isinstance(val, float) and val.is_integer():
                             pass
                         else:
                            errors.append(f"Tipo incorreto em '{path}.{prop}': esperava {expected_type}, recebeu {type(val).__name__}")
                
                # Recursão Object
                if expected_type == "object" and isinstance(val, dict):
                    errors.extend(validate_against_schema(val, prop_schema, path=f"{path}.{prop}"))
                
                # Recursão Array (validar itens)
                if expected_type == "array" and isinstance(val, list) and "items" in prop_schema:
                    item_schema = prop_schema["items"]
                    # Se items for $ref, ignorar validação profunda no MVP (complexidade alta sem lib)
                    # Mas se for objeto direto, validar
                    if "type" in item_schema and item_schema["type"] == "object":
                        for i, item in enumerate(val):
                            if isinstance(item, dict):
                                errors.extend(validate_against_schema(item, item_schema, path=f"{path}.{prop}[{i}]"))

    return errors

# Funções de normalização movidas para core.normalizer



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
    """
    Realiza análise técnica em documentos específicos com validação e repair.
    """
    
    # 1. Preparação (Comum)
    search_query = question if question else f"Realizar análise de {analysis_type} nestes documentos."
    
    # Context Data Holder
    doc_text = ""
    coverage_meta = None
    debug_capture = {} # Armazena info de debug

    def _trunc(text: str, limit: int = 5000) -> str:
        if len(text) <= limit: return text
        return text[:limit] + f"... [Truncated {len(text)-limit} chars]"

    # =========================================================================
    # MODE: SCAN ALL (100% Chunks)
    # =========================================================================
    if scan_all:
        logger.info(f"🚀 [ADT] Modo SCAN ALL ativado para {len(document_ids)} documentos.")
        
        from core.documents import get_doc_manager
        dm = get_doc_manager()
        client = dm.vector_db.client
        collection_name = dm.vector_db.collection_name
        
        all_chunks = []
        
        # A. Fetch All Chunks do Qdrant
        for doc_id in document_ids:
            try:
                # Scroll para pegar tudo
                offset = None
                while True:
                    # Filtro robusto (doc_id ou source)
                    q_filter = Filter(
                        should=[
                            FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
                            FieldCondition(key="source", match=MatchValue(value=doc_id))
                        ]
                    )
                    
                    records, offset = client.scroll(
                        collection_name=collection_name,
                        scroll_filter=q_filter,
                        limit=100,
                        with_payload=True,
                        with_vectors=False,
                        offset=offset
                    )
                    
                    for r in records:
                        if r.payload and "text" in r.payload:
                            all_chunks.append({
                                "text": r.payload["text"],
                                "chunk_id": r.payload.get("chunk_id", 0),
                                "doc_id": doc_id,
                                "source_id": f"{doc_id}#chunk{r.payload.get('chunk_id')}" 
                            })
                    
                    if offset is None:
                        break
            except Exception as e:
                logger.error(f"❌ Erro ao buscar chunks para {doc_id}: {e}")
        
        # Validar conteúdo
        total_chunks = len(all_chunks)
        if total_chunks == 0:
            return {
                "error": "DOCUMENT_NOT_INDEXED_IN_QDRANT",
                "message": f"Nenhum chunk encontrado para: {', '.join(document_ids)}",
                "details": ["Certifique-se que o documento foi indexado corretamente."]
            }
            
        # Ordenar chunks para leitura linear (importante para contexto)
        all_chunks.sort(key=lambda x: (x['doc_id'], x['chunk_id']))
        
        logger.info(f"📦 [ADT] Scan Load: {total_chunks} chunks carregados.")
        
        # B. Batch Processing Loop
        aggregated_items = {}
        processed_count = 0
        
        # Helper para chamar LLM no loop 
        # (Definido apenas o necessário para não duplicar lógica)
        current_prompt_txt, current_schema = load_resources(analysis_type)
        
        # System Prompt Base
        base_sys_prompt = f"{ADT_SYSTEM_PROMPT}\n\nMODO EXTRATOR: Analise os fragmentos abaixo e extraia itens de {analysis_type}."

        batch_results = []
        
        num_batches = (total_chunks + scan_batch_size - 1) // scan_batch_size
        
        for i in range(0, total_chunks, scan_batch_size):
            batch_num = (i // scan_batch_size) + 1
            progress_pct = int((batch_num / num_batches) * 100)
            
            logger.info(f"⏳ [ADT SCAN] Processando Lote {batch_num}/{num_batches} ({progress_pct}%) - Chunks {i} a {min(i+scan_batch_size, total_chunks)}...")
            
            batch = all_chunks[i : i + scan_batch_size]
            batch_text = "\n---\n".join([f"[Chunk {c['chunk_id']}] {c['text']}" for c in batch])
            
            # Prompt Específico de Extração
            extraction_prompt = f"""
ANÁLISE PARCIAL (Lote {i//scan_batch_size + 1}):
Tipo: {analysis_type}
Documentos: {', '.join(document_ids)}

<context_data>
{batch_text}
</context_data>

<task>
Identifique APENAS itens do tipo '{analysis_type}' presentes NESTE LOTE.
Retorne JSON: {{ "items": [...] }}
Se nada for encontrado, retorne {{ "items": [] }}
</task>
"""
            try:
                # Invoke LLM
                messages = [("system", base_sys_prompt), ("user", extraction_prompt)]
                raw_resp = llm.invoke(messages)
                content = raw_resp.content.strip()
                
                # Debug Capture (Last Batch)
                if debug_llm:
                    debug_capture["llm_request"] = {
                        "model": getattr(llm, "model_name", "unknown"),
                        "messages": [
                            {"role": m[0], "content": _trunc(m[1])} for m in messages
                        ]
                    }
                    debug_capture["llm_response_raw"] = _trunc(content)
                
                # Clean markdown
                if content.startswith("```json"): content = content[7:]
                if content.startswith("```"): content = content[3:]
                if content.endswith("```"): content = content[:-3]
                
                # Parse
                batch_json = json.loads(content.strip())
                
                # Extrair items (suporta lista direta ou dict)
                items_list = []
                if isinstance(batch_json, list): 
                    items_list = batch_json
                elif isinstance(batch_json, dict):
                    # Tenta pegar chaves conhecidas
                    for k in ["risks", "ambiguities", "requirements", "items"]:
                        if k in batch_json and isinstance(batch_json[k], list):
                            items_list.extend(batch_json[k])
                
                batch_results.extend(items_list)
                processed_count += len(batch)
                logger.info(f"   ✅ [ADT SCAN] Lote {batch_num} concluído: {len(items_list)} itens extraídos.")
                
            except Exception as e:
                logger.error(f"⚠️ Erro no batch {i}: {e}")
        
        # C. Deduplication & Aggregation
        unique_hashes = set()
        final_list = []
        
        for item in batch_results:
            # Hash simplificado (desc + evidence)
            desc = item.get("description") or item.get("statement") or item.get("question") or ""
            evidence = item.get("evidence") or ""
            h = hash(f"{desc.strip()}|{evidence.strip()}")
            
            if h not in unique_hashes:
                unique_hashes.add(h)
                final_list.append(item)
        
        # Preparar "data" para normalização final
        # Vamos injetar isso na estrutura padrão
        data = {"items": final_list} # Normalizador vai consertar a chave correta
        doc_text = "(Scan All Mode - Full Content Processed)" # Placeholder para prompt de repair se necessário
        
        coverage_meta = {
            "analysis_mode": "scan_all",
            "total_chunks": total_chunks,
            "processed_chunks": processed_count,
            "batches": (total_chunks + scan_batch_size - 1) // scan_batch_size,
        }
        
        if debug_llm:
             debug_capture["context_stats"] = coverage_meta

    # =========================================================================
    # MODE: HYBRID SEARCH (Analytic Retrieval)
    # =========================================================================
    else:
        logger.info(f"🔍 [ADT] Iniciando análise: {analysis_type} em {len(document_ids)} docs. Query: '{search_query}'")
        
        retrieval_result = hybrid_search(
            query=search_query,
            k_docs=20,     # Buscar bastante contexto
            k_memory=0,    # Priorizar docs
            filters={"source": document_ids}
        )
        
        doc_snips = retrieval_result.get("doc_snips", [])
        doc_text, _ = format_hybrid_snips_for_context(doc_snips, [])
        
        if not doc_text:
            doc_text = "(Nenhum trecho relevante encontrado nos documentos especificados)"
            logger.warning(f"⚠️ [ADT] Nenhum documento encontrado para IDs: {document_ids}")
        
        # Placeholder vazio para fluxo normal
        data = None 
        
        if debug_llm:
            debug_capture["context_stats"] = {
                "chars": len(doc_text),
                "doc_snips": len(doc_snips)
            }

    # 3. Montar Prompt Base (Usado apenas se data ainda for None, ou seja, Hybrid Mode)
    # No modo Scan All, já temos 'data', mas precisamos passar pelo fluxo de normalização/validação
    
    if data is None: # Hybrid Mode Flow
        base_prompt = f"""
<context_data>
{doc_text}
</context_data>

<analysis_request>
META: {analysis_type}
PERGUNTA ESPECÍFICA: {question if question else 'N/A (Análise Geral)'}
DOCUMENTOS ALVO: {', '.join(document_ids)}
</analysis_request>

<output_instruction>
Gere a saída estritamente em JSON seguindo o schema.
Não inclua markdown ```json no início ou fim. Apenas o raw JSON.
</output_instruction>
"""
    else:
        # Scan All Flow skip generation step
        base_prompt = "SKIPPED_IN_SCAN_ALL"

    
    if llm is None:
        return {"error": "LLM não inicializado"}

    # Carregar recursos específicos da análise
    current_prompt, current_schema = load_resources(analysis_type)

    def call_llm_with_prompt(user_prompt_text, sys_prompt):
        messages = [
            ("system", sys_prompt),
            ("user", user_prompt_text)
        ]
        resp = llm.invoke(messages)
        content = resp.content.strip()
        print(f"🤖 [ADT] RAW LLM RESPONSE:\n{content}\n-----------------------------------")
        
        if debug_llm:
            debug_capture["llm_request"] = {
                "model": getattr(llm, "model_name", "unknown"),
                "messages": [
                    {"role": m[0], "content": _trunc(m[1])} for m in messages
                ]
            }
            debug_capture["llm_response_raw"] = _trunc(content)

        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        return content.strip()

    # 4. Primeira Tentativa (Gerar ou Usar Scan Result)
    try:
        if data is None:
            logger.info("🤖 [ADT] Tentativa 1: Gerando análise (Hybrid)...")
            raw_json = call_llm_with_prompt(base_prompt, current_prompt)
            data = json.loads(raw_json)
        else:
             logger.info("🤖 [ADT] Usando resultados agregados do Scan All.")
        
        # NORMALIZAÇÃO (Strict Schema)
        # 1. Normalizar estrutura/tipos via novo normalizer
        data = normalize_adt_output(data, analysis_type, current_schema)
        
        # 1.5 CONSOLIDAÇÃO DE RISCOS (Se aplicável)
        if analysis_type == "risk_detection":
            risk_items = data.get("items", {}).get("risks", [])
            # Se debug_llm, passar o dicionário de captura para popular stats
            stats_target = debug_capture if debug_llm else None
            
            if risk_items:
                consolidated = consolidate_risks(risk_items, max_llm_calls=10, debug_stats=stats_target)
                data["items"]["risks"] = consolidated
                
                # Re-normalizar para garantir schema nos novos itens gerados pelo LLM de consolidação
                data = normalize_adt_output(data, analysis_type, current_schema)
        
        # 2. Injeção de Metadados Autoritativos (Sobrescreve o que o LLM mandou/default)
        formatted_docs = [{"doc_id": d, "title": d, "source": "user_upload"} for d in document_ids]
        
        # Garantir que meta existe (o normalizer deve ter criado, mas por segurança)
        if "meta" not in data: data["meta"] = {}
        
        data["meta"].update({
            "analysis_type": analysis_type,
            "language": "pt-BR",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "input_documents": formatted_docs,
            "model": {
                "provider": "lm-studio",
                "name": "hybrid-llm-local",
                "temperature": 0.0
            }
        })
        
        # Injetar Metadata de Coverage (Scan All)
        if coverage_meta:
            data["meta"]["coverage"] = coverage_meta
            # Adicionar notas no summary também para visibilidade
            if "summary" in data and "coverage_notes" in data["summary"]:
                data["summary"]["coverage_notes"].append(
                    f"MODO SCAN ALL: Processados {coverage_meta['processed_chunks']}/{coverage_meta['total_chunks']} chunks."
                )

        # Validar
        errors = validate_against_schema(data, schema=current_schema)
        
        # Injetar debug se solicitado (bypass schema check)
        if debug_llm and debug_capture:
            if "meta" not in data: data["meta"] = {}
            data["meta"]["debug"] = debug_capture
        
        if errors:
            logger.warning(f"⚠️ [ADT] Falha na validação do schema (Tentativa 1): {len(errors)} erros.")
            # 5. Tentativa de Reparo (Repair Loop)
            # Se for Scan All, o 'base_prompt' original não tem o contexto todo.
            # Precisamos sintatizar um prompt de reparo inteligente.
            
            logger.info("🔧 [ADT] Iniciando Repair Loop...")
            
            if scan_all:
                repair_context_msg = "CONTEXTO: Os dados foram extraídos via Scan All (lotes). A estrutura JSON resultante está inválida."
            else:
                repair_context_msg = base_prompt

            repair_prompt = f"""
{repair_context_msg}

<repair_instruction>
O JSON gerado anteriormente estava inválido.
ERROS ENCONTRADOS:
{chr(10).join(errors[:10])}

CORRIJA o JSON para ficar compatível.
NÃO altere o conteúdo factual ou texto.
APENAS ajuste a estrutura para corrigir os erros acima.
Se o objeto raiz for uma lista, envolva-o em {{ "items": {{ "risks": [...] }} }} (ou a chave adequada).
</repair_instruction>
<json_to_fix>
{json.dumps(data)}
</json_to_fix>
"""
            # Se o JSON for MUITO grande (Scan All), isso pode estourar o contexto do LLM.
            # MVP: Tentar reparar. Se falhar, falhar.
            
            raw_json_2 = call_llm_with_prompt(repair_prompt, current_prompt)
            data = json.loads(raw_json_2)
            
            # NORMALIZAÇÃO (Repair)
            data = normalize_adt_output(data, analysis_type, current_schema)
            
            # Re-injetar meta se perdido (Repair pode ter resetado)
            if "meta" not in data: data["meta"] = {}
            data["meta"].update({
                "analysis_type": analysis_type,
                "input_documents": formatted_docs
            })
            if coverage_meta: 
                data["meta"]["coverage"] = coverage_meta
            
            # Revalidar
            errors_2 = validate_against_schema(data, schema=current_schema)
            if errors_2:
                logger.error(f"❌ [ADT] Falha no Repair Loop: {len(errors_2)} erros ainda presentes.")
                return {
                    "error": "INVALID_ADT_JSON",
                    "message": "O modelo falhou em gerar um JSON válido após tentativa de correção.",
                    "details": errors_2[:10]
                }
            else:
                logger.info("✅ [ADT] Repair Loop com sucesso!")
        
        return data

    except json.JSONDecodeError as e:
        logger.error(f"❌ [ADT] Erro Grave de Parse JSON: {e}")
        return {
            "error": "INVALID_ADT_JSON",
            "message": "Falha crítica no parse do JSON retornado.",
            "details": [str(e)]
        }
    except Exception as e:
        logger.error(f"❌ [ADT] Erro geral: {e}")
        return {"error": str(e)}
