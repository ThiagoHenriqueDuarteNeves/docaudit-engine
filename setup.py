"""
Setup Script - Configuração inicial do RAG Chatbot
Cria arquivo .env com senha na primeira execução
"""
import os
from pathlib import Path
import getpass


def setup_environment():
    """Cria arquivo .env com configurações iniciais"""
    env_path = Path(".env")
    
    if env_path.exists():
        print("✅ Arquivo .env já existe!")
        with open(env_path, 'r') as f:
            print(f.read())
        
        resposta = input("\nDeseja reconfigurar? (s/N): ").strip().lower()
        if resposta != 's':
            print("Setup cancelado.")
            return False
    
    print("=" * 60)
    print("🔧 CONFIGURAÇÃO INICIAL - RAG CHATBOT COM LM STUDIO")
    print("=" * 60)
    print()
    
    # Senha para Gradio
    print("1. Defina uma senha para acessar a interface web:")
    while True:
        password = getpass.getpass("   Senha: ").strip()
        if len(password) < 4:
            print("   ❌ Senha muito curta (mínimo 4 caracteres)")
            continue
        
        password_confirm = getpass.getpass("   Confirme: ").strip()
        if password != password_confirm:
            print("   ❌ Senhas não coincidem")
            continue
        
        break
    
    print("   ✅ Senha configurada!")
    print()
    
    # URL do LM Studio
    print("2. URL do LM Studio (pressione Enter para usar padrão):")
    lm_studio_url = input(f"   URL [http://localhost:1234/v1]: ").strip()
    if not lm_studio_url:
        lm_studio_url = "http://localhost:1234/v1"
    
    print(f"   ✅ LM Studio: {lm_studio_url}")
    print()
    
    # Device para embeddings
    print("3. Dispositivo para embeddings:")
    print("   [1] cuda (GPU NVIDIA)")
    print("   [2] cpu (mais lento)")
    device_choice = input("   Escolha [1]: ").strip()
    device = "cuda" if device_choice != "2" else "cpu"
    print(f"   ✅ Device: {device}")
    print()
    
    # Criar .env
    env_content = f"""# RAG Chatbot Configuration
# Gerado em: {Path.cwd()}

# Autenticação Gradio
GRADIO_SERVER_NAME=0.0.0.0
GRADIO_SERVER_PORT=7860
GRADIO_USERNAME=admin
GRADIO_PASSWORD={password}

# LM Studio API
LM_STUDIO_URL={lm_studio_url}
LM_STUDIO_API_KEY=lm-studio

# Embeddings
EMBEDDING_DEVICE={device}
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Vector Database
CHROMA_PERSIST_DIR=./db
DOCS_DIR=./docs

# Memory
MEMORY_DB_PATH=./memory/conversations.db
MEMORY_WINDOW_SIZE=10

# Document Limits
MAX_FILE_SIZE_MB=50
MAX_TOTAL_FILES=100
"""
    
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    print("=" * 60)
    print("✅ CONFIGURAÇÃO CONCLUÍDA!")
    print(f"📄 Arquivo criado: {env_path.absolute()}")
    print()
    print("Próximos passos:")
    print("1. Certifique-se que o LM Studio está rodando")
    print("2. Execute: python app.py")
    print("3. Acesse: http://localhost:7860")
    print(f"4. Login: admin / {password}")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    try:
        setup_environment()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelado pelo usuário")
    except Exception as e:
        print(f"\n\n❌ Erro durante setup: {e}")
