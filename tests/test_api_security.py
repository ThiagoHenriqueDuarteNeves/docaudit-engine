
import sys
from unittest.mock import MagicMock

# 1. Setup Mocks (Simular dependências para não quebrar no CI sem GPU/DB)
mock_memory = MagicMock()
mock_doc_manager = MagicMock()

sys.modules["memory_manager"] = MagicMock()
sys.modules["memory_manager"].ConversationMemory.return_value = mock_memory
sys.modules["document_manager"] = MagicMock()
sys.modules["document_manager"].DocumentManager.return_value = mock_doc_manager

# Mocks de IA
sys.modules["langchain_openai"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()

# Importar app após mocks
from api import app
from fastapi.testclient import TestClient

client = TestClient(app)

import pytest

def test_cors_allowed_origins():
    """
    Verifica se a API responde corretamente a requisições pre-flight (OPTIONS)
    para as origens permitidas (Prod, Dev, Vercel).
    """
    allowed_origins = [
        "https://aurora.share.zrok.io",
        "https://aurorarag.share.zrok.io",
        "https://aurora-two-theta.vercel.app",
        "http://localhost:5173",
        "https://qualquer-coisa.vercel.app" # Teste do Regex
    ]
    
    for origin in allowed_origins:
        response = client.options(
            "/api/models",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET"
            }
        )
        assert response.status_code == 200, f"CORS falhou para a origem: {origin}"
        assert response.headers.get("access-control-allow-origin") == origin, f"Header de CORS incorreto para: {origin}"

def test_cors_disallowed_origin():
    """
    Verifica se a API bloqueia origens não autorizadas.
    """
    disallowed_origin = "https://site-malicioso.com"
    response = client.options(
        "/api/models",
        headers={
            "Origin": disallowed_origin,
            "Access-Control-Request-Method": "GET"
        }
    )
    # No FastAPI, o middleware de CORS não retorna 400 por padrão em OPTIONS, 
    # ele apenas não retorna os headers de 'Access-Control-Allow-Origin'.
    # Se o header não existe, o navegador bloqueia a requisição.
    assert "access-control-allow-origin" not in response.headers

def test_models_endpoint_health():
    """
    Verifica se o endpoint de modelos está respondendo.
    """
    response = client.get("/api/models")
    assert response.status_code == 200

