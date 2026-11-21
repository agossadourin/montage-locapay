"""Interface du montage automatique Locapay (fenêtre Mac via fenetre.py, ou navigateur)."""
import os, subprocess, sys, time, traceback

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
           vocabulaire, modele, corrections, cache, auto_qt=False, progress=gr.Progress()):
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
        if auto_qt:
            try:
                lire_quicktime(sortie)
            except Exception:
                pass
        return sortie, M.texte_transcription(mots), M.resume_plan(plan), [sortie, srt, txt], info, cache, sortie
    except gr.Error:
        raise
    except Exception as e:
        traceback.print_exc()
        raise gr.Error(f"Problème pendant le montage : {e}")


COLONNES = ["Ordre", "Vidéo", "Durée (s)", "Début (s)", "Fin (s)", "Garder"]
PREMONTAGES = os.path.join(SORTIES, "prémontages")


def lister_clips(fichiers):
    """Remplit le tableau quand on dépose plusieurs vidéos."""
    chemins = [f if isinstance(f, str) else f.name for f in (fichiers or [])]
    lignes = []
    for i, c in enumerate(chemins):
        try:
            d = round(M.duree_video(c), 2)
        except Exception:
            d = 0.0
        lignes.append([i + 1, f"{i + 1} · {os.path.basename(c)}", d, 0.0, d, True])
    return lignes, chemins


def _nombre(x, defaut):
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return defaut


def assembler(tableau, chemins, progress=gr.Progress()):
    if not chemins:
        raise gr.Error("Déposez d'abord plusieurs vidéos.")
    lignes = tableau.values.tolist() if hasattr(tableau, "values") else list(tableau or [])
    morceaux = []
    for i, ligne in enumerate(lignes[:len(chemins)]):
        ordre, _, duree, deb, fin, garder = (list(ligne) + [None] * 6)[:6]
        if str(garder).strip().lower() in ("false", "0", "non", "no", ""):
            continue
        duree = _nombre(duree, None)
        morceaux.append((_nombre(ordre, i + 1), i, chemins[i], _nombre(deb, 0.0), _nombre(fin, duree)))
    if not morceaux:
        raise gr.Error("Aucune vidéo cochée dans « Garder ».")
    morceaux.sort(key=lambda m: (m[0], m[1]))
    os.makedirs(PREMONTAGES, exist_ok=True)
    sortie = os.path.join(PREMONTAGES, f"premontage_{time.strftime('%Y%m%d-%H%M%S')}.mp4")
    try:
        progress(0.01, desc="Assemblage des vidéos…")
        M.premontage([(c, d, f) for _, _, c, d, f in morceaux], sortie,
                     rappel=lambda f: progress(f, desc="Assemblage des vidéos…"))
    except Exception as e:
        traceback.print_exc()
        raise gr.Error(f"Problème pendant l'assemblage : {e}")
    info = (f"✅ Prémontage prêt ({len(morceaux)} vidéos, {M.duree_video(sortie):.1f} s). "
            "Il est placé dans l'onglet **Une vidéo** : cliquez sur **🎬 Monter la vidéo**.")
    return sortie, sortie, info, gr.Tabs(selected="une")


def lire_quicktime(chemin):
    if not chemin or not os.path.exists(chemin):
        raise gr.Error("Aucune vidéo montée pour l'instant.")
    if sys.platform == "darwin":
        subprocess.run(["open", "-a", "QuickTime Player", chemin])
    else:
        subprocess.run(["xdg-open", chemin])


def ouvrir_dossier():
    if sys.platform == "darwin":
        os.system(f'open "{SORTIES}"')


GR6 = int(gr.__version__.split(".")[0]) >= 6
THEME = gr.themes.Soft(primary_hue="teal")
with gr.Blocks(title="Montage automatique Locapay", **({} if GR6 else {"theme": THEME})) as app:
    gr.Markdown(f"# 🎬 Montage automatique Locapay <small style='opacity:.5'>{VERSION}</small>\n"
                "Glissez une vidéo brute face caméra (ou plusieurs, à assembler), cliquez sur **Monter la vidéo**, "
                "récupérez la vidéo prête à publier.")
    cache = gr.State(None)
    chemins_clips = gr.State([])
    derniere_video = gr.State(None)
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Tabs(selected="une") as onglets:
                with gr.Tab("Une vidéo", id="une"):
                    video = gr.File(label="Vidéo brute", file_types=["video"], type="filepath")
                with gr.Tab("Plusieurs vidéos (prémontage)", id="plusieurs"):
                    gr.Markdown("Déposez vos vidéos, puis réglez pour chacune l'**ordre**, le **début** et la **fin** "
                                "(en secondes) et décochez celles à ignorer. **Assembler** les met bout à bout ; "
                                "le résultat passe ensuite dans le montage automatique.")
                    clips = gr.File(label="Vidéos à assembler", file_types=["video"], file_count="multiple",
                                    type="filepath")
                    tableau = gr.Dataframe(headers=COLONNES, datatype=["number", "str", "number", "number", "number", "bool"],
                                           interactive=True, wrap=True, type="array",
                                           **({"column_count": (6, "fixed")} if GR6 else {"col_count": (6, "fixed")}),
                                           label="Ordre et découpe")
                    bouton_assembler = gr.Button("🧩 Assembler les vidéos", variant="secondary")
                    info_pre = gr.Markdown()
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
                auto_qt = gr.Checkbox(value=(sys.platform == "darwin"), label="Ouvrir la vidéo dans QuickTime à la fin du montage")
            corrections = gr.Textbox(value="Locapé=Locapay; Lokapay=Locapay", lines=2,
                                     label="Corrections de mots (mot_faux=mot_juste; …) — puis recliquez sur Monter")
            bouton = gr.Button("🎬 Monter la vidéo", variant="primary", size="lg")
        with gr.Column(scale=1):
            resultat = gr.Video(label="Vidéo montée", height=560)
            info = gr.Markdown()
            with gr.Row():
                quicktime = gr.Button("▶️ Lire dans QuickTime", variant="primary")
                dossier = gr.Button("📂 Ouvrir le dossier des montages")
            fichiers = gr.File(label="Fichiers (vidéo, sous-titres .srt, transcription)", file_count="multiple")
            with gr.Accordion("Transcription et plan de montage", open=False):
                transcription = gr.Textbox(label="Transcription", lines=5)
                plan = gr.Textbox(label="Plan (MAJUSCULES = mot en gras)", lines=12)

    bouton.click(monter, [video, musique, c1, c2, ecrans, position, hesit, pause, effets, vol, logo, autre_logo,
                          vocabulaire, modele, corrections, cache, auto_qt],
                 [resultat, transcription, plan, fichiers, info, cache, derniere_video])
    dossier.click(ouvrir_dossier)
    quicktime.click(lire_quicktime, [derniere_video], None)
    clips.change(lister_clips, [clips], [tableau, chemins_clips])
    bouton_assembler.click(assembler, [tableau, chemins_clips], [video, derniere_video, info_pre, onglets])

def lancer(port=None, navigateur=True, bloquant=True):
    app.queue().launch(inbrowser=navigateur, server_name="127.0.0.1", server_port=port,
                       allowed_paths=[SORTIES], prevent_thread_lock=not bloquant,
                       **({"theme": THEME} if GR6 else {}))


if __name__ == "__main__":
    lancer()
