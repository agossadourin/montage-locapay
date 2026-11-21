"""Interface du montage automatique Locapay (fenêtre Mac via fenetre.py, ou navigateur)."""
import os, sys, time, traceback

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
# Les apps lancées depuis le Finder n'ont pas toujours Homebrew dans le PATH
os.environ["PATH"] = os.pathsep.join(["/opt/homebrew/bin", "/usr/local/bin", os.environ.get("PATH", "")])

import gradio as gr
import montage_auto as M

SORTIES = os.path.join(os.path.expanduser("~"), "Movies", "Montages Locapay")
os.makedirs(SORTIES, exist_ok=True)
LOGO_DEFAUT = os.path.join(ICI, "logo_locapay.png")
try:
    VERSION = "v" + open(os.path.join(os.path.dirname(ICI), "VERSION")).read().strip()
except OSError:
    VERSION = ""


def _reglages(c1, c2, ecrans, position, hesit, pause, effets, vol, logo, autre_logo):
    fichier_logo = (autre_logo or LOGO_DEFAUT) if logo else ""
    return M.Reglages(couleur_1=c1, couleur_2=c2, nb_ecrans_couleur=int(ecrans), position_sous_titres=position,
                      supprimer_hesitations=hesit, pause_max=pause, effets_sonores=effets, volume_musique=vol,
                      logo_en_coin=logo, fichier_logo=fichier_logo,
                      police_serif=os.path.join(ICI, "polices", "serif.ttf"),
                      police_grasse=os.path.join(ICI, "polices", "gras.ttf"))


def monter(video, musique, c1, c2, ecrans, position, hesit, pause, effets, vol, logo, autre_logo,
           vocabulaire, modele, corrections, cache, progress=gr.Progress()):
    if not video:
        raise gr.Error("Ajoutez d'abord une vidéo brute.")
    try:
        modele = "small" if modele.startswith("Rapide") else "turbo"
        cle = (video, os.path.getsize(video), modele, vocabulaire)
        if cache and cache.get("cle") == cle:
            mots_bruts = cache["mots"]
        else:
            progress(0.02, desc="Transcription de la voix… (la 1re fois, le modèle se télécharge)")
            mots_bruts = M.transcrire(video, modele=modele, langue="fr", vocabulaire=vocabulaire)
            cache = {"cle": cle, "mots": mots_bruts}
        mots = M.appliquer_corrections(mots_bruts, corrections)
        R = _reglages(c1, c2, ecrans, position, hesit, pause, effets, vol, logo, autre_logo)
        plan = M.construire_plan(mots, M.duree_video(video), R)

        base = os.path.splitext(os.path.basename(video))[0]
        sortie = os.path.join(SORTIES, f"{base}_monte_{time.strftime('%Y%m%d-%H%M%S')}.mp4")
        progress(0.30, desc="Montage…")
        M.monter(video, plan, R, sortie, musique=musique or None, progression=False,
                 rappel=lambda f: progress(0.30 + 0.62 * f, desc="Montage…"))
        progress(0.95, desc="Finalisation…")
        srt = sortie.replace(".mp4", ".srt"); M.ecrire_srt(plan, srt)
        txt = sortie.replace(".mp4", "_transcription.txt")
        open(txt, "w", encoding="utf-8").write(M.texte_transcription(mots))
        info = f"✅ Vidéo enregistrée dans **Vidéos › Montages Locapay** : `{os.path.basename(sortie)}`"
        return sortie, M.texte_transcription(mots), M.resume_plan(plan), [sortie, srt, txt], info, cache
    except gr.Error:
        raise
    except Exception as e:
        traceback.print_exc()
        raise gr.Error(f"Problème pendant le montage : {e}")


def ouvrir_dossier():
    if sys.platform == "darwin":
        os.system(f'open "{SORTIES}"')


GR6 = int(gr.__version__.split(".")[0]) >= 6
THEME = gr.themes.Soft(primary_hue="teal")
with gr.Blocks(title="Montage automatique Locapay", **({} if GR6 else {"theme": THEME})) as app:
    gr.Markdown(f"# 🎬 Montage automatique Locapay <small style='opacity:.5'>{VERSION}</small>\n"
                "Glissez une vidéo brute face caméra, cliquez sur **Monter la vidéo**, récupérez la vidéo prête à publier.")
    cache = gr.State(None)
    with gr.Row():
        with gr.Column(scale=1):
            video = gr.File(label="Vidéo brute", file_types=["video"], type="filepath")
            musique = gr.File(label="Musique de fond (facultatif)", file_types=["audio"], type="filepath")
            with gr.Accordion("Réglages", open=False):
                with gr.Row():
                    c1 = gr.ColorPicker(value="#2E2C51", label="Couleur 1 (écrans + fin)")
                    c2 = gr.ColorPicker(value="#0AC2A4", label="Couleur 2")
                ecrans = gr.Slider(0, 4, value=2, step=1, label="Nombre d'écrans de couleur")
                position = gr.Slider(0.40, 0.85, value=0.66, step=0.01, label="Hauteur des sous-titres (0 = haut, 1 = bas)")
                hesit = gr.Checkbox(value=True, label="Couper les hésitations (euh, hum…)")
                pause = gr.Slider(0.20, 1.00, value=0.45, step=0.05, label="Blanc maximum conservé (secondes)")
                effets = gr.Radio(["léger", "aucun"], value="léger", label="Effets sonores")
                vol = gr.Slider(0.05, 0.50, value=0.18, step=0.01, label="Volume de la musique")
                logo = gr.Checkbox(value=True, label="Afficher le logo")
                autre_logo = gr.File(label="Autre logo (PNG, facultatif)", file_types=["image"], type="filepath")
                vocabulaire = gr.Textbox(value="Locapay, démarcheurs, loyer, propriétaire, locataire, Cotonou, Bénin",
                                         label="Mots rares à bien reconnaître")
                modele = gr.Radio(["Précis (recommandé)", "Rapide"], value="Précis (recommandé)", label="Transcription")
            corrections = gr.Textbox(value="Locapé=Locapay; Lokapay=Locapay", lines=2,
                                     label="Corrections de mots (mot_faux=mot_juste; …) — puis recliquez sur Monter")
            bouton = gr.Button("🎬 Monter la vidéo", variant="primary", size="lg")
        with gr.Column(scale=1):
            resultat = gr.Video(label="Vidéo montée", height=560)
            info = gr.Markdown()
            dossier = gr.Button("📂 Ouvrir le dossier des montages")
            fichiers = gr.File(label="Fichiers (vidéo, sous-titres .srt, transcription)", file_count="multiple")
            with gr.Accordion("Transcription et plan de montage", open=False):
                transcription = gr.Textbox(label="Transcription", lines=5)
                plan = gr.Textbox(label="Plan (MAJUSCULES = mot en gras)", lines=12)

    bouton.click(monter, [video, musique, c1, c2, ecrans, position, hesit, pause, effets, vol, logo, autre_logo,
                          vocabulaire, modele, corrections, cache],
                 [resultat, transcription, plan, fichiers, info, cache])
    dossier.click(ouvrir_dossier)

def lancer(port=None, navigateur=True, bloquant=True):
    app.queue().launch(inbrowser=navigateur, server_name="127.0.0.1", server_port=port,
                       allowed_paths=[SORTIES], prevent_thread_lock=not bloquant,
                       **({"theme": THEME} if GR6 else {}))


if __name__ == "__main__":
    lancer()
