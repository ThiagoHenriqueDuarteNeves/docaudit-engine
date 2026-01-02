@echo off
title Aurora RAG - Startup Manager
echo ===================================================
echo 🚀 Iniciando TODOS os Ambientes (Dev + Prod)
echo ===================================================

echo.
echo [1/6] 📦 Subindo Infraestrutura Base (Qdrant)...
docker-compose -f rag_retrieval/docker-compose.yml up -d qdrant

echo.
echo [2/6] 🏭 Subindo Ambiente de PRODUCAO (Porta 8081)...
docker-compose -f docker-compose.prod.yml up -d build 

echo.
echo [3/6] 🌐 Iniciando Zrok PROD (aurora -^> 8081)...
start "Zrok PROD" cmd /k "title Zrok PROD && zrok share reserved aurora --headless --override-endpoint http://localhost:8081"

echo.
echo [4/6] 🛠️ Iniciando Ambiente de DESENVOLVIMENTO (Porta 8000)...
start "DEV Backend (8000)" cmd /k "title DEV Backend && $env:USE_HYBRID_RETRIEVAL='true' && .\.venv\Scripts\python -m uvicorn api:app --reload --host 0.0.0.0 --port 8000"

echo.
echo [5/6] � Iniciando Zrok DEV (aurorarag -^> 8000)...
start "Zrok DEV" cmd /k "title Zrok DEV && zrok share reserved aurorarag --headless --override-endpoint http://localhost:8000"

echo.
echo [6/6] � Iniciando Frontend (Vite)...
cd frontend-new
start "Frontend" cmd /k "title Frontend && npm run dev"
cd ..

echo.
echo ===================================================
echo ✅ Tudo iniciado!
echo ---------------------------------------------------
echo 🛠️  DEV (Local): http://localhost:8000  (Zrok: https://aurorarag.share.zrok.io)
echo 🏭 PROD (Docker): http://localhost:8081 (Zrok: https://aurora.share.zrok.io)
echo 🎨 Frontend:      http://localhost:5173
echo 🗄️  Qdrant:        http://localhost:6333
echo ===================================================
pause
