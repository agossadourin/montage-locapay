#!/bin/bash
# Récupère la dernière version depuis GitHub et met l'app à jour.
cd "$(dirname "$0")" || exit 1
set -e
trap 'echo; echo "❌ La mise à jour s est arrêtée (voir le message ci-dessus)."; read -r -p "Entrée pour fermer…"' ERR
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

echo "➡️  Récupération de la dernière version…"
BRANCHE="$(git ls-remote --symref origin HEAD | awk '/^ref:/ {sub("refs/heads/", "", $2); print $2}')"
git pull --ff-only origin "${BRANCHE:-main}"
echo "➡️  Mise à jour des bibliothèques…"
uv pip install --python .venv/bin/python -r "requirements/mac-$(uname -m).txt"
echo "➡️  Mise à jour de l app…"
bash macos/build_app.sh
echo
echo "✅ À jour : version $(cat VERSION). Relancez « Montage Locapay »."
read -r -p "Appuyez sur Entrée pour fermer…"
