# Script para configurar firewall do Windows para permitir acesso ao Vite
# Execute como Administrador

Write-Host "🔥 Configurando Firewall do Windows para Vite Dev Server..." -ForegroundColor Cyan
Write-Host ""

# Porta do Vite
$port = 5173
$ruleName = "Vite Dev Server (Port $port)"

# Remove regra antiga se existir
Write-Host "🗑️  Removendo regra antiga (se existir)..." -ForegroundColor Yellow
netsh advfirewall firewall delete rule name="$ruleName" 2>$null

# Adiciona nova regra
Write-Host "✅ Adicionando nova regra no firewall..." -ForegroundColor Green
netsh advfirewall firewall add rule name="$ruleName" dir=in action=allow protocol=TCP localport=$port

Write-Host ""
Write-Host "✅ Firewall configurado com sucesso!" -ForegroundColor Green
Write-Host ""
Write-Host "📱 Agora você pode acessar de outros dispositivos:" -ForegroundColor Cyan

# Obtém o IP local
$ip = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Wi-Fi*","Ethernet*" | Where-Object {$_.IPAddress -like "192.168.*" -or $_.IPAddress -like "10.*"} | Select-Object -First 1).IPAddress

if ($ip) {
    Write-Host "   http://${ip}:${port}" -ForegroundColor White
} else {
    Write-Host "   (Não foi possível detectar IP local automaticamente)" -ForegroundColor Yellow
    Write-Host "   Execute: ipconfig" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "💡 Certifique-se de que:" -ForegroundColor Cyan
Write-Host "   1. O servidor Vite está rodando (npm run dev)" -ForegroundColor White
Write-Host "   2. Seu celular está na mesma rede Wi-Fi" -ForegroundColor White
Write-Host "   3. LM Studio está configurado para aceitar conexões de rede" -ForegroundColor White
Write-Host ""
