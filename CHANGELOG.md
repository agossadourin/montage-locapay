# Historique des versions

## 0.14.1 — 2026-11-21
- Gemini : message clair quand la clé est en offre gratuite (la création d'images demande d'activer la facturation), et le montage automatique n'insiste plus pour chaque moment après un refus.

## 0.14.0 — 2026-11-21
- **✨ Illustrations créées par Gemini** (facultatif, payant ≈ 0,03 $ l'image) : au lieu de chercher des photos existantes, Gemini crée pour chaque passage une **image verticale** adaptée à ce qui est dit et à votre contexte (Bénin, Cotonou, location…, modifiable).
  - ⚙️ Paramètres › Clés API : clé Gemini, bouton « Tester », choix de la source des illustrations du montage automatique (banques gratuites ou Gemini), contexte donné à Gemini.
  - Éditeur : bouton **✨ Image IA** (image pour le passage sous la tête de lecture) et, dans une illustration, consigne modifiable + **✨ Créer l'image**.
  - Images mises en cache : régénérer la même consigne ne coûte rien. En cas de refus (clé, facturation), les banques d'images prennent le relais et le message s'affiche dans l'éditeur.
- Correction : le choix de l'IA (Ollama / Claude) n'était pas conservé d'un lancement à l'autre.
- Paramètres : les clés affichées sont relues à chaque ouverture de la page.

## 0.13.1 — 2026-11-21
- Retour aux **coupes franches** entre les plans par défaut (aussi pour les projets déjà créés). Les transitions restent disponibles au besoin : petit rond entre deux plans dans l'éditeur, ou ⚙️ Paramètres › Style.
- L'aperçu de l'éditeur garde ses deux lecteurs en relais (pas de saccade aux changements de plan).

## 0.13.0 — 2026-11-21
- **Illustrations au bon format** : la recherche propose d'abord des images et vidéos **verticales** (portrait) ; les médias en paysage passent en dernier (badge « ▭ paysage » dans la grille), et le montage automatique ne les choisit plus d'office.
- **Plus de zoom excessif** : une illustration plus large que haute (votre propre fichier, ou un choix manuel) est montrée **en entier sur un fond flou** au lieu d'être recadrée. Réglable par illustration dans l'éditeur : *Automatique*, *Plein écran (bords rognés)* ou *Image entière sur fond flou*. Les illustrations déjà placées dans vos projets en profitent sans rien refaire.
- **⚙️ Paramètres** : bouton **← Retour à l'éditeur** toujours visible (on revient sur le projet ouvert), et le lien de l'éditeur ouvre directement la section Paramètres.

## 0.12.0 — 2026-11-21
- **Transitions fluides dans la vidéo exportée** : entre deux plans, au choix **fondu enchaîné**, **zoom**, **flash blanc**, **glissement** ou **coupe franche**. Quand deux plans viennent de la même prise (simple recadrage), le zoom glisse en douceur d'un cadrage à l'autre au lieu de sauter.
- Réglage dans **⚙️ Paramètres › Style** (type et durée), dans l'éditeur pour tout le projet (panneau de droite sans sélection), ou **plan par plan** : cliquez sur le petit rond entre deux plans de la piste 🎬, puis **▶︎ Voir**.
- **Aperçu de l'éditeur sans saccade** : deux lecteurs en relais — le plan suivant est déjà prêt quand l'actuel se termine, et les transitions sont visibles dans l'aperçu.

## 0.11.0 — 2026-11-21
- **Modifier un sous-titre directement sur la vidéo** : en pause, cliquez sur le texte dans l'aperçu, tapez, **Entrée** pour valider, **Échap** pour annuler (⌘Z pour revenir en arrière). Le mot clé est conservé s'il est toujours là.
- **⌥ + clic sur un mot** dans l'aperçu : il devient (ou n'est plus) le mot clé en GRAS.
- En pause, les mots pas encore prononcés restent visibles, estompés, pour pouvoir les corriger.

## 0.10.0 — 2026-11-21
- **🎵 Musique libre de droits, gratuite et sans clé** (Openverse) : dans l'éditeur, « ＋ Musique » → ambiances (Dynamique, Afro, Inspirant, Joyeux, Calme, Électro) ou recherche libre, écoute ▶️, « Utiliser ». Seuls les morceaux **autorisés pour un usage commercial** sont proposés.
- **Crédits** : si la licence demande de citer l'artiste (CC BY), le texte est affiché (bouton Copier), rappelé à l'export et enregistré à côté de la vidéo (`…_credits.txt`).
- Plus aucune statistique envoyée par l'interface (Gradio).

## 0.9.0 — 2026-11-21
- **IA locale gratuite avec Ollama** : alternative à Claude pour choisir les moments à illustrer et analyser un style (modèle `qwen2.5vl:3b`, texte + images, ≈ 3 Go, adapté à un Mac 8 Go ; mémoire libérée après chaque usage). Installation : « Installer IA locale (Ollama).command ».
- Paramètres › Clés API : choix de l'IA (Aucune / Ollama / Claude) et bouton « 🔌 Tester Ollama ».
- La mémoire du modèle de transcription est libérée après usage (Mac 8 Go).

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
