# Installe l'IA locale gratuite (Ollama + modèle qwen2.5vl:3b, environ 3 Go) et l'active dans Raccord.
param([switch]$SansPause)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$Modele = "qwen2.5vl:3b"
$Racine = Split-Path -Parent $PSScriptRoot
$Pause = -not $SansPause -and -not $env:CI -and [Environment]::UserInteractive

function Trouver-Ollama {
    $c = Get-Command ollama -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    $p = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path $p) { return $p }
    return $null
}
function Repond { try { Invoke-WebRequest "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 2 | Out-Null; $true } catch { $false } }

try {
    Write-Host "=============================================="
    Write-Host "  IA locale gratuite (Ollama) pour Raccord"
    Write-Host "=============================================="
    $Ollama = Trouver-Ollama
    if (-not $Ollama) {
        Write-Host "-> Téléchargement d'Ollama..." -ForegroundColor Cyan
        $setup = Join-Path $env:TEMP "OllamaSetup.exe"
        Invoke-WebRequest "https://ollama.com/download/OllamaSetup.exe" -OutFile $setup -UseBasicParsing
        Write-Host "-> Installation d'Ollama (une fenêtre peut s'ouvrir)..." -ForegroundColor Cyan
        Start-Process $setup -ArgumentList "/SILENT", "/NORESTART" -Wait
        $Ollama = Trouver-Ollama
        if (-not $Ollama) { throw "Ollama ne s'est pas installé." }
    }
    if (-not (Repond)) { Start-Process $Ollama -ArgumentList "serve" -WindowStyle Hidden }
    for ($i = 0; $i -lt 30 -and -not (Repond); $i++) { Start-Sleep -Seconds 1 }
    if (-not (Repond)) { throw "Ollama ne démarre pas." }
    Write-Host "   OK : Ollama fonctionne" -ForegroundColor Green

    Write-Host "-> Téléchargement du modèle $Modele (environ 3 Go, une seule fois)..." -ForegroundColor Cyan
    & $Ollama pull $Modele
    if ($LASTEXITCODE -ne 0) { throw "Le modèle n'a pas pu être téléchargé." }
    Write-Host "   OK : modèle prêt" -ForegroundColor Green

    $Py = Join-Path $Racine ".venv\Scripts\python.exe"
    if (Test-Path $Py) {
        Push-Location $Racine
        & $Py -X utf8 -c "import sys; sys.path.insert(0, 'app'); import configuration as C; c = C.charger_config(); c.setdefault('ia', {})['fournisseur'] = 'ollama'; C.sauver_config(c); print('   OK : IA locale activée dans Raccord')"
        Pop-Location
    }
    Write-Host ""
    Write-Host "Terminé. Relancez Raccord."
    if ($Pause) { Read-Host "Appuyez sur Entrée pour fermer" | Out-Null }
}
catch {
    Write-Host "ERREUR : $_" -ForegroundColor Red
    if ($Pause) { Read-Host "Appuyez sur Entrée pour fermer" | Out-Null }
    exit 1
}
