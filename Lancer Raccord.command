#!/bin/bash
# Ouvre l'interface de montage dans le navigateur
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
if [ ! -x .venv/bin/python ]; then
  echo "⚠️  Lancez d'abord « Installer.command » (une seule fois)."
  read -r -p "Appuyez sur Entrée pour fermer…"
  exit 1
fi
echo "🎬 Raccord"
echo "   L'interface s'ouvre dans votre navigateur (adresse : http://127.0.0.1:7860)."
echo "   Laissez cette fenêtre ouverte pendant que vous travaillez ; fermez-la pour arrêter."
echo
.venv/bin/python app/interface.py
