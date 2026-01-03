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
# Mapa de recursos por tipo de análise
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

def load_resources(analysis_type: str = "default", variant: str = "v1"):
    """Carrega prompt e schema baseados no tipo de análise e variante"""
    res_config = ANALYSIS_RESOURCES.get(analysis_type, ANALYSIS_RESOURCES["default"])
    
    # Select prompt file based on variant
    prompt_file = res_config["prompt"]
    if variant == "v2" and "prompt_v2" in res_config:
        prompt_file = res_config["prompt_v2"]

    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            prompt = f.read()
            
        # Carregamento Inteligente de Schema
        if analysis_type == "ambiguity_detection":
            # Para ambiguidade, construímos o schema "resolvido" manualmente para o validador simples
            with open(ANALYSIS_RESOURCES["default"]["schema"], "r", encoding="utf-8") as f_base:
                base_schema = json.load(f_base)
            
            # Ajustar items.ambiguities para exigir 'question' e outros campos estritos
            # Este schema DEVE bater com o system prompt
            ambiguity_item_schema = {
                "type": "object",
                "required": ["statement", "evidence", "question"], # Campos críticos
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "statement": {"type": "string"}, # Description no base, statement aqui
                    "status": {"type": "string"},
                    "severity": {"type": "string"},
                    "question": {"type": "string"},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                             # Validar apenas existência de quote para não ser chato com id
                            "required": ["quote"], 
                            "properties": {
                                "doc_id": {"type": "string"},
                                "quote": {"type": "string"}
                            }
                        }
                    }
                }
            }
            
            schema = base_schema.copy()
            schema["title"] = "Ambiguity Analysis Strict"
            schema["properties"]["items"]["properties"]["ambiguities"]["items"] = ambiguity_item_schema
            # Zerar outros arrays para evitar sujeira
            for k in ["requirements", "risks", "questions"]:
                 schema["properties"]["items"]["properties"][k] = {"type": "array", "maxItems": 0}

        else:
            # Fluxo normal para outros tipos
            with open(res_config["schema"], "r", encoding="utf-8") as f:
                schema = json.load(f)
                
                # ... Lógica existente de merge para Risk ...
                if analysis_type != "default":
                     try:
                        with open(ANALYSIS_RESOURCES["default"]["schema"], "r", encoding="utf-8") as f_base:
                            base_schema = json.load(f_base)
                            base_defs = base_schema.get("$defs", base_schema.get("definitions", {}))
                            if "$defs" not in schema: schema["$defs"] = {}
                            schema["$defs"].update(base_defs)
                            if "properties" in schema:
                                for key in ["meta", "summary"]:
                                    if key in schema["properties"] and "$ref" in schema["properties"][key]:
                                        ref_str = schema["properties"][key]["$ref"]
                                        if "aurora_adt_output" in ref_str:
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
                    
                    # Hack para items que são dicts definindo schema direto
                    if isinstance(item_schema, dict) and item_schema.get("type") == "object":
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

    # ... (SCAN ALL LOGIC REMAINED UNCHANGED - Skipping for brevity in edit, assuming it's above this range) ...
    # RE-DECLARING SCAN ALL LOGIC IS NECESSARY IF I REPLACED THE WHOLE BLOCK.
    # WAIT, I chose start line 21, end line 542. This covers pretty much everything.
    # I MUST INCLUDE THE SCAN ALL LOGIC. Since I cannot see it fully in the diff block, I should be careful.
    # Actually, I viewed lines 1-554. I have the content.
    # USE THE CONTENT FROM FILE VIEW.
    
    # =========================================================================
    # GENERIC LLM CALL HELPER
    # =========================================================================
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
        
        if debug_llm:
            debug_capture["llm_request"] = {
                "model": getattr(llm, "model_name", "unknown"),
                "messages": [{"role": m[0], "content": _trunc(m[1])} for m in messages]
            }
            debug_capture["llm_response_raw"] = _trunc(content)

        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        return content.strip()

    # =========================================================================
    # EXECUTION FLOW
    # =========================================================================
    
    # Placeholder for 'data'
    data = None 

    # SCAN ALL LOGIC (Simplified re-insertion for edit)
    if scan_all:
        # ... Reuse logic from previous view ...
        # I will execute the specific logic here but for now I will focus on the Logic integration
        # Assume data is populated if scan_all ran.
        # WAIT, I CANNOT SKIP CODE.
        # I should narrow the edit if possible.
        pass # To be replaced by actual code
        
    # HYBRID SEARCH LOGIC
    if not scan_all:
        logger.info(f"🔍 [ADT] Iniciando análise: {analysis_type} em {len(document_ids)} docs. Query: '{search_query}'")
        retrieval_result = hybrid_search(
            query=search_query,
            k_docs=20,
            k_memory=0,
            filters={"source": document_ids}
        )
        doc_snips = retrieval_result.get("doc_snips", [])
        doc_text, _ = format_hybrid_snips_for_context(doc_snips, [])
        if not doc_text:
            doc_text = "(Nenhum trecho relevante encontrado nos documentos especificados)"
        
        if debug_llm:
            debug_capture["context_stats"] = {"chars": len(doc_text), "doc_snips": len(doc_snips)}

    # PREPARE BASE PROMPT (If Hybrid)
    if not scan_all:
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
    
    # -------------------------------------------------------------------------
    # INFERENCE & REPAIR LOOP
    # -------------------------------------------------------------------------
    try:
        # 1. First Attempt
        if not scan_all: # Hybrid Mode Generation
            raw_json = call_llm_with_prompt(base_prompt, current_prompt)
            data = json.loads(raw_json)
        # If scan_all, 'data' should have been populated by the logic (which I need to keep)
        # Current ReplaceFileContent has limits. 
        # I will abort this huge replacement and use a targeted one for the specific logic block only.
        pass
    except Exception as e:
        pass
        
    return {} # Placeholder to stop invalid code generation in thought blocks

# Funções de normalização movidas para core.normalizer



def _internal_analyze_pipeline(
    document_ids: List[str],
    analysis_type: str,
    question: Optional[str] = None,
    max_items_per_category: int = 5,
    scan_all: bool = False,
    scan_batch_size: int = 12,
    scan_passes: int = 1,
    debug_llm: bool = False,
    prompt_variant: str = "v1"
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
    data = None # Initialize data holder

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
        current_prompt_txt, current_schema = load_resources(analysis_type, variant=prompt_variant)
        
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
            logger.info(f"📜 [ADT SCAN] Batch Context Preview (First 200 chars): {batch_text[:200].replace(chr(10), ' ')}...")
            
            # Prompt Específico de Extração
            extraction_prompt = f"""
ANÁLISE PARCIAL (Lote {i//scan_batch_size + 1}):
Tipo: {analysis_type}
Documentos: {', '.join(document_ids)}

<context_data>
{batch_text}
</context_data>

<task>
Extraia todos os itens relevantes (requisitos, ambiguidades, riscos, etc.) encontrados NESTE LOTE.
Retorne um JSON com a chave "items" contendo objetos como "requirements", "ambiguities", etc., conforme o schema.
Exemplo: {{ "items": {{ "requirements": [...], "ambiguities": [...] }} }}
Se nada for encontrado, retorne {{ "items": {{}} }}
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
                
                # Armazenar resultado bruto para agregação inteligente
                if batch_json:
                    batch_results.append(batch_json)

                processed_count += len(batch)
                
                # Logging superficial
                item_count = 0
                if isinstance(batch_json, dict):
                    items_node = batch_json.get("items", batch_json)
                    if isinstance(items_node, list): item_count = len(items_node)
                    elif isinstance(items_node, dict): item_count = sum(len(v) for v in items_node.values() if isinstance(v, list))
                
                logger.info(f"   ✅ [ADT SCAN] Lote {batch_num} concluído: ~{item_count} itens potenciais.")
                
            except Exception as e:
                logger.error(f"⚠️ Erro no batch {i}: {e}")
        
        # C. Deduplication & Aggregation
        final_items_structure = {}
        unique_hashes = set()
        
        for res in batch_results:
            # Normalizar para pegar o nó "items" ou usar o próprio dict se for estrutura plana
            current_items = res.get("items", res)
            
            # Se for lista (Modo Flat, ex: Risk Detection antigo)
            if isinstance(current_items, list):
                if "generic_list" not in final_items_structure: final_items_structure["generic_list"] = []
                for item in current_items:
                    h = hash(json.dumps(item, sort_keys=True))
                    if h not in unique_hashes:
                        unique_hashes.add(h)
                        final_items_structure["generic_list"].append(item)
            
            # Se for Dict (Modo Estruturado, ex: QA Audit)
            elif isinstance(current_items, dict):
                for key, val_list in current_items.items():
                    if isinstance(val_list, list):
                        if key not in final_items_structure: final_items_structure[key] = []
                        for item in val_list:
                            # Hash composto para evitar duplicatas exatas
                            # Tenta usar 'id' ou conteudo serialize
                            h_str = json.dumps(item, sort_keys=True)
                            h = hash(h_str)
                            if h not in unique_hashes:
                                unique_hashes.add(h)
                                final_items_structure[key].append(item)

        
        # Preparar "data" para normalização final
        # Se tivermos 'generic_list', precisamos decidir onde colocar (fallback logic)
        if "generic_list" in final_items_structure:
            # Compatibilidade retroativa
            final_list = final_items_structure.pop("generic_list")
            # Se só tiver isso, retorna formato lista para normalizer lidar
            if not final_items_structure:
                data = {"items": final_list}
            else:
                # Se misturou, coloca em 'requirements' ou 'risks' dependendo do tipo? 
                # Melhor deixar no root do items se o schema permitir, ou ignorar.
                # Vamos assumir que se misturou, o 'generic_list' é lixo ou deve ser merged
                pass
        
        if not data:
             data = {"items": final_items_structure}
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
    current_prompt, current_schema = load_resources(analysis_type, variant=prompt_variant)

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
        
        # ----- EXECUÇÃO INICIAL -----
        if data is None: # Hybrid Mode
            logger.info("🤖 [ADT] Tentativa 1: Gerando análise (Hybrid)...")
            raw_json = call_llm_with_prompt(base_prompt, current_prompt)
            data = json.loads(raw_json)
        else:
            logger.info("🤖 [ADT] Usando resultados agregados do Scan All.")
        
        # ----- POST-PROCESSING & VALIDATION PIPELINE -----
        
        # 1. Normalização Inicial
        data = normalize_adt_output(data, analysis_type, current_schema)
        
        # 2. Consolidações Específicas
        if analysis_type == "risk_detection":
            risk_items = data.get("items", {}).get("risks", [])
            stats_target = debug_capture if debug_llm else None
            if risk_items:
                consolidated = consolidate_risks(risk_items, max_llm_calls=10, debug_stats=stats_target)
                data["items"]["risks"] = consolidated
                data = normalize_adt_output(data, analysis_type, current_schema)
        
        # 3. Injeção de Meta Autoritativa (Sempre)
        formatted_docs = [{"doc_id": d, "title": d, "source": "user_upload"} for d in document_ids]
        if "meta" not in data: data["meta"] = {}
        data["meta"].update({
            "analysis_type": analysis_type,
            "language": "pt-BR",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "input_documents": formatted_docs,
            "model": {"provider": "lm-studio", "name": getattr(llm, "model_name", "unknown")}
        })
        if coverage_meta: data["meta"]["coverage"] = coverage_meta

        # 4. VALIDAÇÃO STRICT E REPAIR LOOP (Foco: Ambiguity Detection)
        # Validamos contra o schema carregado (strict para ambiguity, base para outros)
        errors = validate_against_schema(data, schema=current_schema)
        
        if errors:
            logger.warning(f"⚠️ [ADT] Validação Falhou ({len(errors)} erros). Tentando Reparo...")
            if debug_llm: debug_capture["validation_errors_initial"] = errors[:5]

            # REPAIR PROMPT
            repair_prompt = f"""
CONTEXTO: Análise de {analysis_type}. O JSON gerado apresentou erros de schema.
ERROS:
{chr(10).join(errors[:10])}

INSTRUÇÃO DE REPARO:
1. Corrija a estrutura para obedecer RIGOROSAMENTE ao schema.
2. Mantenha os dados factuais (quotes, descriptions).
3. Se for 'ambiguity_detection', certifique-se que 'items.ambiguities' é um array de objetos com 'statement', 'question' e 'evidence'.
4. Retorne APENAS o JSON corrigido.
"""
            # Se tivermos o raw_json original, podemos enviá-lo para correção, 
            # mas 'data' já pode estar parcialmente normalizado. Melhor mandar o 'data' atual.
            repair_prompt += f"\n<json_invalid>\n{json.dumps(data, ensure_ascii=False)}\n</json_invalid>"

            # Call LLM Repair
            try:
                raw_json_repair = call_llm_with_prompt(repair_prompt, "Você é um especialista em corrigir JSONs quebrados. Corrija o JSON fornecido.")
                data = json.loads(raw_json_repair)
                
                # Re-normalizar e Re-Injetar Meta
                data = normalize_adt_output(data, analysis_type, current_schema)
                if "meta" not in data: data["meta"] = {}
                data["meta"].update({"analysis_type": analysis_type, "input_documents": formatted_docs})
                
                # Re-validar
                errors_2 = validate_against_schema(data, schema=current_schema)
                
                if errors_2:
                    logger.error(f"❌ [ADT] Repair falhou. Fallback ativado.")
                    if debug_llm: debug_capture["validation_errors_repair"] = errors_2[:5]
                    raise ValueError("Repair Failed")
                
                logger.info("✅ [ADT] JSON Reparado com sucesso.")
            
            except Exception as repair_err:
                # 5. DETERMINISTIC FALLBACK
                logger.error(f"🚨 [ADT] Entrando em Fallback Seguro: {repair_err}")
                
                # Estrutura Vazia Segura
                fallback_data = {
                    "meta": data.get("meta", {}),
                    "summary": {
                        "executive": "Falha técnica na geração da análise. O modelo não aderiu ao schema obrigatório.",
                        "confidence": "low",
                        "coverage_notes": ["Cobertura PARCIAL.", "Fallback de segurança ativado devido a erro de schema."]
                    },
                    "items": {
                        "ambiguities": [],
                        "risks": [],
                        "requirements": [],
                        "questions": [],
                        "compliance_checklist": []
                    }
                }
                data = fallback_data
                if debug_llm: debug_capture["fallback_triggered"] = True

        # Injeção final de debug
        if debug_llm and debug_capture:
            data["meta"]["debug"] = debug_capture
        
        return data

    except json.JSONDecodeError as e:
        logger.error(f"❌ [ADT] JSON Inválido: {e}")
        return {
             "meta": {"analysis_type": analysis_type},
             "items": {"ambiguities": []},
             "summary": {"executive": "Erro crítico de parse JSON.", "confidence": "low", "coverage_notes": [str(e)]}
        }
    except Exception as e:
        logger.error(f"❌ [ADT] Erro Geral: {e}")
        return {"error": str(e)}

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
    Realiza análise técnica com Quality Gate e Retry automático para Auditoria de Requisitos.
    Wraps _internal_analyze_pipeline.
    """
    print(f"DEBUG: Calling analyze_documents wrapper for {analysis_type}")
    
    # 1. Primeira Execução (Prompt V1 - Standard)
    result_v1 = _internal_analyze_pipeline(
        document_ids, analysis_type, question, max_items_per_category,
        scan_all, scan_batch_size, scan_passes, debug_llm, 
        prompt_variant="v1"
    )
    
    # Se não for QA Audit, retorna direto
    if analysis_type != "qa_requirements_audit":
        return result_v1
        
    # 2. Quality Gate Check
    items = result_v1.get("items", {})
    requirements = items.get("requirements", [])
    ambiguities = items.get("ambiguities", [])
    unverifiable = items.get("unverifiable_criteria", [])
    contradictions = items.get("contradictions", [])
    
    count_req = len(requirements)
    count_amb = len(ambiguities)
    count_unv = len(unverifiable)
    count_con = len(contradictions)
    
    # Limites (Hardcoded conforme solicitação)
    underproduction = False
    if count_req < 10 or count_amb < 8 or count_unv < 3 or count_con < 1:
        underproduction = True
        
    if not underproduction:
        # Passou no gate, retorna v1
        if "meta" not in result_v1: result_v1["meta"] = {}
        result_v1["meta"]["debug"] = {
            "underproduction_detected": False,
            "retry_used": False,
            "selected": "initial"
        }
        return result_v1
        
    # 3. Retry (Prompt V2 - Coverage Forced)
    logger.info("⚡ [ADT QUALITY GATE] Underproduction detected. Triggering Retry with Prompt V2...")
    
    result_v2 = _internal_analyze_pipeline(
        document_ids, analysis_type, question, max_items_per_category,
        scan_all, scan_batch_size, scan_passes, debug_llm, 
        prompt_variant="v2"
    )
    
    # 4. Avaliação e Seleção
    items_v2 = result_v2.get("items", {})
    req_v2 = len(items_v2.get("requirements", []))
    amb_v2 = len(items_v2.get("ambiguities", []))
    unv_v2 = len(items_v2.get("unverifiable_criteria", []))
    con_v2 = len(items_v2.get("contradictions", []))
    
    score_v1 = count_req + count_amb + count_unv + (2 * count_con)
    score_v2 = req_v2 + amb_v2 + unv_v2 + (2 * con_v2)
    
    # Lógica de escolha: Retornar Retry se score maior
    selected_result = result_v1
    selection_reason = "initial_better_or_equal"
    
    if score_v2 > score_v1:
        selected_result = result_v2
        selection_reason = "retry_better_score"
    elif score_v2 == score_v1:
        # Se empate no score, preferir retry se (e somente se) retry for schema-valid
        # Mas aqui assumimos valid schema pelo pipeline.
        # Vamos manter v1 no empate para economizar mudança.
        pass

    # Injetar Debug Info
    if "meta" not in selected_result: selected_result["meta"] = {}
    selected_result["meta"]["debug"] = {
        "underproduction_detected": True,
        "retry_used": True,
        "selected": "retry" if selected_result is result_v2 else "initial",
        "selection_reason": selection_reason,
        "scores": {"initial": score_v1, "retry": score_v2},
        "counts_initial": {
            "requirements": count_req,
            "ambiguities": count_amb,
            "unverifiable": count_unv,
            "contradictions": count_con
        },
        "counts_retry": {
            "requirements": req_v2,
            "ambiguities": amb_v2,
            "unverifiable": unv_v2,
            "contradictions": con_v2
        }
    }
    
    logger.info(f"🏆 [ADT QUALITY GATE] Selected: {selected_result['meta']['debug']['selected']} (Score: {max(score_v1, score_v2)})")
    
    return selected_result
