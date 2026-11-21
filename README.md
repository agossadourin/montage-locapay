# 🎬 Montage Locapay

Montage vidéo automatique « style Locapay » pour vidéos face caméra (Reels, TikTok, Shorts).

On donne une **vidéo brute**, l'outil :

1. **transcrit** la voix mot par mot (Whisper, en local sur le Mac) ;
2. **coupe** les blancs et les hésitations (« euh », « hum »…) ;
3. ajoute les **sous-titres animés mot par mot** : italique fin + mot clé en **GRAS CAPITALES** ;
4. alterne les **recadrages** (punch-in) avec un léger zoom continu ;
5. insère des **écrans de couleur** de marque, le **logo** et un **écran de fin** ;
6. ajoute des **effets sonores légers** et, en option, une **musique de fond** qui baisse quand on parle ;
7. exporte une vidéo **verticale 1080×1920** prête à publier, plus les sous-titres `.srt` et la transcription `.txt`.

---

## Installation sur Mac

```bash
git clone https://github.com/agossadourin/montage-locapay.git ~/Documents/montage-locapay
cd ~/Documents/montage-locapay
./Installer.command
```

L'installateur met en place ffmpeg (Homebrew), Python (uv), les bibliothèques, le modèle de transcription (~1,5 Go, une seule fois) et crée l'app **Montage Locapay** dans le dossier Applications.

> Le dépôt est privé : pour le `git clone`, connectez-vous une fois avec `brew install gh && gh auth login`, ou utilisez GitHub Desktop.

## Utilisation

Ouvrez **Montage Locapay** (Launchpad / Applications / Spotlight) : l'app s'ouvre sur l'**éditeur**.

1. **＋ Nouveau projet** : déposez une ou plusieurs vidéos. Elles arrivent sur la piste 🎬 Vidéo.
2. **Prémontage** : <kbd>S</kbd> pour couper à la tête de lecture, <kbd>Suppr</kbd> pour enlever, glissez pour réordonner, tirez les bords pour raccourcir.
3. **✨ Montage automatique** : blancs coupés, sous-titres, écrans de couleur, illustrations. Les passages douteux (fon, reprises) apparaissent sur la piste rouge **⚠️ À vérifier** : écoutez, coupez, traduisez ou gardez.
4. Retouchez, puis **⬆️ Exporter** : la vidéo arrive dans **Vidéos › Montages Locapay**.

Le **mode classique** (et les **⚙️ Paramètres** : identité, style, clés) reste accessible par le lien en haut de l'éditeur.

**Validation des passages** (activée par défaut) : au premier clic sur **Monter la vidéo**, l'outil liste les phrases et signale ⚠️ les **passages incompris** (bruit, fon ou autre langue), les **prises répétées** et les **faux départs**. Cliquez sur une ligne pour l'écouter, cochez/décochez **Garder** et **Sous-titres**, corrigez le texte — pour un passage en fon, tapez la traduction française, elle s'affichera en sous-titres — puis recliquez sur **Monter la vidéo**.

**⚙️ Paramètres** :
- **🎨 Identité visuelle** : nom, couleurs, logo, polices de votre marque (bouton 💾). Appliquée à tous les styles.
- **🎞 Style** : choisissez un style, ajustez-le (🎚), ou **copiez le style d'une vidéo** : déposez une vidéo dont vous aimez le montage, l'outil l'analyse et crée un style réutilisable.
- **🤖 IA** (facultative) : **Ollama** — gratuite, sur votre Mac (installez-la avec `Installer IA locale (Ollama).command`) — ou **Claude** (payante). Sans IA, des règles automatiques font le travail.
- **🔑 Clés API** (facultatives) : **Pexels** / **Pixabay** (gratuites) pour trouver des images d'illustration ; **Claude** (payante, quelques centimes par vidéo) pour un choix des moments et une analyse de style plus fins.

**🖼 Illustrations** : au premier clic sur **Monter**, l'outil propose des images/vidéos aux moments où l'on parle de quelque chose de concret. Cliquez sur une illustration puis **🔄 Autre proposition** ou **📁 Mon fichier** ; modifiez la recherche puis **🔍 Relancer** ; décochez **Garder** pour la retirer.

**✂️ Retoucher comme dans CapCut** : après le montage, cliquez sur **Retoucher dans l'éditeur (timeline)** (ou lien **l'éditeur** en haut de page pour rouvrir un projet). Aperçu en direct et pistes Vidéo / Sous-titres / Illustrations / Écrans / Musique : glisser pour déplacer, bords pour raccourcir, **S** couper, **Suppr** supprimer, **⌘Z** annuler, **Espace** lecture. Cliquez sur un élément pour le modifier dans le panneau de droite. **Exporter** refait la vidéo.

**🎵 Musique** : dans l'éditeur, **＋ Musique** → choisissez une ambiance, écoutez, **Utiliser** (musiques libres pour usage commercial, via Openverse). Si l'artiste doit être crédité, le texte à mettre en description est fourni et enregistré à côté de la vidéo.

**Corriger un mot** : **✏️ Corrections de mots › ➕** — choisissez le **moment** (une phrase précise, ou partout), cliquez sur le ou les **mots**, tapez la **correction** (vide = supprimer), **✔ Ajouter**, puis **Monter la vidéo**. Les corrections « dans toutes mes vidéos » sont mémorisées (`Vidéos › Montages Locapay › .dictionnaire_corrections.json`).

**Plusieurs rushs ?** Onglet **Plusieurs vidéos (prémontage)** : déposez-les, réglez l'ordre, le début et la fin de chacun (en secondes), décochez ceux à ignorer, cliquez sur **Assembler**, puis sur **Monter la vidéo**. Les prémontages sont gardés dans **Vidéos › Montages Locapay › prémontages**.

Sans l'app, `Lancer Montage.command` ouvre la même interface dans le navigateur.

## Mettre à jour

Double-cliquez sur **`Mettre à jour.command`** (ou `git pull` dans le dossier). L'app exécute directement le code du dépôt : une modification de `app/` est prise en compte au prochain lancement.

---

## Organisation du dépôt

| Chemin | Rôle |
|---|---|
| `app/montage_auto.py` | **Le moteur** : transcription, plan de montage (coupes, groupes de sous-titres, mots clés, écrans de couleur), rendu image par image, effets sonores, mixage audio. |
| `app/interface.py` | Interface (Gradio) : paramètres, validation, corrections, illustrations, bouton Monter. |
| `app/configuration.py` | Paramètres persistants (identité, clés, profils de style) dans `Vidéos › Montages Locapay › .parametres`. |
| `app/analyse_style.py` | Analyse d'une vidéo de référence → profil de style. |
| `app/illustrations.py` | Choix des moments à illustrer, recherche Pexels/Pixabay, téléchargement. |
| `app/musique.py` | Recherche de musique libre (Openverse, usage commercial) et crédits. |
| `app/ia.py` | Appels facultatifs à Claude (API Anthropic). |
| `app/fenetre.py` | Ouvre l'app dans une fenêtre Chrome dédiée (ou WebKit/pywebview à défaut). |
| `app/projet.py` | Projet éditable (pistes) : création depuis un montage, conversion en plan, rendu. |
| `app/editeur.py` | Serveur de l'éditeur : projet, médias, export en tâche de fond. |
| `app/editeur.html` | L'éditeur timeline (HTML/JS, sans dépendance). |
| `app/polices/`, `app/logo_locapay.png` | Polices (Playfair Display, Montserrat — licence OFL) et logo. |
| `macos/build_app.sh` | Crée `Montage Locapay.app` (lanceur léger qui pointe vers ce dossier). |
| `macos/AppIcon.icns` | Icône de l'app. |
| `requirements/` | Dépendances par machine (`mac-arm64`, `mac-x86_64`, `dev`). |
| `colab/` | Version Google Colab (`build_nb.py` régénère le notebook depuis le moteur). |
| `tests/` | Tests automatiques (lancés par GitHub Actions à chaque push). |

### Où modifier quoi

- **Style des sous-titres** (polices, tailles, ombre, animation) : `image_mot`, `mise_en_page`, `coller_anime` dans `montage_auto.py`.
- **Choix du mot en gras** : `STOP` (mots ignorés) et la sélection `cle` dans `construire_plan`.
- **Découpage des groupes de mots** : règles dans `construire_plan` (pause > 0,30 s, ponctuation, 4 mots max, `FAIBLES`).
- **Rythme des coupes / zooms** : `Reglages.duree_plan_max`, `Reglages.zoom`, `cycle`.
- **Écrans de couleur** : nombre et position dans `construire_plan` (bloc « écrans de couleur »).
- **Effets sonores** : fonctions `sfx_*` et la liste `evts` dans `monter`.
- **Styles** : champs de `ProfilStyle` (`configuration.py`) ↔ `Reglages` (`montage_auto.py`) ; étalonnages dans `ETALONNAGES`.
- **Analyse de référence** : seuils et règles dans `analyse_style.py` (`est_ecran_uni`, `choisir_etalonnage`, `mesures_sous_titres`).
- **Illustrations** : dictionnaire `MOTS_IMAGES` (mot → recherche en anglais) et `choisir_moments` dans `illustrations.py` ; rendu `Illustration` dans `montage_auto.py`.
- **Éditeur timeline** : `editeur.html` (aperçu : `rendreScene`, pistes : `dessinerTimeline`, gestes : bloc « glisser / rogner », inspecteur : `inspecter`) ; format du projet décrit en tête de `projet.py`.
- **Corrections de mots** : `corriger` dans `montage_auto.py` (par index de mots ou par expression), éditeur ➕ dans `interface.py` (bloc « corrections de mots »).
- **Détection des passages à valider** : `analyser` (seuil `SEUIL_CONFIANCE`, règles de reprise) et `appliquer_validation` dans `montage_auto.py`.
- **Prémontage** (assemblage de plusieurs rushs) : `premontage` dans `montage_auto.py`, onglet « Plusieurs vidéos » dans `interface.py`.
- **Nouveaux réglages dans l'interface** : ajouter le champ dans `Reglages`, puis le composant dans `interface.py`.

### Développer

```bash
uv pip install --python .venv/bin/python -r requirements/dev.txt
.venv/bin/python -m pytest -q                         # tests
.venv/bin/python app/montage_auto.py brut.mp4 sortie.mp4   # en ligne de commande
python colab/build_nb.py                              # régénérer le notebook Colab
```

Versionnage : mettre à jour `VERSION` et `CHANGELOG.md`, puis `git tag vX.Y.Z`.

Journal de l'app (en cas de problème) : `~/Library/Logs/Montage Locapay.log`.
