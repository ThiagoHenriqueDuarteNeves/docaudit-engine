
import pytest
import json
import os
from core.adt import analyze_documents, ANALYSIS_RESOURCES
from document_manager import DocumentManager

# Caminho do arquivo de demo (PDF agora)
DEMO_FILE_PATH = "assets/demo/AuditDocEngine_Demo_SRS_QA_Requisitos.pdf"
DEMO_DOC_ID = "AuditDocEngine_Demo_SRS_QA_Requisitos.pdf"

@pytest.fixture(scope="module")
def ingest_demo_doc():
    """Garante que o doc de demo está indexado no Qdrant"""
    import shutil
    
    # 0. Setup paths
    source_path = DEMO_FILE_PATH
    target_path = os.path.join("docs", DEMO_DOC_ID)
    
    # Garantir que docs existe
    os.makedirs("docs", exist_ok=True)
    
    # 1. Copiar arquivo para pasta de scan (docs/)
    if os.path.exists(source_path):
        shutil.copy(source_path, target_path)
    else:
        pytest.skip(f"Arquivo de demo {source_path} não encontrado.")

    dm = DocumentManager()
    
    # 2. Indexar (força reindexação se necessário ou confia no hash)
    # Como é teste, vamos confiar no scan do Manager
    stats = dm.scan_and_index()
    print(f"\n[Fixture] Indexação Stats: {stats}")
    
    import time
    time.sleep(2)
    
    return DEMO_DOC_ID

def test_qa_requirements_audit_pipeline(ingest_demo_doc):
    """
    Teste end-to-end do modo 'qa_requirements_audit'.
    Valida schema, presença de itens e regras de negócio do demo.
    """
    doc_id = ingest_demo_doc
    
    # 1. Executar Análise
    print(f"\n[Test] Iniciando análise para doc: {doc_id}")
    result = analyze_documents(
        document_ids=[doc_id],
        analysis_type="qa_requirements_audit",
        scan_all=True,
        debug_llm=True
    )
    
    # 2. Validações Estruturais Básicas
    assert "error" not in result, f"Erro na análise: {result.get('error')}"
    assert "meta" in result
    assert result["meta"]["analysis_type"] == "qa_requirements_audit"
    assert "items" in result
    
    items = result["items"]
    
    # Valida presença das chaves obrigatórias (Schema Check 'light')
    assert "requirements" in items
    assert "ambiguities" in items
    assert "contradictions" in items
    assert "unverifiable_criteria" in items
    assert "coverage" in items

    # 3. Validações de Conteúdo (Demo Específico)
    
    # Requisitos (esperamos ~13 itens RF+RN+RNF+CA)
    rf_count = len(items["requirements"])
    print(f"\n[Test] Requisitos extraídos: {rf_count}")
    assert rf_count >= 10, f"Esperado >= 10 requisitos, achou {rf_count}"
    
    # Ambiguidades: Esperamos detectar 'amigável', 'intervalo curto', 'muito rápido', 'sempre que possível', 'bonito'
    ambiguities = items["ambiguities"]
    amb_texts = [a["trecho_problematico"].lower() + " " + a.get("evidencia_literal", "").lower() for a in ambiguities]
    print(f"[Test] Ambiguidades: {len(ambiguities)}")
    
    target_ambiguities = ["intervalo curto", "muito rápido", "sempre que possível", "bonito", "amigável"]
    found_targets = 0
    for target in target_ambiguities:
        if any(target in t for t in amb_texts):
            found_targets += 1
            print(f"  -> Achou ambiguidade alvo: '{target}'")
    
    assert found_targets >= 2, f"Esperado encontrar pelo menos 2 ambiguidades alvo, achou {found_targets}"
    assert len(ambiguities) >= 3, "Esperado pelo menos 3 ambiguidades no total"

    # Contradição: 7 dias vs 30 dias
    contradictions = items["contradictions"]
    print(f"[Test] Contradições: {len(contradictions)}")
    has_date_conflict = False
    for c in contradictions:
        text_blob = (c["descricao"] + c["evidencia_a"] + c["evidencia_b"]).lower()
        if "7 dias" in text_blob or "30 dias" in text_blob:
            has_date_conflict = True
    
    assert has_date_conflict, "Não detectou a contradição de prazos (7 vs 30 dias)"
    
    # Critérios Não Verificáveis: "bonito", "amigável", "muito rápido"
    unverifiable = items["unverifiable_criteria"]
    print(f"[Test] Não Verificáveis: {len(unverifiable)}")
    assert len(unverifiable) >= 1, "Deveria ter detectado 'sistema bonito' ou similar como não verificável"

    # 4. Validação de Schema: Evidência Literal Obrigatória
    for cat in ["requirements", "ambiguities", "contradictions", "unverifiable_criteria"]:
        for item in items[cat]:
            assert "evidencia_literal" in item, f"Item em {cat} sem evidencia_literal: {item}"
            assert item["evidencia_literal"] and len(item["evidencia_literal"]) > 2, f"Evidência vazia em {cat}"

    # 5. Coverage Counts
    counts = items["coverage"]["counts"]
    assert counts["funcional"] > 0
    assert counts["nao_funcional"] > 0
    assert counts["regra_negocio"] > 0
    
    print("\n✅ Teste QA Requirements Audit Demo: SUCESSO")
