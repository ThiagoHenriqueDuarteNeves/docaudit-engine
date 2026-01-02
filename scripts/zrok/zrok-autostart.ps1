# =============================================================================
# zrok-autostart.ps1 - Script de Autostart para Zrok
# Coloque este script na pasta Startup ou configure no Agendador de Tarefas
# =============================================================================

# Aguarda 30 segundos para garantir que a rede esta pronta
Start-Sleep -Seconds 30

# Configura o PATH
$env:PATH += ";$env:USERPROFILE\bin"

# Log file
$logFile = "$env:USERPROFILE\zrok-autostart.log"

# Registra inicio
Add-Content -Path $logFile -Value "$(Get-Date) - Iniciando zrok autostart..."

# Inicia o zrok em loop (reinicia se cair)
while ($true) {
    try {
        Add-Content -Path $logFile -Value "$(Get-Date) - Conectando ao zrok..."
        
        # Inicia o tunel
        zrok share reserved aurorarag --override-endpoint http://localhost:8000 --headless
        
        # Se chegou aqui, o zrok terminou (caiu)
        Add-Content -Path $logFile -Value "$(Get-Date) - Zrok desconectado. Reconectando em 10s..."
        Start-Sleep -Seconds 10
    }
    catch {
        Add-Content -Path $logFile -Value "$(Get-Date) - Erro: $_"
        Start-Sleep -Seconds 10
    }
}
