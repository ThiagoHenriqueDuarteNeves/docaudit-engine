@echo off
echo ===================================================
echo 🚀 Iniciando Backend (Debug Mode)
echo ===================================================

echo [1/4] Configurando Variaveis de Ambiente...
set QDRANT_URL=http://localhost:6333
set VECTORSTORE_BACKEND=qdrant
set OVERRIDES_DISABLE=1
set COLLECTION_NAME=default
set EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
set EMBED_DIM=384

echo [2/4] Verificando Python no Venv...
if exist ".venv\Scripts\python.exe" (
    echo    - Venv encontrado.
) else (
    echo    - ERRO: .venv nao encontrado!
    pause
    exit /b
)

echo [3/4] Testando Import do PyTorch...
.venv\Scripts\python -c "import torch; print(f'   - PyTorch: {torch.__version__} (CUDA: {torch.cuda.is_available()})')"

echo [4/4] Iniciando Uvicorn na porta 8002...
.venv\Scripts\python -m uvicorn api:app --reload --host 0.0.0.0 --port 8002

echo.
echo ⚠️ O servidor parou. Verifique o erro acima.
pause
