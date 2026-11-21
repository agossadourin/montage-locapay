# Historique des versions

## 0.4.0 — 2026-11-21
- **Validation avant montage** : au premier clic sur « Monter », l'outil découpe la transcription en phrases et signale celles à vérifier — **passages incompris** (confiance Whisper faible : bruit, **fon** ou autre langue), **prises répétées** et **faux départs** (il propose de garder la dernière prise). On écoute chaque phrase d'un clic, on choisit Garder / Sous-titres, on corrige le texte (ou on tape la traduction française d'un passage en fon, affichée en sous-titres), puis on reclique sur « Monter ».
- Transcription : conserve la confiance de Whisper pour chaque mot.

## 0.3.0 — 2026-11-21
- **Prémontage** : onglet « Plusieurs vidéos » — on dépose plusieurs rushs, on règle l'ordre, le début et la fin de chacun, on décoche ceux à ignorer, puis « Assembler » les met bout à bout (recadrage vertical, son harmonisé) avant le montage automatique.
- **Lecture fiable** : bouton « ▶️ Lire dans QuickTime » et ouverture automatique de la vidéo montée dans QuickTime à la fin (désactivable).

## 0.2.0 — 2026-11-21
- App Mac **Montage Locapay** : fenêtre native (pywebview), icône, rangée dans Applications.
- `Mettre à jour.command` : `git pull` + dépendances + reconstruction de l'app.
- Dépendances par architecture (`requirements/`), tests automatiques et intégration continue GitHub Actions.
- Installateur plus robuste (uv via Homebrew, nouvelles tentatives en cas de coupure réseau).

## 0.1.0 — 2026-11-20
- Moteur de montage automatique : transcription Whisper (mlx / faster-whisper / openai-whisper), coupe des blancs et hésitations, sous-titres animés mot par mot avec mot clé en gras, recadrages alternés, écrans de couleur, logo, écran de fin, effets sonores légers, musique avec ducking, export 1080×1920 + `.srt` + `.txt`.
- Interface navigateur (Gradio) et notebook Google Colab.
