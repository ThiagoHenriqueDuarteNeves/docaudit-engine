import requests
import json
import sys
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Config
BASE_URL = "http://localhost:8002"
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "default"

def get_qdrant_count(filename):
    client = QdrantClient(url=QDRANT_URL)
    count_filter = Filter(
        must=[
            FieldCondition(key="doc_id", match=MatchValue(value=filename))
        ]
    )
    res = client.count(collection_name=COLLECTION_NAME, count_filter=count_filter)
    return res.count

def get_candidate_document():
    try:
        resp = requests.get(f"{BASE_URL}/api/documents")
        if resp.status_code != 200:
            print("❌ Falha ao listar documentos via API")
            return None
            
        docs = resp.json()
        candidates = []
        
        print("🔍 Buscando documento adequado para teste...")
        for d in docs:
            fname = d["filename"]
            # Check Qdrant Count directly
            count = get_qdrant_count(fname)
            print(f"   - {fname}: {count} chunks no Qdrant")
            if count > 0:
                candidates.append((fname, count))
        
        if not candidates:
            return None
            
        # Sort by count (ascending) to be gentle on CPU backend
        candidates.sort(key=lambda x: x[1])
        return candidates[0] # (filename, count)
        
    except Exception as e:
        print(f"❌ Erro ao buscar/filtrar documentos: {e}")
        return None

def test_coverage():
    print("🚀 Iniciando Validação de Cobertura 100%...")
    
    candidate = get_candidate_document()
    if not candidate:
        print("❌ Nenhum documento com chunks encontrado no Qdrant.")
        sys.exit(1)
        
    target_doc, expected_chunks = candidate
    print(f"\n📋 Alvo selecionado: {target_doc}")
    print(f"🔢 Chunks esperados (Qdrant Source): {expected_chunks}")
    
    payload = {
        "document_ids": [target_doc],
        "analysis_type": "risk_detection",
        "question": "Coverage Check",
        "max_items_per_category": 1, 
        "scan_all": True,
        "scan_batch_size": 10
    }
    
    print("⏳ Enviando request scan_all...")
    try:
        # Aumentando timeout para 15min (346 chunks no Local LLM demora)
        resp = requests.post(f"{BASE_URL}/api/analyze", json=payload, timeout=900)
        
        if resp.status_code == 200:
            data = resp.json()
            meta = data.get("meta", {}).get("coverage", {})
            
            print(f"📊 Resposta Backend: {json.dumps(meta, indent=2)}")
            
            # Assertions
            reported_total = meta.get("total_chunks", -1)
            reported_processed = meta.get("processed_chunks", -1)
            
            if reported_total != expected_chunks:
                print(f"❌ Mismatch! Esperado: {expected_chunks}, Backend viu: {reported_total}")
                sys.exit(1)
                
            if reported_processed != expected_chunks:
                print(f"❌ Incompleto! Processou {reported_processed} de {expected_chunks}")
                sys.exit(1)
                
            print(f"\n✅ SUCESSO: O backend escaneou exatamente {reported_processed}/{expected_chunks} chunks (100%).")
            
        else:
            print(f"❌ Falha HTTP {resp.status_code}: {resp.text}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Erro de execução: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_coverage()
