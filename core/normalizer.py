import json
import logging
import re
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("aurora.normalizer")

class SchemaNormalizer:
    """
    Normalizador estrito baseado em schema JSON.
    Reconstroi o objeto apenas com campos permitidos, injeta defaults e corrige tipos.
    """
    def __init__(self, schema: Dict[str, Any]):
        self.root_schema = schema
        self.definitions = schema.get("$defs", schema.get("definitions", {}))

    def normalize(self, data: Any) -> Any:
        return self._normalize_node(data, self.root_schema)

    def _resolve_ref(self, ref: str) -> Dict[str, Any]:
        """Resolves internal $ref (e.g. #/$defs/itemArray)"""
        if not ref.startswith("#/"):
            # External refs not supported without loader overlap, assume handled or loose
            # For this strict normalizer, we rely on definitions being present
            return {}
        
        parts = ref.split("/")
        # root is parts[0] (#)
        current = self.root_schema
        for part in parts[1:]:
            if part in current:
                current = current[part]
            else:
                return {}
        return current

    def _get_default(self, schema_node: Dict[str, Any]) -> Any:
        if "default" in schema_node:
            return schema_node["default"]
        
        t = schema_node.get("type")
        if t == "string": return ""
        if t == "number": return 0.0
        if t == "integer": return 0
        if t == "boolean": return False
        if t == "array": return []
        if t == "object": return {}
        return None

    def _normalize_node(self, data: Any, schema_node: Dict[str, Any]) -> Any:
        # 1. Resolve Ref
        if "$ref" in schema_node:
            resolved = self._resolve_ref(schema_node["$ref"])
            if resolved:
                return self._normalize_node(data, resolved)
            # If resolve fails (external file?), fallback to loose behavior or skip
            return data

        # 2. Type Check & Coercion
        expected_type = schema_node.get("type")
        
        if expected_type == "object":
            if not isinstance(data, dict):
                data = {}
            
            # Reconstruct object (Whitelist)
            normalized_obj = {}
            properties = schema_node.get("properties", {})
            required = schema_node.get("required", [])

            # Process all properties defined in schema
            for key, prop_schema in properties.items():
                if key in data:
                    normalized_obj[key] = self._normalize_node(data[key], prop_schema)
                elif key in required:
                    # Missing required: inject default
                    default_val = self._get_default(prop_schema)
                    # Handle enum default (first item)
                    if default_val is None and "enum" in prop_schema and prop_schema["enum"]:
                        default_val = prop_schema["enum"][0]
                    
                    # Special case: inner object required but missing
                    if prop_schema.get("type") == "object" and default_val == {}:
                         default_val = self._normalize_node({}, prop_schema)
                         
                    normalized_obj[key] = default_val
                # else: optional and missing -> ignore (drop)

            # Note: additionalProperties: false is implicit by iteration over properties only
            return normalized_obj

        elif expected_type == "array":
            if not isinstance(data, list):
                # Try validation: single item to list?
                if data:
                    data = [data]
                else:
                    return []
            
            item_schema = schema_node.get("items", {})
            if not item_schema:
                return data # Weak array schema
                
            normalized_list = []
            for item in data:
                normalized_list.append(self._normalize_node(item, item_schema))
            return normalized_list

        elif expected_type == "string":
            if not isinstance(data, str):
                data = str(data) if data is not None else ""
            
            # Enum Enforcement
            if "enum" in schema_node:
                if data not in schema_node["enum"]:
                    # Fallback strategies
                    # 1. Case insensitive match
                    for valid in schema_node["enum"]:
                        if valid.lower() == data.lower():
                            return valid
                    # 2. Default or First enum
                    return schema_node.get("default", schema_node["enum"][0])
            
            # MaxLength constraint (truncation)
            if "maxLength" in schema_node and len(data) > schema_node["maxLength"]:
                data = data[:schema_node["maxLength"]]
                
            return data

        elif expected_type == "integer":
            try:
                val = int(data)
                return val
            except (ValueError, TypeError):
                return self._get_default(schema_node)

        elif expected_type == "number":
            try:
                val = float(data)
                return val
            except (ValueError, TypeError):
                return self._get_default(schema_node)

        elif expected_type == "boolean":
            if isinstance(data, bool): return data
            if isinstance(data, str): return data.lower() == "true"
            return bool(data)

        # Fallback for unknown types (any)
        return data


def normalize_adt_output(raw_resp: Union[str, Dict, List], analysis_type: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entrypoint for normalization.
    Pre-processes output (markdown stripping) and then applies Strict Schema Normalization.
    """
    # 1. Parse & Clean Markdown
    data = {}
    if isinstance(raw_resp, str):
        cleaned = raw_resp.strip()
        # Code fence stripping
        match = re.search(r"```(?:json)?(.*?)```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
        
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Normalizer received invalid JSON string. Returning empty default structure.")
            data = {}
    else:
        data = raw_resp

    # 2. Structural Fixes (List -> Dict)
    if isinstance(data, list):
        if analysis_type == "risk_detection":
            data = {"items": {"risks": data}}
        else:
             # Heuristic mapping for base types
             data = {"items": {"requirements": data}} # Default fallback?
             
    if not isinstance(data, dict):
        data = {}

    # 3. Schema Normalization
    normalizer = SchemaNormalizer(schema)
    normalized_data = normalizer.normalize(data)
    
    return normalized_data

def sanitize_llm_json_output(raw_text: str) -> str:
    """
    Sanitiza a saída do LLM para garantir que apenas o JSON seja parseado.
    1. Remove markdown fences.
    2. Encontra o primeiro '{' e extrai até o '}' balanceado correspondente.
    """
    if not raw_text:
        return ""
        
    text = raw_text.strip()
    
    # 1. Remover Markdown fences
    import re
    fence_pattern = r"```(?:json)?\s*(.*?)\s*```"
    match = re.search(fence_pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
    
    # 2. Extração por Brace Matching
    start_idx = text.find("{")
    if start_idx == -1:
        # Se não achar '{', checa se é array '['
        start_idx_list = text.find("[")
        if start_idx_list != -1:
             start_idx = start_idx_list
             open_char = "["
             close_char = "]"
        else:
             return text 
    else:
        # Se achou '{' checa prioridade com '['
        start_idx_list = text.find("[")
        if start_idx_list != -1 and start_idx_list < start_idx:
             start_idx = start_idx_list
             open_char = "["
             close_char = "]"
        else:
             open_char = "{"
             close_char = "}"

    # Brace Matching Loop
    balance = 0
    end_idx = -1
    in_string = False
    escape = False
    
    for i in range(start_idx, len(text)):
        char = text[i]
        
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == open_char:
                balance += 1
            elif char == close_char:
                balance -= 1
                if balance == 0:
                    end_idx = i + 1
                    break
    
    if end_idx != -1:
        return text[start_idx:end_idx]
    
    return text[start_idx:]
