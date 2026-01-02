# Deploy Script - Local RAG Chatbot
# 1. Roda Testes (CI)
# 2. Se passar, faz o "Swap": Para Dev -> Sobe Prod

Write-Host ">>> DEBUG: Versao ASCII Pura" -ForegroundColor Magenta
Write-Host ">>> Iniciando Deploy para PRODUCAO..." -ForegroundColor Cyan

# 1. Rodar Testes e Seguranca
Write-Host ">>> Rodando Qualidade e Seguranca (act)..." -ForegroundColor Yellow
act -j test, security --container-architecture linux/amd64 --rm
if ($LASTEXITCODE -ne 0) {
    Write-Host "XXX ERRO: Os testes falharam! Abortando deploy." -ForegroundColor Red
    exit 1
}
Write-Host ">>> Testes aprovados!" -ForegroundColor Green

# 2. Swap (Troca de Turno)
Write-Host ">>> Trocando de Turno (Parando Dev...)" -ForegroundColor Yellow
docker-compose stop rag-app

# 3. Subir Prod
Write-Host ">>> Construindo e subindo Producao (Porta 8081)..." -ForegroundColor Yellow
# --build garante que a imagem pegue o codigo mais recente
docker-compose -f docker-compose.prod.yml up -d --build

if ($LASTEXITCODE -ne 0) {
    Write-Host "XXX ERRO ao subir producao!" -ForegroundColor Red
    # Opcional: Tentar religar o dev?
    exit 1
}

Write-Host ">>> SUCESSO! Producao rodando em: http://localhost:8081" -ForegroundColor Green
Write-Host ">>> Nota: O banco de dados de producao comeca vazio (./db_prod)." -ForegroundColor Gray
