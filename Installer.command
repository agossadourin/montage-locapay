#!/bin/bash
# Installation du Montage automatique Locapay (à lancer une seule fois).
cd "$(dirname "$0")" || exit 1
DOSSIER="$(pwd)"
set -e
trap 'echo; echo "❌ L installation s est arrêtée (voir le message ci-dessus)."; read -r -p "Appuyez sur Entrée pour fermer…"' ERR

echo "=============================================="
echo "  Installation du Montage automatique Locapay"
echo "=============================================="
xattr -dr com.apple.quarantine "$DOSSIER" 2>/dev/null || true
chmod +x "$DOSSIER"/*.command "$DOSSIER"/macos/*.sh 2>/dev/null || true

charger_brew() {
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [ -x "$b" ]; then eval "$("$b" shellenv)"; return 0; fi
  done
  return 1
}

# 1) ffmpeg (traitement vidéo)
charger_brew || true
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  if ! command -v brew >/dev/null 2>&1; then
    echo
    echo "➡️  Installation de Homebrew (votre mot de passe Mac sera demandé, il ne s affiche pas)."
    /bin/bash -c "$(curl --http1.1 --retry 5 -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    charger_brew
  fi
  echo
  echo "➡️  Installation de ffmpeg…"
  brew install ffmpeg
fi
echo "✅ ffmpeg prêt"

# 2) uv (installe Python sans toucher au système)
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo
  echo "➡️  Installation de uv (Python)…"
  if command -v brew >/dev/null 2>&1; then
    brew install uv || true
  fi
  if ! command -v uv >/dev/null 2>&1; then
    curl --http1.1 --retry 5 --retry-delay 2 -LsSf https://astral.sh/uv/install.sh -o /tmp/uv-install.sh \
      && sh /tmp/uv-install.sh || true
    export PATH="$HOME/.local/bin:$PATH"
  fi
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "❌ uv n a pas pu être installé (problème de connexion). Relancez l installation dans un instant."
  false
fi
echo "✅ uv prêt"

# 3) Environnement Python + bibliothèques
echo
echo "➡️  Installation des bibliothèques (quelques minutes)…"
uv venv --python 3.11 --allow-existing .venv
ARCH="$(uname -m)"
uv pip install --python .venv/bin/python -r "requirements/mac-$ARCH.txt"
echo "✅ Bibliothèques installées"

# 4) Modèle de transcription (≈1,5 Go, une seule fois)
echo
echo "➡️  Téléchargement du modèle de transcription (≈1,5 Go, une seule fois)…"
if [ "$ARCH" = "arm64" ]; then
  .venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/whisper-large-v3-turbo')"
else
  .venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo', device='auto', compute_type='int8')"
fi
echo "✅ Modèle prêt"

# 5) App dans le dossier Applications
mkdir -p "$HOME/Movies/Montages Locapay"
echo
echo "➡️  Création de l app « Montage Locapay »…"
bash macos/build_app.sh

echo
echo "=============================================="
echo "  ✅ Installation terminée !"
echo "  Ouvrez « Montage Locapay » depuis le Launchpad ou le dossier Applications."
echo "  Vos vidéos montées vont dans : Vidéos › Montages Locapay"
echo "=============================================="
read -r -p "Appuyez sur Entrée pour fermer…"
