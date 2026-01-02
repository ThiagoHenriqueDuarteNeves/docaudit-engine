
import sys
from unittest.mock import MagicMock

# 1. MOCK TUDO antes de importar o app
sys.modules["memory_manager"] = MagicMock()
sys.modules["document_manager"] = MagicMock()
sys.modules["langchain_openai"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["core.documents"] = MagicMock()
sys.modules["core.llm"] = MagicMock()

# Mock do buscador de memória
mock_mem_tool = MagicMock()
# Quando invocado, retorna uma lista de snippets (formato real da tool)
mock_mem_tool.invoke.return_value = [{"text": "O presidente é o Batman.", "source": "user", "timestamp": "2023-01-01T12:00:00"}]

# Mock da MemorySearchTool class
mock_tool_class = MagicMock(return_value=mock_mem_tool)
sys.modules["tools"] = MagicMock()
sys.modules["tools"].MemorySearchTool = mock_tool_class

# Importa a função
from core.chat import build_chat_context, chat_response
from core import config, memory
def test_build_context_basic():
    """
    Testa se o prompt é montado corretamente.
    """
    # 2. Criar um Mock de MEMÓRIA real
    mock_memory = MagicMock()
    mock_memory.format_for_langchain.return_value = "Assitente: Ola"
    mock_memory.user_id = "test_user"
    
    user_query = "Quem é o presidente?"
    context_chunks = [] # Injetado via memory_override

    # Executa a função passando o mock da memória como override
    data = build_chat_context(user_query, history=[], memory_override=mock_memory)

    # Verificações
    assert isinstance(data, dict)
    assert "formatted_prompt" in data
    assert "Quem é o presidente?" in data["formatted_prompt"]
    # Verifica se a memória simulada aparece no prompt
    assert "Assitente: Ola" in data["formatted_prompt"]

def test_build_context_identity():
    """
    Testa se a lógica de identidade (nome) é disparada.
    """
    mock_memory = MagicMock()
    mock_memory.format_for_langchain.return_value = ""
    mock_memory.user_id = "test_user"
    
    # Pergunta que deve acionar identidade
    user_query = "Qual é o seu nome?"
    
    data = build_chat_context(user_query, history=[], memory_override=mock_memory)
    
    # Verifica se o prompt contém as tags de instrução da Aurora
    assert "Você é Aurora" in data["formatted_prompt"]
    assert "user_query" in data["formatted_prompt"]
