import requests
from langchain_openai import ChatOpenAI
from core.config import LM_STUDIO_URL

# Variáveis globais de estado do LLM
llm = None
current_model = None
current_sdk_llm = None

def check_lm_studio_status():
    """Verifica se o LM Studio está respondendo"""
    try:
        # Forçar 127.0.0.1 para evitar problemas de resolução de 'localhost'
        base_url = "http://127.0.0.1:1234"
        response = requests.get(f"{base_url}/v1/models", timeout=2)
        if response.status_code == 200:
            return "online"
        return "offline"
    except:
        return "offline"

def list_lm_studio_models():
    """Lista modelos disponíveis no LM Studio via API /v1/models"""
    try:
        # Usar a URL configurada globalmente
        base_url = LM_STUDIO_URL.replace("/v1", "")
        
        # print(f"DEBUG: Conectando em LM Studio: {base_url}/v1/models")
        response = requests.get(f"{base_url}/v1/models", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            models = [model['id'] for model in data.get('data', [])]
            if models:
                return models
            else:
                return ["Nenhum modelo disponível"]
        else:
            return ["Erro ao conectar"]
    except Exception as e:
        print(f"⚠️ Erro ao listar modelos: {e}")
        return ["LM Studio offline"]

def get_current_model() -> str:
    """Retorna o modelo atualmente em uso"""
    if current_model:
        return f"Modelo atual: {current_model}"
    else:
        return "Modelo: Padrão (LM Studio)"

def initialize_llm():
    """Inicializa o LLM (LangChain) com o primeiro modelo disponível"""
    global llm, current_model
    try:
        models = list_lm_studio_models()
        first_valid_model = None
        
        # Filtrar mensagens de erro da lista
        valid_models = [m for m in models if m not in ["Nenhum modelo disponível", "Erro ao conectar", "LM Studio offline"]]
        
        if valid_models:
            first_valid_model = valid_models[0]
            print(f"🤖 [LLM] Usando modelo: {first_valid_model}")
        
        if first_valid_model:
            llm = ChatOpenAI(
                base_url=LM_STUDIO_URL,
                api_key="lm-studio",
                model=first_valid_model,
                temperature=0.0,
                max_tokens=15000,
                streaming=True
            )
            current_model = first_valid_model
            
            # Teste rápido
            # llm.invoke("test") # Opcional, pode atrasar startup
            print("✅ [LLM] LM Studio conectado e inicializado!")
        else:
             # Fallback genérico
            llm = ChatOpenAI(
                base_url=LM_STUDIO_URL,
                api_key="lm-studio",
                temperature=0.0,
                max_tokens=15000,
                streaming=False
            )
            print("⚠️ [LLM] Inicializado sem modelo específico (fallback).")

    except Exception as e:
        print(f"⚠️ [LLM] Aviso: Não foi possível conectar ao LM Studio na inicialização: {e}")
        llm = None

def set_model(model_name: str) -> str:
    """Troca o modelo LLM em uso"""
    global llm, current_model, current_sdk_llm
    
    current_sdk_llm = None # Reset cache
    
    if not model_name or model_name in ["Nenhum modelo disponível", "Erro ao conectar", "LM Studio offline"]:
        return f"❌ Modelo inválido: {model_name}"
    
    try:
        print(f"🔄 [LLM] Trocando modelo para: {model_name}")
        
        llm = ChatOpenAI(
            base_url=LM_STUDIO_URL,
            api_key="lm-studio",
            model=model_name,
            temperature=0.0,
            max_tokens=15000,
            streaming=True
        )
        
        # Testar conexão
        llm.invoke("test")
        current_model = model_name
        
        print(f"✅ [LLM] Modelo trocado com sucesso: {model_name}")
        return f"✅ Modelo ativo: {model_name}"
        
    except Exception as e:
        print(f"❌ [LLM] Erro ao trocar modelo: {e}")
        return f"❌ Erro ao trocar modelo: {str(e)}"

# Auto-inicialização ao importar
initialize_llm()
