"""Debug script to test QA audit V3 output."""
import json
import sys
sys.path.insert(0, ".")

from core.adt import analyze_documents

result = analyze_documents(
    document_ids=["AuditDocEngine_Demo_SRS_QA_Requisitos.pdf"],
    analysis_type="qa_requirements_audit",
    scan_all=True,
    debug_llm=True
)

print("=" * 60)
print("RESULT STRUCTURE:")
print("=" * 60)

if "error" in result:
    print(f"ERROR: {result}")
    sys.exit(1)

items = result.get("items", {})
print(f"Requirements: {len(items.get('requirements', []))}")
print(f"Ambiguities: {len(items.get('ambiguities', []))}")
print(f"Contradictions: {len(items.get('contradictions', []))}")
print(f"Unverifiable: {len(items.get('unverifiable_criteria', []))}")

print("\n" + "=" * 60)
print("DEBUG INFO:")
print("=" * 60)
debug = result.get("meta", {}).get("debug", {})
print(json.dumps(debug, indent=2, ensure_ascii=False))

print("\n" + "=" * 60)
print("AMBIGUITIES (first 3):")
print("=" * 60)
for amb in items.get("ambiguities", [])[:3]:
    print(f"  - {amb.get('trecho_problematico', 'N/A')}: {amb.get('evidencia_literal', 'N/A')[:100]}")

print("\n" + "=" * 60)
print("UNVERIFIABLE (all):")
print("=" * 60)
for unv in items.get("unverifiable_criteria", []):
    print(f"  - {unv.get('id_requisito', 'N/A')}: {unv.get('motivo', 'N/A')[:80]}")
    print(f"    Evidence: {unv.get('evidencia_literal', 'N/A')[:100]}")
