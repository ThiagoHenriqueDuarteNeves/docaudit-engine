# =============================================================================
# PR.ps1 - Script de Automacao para Pull Request
# Valida localmente (act) -> Commit -> Push -> Cria PR
# =============================================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$Message,
    
    [string]$TargetBranch = "dev"
)

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "   AUTOMACAO DE PULL REQUEST" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Verificar branch atual
$currentBranch = git branch --show-current
Write-Host "[INFO] Branch atual: $currentBranch" -ForegroundColor Yellow
Write-Host "[INFO] Branch destino: $TargetBranch" -ForegroundColor Yellow
Write-Host "[INFO] Mensagem: $Message" -ForegroundColor Yellow
Write-Host ""

# =============================================================================
# ETAPA 1: Rodar ACT (Testes + Seguranca)
# =============================================================================
Write-Host "[1/4] Rodando validacao local (act)..." -ForegroundColor Cyan
Write-Host "      Isso pode levar alguns minutos..." -ForegroundColor Gray

.\act -j test,security --rm

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERRO] Validacao local FALHOU!" -ForegroundColor Red
    Write-Host "       Corrija os erros acima antes de continuar." -ForegroundColor Red
    Write-Host ""
    exit 1
}

Write-Host "[OK] Validacao local passou!" -ForegroundColor Green
Write-Host ""

# =============================================================================
# ETAPA 2: Git Add + Commit
# =============================================================================
Write-Host "[2/4] Fazendo commit das mudancas..." -ForegroundColor Cyan

git add -A
git commit -m "$Message" --no-verify

if ($LASTEXITCODE -ne 0) {
    Write-Host "[AVISO] Nada para commitar ou erro no commit." -ForegroundColor Yellow
}

Write-Host "[OK] Commit realizado!" -ForegroundColor Green
Write-Host ""

# =============================================================================
# ETAPA 3: Git Push
# =============================================================================
Write-Host "[3/4] Fazendo push para origin/$currentBranch..." -ForegroundColor Cyan

git push -u origin $currentBranch --no-verify

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERRO] Falha no push!" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Push realizado!" -ForegroundColor Green
Write-Host ""

# =============================================================================
# ETAPA 4: Criar Pull Request
# =============================================================================
Write-Host "[4/4] Criando Pull Request..." -ForegroundColor Cyan

# Verificar se gh esta instalado
$ghInstalled = Get-Command gh -ErrorAction SilentlyContinue
if (-not $ghInstalled) {
    Write-Host "[AVISO] GitHub CLI (gh) nao instalado." -ForegroundColor Yellow
    Write-Host "        Instale com: winget install GitHub.cli" -ForegroundColor Yellow
    Write-Host "        Depois rode: gh auth login" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "[INFO] Push feito! Crie o PR manualmente no GitHub." -ForegroundColor Cyan
    exit 0
}

# Criar PR
gh pr create --base $TargetBranch --head $currentBranch --title "$Message" --body "Criado automaticamente via pr.ps1"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=============================================" -ForegroundColor Green
    Write-Host "   PULL REQUEST CRIADO COM SUCESSO!" -ForegroundColor Green
    Write-Host "=============================================" -ForegroundColor Green
} else {
    Write-Host "[AVISO] Erro ao criar PR (pode ja existir)." -ForegroundColor Yellow
    Write-Host "        Verifique no GitHub." -ForegroundColor Yellow
}

Write-Host ""
