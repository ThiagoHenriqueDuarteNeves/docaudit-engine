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

# Configurar logger
logger = logging.getLogger("aurora.adt")

# Carregar System Prompt e Schema
ADT_SCHEMA = None
try:
    with open("prompts/aurora_adt_system_prompt.txt", "r", encoding="utf-8") as f:
        ADT_SYSTEM_PROMPT = f.read()
    
    with open("schemas/aurora_adt_output.schema.json", "r", encoding="utf-8") as f:
        ADT_SCHEMA = json.load(f)
except Exception as e:
    print(f"⚠️ Erro ao carregar recursos ADT: {e}")
    ADT_SYSTEM_PROMPT = "Você é um analista técnico. Responda em JSON."

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

def normalize_adt_output(data: any, analysis_type: str, document_ids: List[str]) -> dict:
    """
    Normaliza o output do LLM para garantir conformidade ESTRITA com o schema.
    Trata casos onde LLM retorna lista na raiz.
    """
    # 0. Root Repair (List -> Dict)
    if isinstance(data, list):
        if len(data) == 1 and isinstance(data[0], dict):
            # Caso: wrapped in list [{"..."}]
            data = data[0]
        else:
            # Caso: raw items list
            data = {"items": data}

    # Se ainda não for dict (ex: string solta ou primitive), forçar dict vazio
    if not isinstance(data, dict):
        data = {}

    # 1. Meta (Strict Schema Compliance)
    # input_documents deve ser lista de objetos, não strings
    formatted_docs = [{"doc_id": d, "title": d, "source": "user_upload"} for d in document_ids]
    
    data["meta"] = {
        "analysis_type": analysis_type,
        "language": "pt-BR",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "input_documents": formatted_docs,
        "model": {
            "provider": "lm-studio",
            "name": "hybrid-llm-local",
            "temperature": 0.0
        }
    }

    # 2. Summary (Strict Keys: executive, confidence, coverage_notes)
    if "summary" not in data or not isinstance(data["summary"], dict):
        # Se for string ou ausente, criar do zero
        original_text = data.get("summary", "Resumo não gerado.") if isinstance(data.get("summary"), str) else "Resumo não gerado."
        data["summary"] = {
            "executive": original_text[:1500], # Limite do schema
            "confidence": "medium",
            "coverage_notes": ["Gerado automaticamente via fallback."]
        }
    else:
        # Normalizar chaves existentes
        summ = data["summary"]
        # Mapear chaves erradas comuns
        if "high_level" in summ and "executive" not in summ:
            summ["executive"] = summ.pop("high_level")
        
        # Garantir obrigatórios
        if "executive" not in summ:
            summ["executive"] = "Resumo indisponível."
        if "confidence" not in summ:
            summ["confidence"] = "medium"
        
        # Garantir coverage_notes como array
        if "coverage_notes" not in summ:
            summ["coverage_notes"] = []
        elif isinstance(summ["coverage_notes"], str):
            summ["coverage_notes"] = [summ["coverage_notes"]]

    # 3. Items Topology
    target_keys = ["ambiguities", "requirements", "risks", "compliance_checklist", "questions"]
    
    # Garantir que items é dict
    if "items" not in data or not isinstance(data["items"], dict):
        # Se items for lista, tentar salvar
        items_content = data.get("items", []) if isinstance(data.get("items"), list) else []
        data["items"] = {}
        
        # Tentar inferir onde colocar a lista baseada no tipo de análise
        inferred_key = "general_issues" # Fallback
        if "ambiguity" in analysis_type: inferred_key = "ambiguities"
        elif "risk" in analysis_type: inferred_key = "risks"
        elif "requirement" in analysis_type: inferred_key = "requirements"
        
        if items_content:
            data["items"][inferred_key] = items_content

    # Mover chaves soltas da raiz para items
    for key in target_keys:
        if key in data:
            data["items"][key] = data.pop(key)
    
    # Garantir chaves obrigatórias vazias em items se não existirem
    # (O schema exige que as chaves existam, mesmo vazias)
    for key in target_keys:
        if key not in data["items"]:
            data["items"][key] = []
            
    return data


def analyze_documents(
    document_ids: List[str],
    analysis_type: str,
    question: Optional[str] = None,
    max_items_per_category: int = 5
) -> dict:
    """
    Realiza análise técnica em documentos específicos com validação e repair.
    """
    
    # 1. Definir Query de Busca
    search_query = question if question else f"Realizar análise de {analysis_type} nestes documentos."
    
    logger.info(f"🔍 [ADT] Iniciando análise: {analysis_type} em {len(document_ids)} docs. Query: '{search_query}'")
    
    # 2. Retrieval Focado
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

    # 3. Montar Prompt Base
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
    
    if llm is None:
        return {"error": "LLM não inicializado"}

    def call_llm(prompt_text):
        messages = [
            ("system", ADT_SYSTEM_PROMPT),
            ("user", prompt_text)
        ]
        resp = llm.invoke(messages)
        content = resp.content.strip()
        
        print(f"🤖 [ADT] RAW LLM RESPONSE:\n{content}\n-----------------------------------")

        # Limpar markdown block
        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        return content.strip()

    # 4. Primeira Tentativa
    try:
        logger.info("🤖 [ADT] Tentativa 1: Gerando análise...")
        raw_json = call_llm(base_prompt)
        data = json.loads(raw_json)
        
        # NORMALIZAÇÃO (Envelope Builder)
        data = normalize_adt_output(data, analysis_type, document_ids)
        
        # Validar
        errors = validate_against_schema(data)
        
        if errors:
            logger.warning(f"⚠️ [ADT] Falha na validação do schema (Tentativa 1): {len(errors)} erros.")
            # 5. Tentativa de Reparo (Repair Loop)
            logger.info("🔧 [ADT] Iniciando Repair Loop...")
            
            repair_prompt = f"""
{base_prompt}

<repair_instruction>
O JSON gerado anteriormente estava inválido.
ERROS ENCONTRADOS:
{chr(10).join(errors[:10])}

CORRIJA o JSON para ficar compatível.
NÃO altere o conteúdo factual ou texto.
APENAS ajuste a estrutura para corrigir os erros acima.
</repair_instruction>
"""
            raw_json_2 = call_llm(repair_prompt)
            data = json.loads(raw_json_2)
            
            # NORMALIZAÇÃO (Repair)
            data = normalize_adt_output(data, analysis_type, document_ids)
            
            # Revalidar
            errors_2 = validate_against_schema(data)
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
