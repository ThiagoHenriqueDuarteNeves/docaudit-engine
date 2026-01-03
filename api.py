"""
API REST para o RAG Chatbot
Expõe todas as funcionalidades via endpoints HTTP
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends, Form, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import shutil
from pathlib import Path
import json

# ============================================================================
# IMPORTS DO CORE REFATORADO (Substituindo app.py)
# ============================================================================
from core.chat import build_chat_context, chat_stream
from core.llm import (
    check_lm_studio_status,
    list_lm_studio_models,
    set_model,
    get_current_model
)
from core.documents import get_doc_manager
from core.memory import get_memory_instance
from core.adt import analyze_documents # Aurora ADT
from memory_manager import ConversationMemory

# Instâncias Globais
doc_manager = get_doc_manager()
global_memory = get_memory_instance() # Fallback

# Inicializar FastAPI
app = FastAPI(
    title="Local RAG Chatbot API",
    description="API REST para chatbot RAG com memória semântica (Refatorado)",
    version="2.0.0"
)

# Garantir diretório de imagens
IMAGES_DIR = Path(__file__).parent / "images"
IMAGES_DIR.mkdir(exist_ok=True)

# Montar arquivos estáticos
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

# Configuração de CORS - Segura para Produção
origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:8000",
    "http://localhost:8081",
    "http://localhost:5500",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8081",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "https://aurora.share.zrok.io",          # Produção Zrok
    "https://aurorarag.share.zrok.io",       # Dev Zrok
    "https://aurora-projeto.vercel.app",     # Vercel Project
    "https://aurora-two-theta.vercel.app",   # Vercel Main
    "https://aurorabotlog-projeto.vercel.app", # Vercel AB Test
    "https://aurorahomolog-projeto.vercel.app", # Vercel Homolog (Project)
    "https://aurorahomolog.vercel.app"          # Vercel Homolog (Generic)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app", # Permite branches de preview do Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# ============================================================================
# MEMORY FACTORY
# ============================================================================

# Cache para instâncias de memória: {user_id: ConversationMemory}
_memory_instances = {}

def get_memory(request: Request, x_user_id: Optional[str] = Header(None)) -> ConversationMemory:
    """
    Dependency Injection: Recupera ou cria a instância de memória para o usuário.
    Se o header X-User-ID não for enviado, usa 'default'.
    """
    user_id = x_user_id if x_user_id else "default"
    
    if user_id not in _memory_instances:
        print(f"🔄 Criando nova sessão de memória para usuário: {user_id}")
        _memory_instances[user_id] = ConversationMemory(user_id=user_id)
    
    return _memory_instances[user_id]

# ============================================================================
# MODELS
# ============================================================================

class ChatMessage(BaseModel):
    message: str
    image: Optional[str] = None  # Base64 data URI
    history: List[List[str]] = []

class ChatResponse(BaseModel):
    response: str
    memory_count: int
    doc_count: int

class StatusResponse(BaseModel):
    status: str
    message: str

class ModelSelectRequest(BaseModel):
    model: str

class Document(BaseModel):
    filename: str
    size: str
    date: str

class Archive(BaseModel):
    id: str
    date: str
    messages: str

# Modelos para Depuração de Contexto
class DebugSnippet(BaseModel):
    source: str
    text: str
    score: Optional[float] = None
    metadata: Optional[dict] = None

class DebugResponse(BaseModel):
    formatted_prompt: str
    mem_hits: List[DebugSnippet]
    doc_hits: List[DebugSnippet]
    identity_info: dict
    is_identity_question: bool
    chat_history: str

class AnalyzeRequest(BaseModel):
    document_ids: List[str]
    analysis_type: str
    question: Optional[str] = None
    max_items_per_category: Optional[int] = 5
    scan_all: bool = False
    scan_batch_size: int = 12
    scan_passes: int = 1
    debug_llm: bool = False

@app.post("/api/index")
async def index_document(
    file: UploadFile = File(...),
    doc_id: Optional[str] = Form(None)
):
    """
    Upload e indexação imediata de documento.
    Aceita PDF, TXT, MD.
    """
    try:
        # 1. Validar e Salvar
        # Use the same directory as the DocumentManager to ensure visibility
        UPLOAD_DIR = doc_manager.docs_dir
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        
        # Sanitize filename
        safe_name = Path(file.filename).name
        # Use doc_id as filename if provided, else original name
        # But we must preserve extension
        ext = Path(safe_name).suffix
        
        target_name = safe_name
        if doc_id: 
            # If doc_id provided, ensure it ends with correct extension or append it
            if not doc_id.lower().endswith(ext.lower()):
                target_name = f"{doc_id}{ext}"
            else:
                target_name = doc_id
        
        # Prevent collisions or overwrites? 
        # For this demo, overwrite is fine as we want to update content.
        
        file_path = UPLOAD_DIR / target_name
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. Indexar
        # doc_manager is global in api.py
        result = doc_manager.index_single_file(file_path)
        
        if result['status'] == 'error':
            raise HTTPException(status_code=500, detail=result['message'])
            
        return {
            "doc_id": result.get('doc_id', target_name),
            "status": result['status'],
            "chunks": result.get('chunks', 0),
            "filename": target_name,
            "message": result['message']
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        print(f"Index error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents")
async def list_documents():
    """
    Lista todos os documentos disponíveis (indexados) para análise.
    """
    try:
        # doc_manager is global
        docs = doc_manager.list_documents()
        return {"documents": docs}
    except Exception as e:
        print(f"Error listing documents: {e}")
        return {"documents": [], "error": str(e)}

# ============================================================================
# ENDPOINTS - CHAT
# ============================================================================
@app.post("/api/debug/context", response_model=DebugResponse)
async def generate_debug_context(request: ChatMessage, user_memory: ConversationMemory = Depends(get_memory)):
    """
    Gera o contexto e prompt que seriam usados para uma mensagem.
    """
    try:
        # DEBUG: Log context call
        from pathlib import Path
        from datetime import datetime
        debug_log = Path(__file__).parent / "debug_context_trace.txt"
        with open(debug_log, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now()}] DEBUG CONTEXT CALL (User: {user_memory.user_id})\n")
        
        # Chamar construtor de contexto com a memória correta
        context_data = build_chat_context(
            message=request.message,
            history=[], # Usa histórico do DB via build_chat_context
            memory_override=user_memory
        )
        
        # Converter snippets de memória
        mem_hits = []
        if context_data.get("mem_snips"):
            for s in context_data["mem_snips"]:
                mem_hits.append(DebugSnippet(
                    source=s.get("source", "unknown"),
                    text=s.get("text", ""),
                    score=s.get("score"),
                    metadata=s.copy()
                ))
                
        # Converter snippets de documento
        doc_hits = []
        if context_data.get("doc_snips"):
            for s in context_data["doc_snips"]:
                doc_hits.append(DebugSnippet(
                    source=s.get("source", "unknown"),
                    text=s.get("text", ""),
                    score=s.get("score"),
                    metadata=s.copy()
                ))
        
        return DebugResponse(
            formatted_prompt=context_data["formatted_prompt"],
            mem_hits=mem_hits,
            doc_hits=doc_hits,
            identity_info=context_data.get("identity_info", {}),
            is_identity_question=context_data.get("is_identity_question", False),
            chat_history=context_data.get("chat_history_text", "")
        )
             
    except Exception as e:
        import traceback
        print(f"Erro debug: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze")
async def analyze_endpoint(request: AnalyzeRequest):
    """
    Endpoint para análise técnica de documentos (Aurora ADT).
    """
    try:
        print(f"📊 [API/analyze] Request: {request.analysis_type} on {request.document_ids}")
        
        result = analyze_documents(
            document_ids=request.document_ids,
            analysis_type=request.analysis_type,
            question=request.question,
            max_items_per_category=request.max_items_per_category,
            scan_all=request.scan_all,
            scan_batch_size=request.scan_batch_size,
            scan_passes=request.scan_passes,
            debug_llm=request.debug_llm
        )
        
        if "error" in result:
             if result.get("error") == "INVALID_ADT_JSON":
                 # Retornar 422 com os detalhes de validação
                 return JSONResponse(
                     status_code=422,
                     content=result
                 )
             elif "meta" not in result:
                 # Outros erros genéricos
                 raise HTTPException(status_code=500, detail=result["error"])
             
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat(
    request: Request,
    user_memory: ConversationMemory = Depends(get_memory),
    x_user_id: Optional[str] = Header(None)
):
    """
    Envia mensagem para o chatbot e recebe resposta via STREAMING.
    """
    current_user = x_user_id if x_user_id else "default"
    
    # DEBUG: Log
    from pathlib import Path
    from datetime import datetime
    debug_log = Path(__file__).parent / "api_debug_log.txt"
    
    content_type = request.headers.get("content-type", "")
    message = ""
    parsed_history = []
    image_data = None
    image_name = None
    
    try:
        print(f"📥 [API/chat] Content-Type: {content_type}")
        
        if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            message = form.get("message", "")
            history_str = form.get("history", "[]")
            try:
                parsed_history = json.loads(history_str)
            except:
                parsed_history = []
            
            image = form.get("image")
            if image and hasattr(image, 'read'):
                contents = await image.read()
                image_data = contents
                import uuid
                original_name = getattr(image, 'filename', 'image.png')
                image_name = f"{uuid.uuid4()}_{original_name}"
        else:
            body = await request.json()
            message = body.get("message", "")
            parsed_history = body.get("history", [])
        
        # Validação
        if not message or not message.strip():
            raise HTTPException(status_code=422, detail="Campo 'message' é obrigatório")
        
        print(f"💬 [API/chat] Stream Request: '{message[:30]}...' HasImage: {image_data is not None}")
        
        # Generator wrapper para logging de erros
        async def stream_generator():
            try:
                # Usar o novo chat_stream do core
                for token in chat_stream(
                    message, 
                    parsed_history, 
                    memory_override=user_memory, 
                    image=image_data, 
                    image_name=image_name
                ):
                    yield token
            except Exception as e:
                import traceback
                traceback.print_exc()
                yield f"❌ Erro de Stream: {str(e)}"

        return StreamingResponse(
            stream_generator(), 
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no", # Nginx/Proxies
                "Content-Encoding": "none"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/memory/clear")
async def clear_memory(user_memory: ConversationMemory = Depends(get_memory)):
    """
    Arquiva e limpa a memória do usuário.
    """
    try:
        user_memory.archive_and_clear()
        return StatusResponse(status="success", message="Memória arquivada e limpa com sucesso")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ENDPOINTS - DOCUMENTOS (Lógica Refatorada)
# ============================================================================

@app.get("/api/documents", response_model=List[Document])
async def list_documents():
    """
    Lista todos os documentos indexados.
    """
    try:
        docs = doc_manager.list_documents()
        return [
            Document(
                filename=doc['filename'], 
                size=f"{doc['size_mb']} MB", # Formatando para manter contrato da API anterior
                date=doc['modified'].split('T')[0]
            )
            for doc in docs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Faz upload de um documento PDF.
    """
    try:
        # Salvar arquivo temporariamente
        temp_path = Path("docs") / file.filename
        temp_path.parent.mkdir(exist_ok=True)
        
        # Escrever bytes
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Validar e Copiar (Lógica direta sem Gradio)
        dest_path = doc_manager.docs_dir / file.filename
        
        if dest_path.exists():
            return StatusResponse(status="error", message=f"⚠️ Arquivo {file.filename} já existe!")
            
        is_valid, msg = doc_manager.validate_file(temp_path)
        if not is_valid:
             return StatusResponse(status="error", message=f"❌ {msg}")
             
        # Copiar para destino final
        shutil.copy2(temp_path, dest_path)
        
        return StatusResponse(status="success", message=f"✅ {file.filename} carregado com sucesso! Clique em 'Reindexar'.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents/list")
async def list_docs_names():
    """
    Lista apenas nomes (para dropdowns, etc)
    """
    try:
        docs = doc_manager.list_documents()
        names = [d['filename'] for d in docs]
        return {"documents": names}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/documents/{filename}")
async def delete_document(filename: str):
    """
    Deleta um documento.
    """
    try:
        success, msg = doc_manager.delete_document(filename)
        if not success:
            raise HTTPException(status_code=404, detail=msg)
        return StatusResponse(status="success", message=msg)
    except Exception as e:
         if isinstance(e, HTTPException): raise e
         raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/documents/reindex")
async def reindex(background_tasks: BackgroundTasks):
    """
    Reindexa documentos em background (não bloqueia a requisição).
    """
    def do_reindex():
        try:
            stats = doc_manager.scan_and_index()
            print(f"✅ Reindex completo: {stats['message']} (Chunks: {stats['total_chunks']})")
        except Exception as e:
            print(f"❌ Erro no reindex: {e}")
    
    background_tasks.add_task(do_reindex)
    return StatusResponse(status="started", message="🔄 Reindexação iniciada em background...")


# ============================================================================
# ENDPOINTS - HISTÓRICO
# ============================================================================

@app.get("/api/archives", response_model=List[Archive])
async def list_archives(user_memory: ConversationMemory = Depends(get_memory)):
    """
    Lista conversas arquivadas.
    """
    try:
        archives = user_memory.list_archives()
        result = []
        for arch in archives:
            msgs = user_memory.load_archive(arch['id'])
            preview = f"{len(msgs)} mensagens" if msgs else "Vazio"
            
            result.append(Archive(
                id=str(arch['id']), 
                date=str(arch['archive_date']),
                messages=preview
            ))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ENDPOINTS - MODELOS LLM
# ============================================================================

@app.get("/api/models")
async def get_models():
    """
    Lista modelos disponíveis.
    """
    try:
        models = list_lm_studio_models()
        return {
            "models": models,
            "current": get_current_model()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/model/select")
async def select_model_endpoint(request: ModelSelectRequest):
    """
    Seleciona modelo.
    """
    try:
        result = set_model(request.model)
        if "❌" in result:
             raise HTTPException(status_code=400, detail=result)
        return {
            "status": "success", 
            "message": result, 
            "current_model": get_current_model()
        }
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ENDPOINTS - STATUS
# ============================================================================

@app.get("/api/status")
async def get_status():
    """
    Verifica status geral.
    """
    try:
        lm_status = check_lm_studio_status()
        return {
            "lm_studio": lm_status,
            "api": "online",
            "memory_enabled": True,
            "documents_enabled": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
