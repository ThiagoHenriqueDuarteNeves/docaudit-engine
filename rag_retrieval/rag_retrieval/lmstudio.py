"""
LangChain + LM Studio Integration
Factory functions for LLM and Embeddings via LM Studio
"""
import os
from typing import Optional
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings


# Default LM Studio configuration
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
LMSTUDIO_API_KEY = os.getenv("LMSTUDIO_API_KEY", "lm-studio")  # Dummy key for LM Studio
LMSTUDIO_CHAT_MODEL = os.getenv("LMSTUDIO_CHAT_MODEL", "")  # Model loaded in LM Studio
LMSTUDIO_EMBED_MODEL = os.getenv("LMSTUDIO_EMBED_MODEL", "")  # Embedding model in LM Studio


def build_llm(
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    streaming: bool = False,
    **kwargs
) -> BaseChatModel:
    """
    Build LangChain ChatOpenAI instance pointing to LM Studio
    
    Args:
        model: Model name (optional if only one model loaded)
        base_url: LM Studio API URL
        api_key: API key (dummy for LM Studio)
        temperature: Generation temperature
        max_tokens: Max tokens to generate
        streaming: Enable streaming responses
        **kwargs: Additional ChatOpenAI parameters
    
    Returns:
        ChatOpenAI instance configured for LM Studio
    """
    return ChatOpenAI(
        model=model or LMSTUDIO_CHAT_MODEL or "local-model",
        base_url=base_url or LMSTUDIO_BASE_URL,
        api_key=api_key or LMSTUDIO_API_KEY,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        **kwargs
    )


def build_embeddings(
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> Embeddings:
    """
    Build LangChain OpenAIEmbeddings instance pointing to LM Studio
    
    Note: LM Studio must have an embedding model loaded for this to work.
    If not using LM Studio embeddings, use sentence-transformers directly.
    
    Args:
        model: Embedding model name
        base_url: LM Studio API URL
        api_key: API key (dummy for LM Studio)
        **kwargs: Additional OpenAIEmbeddings parameters
    
    Returns:
        OpenAIEmbeddings instance configured for LM Studio
    """
    return OpenAIEmbeddings(
        model=model or LMSTUDIO_EMBED_MODEL or "local-embedding",
        base_url=base_url or LMSTUDIO_BASE_URL,
        api_key=api_key or LMSTUDIO_API_KEY,
        **kwargs
    )


def build_local_embeddings(model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
    """
    Build embeddings using local sentence-transformers model
    (No LM Studio dependency)
    
    Args:
        model_name: HuggingFace model name
    
    Returns:
        HuggingFaceEmbeddings instance
    """
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        from langchain_community.embeddings import HuggingFaceEmbeddings
    
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )


def check_lmstudio_connection(base_url: Optional[str] = None) -> dict:
    """
    Check if LM Studio is accessible and get available models
    
    Returns:
        dict with status, models, and error if any
    """
    import httpx
    
    url = base_url or LMSTUDIO_BASE_URL
    
    try:
        response = httpx.get(f"{url}/models", timeout=5.0)
        response.raise_for_status()
        
        data = response.json()
        models = [m.get("id", "unknown") for m in data.get("data", [])]
        
        return {
            "status": "ok",
            "url": url,
            "models": models,
            "error": None
        }
    except httpx.ConnectError:
        return {
            "status": "error",
            "url": url,
            "models": [],
            "error": "Cannot connect to LM Studio. Is it running?"
        }
    except Exception as e:
        return {
            "status": "error",
            "url": url,
            "models": [],
            "error": str(e)
        }


# Convenience function for quick LLM invoke
async def invoke_llm(
    prompt: str,
    system_message: Optional[str] = None,
    **kwargs
) -> str:
    """
    Quick LLM invocation with optional system message
    
    Args:
        prompt: User prompt
        system_message: Optional system message
        **kwargs: Additional build_llm parameters
    
    Returns:
        LLM response text
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    
    llm = build_llm(**kwargs)
    
    messages = []
    if system_message:
        messages.append(SystemMessage(content=system_message))
    messages.append(HumanMessage(content=prompt))
    
    response = await llm.ainvoke(messages)
    return response.content
