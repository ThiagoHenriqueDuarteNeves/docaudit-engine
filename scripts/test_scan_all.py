import requests
import json
import sys

BASE_URL = "http://localhost:8002"

def get_first_document():
    try:
        resp = requests.get(f"{BASE_URL}/api/documents")
        if resp.status_code == 200:
            docs = resp.json()
            # Prefer PDF
            for d in docs:
                if d["filename"].lower().endswith(".pdf"):
                    return d["filename"]
            # Fallback
            if docs:
                return docs[0]["filename"]
    except Exception as e:
        print(f"Erro ao buscar documentos: {e}")
    return None

def test_scan_all():
    print("🚀 Iniciando Teste de Scan All (Risk Detection)...")
    
    doc_id = get_first_document()
    if not doc_id:
        print("❌ Nenhum documento encontrado para teste.")
        sys.exit(1)
        
    print(f"📄 Documento alvo: {doc_id}")
    
    payload = {
        "document_ids": [doc_id],
        "analysis_type": "risk_detection",
        "question": "Identifique riscos (Scan Full).",
        "max_items_per_category": 100,
        "scan_all": True,
        "scan_batch_size": 20
    }
    
    try:
        print("⏳ Enviando request SCAN_ALL (pode demorar MUITO)...")
        resp = requests.post(f"{BASE_URL}/api/analyze", json=payload, timeout=300)
        
        print(f"Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            
            # Check for error
            if "error" in data:
                print(f"❌ Backend returned error: {json.dumps(data, indent=2, ensure_ascii=False)}")
                sys.exit(1)

            # Validações Específicas
            meta = data.get("meta", {})
            if "coverage" not in meta:
                print(f"❌ Falha: Meta.coverage ausente. JSON Recebido:\n{json.dumps(data, indent=2, ensure_ascii=False)}")
                sys.exit(1)
            
            cov = meta["coverage"]
            print(f"📊 Coverage: {cov}")
            assert cov["analysis_mode"] == "scan_all"
            assert cov["total_chunks"] > 0
            assert cov["processed_chunks"] == cov["total_chunks"]
            
            risks = data.get("items", {}).get("risks", [])
            print(f"✅ Sucesso! {len(risks)} riscos identificados via Scan All.")
            
        else:
            print(f"❌ Falha: {resp.text}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Erro de execução: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_scan_all()
