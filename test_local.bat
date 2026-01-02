@echo off
echo ==========================================
echo    Iniciando Ambiente de TESTE LOCAL
echo ==========================================

echo.
echo [1/3] Verificando Qdrant...
docker-compose -f rag_retrieval/docker-compose.yml up -d qdrant

echo.
echo [2/3] Iniciando Backend (Porta 8000)...
start "Backend API" cmd /k "python -m uvicorn api:app --reload --host 0.0.0.0 --port 8000"

echo.
echo [3/3] Iniciando Frontend (Porta 5173)...
cd frontend-new
start "Frontend" cmd /k "npm run dev"
cd ..

echo.
echo ==========================================
echo    Ambiente Iniciado!
echo ==========================================
