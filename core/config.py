import os
import torch
from dotenv import load_dotenv

# Carregar variáveis de ambiente
# Debug prints (opcional, pode ser removido se poluir logs)
# print(f"🔍 [CONFIG] Env 'LM_STUDIO_URL' antes de carregar .env: {os.environ.get('LM_STUDIO_URL')}")

# Prioridade: Docker Environment > .env file
# override=False garante que se a variável já existe (passada pelo docker-compose), NÃO será sobrescrita pelo arquivo .env
load_dotenv(override=False) 

# print(f"🔍 [CONFIG] Env 'LM_STUDIO_URL' depois de carregar .env: {os.environ.get('LM_STUDIO_URL')}")

# Configurações Básicas
LM_STUDIO_URL = os.getenv('LM_STUDIO_URL', 'http://127.0.0.1:1234/v1')
GRADIO_USERNAME = os.getenv('GRADIO_USERNAME', 'admin')
GRADIO_PASSWORD = os.getenv('GRADIO_PASSWORD', 'admin')
MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '50'))
MAX_TOTAL_FILES = int(os.getenv('MAX_TOTAL_FILES', '100'))

# Configuração de Device
EMBEDDING_DEVICE = os.getenv('EMBEDDING_DEVICE', 'cuda')

# Workaround para Python 3.13 e verificações de GPU
if EMBEDDING_DEVICE == 'cuda' and not torch.cuda.is_available():
    print("⚠️ [CONFIG] AVISO: CUDA configurado mas não disponível. Usando CPU para embeddings.")
    EMBEDDING_DEVICE = 'cpu'

print(f"✅ [CONFIG] Usando device: {EMBEDDING_DEVICE}")
print(f"🔌 [CONFIG] LM Studio URL: {LM_STUDIO_URL}")
