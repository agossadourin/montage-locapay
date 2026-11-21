# Historique des versions

## 0.8.0 — 2026-11-21
- **On commence par la timeline** : l'app s'ouvre sur l'éditeur. « ＋ Nouveau projet » : on dépose une ou plusieurs vidéos, elles arrivent aussitôt sur la piste vidéo (avec la forme d'onde) pour le prémontage — couper, réordonner, raccourcir, supprimer.
- **✨ Montage automatique dans la timeline** : sur ce qui est gardé, coupe les blancs et hésitations, ajoute sous-titres, écrans de couleur et illustrations (style + identité des Paramètres). La transcription est gardée dans le projet : relancer est rapide.
- **Piste ⚠️ À vérifier** : passages incompris (fon, bruit) et reprises sont signalés **sans être coupés**. Pour chacun : ▶︎ Écouter, ✂️ Couper ce passage, 💬 ajouter un sous-titre (traduction), ✓ Garder tel quel.
- Illustrations : 🔄 Autre proposition, 🔍 nouvelle recherche avec vignettes, 📁 votre fichier — directement dans l'éditeur.
- Le parcours classique (page Paramètres / mode classique) reste disponible.

## 0.7.0 — 2026-11-21
- **✂️ Éditeur façon CapCut** : après chaque montage automatique, bouton « Retoucher dans l'éditeur ». Aperçu en direct (sous-titres animés, illustrations, écrans de couleur, logo, écran de fin, musique) et 5 pistes : Vidéo (avec forme d'onde de la voix), Sous-titres, Illustrations, Écrans, Musique.
  - Glisser pour déplacer, tirer les bords pour raccourcir, **S** pour couper un plan, **Suppr** pour supprimer, **⌘Z / ⇧⌘Z** annuler/rétablir, **Espace** lecture, flèches image par image.
  - Inspecteur : texte et mot clé d'un sous-titre, cadrage (zoom) d'un plan, couleur d'un écran, remplacement d'une illustration, volume et départ de la musique ; ajout de sous-titres, écrans, illustrations, musique.
  - Sous-titres, illustrations et écrans restent calés sur la voix quand on raccourcit ou réordonne les plans.
  - Enregistrement automatique ; **Exporter** refait la vidéo finale (lecture QuickTime / Finder).
- L'app s'ouvre dans une **fenêtre Chrome dédiée** (sans barre d'adresse) quand Chrome est installé : lecture vidéo fiable. Repli sur la fenêtre WebKit sinon.
- Les vidéos sources sont conservées (`Montages Locapay/.sources`) pour pouvoir rouvrir les projets plus tard.

## 0.6.0 — 2026-11-21
- **⚙️ Paramètres** en onglets : **Identité visuelle** (nom, couleurs, logo, polices — enregistrée et appliquée à tous les styles), **Style**, **Clés API**, **Avancé**.
- **Profils de style** : un style = rythme des coupes, zooms, sous-titres (position, taille, mots à la fois, mot clé, casse, animation), étalonnage, écrans de couleur, écran de fin, densité d'illustrations. Styles enregistrables, ajustables, sélectionnables.
- **Copier le style d'une vidéo** : analyse d'une vidéo de référence (coupes, écrans de couleur, étalonnage, écran de fin, sous-titres par OCR Apple Vision) → nouveau style, appliqué avec votre identité. Plus fin avec une clé Claude (lecture visuelle des images).
- **Illustrations (B-roll)** : aux moments où l'on parle de quelque chose de concret (loyer, téléphone, maison…), une image ou vidéo libre de droits est proposée (Pexels / Pixabay, clés gratuites ; choix des moments par Claude si une clé est fournie). Validation : autre proposition, votre propre fichier, recherche modifiable, retrait. Insertion plein écran (léger zoom sur les photos), sous-titres conservés par-dessus.
- Nouveaux étalonnages : naturel, chaud, contrasté, froid, désaturé.

## 0.5.0 — 2026-11-21
- **Corrections de mots, version pro** : bouton ➕ → on choisit le **moment** (une phrase précise, avec son minutage, ou « partout »), puis le ou les **mots** dans la phrase, puis la **correction** (vide = supprimer ces mots). Écoute du moment, liste des corrections, suppression d'une ligne.
- **Dictionnaire permanent** : les corrections « dans toutes mes vidéos » (ex. Locapé → Locapay) sont mémorisées et appliquées automatiquement aux prochaines vidéos.
- Les choix faits dans la validation des passages sont conservés quand on ajoute des corrections.

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
