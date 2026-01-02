@echo off
echo ===================================================
echo 🚀 Iniciando Local RAG Chatbot (Aurora)
echo ===================================================

echo [1/2] Iniciando Backend (API + GPU Support)...
start "RAG Backend" cmd /k ".\.venv\Scripts\python -m uvicorn api:app --reload --host 0.0.0.0 --port 8000"

echo [2/2] Iniciando Frontend (Vite)...
cd frontend-new
start "RAG Frontend" cmd /k "npm run dev"

echo.
echo ✅ Serviços iniciados em janelas separadas.
echo ⏳ Aguarde o carregamento completo...
echo.
pause
