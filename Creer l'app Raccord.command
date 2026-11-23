#!/bin/bash
# Crée (ou recrée) l'app « Raccord » dans Applications — sans rien télécharger.
cd "$(dirname "$0")" || exit 1
bash macos/build_app.sh && echo && echo "✅ Ouvrez « Raccord » depuis le Launchpad ou le dossier Applications."
read -r -p "Appuyez sur Entrée pour fermer…"
