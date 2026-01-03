
import sys
import os
import json
import requests

# Ajuste path para importar core se executado da raiz
sys.path.append(os.getcwd())

def run_demo():
    print("🚀 Iniciando Demo: QA Requirements Audit")
    
    # 1. Definir endpoint e payload
    url = "http://localhost:8000/api/analyze" # Ajuste porta se necessário
    if len(sys.argv) > 1:
        doc_id = sys.argv[1]
    else:
        doc_id = "AuditDocEngine_Demo_SRS_QA_Requisitos.pdf"
        
    payload = {
        "document_ids": [doc_id],
        "analysis_type": "qa_requirements_audit",
        "question": "Auditoria completa de qualidade.",
        "debug_llm": True
    }
    
    print(f"📡 Enviando request para {url} com doc_id={doc_id}...")
    
    try:
        # Tenta importar internamente para rodar standalone se server não estiver on
        # Mas o script pede "via curl" no prompt -> vamos simular request se server off?
        # Melhor seguir a arquitetura: o script deve ser um client. 
        # Se falhar conexão, avisa.
        resp = requests.post(url, json=payload, timeout=120)
        
        if resp.status_code == 200:
            data = resp.json()
            print("\n✅ Análise Concluída com Sucesso!")
            
            summary = data.get("summary", {})
            items = data.get("items", {})
            
            print(f"\n📋 Resumo Executivo:\n{summary.get('executive')}")
            print(f"Confidence: {summary.get('confidence')}")
            
            print(f"\n📊 Coverage:")
            print(json.dumps(items.get("coverage", {}).get("counts"), indent=2))
            
            print(f"\n⚠️ Top 5 Ambiguidades:")
            for i, amb in enumerate(items.get("ambiguities", [])[:5]):
                print(f"  {i+1}. '{amb.get('trecho_problematico')}' -> {amb.get('problema')}")
            
            print(f"\n⚔️ Contradições ({len(items.get('contradictions', []))}):")
            for c in items.get("contradictions", []):
                print(f"  - {c.get('descricao')} (Sev: {c.get('severidade')})")
                
            print(f"\n💾 Output completo salvo em demo_output.json")
            with open("demo_output.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        else:
            print(f"❌ Erro na requisição: {resp.status_code}")
            print(resp.text)
            
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")
        print("Certifique-se que o backend está rodando: 'run_backend.bat'")

if __name__ == "__main__":
    run_demo()
