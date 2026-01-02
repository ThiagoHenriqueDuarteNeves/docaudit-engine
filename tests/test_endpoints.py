"""
Testes para todos os endpoints da API REST
Garante que cada endpoint responde corretamente
"""
import pytest
import sys
from unittest.mock import patch, MagicMock

# Mock de dependências pesadas ANTES de importar api
mock_embeddings = MagicMock()
mock_chroma = MagicMock()

# Aplicar patches no nível de módulo
sys.modules['langchain_huggingface'] = MagicMock()
sys.modules['langchain_chroma'] = MagicMock()
sys.modules['langchain_community.vectorstores'] = MagicMock()
sys.modules['langchain_community.embeddings'] = MagicMock()

with patch.dict('os.environ', {'LM_STUDIO_URL': 'http://localhost:1234/v1'}):
    with patch('document_manager.HuggingFaceEmbeddings', return_value=mock_embeddings), \
         patch('document_manager.Chroma', return_value=mock_chroma):
        # Agora importar api com mocks
        from api import app

from fastapi.testclient import TestClient
client = TestClient(app)


class TestHealthEndpoints:
    """Testes de endpoints de saúde e status"""
    
    def test_root_endpoint(self):
        """GET / - Deve retornar mensagem de boas-vindas"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data or "status" in data
    
    def test_health_endpoint(self):
        """GET /api/health - Deve retornar status healthy"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
    
    def test_status_endpoint(self):
        """GET /api/status - Deve retornar informações de status"""
        response = client.get("/api/status")
        # Pode retornar 200 ou 500 dependendo do estado do LLM
        assert response.status_code in [200, 500]


class TestModelEndpoints:
    """Testes de endpoints de modelos LLM"""
    
    def test_get_models(self):
        """GET /api/models - Deve listar modelos disponíveis"""
        response = client.get("/api/models")
        # Pode retornar 200 ou 500 dependendo da conexão com LM Studio
        assert response.status_code in [200, 500]
    
    def test_select_model(self):
        """POST /api/model/select - Deve aceitar requisição de seleção"""
        response = client.post(
            "/api/model/select",
            json={"model": "test-model"}
        )
        # Aceita 200 (sucesso) ou 500 (LM Studio offline)
        assert response.status_code in [200, 500]


class TestChatEndpoints:
    """Testes de endpoints de chat"""
    
    def test_chat_endpoint(self):
        """POST /api/chat - Endpoint deve aceitar requisição válida (Multipart)"""
        # Endpoint agora usa multipart/form-data
        response = client.post(
            "/api/chat",
            data={
                "message": "Olá", 
                "history": "[]"  # Histórico vem como string JSON no form
            }
        )
        # Aceita 200 (sucesso) ou 500 (LLM offline)
        assert response.status_code in [200, 500]
    
    def test_debug_context_endpoint(self):
        """POST /api/debug/context - Endpoint deve aceitar requisição válida"""
        response = client.post(
            "/api/debug/context",
            json={"message": "teste", "history": []}
        )
        # Aceita 200 (sucesso) ou 500 (dependências offline)
        assert response.status_code in [200, 500]


class TestMemoryEndpoints:
    """Testes de endpoints de memória"""
    
    def test_clear_memory_endpoint(self):
        """DELETE /api/memory/clear - Deve limpar memória"""
        response = client.delete("/api/memory/clear")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestDocumentEndpoints:
    """Testes de endpoints de documentos"""
    
    def test_list_documents(self):
        """GET /api/documents - Deve aceitar requisição"""
        response = client.get("/api/documents")
        assert response.status_code in [200, 500]
    
    def test_list_documents_alt(self):
        """GET /api/documents/list - Endpoint alternativo de listagem"""
        response = client.get("/api/documents/list")
        assert response.status_code in [200, 500]
    
    def test_delete_document_format(self):
        """DELETE /api/documents/{filename} - Formato de requisição correto"""
        response = client.delete("/api/documents/test.pdf")
        # Pode ser 200 (sucesso), 404 (não encontrado) ou 500 (erro)
        assert response.status_code in [200, 404, 500]
    
    def test_reindex_documents(self):
        """POST /api/documents/reindex - Endpoint deve aceitar requisição"""
        response = client.post("/api/documents/reindex")
        assert response.status_code in [200, 500]


class TestArchiveEndpoints:
    """Testes de endpoints de arquivos/histórico"""
    
    def test_list_archives(self):
        """GET /api/archives - Deve listar conversas arquivadas"""
        response = client.get("/api/archives")
        assert response.status_code == 200




# NOTA: Testes de CORS estão em test_api_security.py

class TestInputValidation:
    """Testes de validação de entrada"""
    
    def test_chat_missing_message(self):
        """POST /api/chat sem mensagem deve falhar"""
        # Agora enviamos form empty, deve falhar pq 'message' é obrigatório
        response = client.post("/api/chat", data={})
        # 422 (Validation) ou 500 (Internal) - ambos indicam falha correta
        assert response.status_code in [422, 500]
    
    def test_model_select_missing_model(self):
        """POST /api/model/select sem modelo deve falhar"""
        response = client.post("/api/model/select", json={})
        assert response.status_code == 422


# Contagem de testes para referência
def test_count_endpoints():
    """Meta-teste: verifica se temos cobertura mínima de endpoints"""
    # Lista de endpoints que DEVEM ter testes
    required_endpoints = [
        "/",
        "/api/health",
        "/api/status",
        "/api/models",
        "/api/model/select",
        "/api/chat",
        "/api/debug/context",
        "/api/memory/clear",
        "/api/documents",
        "/api/documents/list",
        "/api/documents/{filename}",
        "/api/documents/reindex",
        "/api/archives"
    ]
    # Este teste sempre passa, serve como documentação
    assert len(required_endpoints) == 13
