import requests
import json
import sys

BASE_URL = "http://localhost:8002"

def get_first_document():
    try:
        resp = requests.get(f"{BASE_URL}/api/documents")
        if resp.status_code == 200:
            docs = resp.json()
            if docs:
                return docs[0]["filename"]
    except Exception as e:
        print(f"Erro ao buscar documentos: {e}")
    return None

def test_risk_detection():
    print("🚀 Iniciando Teste de Risk Detection...")
    
    doc_id = get_first_document()
    if not doc_id:
        print("❌ Nenhum documento encontrado para teste. Indexe um PDF primeiro.")
        sys.exit(1)
        
    print(f"📄 Documento alvo: {doc_id}")
    
    payload = {
        "document_ids": [doc_id],
        "analysis_type": "risk_detection",
        "question": "Identifique riscos de eliminação, contestação administrativa ou judicial presentes no documento.",
        "max_items_per_category": 3
    }
    
    try:
        print("⏳ Enviando request (pode demorar)...")
        resp = requests.post(f"{BASE_URL}/api/analyze", json=payload, timeout=120)
        
        print(f"Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            # print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Validações Básicas
            assert "meta" in data, "Meta missing"
            assert "summary" in data, "Summary missing"
            assert "items" in data, "Items missing"
            assert "risks" in data["items"], "Risks array missing in items"
            
            risks = data["items"]["risks"]
            print(f"✅ Sucesso! {len(risks)} riscos identificados.")
            
            if len(risks) > 0:
                first = risks[0]
                print(f"📝 Exemplo de Risco: [{first.get('risk_type')}] {first.get('description')}")
                assert "risk_type" in first, "Risk Type missing"
                assert "evidence" in first, "Evidence missing"
                
        else:
            print(f"❌ Falha: {resp.text}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Erro de execução: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_risk_detection()
