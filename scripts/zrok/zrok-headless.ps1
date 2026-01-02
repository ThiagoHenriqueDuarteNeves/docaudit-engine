# zrok-headless.ps1 - Inicia tunnels zrok em modo headless (sem janela)
# Ambientes: Produção (aurora) + Dev (aurorarag)
# Para rodar: powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File .\zrok-headless.ps1

$logDir = $PSScriptRoot

# Mata processos zrok anteriores se existirem
Get-Process -Name "zrok" -ErrorAction SilentlyContinue | Stop-Process -Force

# 1. Tunnel PRODUÇÃO (aurora → porta 8081)
Start-Process -FilePath "zrok" `
    -ArgumentList "share", "reserved", "aurora", "--override-endpoint", "http://localhost:8081", "--headless" `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$logDir\zrok-prod.log" `
    -RedirectStandardError "$logDir\zrok-prod-error.log"

# 2. Tunnel DEV (aurorarag → porta 8000)
Start-Process -FilePath "zrok" `
    -ArgumentList "share", "reserved", "aurorarag", "--override-endpoint", "http://localhost:8000", "--headless" `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$logDir\zrok-dev.log" `
    -RedirectStandardError "$logDir\zrok-dev-error.log"

Write-Host ">>> Tunnels zrok iniciados em modo headless" -ForegroundColor Green
Write-Host ">>> PROD: https://aurora.share.zrok.io (porta 8081)" -ForegroundColor Cyan
Write-Host ">>> DEV:  https://aurorarag.share.zrok.io (porta 8000)" -ForegroundColor Yellow
Write-Host ">>> Logs: $logDir\zrok-*.log" -ForegroundColor Gray
