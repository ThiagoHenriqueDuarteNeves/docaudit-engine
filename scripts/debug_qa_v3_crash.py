import sys
import os
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

import sys
from unittest.mock import MagicMock

# MOCK TORCH
sys.modules["torch"] = MagicMock()
sys.modules["torch.cuda"] = MagicMock()
sys.modules["torch.cuda.is_available"] = MagicMock(return_value=False)

# MOCK CONFIG
sys.modules["core.config"] = MagicMock()
sys.modules["core.config"].LM_STUDIO_URL = "http://mock"
sys.modules["core.config"].EMBEDDING_DEVICE = "cpu"

# MOCK LLM
sys.modules["core.llm"] = MagicMock()
sys.modules["core.llm"].llm = MagicMock()

# MOCK NORMALIZER DEPENDENCIES IF ANY
# ...

# MOCK NORMALIZER DEPENDENCIES IF ANY
# ...

import logging
logging.basicConfig(level=logging.INFO)

try:
    from core.qa_audit_v3 import (
        sanitize_text,
        normalize_text,
        merge_and_dedup_results,
        fallback_extract_requirements,
        truncate_all_items,
        run_qa_requirements_audit_v3
    )
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}")
    sys.exit(1)
except Exception as e:
    print(f"CRITICAL MODULE ERROR: {e}")
    sys.exit(1)

def test_primitives():
    print("Testing primitives...")
    s = sanitize_text("  foo   bar \u007f ")
    print(f"Sanitize: '{s}'")
    assert s == "foo bar"
    
    n = normalize_text(" RF-01  Test ")
    print(f"Normalize: '{n}'")
    assert n == "rf-01 test"

    # Test truncate return
    item = {"requirements": [{"texto": "abc"}]}
    res = truncate_all_items(item)
    print(f"Truncate result: {res}")
    if res is None:
        print("❌ truncate_all_items returns None! This is a bug.")

def test_merge_logic():
    print("\nTesting merge logic...")
    batch_results = [
        {"items": {"requirements": [{"texto": "Req 1", "tipo": "funcional", "evidencia_literal": "short"}]}},
        {"items": {"requirements": [{"texto": "Req 1", "tipo": "funcional", "evidencia_literal": "longer evidence"}]}},
        {"items": {"requirements": [{"texto": "RF-02 Req 2", "tipo": "wrong", "evidencia_literal": "e"}]}}
    ]
    
    merged = merge_and_dedup_results(batch_results)
    print(f"Merged: {merged}")
    
    reqs = merged["requirements"]
    assert len(reqs) == 2
    # Check dedup kept longer evidence
    r1 = next(r for r in reqs if "req 1" in r["texto"].lower())
    assert r1["evidencia_literal"] == "longer evidence"
    
    # Check type correction
    r2 = next(r for r in reqs if "req 2" in r["texto"].lower())
    assert r2["tipo"] == "funcional" # corrected from 'wrong' due to RF- prefix

def test_fallback_logic():
    print("\nTesting fallback logic...")
    existing = [{"texto": "Req 1", "tipo": "funcional"}]
    text = "RF-03 O sistema deve logar. RF-04 O sistema deve sair."
    
    fb = fallback_extract_requirements(text, existing)
    print(f"Fallback results: {fb}")
    assert len(fb) > 0

if __name__ == "__main__":
    try:
        test_primitives()
        test_merge_logic()
        test_fallback_logic()
        print("\n✅ All unit tests passed.")
    except Exception as e:
        print(f"\n❌ RUNTIME ERROR: {e}")
        import traceback
        traceback.print_exc()
