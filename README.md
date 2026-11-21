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

Ouvrez **Montage Locapay** (Launchpad / Applications / Spotlight). Glissez la vidéo, cliquez sur **Monter la vidéo**. Le résultat est enregistré dans **Vidéos › Montages Locapay** et s'ouvre dans QuickTime.

**Plusieurs rushs ?** Onglet **Plusieurs vidéos (prémontage)** : déposez-les, réglez l'ordre, le début et la fin de chacun (en secondes), décochez ceux à ignorer, cliquez sur **Assembler**, puis sur **Monter la vidéo**. Les prémontages sont gardés dans **Vidéos › Montages Locapay › prémontages**.

Sans l'app, `Lancer Montage.command` ouvre la même interface dans le navigateur.

## Mettre à jour

Double-cliquez sur **`Mettre à jour.command`** (ou `git pull` dans le dossier). L'app exécute directement le code du dépôt : une modification de `app/` est prise en compte au prochain lancement.

---

## Organisation du dépôt

| Chemin | Rôle |
|---|---|
| `app/montage_auto.py` | **Le moteur** : transcription, plan de montage (coupes, groupes de sous-titres, mots clés, écrans de couleur), rendu image par image, effets sonores, mixage audio. |
| `app/interface.py` | Interface (Gradio) : réglages, bouton Monter, aperçu. |
| `app/fenetre.py` | Ouvre l'interface dans une fenêtre Mac native (pywebview). |
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
