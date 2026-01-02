"""
Smoke Test (Teste de Fumaça) 🌫️
Objetivo: Garantir que a aplicação liga sem explodir.

Versão Mockada: Como o ambiente de CI não tem banco de dados nem GPU,
nós "fingimos" (mock) as dependências pesadas. Se o import funcionar,
o código está sintaticamente correto.
"""
import sys
from unittest.mock import MagicMock

# 1. Criar Mocks para dependências pesadas ou externas
# Isso impede que o código tente conectar no ChromaDB, SQLite ou OpenAI real
mock_memory = MagicMock()
mock_doc_manager = MagicMock()

# Configurar o módulo memory_manager para retornar nosso mock
sys.modules["memory_manager"] = MagicMock()
sys.modules["memory_manager"].ConversationMemory.return_value = mock_memory

sys.modules["document_manager"] = MagicMock()
sys.modules["document_manager"].DocumentManager.return_value = mock_doc_manager

# Também mockar bibliotecas de IA que podem exigir credenciais/GPU
sys.modules["langchain_openai"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()

# 2. Agora é seguro importar o app (ele vai usar os mocks)
try:
    from api import app
    from fastapi.testclient import TestClient
except ImportError as e:
    # Se falhar aqui, é erro de dependência real (ex: FastAPI não instalado)
    raise e

client = TestClient(app)

def test_api_starts():
    """
    Verifica se conseguimos fazer uma chamada básica para a API.
    A API deve subir mesmo com os componentes de IA mockados.
    """
    # A rota /docs é gerada automaticamente pelo FastAPI
    response = client.get("/docs")
    assert response.status_code == 200

def test_debug_endpoint_exists():
    """
    Verifica se o nosso endpoint de debug foi registrado corretamente.
    """
    # Lista todas as rotas registradas no FastAPI
    routes = [route.path for route in app.routes]
    assert "/api/debug/context" in routes
