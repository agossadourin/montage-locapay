"""Génère colab/Raccord.ipynb à partir de app/montage_auto.py.

À relancer après chaque modification du moteur :  python colab/build_nb.py
"""
import base64, gzip, json, os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
mod = base64.b64encode(gzip.compress(open(os.path.join(RACINE, "app", "montage_auto.py"), "rb").read(), mtime=0)).decode()
SORTIE = os.path.join(RACINE, "colab", "Raccord.ipynb")


def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src.strip("\n").splitlines(True)}


def code(src):
    return {"cell_type": "code", "metadata": {"cellView": "form"}, "execution_count": None,
            "outputs": [], "source": src.strip("\n").splitlines(True)}


cells = [
md("""
# Raccord — montage face caméra automatique

Chargez une **vidéo brute face caméra** : le notebook la **transcrit**, **coupe les blancs et les hésitations**, ajoute les **sous-titres animés mot par mot** (italique fin + mot clé en gras capitales), les **recadrages**, les **écrans de couleur** de votre marque, votre **logo**, des **effets sonores légers** et, si vous voulez, une **musique de fond** qui baisse quand on parle. Vous récupérez un MP4 vertical 1080×1920 prêt à publier.

**Mode d'emploi**
1. Vérifiez que le GPU est activé : menu **Exécution › Modifier le type d'exécution › T4 GPU** (gratuit).
2. Menu **Exécution › Tout exécuter**.
3. À l'étape 3, cliquez sur **Choisir des fichiers** et sélectionnez votre vidéo (et votre musique si vous l'avez cochée).
4. Le téléchargement de la vidéo montée démarre tout seul à la fin.

💡 Si un mot est mal transcrit (ex. « Locapé »), corrigez-le à l'étape 5 puis relancez seulement les étapes 5 et 6 (bouton ▶ à gauche de chaque étape).
"""),
code(f"""
#@title 1️⃣ Installation (1 à 2 minutes)
import os, subprocess, base64, gzip, sys
os.makedirs("/content/montage/polices", exist_ok=True)
subprocess.run("pip -q install -U openai-whisper", shell=True, check=True)
P = "/content/montage/polices"
for nom, url in [("serif.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf"),
                 ("gras.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf")]:
    subprocess.run(["wget", "-q", "-O", f"{{P}}/{{nom}}", url])
open("/content/montage/montage_auto.py", "wb").write(gzip.decompress(base64.b64decode("{mod}")))
sys.path.insert(0, "/content/montage")
import importlib, montage_auto as M; importlib.reload(M)
import torch
print("✅ Installation terminée —", "GPU actif 🚀" if torch.cuda.is_available() else "⚠️ pas de GPU (ça marchera, mais plus lentement)")
"""),
code("""
#@title 2️⃣ Réglages
#@markdown **Couleurs des écrans de couleur et de l'écran de fin**
couleur_1 = "#1F2340" #@param {type:"string"}
couleur_2 = "#FFA41B" #@param {type:"string"}
ecrans_de_couleur = 2 #@param {type:"slider", min:0, max:4, step:1}
#@markdown **Sous-titres et découpe**
position_sous_titres = 0.66 #@param {type:"slider", min:0.40, max:0.85, step:0.01}
couper_les_hesitations = True #@param {type:"boolean"}
pause_max_conservee = 0.45 #@param {type:"slider", min:0.20, max:1.00, step:0.05}
#@markdown **Son**
effets_sonores = "léger" #@param ["léger", "aucun"]
ajouter_une_musique = False #@param {type:"boolean"}
volume_musique = 0.18 #@param {type:"slider", min:0.05, max:0.50, step:0.01}
#@markdown **Logo** : cochez pour charger votre PNG (affiché en coin et sur l'écran de fin)
logo = False #@param {type:"boolean"}
#@markdown **Transcription** — mots rares à bien reconnaître, séparés par des virgules
vocabulaire = "" #@param {type:"string"}
modele = "turbo" #@param ["turbo", "large-v3", "medium", "small"]
#@markdown **Vidéo déjà sur Google Drive ?** Indiquez son chemin (ex. `MyDrive/Videos/rush.mp4`), sinon laissez vide.
video_sur_drive = "" #@param {type:"string"}

R = M.Reglages(couleur_1=couleur_1, couleur_2=couleur_2, nb_ecrans_couleur=ecrans_de_couleur,
               position_sous_titres=position_sous_titres, supprimer_hesitations=couper_les_hesitations,
               pause_max=pause_max_conservee, effets_sonores=effets_sonores, volume_musique=volume_musique,
               logo_en_coin=logo, fichier_logo="",
               police_serif="/content/montage/polices/serif.ttf", police_grasse="/content/montage/polices/gras.ttf")
print("✅ Réglages enregistrés")
"""),
code("""
#@title 3️⃣ Charger la vidéo (et la musique)
from google.colab import files
import shutil
os.makedirs("/content/montage/entree", exist_ok=True)
EXT_V = (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".3gp")
if video_sur_drive.strip():
    from google.colab import drive
    drive.mount("/content/drive")
    VIDEO = os.path.join("/content/drive", video_sur_drive.strip().lstrip("/"))
    assert os.path.exists(VIDEO), f"Fichier introuvable : {VIDEO}"
else:
    print("👉 Sélectionnez la vidéo brute :")
    up = files.upload()
    vids = [n for n in up if n.lower().endswith(EXT_V)]
    assert vids, "Aucune vidéo reconnue (formats : mp4, mov, m4v, avi, mkv, webm)."
    VIDEO = f"/content/montage/entree/{vids[0]}"
    shutil.move(vids[0], VIDEO)
MUSIQUE = None
if ajouter_une_musique:
    print("👉 Sélectionnez la musique (mp3, wav, m4a…) :")
    up = files.upload()
    if up:
        n = list(up)[0]; MUSIQUE = f"/content/montage/entree/{n}"; shutil.move(n, MUSIQUE)
if logo:
    print("👉 Sélectionnez votre logo (PNG, fond transparent de préférence) :")
    up = files.upload()
    if up:
        n = list(up)[0]; R.fichier_logo = f"/content/montage/entree/{n}"; shutil.move(n, R.fichier_logo)
DUREE = M.duree_video(VIDEO)
print(f"✅ Vidéo : {os.path.basename(VIDEO)} ({DUREE:.1f} s)" + (f" — musique : {os.path.basename(MUSIQUE)}" if MUSIQUE else ""))
"""),
code("""
#@title 4️⃣ Transcription automatique
mots_bruts = M.transcrire(VIDEO, modele=modele, langue="fr", vocabulaire=vocabulaire)
print("\\n📝 Transcription :\\n")
print(M.texte_transcription(mots_bruts))
"""),
code("""
#@title 5️⃣ Corrections (facultatif) et plan de montage
#@markdown Format : `mot_mal_reconnu=bon_mot; autre=correction` — ex. `Raccor=Raccord; démarcheur=démarcheurs`
corrections = "" #@param {type:"string"}
mots = M.appliquer_corrections(mots_bruts, corrections)
PLAN = M.construire_plan(mots, DUREE, R)
print(M.resume_plan(PLAN))
print("\\nLes mots en MAJUSCULES seront en gras. Relancez cette étape après une correction.")
"""),
code("""
#@title 6️⃣ Montage et téléchargement
from IPython.display import Video, display
os.makedirs("/content/montage/sortie", exist_ok=True)
base = os.path.splitext(os.path.basename(VIDEO))[0]
SORTIE = f"/content/montage/sortie/{base}_monte.mp4"
print("🎬 Montage en cours…")
M.monter(VIDEO, PLAN, R, SORTIE, musique=MUSIQUE)
M.ecrire_srt(PLAN, SORTIE.replace(".mp4", ".srt"))
open(SORTIE.replace(".mp4", "_transcription.txt"), "w", encoding="utf-8").write(M.texte_transcription(mots))
print("✅ Terminé !")
display(Video(SORTIE, embed=True, width=320))
files.download(SORTIE)
"""),
md("""
---
**Fichiers produits** (dossier `/content/montage/sortie`, panneau 📁 à gauche) : la vidéo montée, les sous-titres `.srt` et la transcription `.txt`.

**Astuces**
- Filmez en vertical, la personne au centre, avec un son propre : la transcription n'en sera que meilleure.
- Trop de coupes ? Montez « pause_max_conservee » (étape 2). Pas assez ? Baissez-la.
- Sous-titres qui cachent les mains ou le visage ? Ajustez « position_sous_titres ».
"""),
]

nb = {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4", "name": "Raccord.ipynb"},
      "kernelspec": {"display_name": "Python 3", "name": "python3"}, "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 0}
json.dump(nb, open(SORTIE, "w"), ensure_ascii=False, indent=1)
print("ok")
