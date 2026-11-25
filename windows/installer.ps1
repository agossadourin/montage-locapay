# Installation de Raccord sous Windows 10 / 11 (64 bits).
# Lancée par Raccord-Setup.exe, ou à la main par « Installer Raccord (Windows).bat ».
# Tout est installé dans le dossier de Raccord (outils\, .venv\) : rien n'est ajouté au système.
param(
    [switch]$DepuisSetup,      # appelée par Raccord-Setup.exe (les raccourcis sont faits par le Setup)
    [switch]$SansModele,       # ne pas télécharger le modèle de transcription (tests)
    [switch]$SansDetourage,    # ne pas installer le détourage automatique des photos
    [switch]$SansPause         # ne jamais attendre une touche (tests automatiques)
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"          # Invoke-WebRequest est bien plus rapide sans barre de progression
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}

$Racine = Split-Path -Parent $PSScriptRoot
Set-Location $Racine
$Outils = Join-Path $Racine "outils"
New-Item -ItemType Directory -Force $Outils | Out-Null
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Outils "python"
$env:UV_CACHE_DIR = Join-Path $Outils "cache"
$env:UV_LINK_MODE = "copy"
$Pause = -not $SansPause -and -not $env:CI -and [Environment]::UserInteractive

function Etape($texte) { Write-Host ""; Write-Host "-> $texte" -ForegroundColor Cyan }
function Ok($texte) { Write-Host "   OK : $texte" -ForegroundColor Green }
function Telecharger($url, $dest) {
    for ($i = 1; $i -le 4; $i++) {
        try { Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing; return }
        catch { if ($i -eq 4) { throw "Téléchargement impossible ($url) : $_" }; Start-Sleep -Seconds (3 * $i) }
    }
}
function Verifier($quoi) { if ($LASTEXITCODE -ne 0) { throw "$quoi a échoué (code $LASTEXITCODE)." } }

try {
    Write-Host "=============================================="
    Write-Host "  Installation de Raccord (Windows)"
    Write-Host "  Comptez 10 à 20 minutes selon la connexion."
    Write-Host "=============================================="
    if (-not [Environment]::Is64BitOperatingSystem) { throw "Raccord demande Windows 64 bits." }

    # 1) uv : installe Python dans le dossier de Raccord, sans toucher au système
    $Uv = Join-Path $Outils "uv\uv.exe"
    if (-not (Test-Path $Uv)) {
        Etape "Installation de uv (Python)..."
        $zip = Join-Path $env:TEMP "raccord-uv.zip"
        Telecharger "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" $zip
        Expand-Archive $zip -DestinationPath (Join-Path $Outils "uv") -Force
        Remove-Item $zip -Force
    }
    Ok "uv"

    # 2) ffmpeg (traitement vidéo)
    $FfBin = Join-Path $Outils "ffmpeg\bin"
    if (-not (Test-Path (Join-Path $FfBin "ffmpeg.exe"))) {
        Etape "Téléchargement de ffmpeg (traitement vidéo, environ 100 Mo)..."
        $zip = Join-Path $env:TEMP "raccord-ffmpeg.zip"
        $tmp = Join-Path $env:TEMP "raccord-ffmpeg"
        Telecharger "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" $zip
        if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
        Expand-Archive $zip -DestinationPath $tmp -Force
        $exe = Get-ChildItem $tmp -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
        if (-not $exe) { throw "ffmpeg.exe introuvable dans l'archive." }
        New-Item -ItemType Directory -Force $FfBin | Out-Null
        Copy-Item (Join-Path $exe.DirectoryName "*.exe") $FfBin -Force
        Remove-Item $zip, $tmp -Recurse -Force
    }
    $env:PATH = "$FfBin;$env:PATH"
    Ok "ffmpeg"

    # 3) Python et bibliothèques
    Etape "Installation de Python et des bibliothèques (quelques minutes)..."
    & $Uv venv --python 3.11 --allow-existing .venv; Verifier "La création de l'environnement Python"
    $Py = Join-Path $Racine ".venv\Scripts\python.exe"
    & $Uv pip install --python $Py -r requirements\windows.txt; Verifier "L'installation des bibliothèques"
    Ok "bibliothèques"
    if (-not $SansDetourage) {
        Etape "Détourage automatique des photos (facultatif, environ 300 Mo)..."
        & $Uv pip install --python $Py -r requirements\windows-detourage.txt
        if ($LASTEXITCODE -ne 0) { Write-Warning "Le détourage n'a pas pu être installé : Raccord fonctionne sans." } else { Ok "détourage" }
    }

    # 4) Modèle de transcription (une seule fois)
    if (-not $SansModele) {
        Etape "Téléchargement du modèle de transcription (environ 1,6 Go, une seule fois)..."
        & $Py -X utf8 -c "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo', device='cpu', compute_type='int8')"
        if ($LASTEXITCODE -ne 0) { Write-Warning "Le modèle sera téléchargé au premier montage." } else { Ok "modèle" }
    }

    # 5) Vérification rapide
    & $Py -X utf8 -c "import sys; sys.path.insert(0, 'app'); import chemins, systeme, gradio, faster_whisper; print('   Dossier des vidéos :', chemins.DOSSIER_APP)"
    Verifier "La vérification de Raccord"

    & $Uv cache clean 2>$null | Out-Null                 # libère 1 à 2 Go de fichiers d'installation

    # 6) Raccourcis (installation à la main ; Raccord-Setup.exe fait les siens)
    if (-not $DepuisSetup) {
        $Pyw = Join-Path $Racine ".venv\Scripts\pythonw.exe"
        $Shell = New-Object -ComObject WScript.Shell
        foreach ($dossier in @([Environment]::GetFolderPath("Desktop"), (Join-Path ([Environment]::GetFolderPath("Programs")) ""))) {
            $lnk = $Shell.CreateShortcut((Join-Path $dossier "Raccord.lnk"))
            $lnk.TargetPath = $Pyw
            $lnk.Arguments = "-X utf8 `"$Racine\app\fenetre.py`""
            $lnk.WorkingDirectory = $Racine
            $lnk.IconLocation = "$Racine\windows\Raccord.ico"
            $lnk.Description = "Raccord : le montage face caméra"
            $lnk.Save()
        }
        Ok "icônes sur le Bureau et dans le menu Démarrer"
    }

    Write-Host ""
    Write-Host "=============================================="
    Write-Host "  Installation terminée !" -ForegroundColor Green
    Write-Host "  Ouvrez Raccord depuis le menu Démarrer ou le Bureau."
    Write-Host "=============================================="
    if ($Pause -and -not $DepuisSetup) { Read-Host "Appuyez sur Entrée pour fermer" | Out-Null }
    exit 0
}
catch {
    Write-Host ""
    Write-Host "ERREUR : $_" -ForegroundColor Red
    Write-Host "Relancez l'installation : elle reprend là où elle s'est arrêtée."
    if ($Pause) { Read-Host "Appuyez sur Entrée pour fermer" | Out-Null }
    exit 1
}
