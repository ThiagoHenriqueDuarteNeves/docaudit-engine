# Script auxiliar para iniciar o tunel zrok
# Usa --override-endpoint para forcar localhost (evita problemas de rede)

# Adiciona o caminho do zrok ao PATH da sessao atual
$env:PATH += ";$env:USERPROFILE\bin"

Write-Host ">>> Iniciando Tunel Fixo (zrok)..." -ForegroundColor Cyan
Write-Host "URL: https://aurorarag.share.zrok.io" -ForegroundColor Green
Write-Host "Target: http://localhost:8000 (Dev)" -ForegroundColor Yellow

# Inicia o compartilhamento publico para a porta 8000 (Dev)
# --override-endpoint forca uso do localhost (resolve problemas de IP)
# --headless garante que nao tente abrir navegador
zrok share reserved aurorarag --override-endpoint http://localhost:8000 --headless
