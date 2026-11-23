#!/bin/bash
# Installe l'IA locale gratuite (Ollama + modèle qwen2.5vl:3b, ≈ 3 Go) et l'active dans Raccord.
cd "$(dirname "$0")" || exit 1
set -e
trap 'echo; echo "❌ L installation de l IA locale s est arrêtée (voir le message ci-dessus)."; read -r -p "Entrée pour fermer…"' ERR
MODELE="qwen2.5vl:3b"
for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)"; done
command -v brew >/dev/null 2>&1 || { echo "❌ Homebrew est introuvable : lancez d abord Installer.command."; false; }

echo "=============================================="
echo "  IA locale gratuite (Ollama) pour Raccord"
echo "=============================================="
if ! command -v ollama >/dev/null 2>&1; then
  echo "➡️  Installation d Ollama…"
  brew install ollama
fi
echo "➡️  Démarrage d Ollama (il se relancera tout seul à chaque démarrage du Mac)…"
brew services start ollama >/dev/null 2>&1 || (nohup ollama serve >/dev/null 2>&1 &)
for i in $(seq 1 30); do curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break; sleep 1; done
curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1 || { echo "❌ Ollama ne démarre pas."; false; }
echo "✅ Ollama fonctionne"

echo "➡️  Téléchargement du modèle $MODELE (≈ 3 Go, une seule fois)…"
ollama pull "$MODELE"
echo "✅ Modèle prêt"

if [ -x .venv/bin/python ]; then
  .venv/bin/python -c "
import sys; sys.path.insert(0, 'app')
import configuration as C
c = C.charger_config(); c.setdefault('ia', {})['fournisseur'] = 'ollama'; C.sauver_config(c)
print('✅ IA locale activée dans Raccord (Paramètres › Clés API)')"
fi
echo
echo "Terminé. Relancez Raccord."
read -r -p "Appuyez sur Entrée pour fermer…"
