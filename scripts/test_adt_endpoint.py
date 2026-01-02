import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_analyze():
    print("🚀 Iniciando teste do endpoint /api/analyze...")
    
    # 1. Obter lista de documentos para pegar um ID válido
    try:
        print("📄 Buscando documentos disponíveis...")
        resp = requests.get(f"{BASE_URL}/api/documents/list")
        if resp.status_code != 200:
            print(f"❌ Falha ao listar documentos: {resp.text}")
            return
            
        data = resp.json()
        docs = data.get("documents", [])
        
    except Exception as e:
        print(f"❌ Erro de conexão (API está rodando?): {e}")
        return

    # Fallback forcefully
    if not docs:
        print("⚠️ Lista vazia. Tentando usar 'test_requirements.txt' forçado...")
        target_doc = "test_requirements.txt"
    else:
        target_doc = docs[0]
        print(f"✅ Documento alvo selecionado: {target_doc}")
        


    # 2. Enviar request de análise
    payload = {
        "document_ids": [target_doc],
        "analysis_type": "requirements_extraction",
        "question": "Quais são os requisitos funcionais mencionados?",
        "max_items_per_category": 3
    }
    
    print(f"\n📤 Enviando payload: {json.dumps(payload, indent=2)}")
    
    try:
        resp = requests.post(f"{BASE_URL}/api/analyze", json=payload, timeout=60) # Timeout alto pois LLM demora
        
        if resp.status_code == 200:
            result = resp.json()
            print("\n✅ SUCESSO! Resposta recebida:")
            # Mostrar resumo para não poluir
            print(json.dumps(result.get("summary", {}), indent=2, ensure_ascii=False))
            
            # Validar campos chaves
            if "items" in result:
                n_reqs = len(result["items"].get("requirements", []))
                print(f"📊 Requisitos extraídos: {n_reqs}")
            else:
                print("⚠️ Campo 'items' ausente no JSON.")
        else:
            print(f"❌ Erro na requisição: {resp.status_code}")
            if resp.status_code == 422:
                print("⚠️ Erro de Validação (Expected):")
                try:
                    error_data = resp.json()
                    print(json.dumps(error_data, indent=2, ensure_ascii=False))
                except:
                    print(resp.text)
            else:
                print(resp.text)
            
    except Exception as e:
         print(f"❌ Erro ao chamar /api/analyze: {e}")

if __name__ == "__main__":
    test_analyze()
