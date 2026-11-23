"""Interface du montage automatique Locapay (fenêtre Mac via fenetre.py, ou navigateur)."""
import json, os, shutil, subprocess, sys, time, traceback
from dataclasses import asdict, fields

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
# Les apps lancées depuis le Finder n'ont pas toujours Homebrew dans le PATH
os.environ["PATH"] = os.pathsep.join(["/opt/homebrew/bin", "/usr/local/bin", os.environ.get("PATH", "")])
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")      # aucune statistique envoyée à Gradio

import gradio as gr
from PIL import Image, ImageDraw

import analyse_style as A
import ia
import configuration as C
import illustrations as I
import montage_auto as M
import projet as P

SORTIES = os.path.join(os.path.expanduser("~"), "Movies", "Montages Locapay")
os.makedirs(SORTIES, exist_ok=True)
try:
    VERSION = "v" + open(os.path.join(os.path.dirname(ICI), "VERSION")).read().strip()
except OSError:
    VERSION = ""

STYLE_CLES = [f.name for f in fields(C.ProfilStyle) if f.name != "description"]
IDENTITE_CLES = ["nom", "couleur_1", "couleur_2", "fichier_logo", "police_serif", "police_grasse"]
CLES_API = ["anthropic", "pexels", "pixabay", "gemini", "cloudflare_compte", "cloudflare_jeton"]
SOURCES_ILL = {"Banques d'images gratuites (Pexels / Pixabay)": "banques",
               "Images créées par IA — Cloudflare (gratuit, ~170 images/jour)": "cloudflare",
               "Images créées par IA — Gemini (payant, ≈ 0,03 $ l'image)": "gemini"}
CHOIX_IA = {"Aucune (règles automatiques, gratuit)": "aucune", "Ollama — sur ce Mac, gratuit": "ollama",
            "Claude — en ligne, payant": "claude"}


def _ia_depuis(cles=None):
    """Configuration d'IA d'après les paramètres enregistrés (et la clé Claude saisie dans l'interface)."""
    cfg = C.charger_config()
    if cles:
        cfg["cles"] = {**cfg["cles"], **{k: v for k, v in cles.items() if v}}
    return ia.config_ia(cfg)
AVANCE_CLES = ["supprimer_hesitations", "volume_musique", "vocabulaire", "modele", "auto_qt"]


def _lignes(tableau):
    return tableau.values.tolist() if hasattr(tableau, "values") else list(tableau or [])


def _fusionner_validation(anciennes_phrases, anciennes_lignes, nouvelles_phrases):
    """Après une correction de mots, les phrases sont recalculées : on garde les choix déjà faits
    (Garder, Sous-titres, texte retouché) pour les phrases qui commencent au même moment."""
    lignes = M.lignes_validation(nouvelles_phrases)
    for nl, ph in zip(lignes, nouvelles_phrases):
        for ap, al in zip(anciennes_phrases, anciennes_lignes):
            if abs(ap["deb"] - ph["deb"]) < 0.15:
                al = (list(al) + [None] * 8)[:8]
                nl[6], nl[7] = M._vrai(al[6]), M._vrai(al[7])
                if M._jetons(str(al[3] or "")) != M._jetons(ap["texte"]):   # texte retouché à la main
                    nl[3] = al[3]
                break
    return lignes


# ============================================================ paramètres (identité, style, clés)
def _profil(valeurs):
    d = dict(zip(STYLE_CLES, valeurs))
    for k in ("mots_par_groupe", "nb_ecrans_couleur"):
        d[k] = int(d[k])
    return C.ProfilStyle.depuis(d)


def _identite(valeurs):
    d = dict(zip(IDENTITE_CLES, valeurs))
    base = C.charger_config()["identite"]
    ident = {k: (d.get(k) or base.get(k)) for k in IDENTITE_CLES}
    # le logo affiché par l'interface est une copie temporaire : on en garde une copie durable
    logo = ident.get("fichier_logo")
    if logo and os.path.exists(logo) and not any(os.path.realpath(logo).startswith(os.path.realpath(r))
                                                   for r in (C.DOSSIER, ICI)):
        ident["fichier_logo"] = _ranger(logo, "logo_courant")
    return ident


def _ranger(fichier, nom):
    """Copie un fichier déposé (logo, police) dans les paramètres, pour qu'il survive au redémarrage."""
    if not fichier or not os.path.exists(fichier) or os.path.dirname(fichier) == os.path.join(C.DOSSIER, "identite"):
        return fichier
    dest = os.path.join(C.DOSSIER, "identite", nom + os.path.splitext(fichier)[1].lower())
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(fichier, dest)
    return dest


def sauver_identite(nom, c1, c2, logo, serif, grasse):
    cfg = C.charger_config()
    cfg["identite"].update({"nom": nom or "", "couleur_1": c1, "couleur_2": c2})
    if logo:
        cfg["identite"]["fichier_logo"] = _ranger(logo, "logo")
    if serif:
        cfg["identite"]["police_serif"] = _ranger(serif, "police_texte")
    if grasse:
        cfg["identite"]["police_grasse"] = _ranger(grasse, "police_mot_cle")
    C.sauver_config(cfg)
    i = cfg["identite"]
    return (f"✅ Identité « {i['nom']} » enregistrée. Polices : texte `{os.path.basename(i['police_serif'])}`, "
            f"mot clé `{os.path.basename(i['police_grasse'])}`.", i["fichier_logo"], i["police_serif"],
            i["police_grasse"])


def sauver_cles(anthropic, pexels, pixabay, gemini="", cf_compte="", cf_jeton="", choix_ia=None, source_ill=None,
                contexte=None):
    cfg = C.charger_config()
    if choix_ia:
        cfg.setdefault("ia", {})["fournisseur"] = CHOIX_IA.get(choix_ia, "aucune")
    cfg["cles"].update({"anthropic": (anthropic or "").strip(), "pexels": (pexels or "").strip(),
                        "pixabay": (pixabay or "").strip(), "gemini": (gemini or "").strip(),
                        "cloudflare_compte": (cf_compte or "").strip(), "cloudflare_jeton": (cf_jeton or "").strip()})
    if source_ill:
        cfg["illustrations"]["source"] = SOURCES_ILL.get(source_ill, "banques")
    if contexte is not None:
        cfg["illustrations"]["contexte"] = contexte.strip() or C.CONTEXTE_DEFAUT
    C.sauver_config(cfg)
    actives = [n for n, v in (("Claude", anthropic), ("Pexels", pexels), ("Pixabay", pixabay), ("Gemini", gemini),
                              ("Cloudflare", (cf_compte or "").strip() and (cf_jeton or "").strip())) if (v or "").strip()]
    avert = ""
    src = cfg["illustrations"]["source"]
    if src == "gemini" and not cfg["cles"]["gemini"]:
        avert = "\n\n⚠️ Gemini choisi, mais aucune clé Gemini."
    if src == "cloudflare" and not (cfg["cles"]["cloudflare_compte"] and cfg["cles"]["cloudflare_jeton"]):
        avert = "\n\n⚠️ Cloudflare choisi, mais l'identifiant de compte ou le jeton manque."
    return ("✅ Clés enregistrées : " + (", ".join(actives) if actives else "aucune")
            + f" · IA : {ia.nom_ia(ia.config_ia(cfg))}"
            + f" · Illustrations : {next(k for k, v in SOURCES_ILL.items() if v == src).split(' (')[0]}" + avert)


def tester_ollama_ui():
    return ia.tester_ollama()[1]


def charger_style_ui(nom):
    p = C.charger_style(nom)
    cfg = C.charger_config(); cfg["style_actif"] = nom or "Locapay"; C.sauver_config(cfg)
    return [getattr(p, k) for k in STYLE_CLES] + [f"*{p.description}*" if p.description else ""]


def sauver_style_ui(nouveau_nom, nom_choisi, *valeurs):
    nom = (nouveau_nom or "").strip() or nom_choisi or "Mon style"
    p = _profil(valeurs)
    p.description = C.charger_style(nom_choisi).description if not (nouveau_nom or "").strip() else \
        f"Style « {nom} » (ajusté à la main)."
    C.sauver_style(nom, p)
    cfg = C.charger_config(); cfg["style_actif"] = nom; C.sauver_config(cfg)
    return gr.update(choices=C.lister_styles(), value=nom), f"✅ Style « {nom} » enregistré."


def analyser_reference(video, nom, cle_anthropic, progress=gr.Progress()):
    if not video:
        raise gr.Error("Déposez d'abord une vidéo de référence.")
    nom = (nom or "").strip() or os.path.splitext(os.path.basename(video))[0][:30]
    try:
        p, rapport = A.analyser(video, cle_api=_ia_depuis({"anthropic": (cle_anthropic or "").strip()}),
                                rappel=lambda f, t: progress(f, desc=t))
    except Exception as e:
        traceback.print_exc()
        raise gr.Error(f"Analyse impossible : {e}")
    C.sauver_style(nom, p)
    cfg = C.charger_config(); cfg["style_actif"] = nom; C.sauver_config(cfg)
    return ([gr.update(choices=C.lister_styles(), value=nom)] + [getattr(p, k) for k in STYLE_CLES]
            + [f"*{p.description}*", f"✅ Style « {nom} » créé et sélectionné.\n\n" + rapport])


# ============================================================ illustrations (B-roll)
def _vignette_vide():
    chemin = os.path.join(I.DOSSIER_CACHE, "_aucune.png")
    if not os.path.exists(chemin):
        os.makedirs(I.DOSSIER_CACHE, exist_ok=True)
        im = Image.new("RGB", (360, 640), (60, 60, 70))
        d = ImageDraw.Draw(im)
        for k, t in enumerate(["Aucune image", "", "Ajoutez une clé Pexels", "(gratuite) dans", "Paramètres › Clés",
                               "ou votre fichier"]):
            d.text((30, 240 + 26 * k), t, fill=(230, 230, 230))
        im.save(chemin)
    return chemin


def _vignette_fichier(chemin):
    if not chemin.lower().endswith(M.EXT_VIDEO):
        return chemin
    v = chemin + ".jpg"
    if not os.path.exists(v):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "0.5", "-i", chemin, "-frames:v", "1",
                        "-vf", "scale=360:-2", v])
    return v if os.path.exists(v) else _vignette_vide()


def _apercu(p):
    if p.get("fichier"):
        return _vignette_fichier(p["fichier"])
    if p.get("resultats"):
        return p["resultats"][p.get("choix", 0) % len(p["resultats"])]["apercu"] or _vignette_vide()
    return _vignette_vide()


def _galerie(illus):
    out = []
    for n, p in enumerate(illus or [], 1):
        src = "votre fichier" if p.get("fichier") else (
            ("vidéo" if p["resultats"][p.get("choix", 0) % len(p["resultats"])]["type"] == "video" else "photo")
            if p.get("resultats") else "à fournir")
        out.append((_apercu(p), f"{n} · {M_tc(p['deb'])} · {p['requete']} ({src})"))
    return out


def M_tc(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def _lignes_illus(illus):
    return [[n, M_tc(p["deb"]), p.get("mot", ""), p["requete"], True] for n, p in enumerate(illus or [], 1)] \
        or [[None, "", "", "", False]]


def proposer_illustrations(mots, duree, par_minute, cles, progress=None):
    props = I.choisir_moments(mots, duree, par_minute=par_minute, cle_api=_ia_depuis(cles))
    banques = cles.get("pexels") or cles.get("pixabay")
    for k, p in enumerate(props):
        if progress:
            progress(0.5 + 0.4 * k / max(1, len(props)), desc="Recherche d'illustrations…")
        p.update({"resultats": I.rechercher(p["requete"], cles) if banques else [], "choix": 0,
                  "fichier": None, "requete_init": p["requete"]})
    return props


def illustrations_pour_rendu(illus, lignes, cles):
    """Applique les choix (Garder, recherche modifiée) et télécharge les médias retenus."""
    items = []
    lignes = _lignes(lignes)
    for p, ligne in zip(illus or [], lignes):
        ligne = (list(ligne) + [None] * 5)[:5]
        if not M._vrai(ligne[4]):
            continue
        requete = str(ligne[3] or p["requete"]).strip()
        if requete != p["requete"] and not p.get("fichier"):
            p["requete"], p["choix"] = requete, 0
            p["resultats"] = I.rechercher(requete, cles) if (cles.get("pexels") or cles.get("pixabay")) else []
        fichier, typ = p.get("fichier"), None
        if not fichier and p.get("resultats"):
            r = p["resultats"][p.get("choix", 0) % len(p["resultats"])]
            try:
                fichier, typ = I.telecharger(r), r["type"]
            except Exception as e:
                print("Téléchargement impossible :", e)
                fichier = None
        if fichier:
            items.append({"deb": p["deb"], "fin": p["fin"], "fichier": fichier, "type": typ})
    return items


def selection_illus(evt: gr.SelectData):
    return evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index


def autre_proposition(illus, sel):
    if illus is None or sel is None or not (0 <= sel < len(illus)):
        raise gr.Error("Cliquez d'abord sur une illustration (dans la galerie ou le tableau).")
    p = illus[sel]
    if not p.get("resultats"):
        raise gr.Error("Pas d'autre résultat : modifiez la recherche ou ajoutez votre fichier.")
    p["fichier"] = None
    p["choix"] = (p.get("choix", 0) + 1) % len(p["resultats"])
    return illus, _galerie(illus)


def relancer_recherches(illus, lignes, cle_pexels, cle_pixabay):
    cles = {"pexels": (cle_pexels or "").strip(), "pixabay": (cle_pixabay or "").strip()}
    if not (cles["pexels"] or cles["pixabay"]):
        raise gr.Error("Ajoutez une clé Pexels ou Pixabay (gratuite) dans Paramètres › Clés API.")
    for p, ligne in zip(illus or [], _lignes(lignes)):
        requete = str((list(ligne) + [None] * 4)[3] or p["requete"]).strip()
        if requete != p["requete"] or not p.get("resultats"):
            p.update({"requete": requete, "resultats": I.rechercher(requete, cles), "choix": 0, "fichier": None})
    return illus, _galerie(illus)


def mon_fichier(fichier, illus, sel):
    if not fichier:
        return illus, _galerie(illus), gr.update()
    if illus is None or sel is None or not (0 <= sel < len(illus)):
        raise gr.Error("Cliquez d'abord sur l'illustration à remplacer.")
    dest = os.path.join(I.DOSSIER_CACHE, f"perso_{int(time.time())}_{os.path.basename(fichier)}")
    os.makedirs(I.DOSSIER_CACHE, exist_ok=True)
    shutil.copyfile(fichier, dest)
    illus[sel]["fichier"] = dest
    return illus, _galerie(illus), None


# ============================================================ montage
def monter(video, musique, *args, progress=gr.Progress()):
    n_i, n_s, n_k, n_a = len(IDENTITE_CLES), len(STYLE_CLES), len(CLES_API), len(AVANCE_CLES)
    identite = _identite(args[:n_i]); args = args[n_i:]
    profil = _profil(args[:n_s]); args = args[n_s:]
    cles = dict(zip(CLES_API, [(x or "").strip() for x in args[:n_k]])); args = args[n_k:]
    av = dict(zip(AVANCE_CLES, args[:n_a])); args = args[n_a:]
    corrections, cache, valider, analyse, tableau, illus, table_illus = args
    if not video:
        raise gr.Error("Ajoutez d'abord une vidéo brute.")
    try:
        modele = "small" if str(av["modele"]).startswith("Rapide") else "turbo"
        vocabulaire = av["vocabulaire"]
        cle = (video, os.path.getsize(video), modele, vocabulaire)
        if cache and cache.get("cle") == cle:
            mots_bruts = cache["mots"]
        else:
            progress(0.02, desc="Transcription de la voix… (la 1re fois, le modèle se télécharge)")
            mots_bruts = M.transcrire(video, modele=modele, langue="fr", vocabulaire=vocabulaire)
            cache = {"cle": cle, "mots": mots_bruts, "phrases": M.analyser(mots_bruts), "video": video}
        duree = M.duree_video(video)
        # les corrections « à un moment précis » ne valent que pour la transcription où on les a choisies
        corr = [c for c in (corrections or []) if c.get("portee") != "moment" or c.get("cle") == cle]
        mots = M.corriger(mots_bruts, corr)
        maj_moments = gr.update(choices=choix_moments(cache))
        rien = gr.update()

        if valider:
            cle_analyse = (cle, repr([(c.get("portee"), c.get("i"), c.get("j"), c.get("avant"), c.get("apres"))
                                      for c in corr]))
            if not analyse or analyse.get("cle")[0] != cle:
                # 1er clic : passages à vérifier + illustrations proposées, puis on attend la validation
                phrases = M.analyser(mots)
                analyse = {"cle": cle_analyse, "phrases": phrases, "video": video}
                progress(0.45, desc="Choix des illustrations…")
                gardes = M.appliquer_validation(mots, phrases, M.lignes_validation(phrases))  # sans les passages écartés
                illus = proposer_illustrations(gardes, duree, profil.illustrations_par_minute, cles, progress) \
                    if profil.illustrations_par_minute > 0 else []
                n = sum(1 for p in phrases if p["alertes"])
                msg = (f"🔎 **{n} passage(s) à vérifier** sur {len(phrases)}" if n else "✅ Aucun passage suspect")
                msg += (f" · 🖼 **{len(illus)} illustration(s) proposée(s)**" if illus else "")
                msg += (". Vérifiez les panneaux **Validation des passages** et **Illustrations** en bas de page "
                        "(cliquez sur une ligne pour l'écouter, changez une image, décochez ce qui ne convient pas), "
                        "puis recliquez sur **🎬 Monter la vidéo**.")
                if illus and not (cles.get("pexels") or cles.get("pixabay")):
                    msg += (" ℹ️ Sans clé Pexels/Pixabay, aucune image n'est cherchée : ajoutez vos fichiers ou "
                            "une clé gratuite dans **Paramètres › Clés API**.")
                return (rien, rien, rien, rien, msg, cache, rien, analyse, M.lignes_validation(phrases),
                        gr.update(open=True), maj_moments, illus, _lignes_illus(illus), _galerie(illus),
                        gr.update(open=bool(illus)), rien, rien)
            lignes = _lignes(tableau)
            if analyse["cle"] != cle_analyse:      # des corrections ont été ajoutées depuis l'analyse
                phrases = M.analyser(mots)
                lignes = _fusionner_validation(analyse["phrases"], lignes, phrases)
                analyse = {"cle": cle_analyse, "phrases": phrases, "video": video}
            tableau = lignes
            mots = M.appliquer_validation(mots, analyse["phrases"], lignes)
        else:
            illus = proposer_illustrations(mots, duree, profil.illustrations_par_minute, cles) \
                if profil.illustrations_par_minute > 0 else []
            table_illus = _lignes_illus(illus)

        progress(0.25, desc="Téléchargement des illustrations…")
        items = illustrations_pour_rendu(illus, table_illus, cles)
        R = C.reglages(M, identite, profil, supprimer_hesitations=av["supprimer_hesitations"],
                       volume_musique=av["volume_musique"], illustrations=items)
        plan = M.construire_plan(mots, duree, R)

        base = os.path.splitext(os.path.basename(video))[0]
        sortie = os.path.join(SORTIES, f"{base}_monte_{time.strftime('%Y%m%d-%H%M%S')}.mp4")
        progress(0.30, desc="Montage…")
        M.monter(video, plan, R, sortie, musique=musique or None, progression=False,
                 rappel=lambda f: progress(0.30 + 0.62 * f, desc="Montage…"))
        progress(0.95, desc="Finalisation…")
        try:   # projet éditable dans la timeline
            proj = P.creer(P.garder_source(video), plan, R, musique=P.garder_source(musique) if musique else None)
            chemin_projet = P.sauver(proj, sortie[:-4] + ".projet.json")
        except Exception:
            traceback.print_exc()
            chemin_projet = ""
        srt = sortie.replace(".mp4", ".srt"); M.ecrire_srt(plan, srt)
        txt = sortie.replace(".mp4", "_transcription.txt")
        open(txt, "w", encoding="utf-8").write(M.texte_transcription(mots))
        info = f"✅ Vidéo enregistrée dans **Vidéos › Montages Locapay** : `{os.path.basename(sortie)}`"
        if items:
            info += f" · {len(items)} illustration(s) insérée(s)"
        if av["auto_qt"]:
            try:
                lire_quicktime(sortie)
            except Exception:
                pass
        return (sortie, M.texte_transcription(mots), M.resume_plan(plan), [sortie, srt, txt], info, cache, sortie,
                analyse, tableau if valider else rien, rien, maj_moments, illus, rien, rien, rien,
                chemin_projet, gr.update(visible=bool(chemin_projet)))
    except gr.Error:
        raise
    except Exception as e:
        traceback.print_exc()
        raise gr.Error(f"Problème pendant le montage : {e}")


# ============================================================ corrections de mots
DICO = os.path.join(SORTIES, ".dictionnaire_corrections.json")
DICO_DEFAUT = [{"portee": "toujours", "avant": "Locapé", "apres": "Locapay"},
               {"portee": "toujours", "avant": "Lokapay", "apres": "Locapay"}]
PARTOUT, TOUJOURS = "video", "toujours"


def charger_dico():
    try:
        with open(DICO, encoding="utf-8") as f:
            return [c for c in json.load(f) if c.get("portee") == TOUJOURS]
    except (OSError, ValueError):
        return [dict(c) for c in DICO_DEFAUT]


def sauver_dico(corrections):
    try:
        with open(DICO, "w", encoding="utf-8") as f:
            json.dump([{k: c[k] for k in ("portee", "avant", "apres")} for c in corrections
                       if c.get("portee") == TOUJOURS], f, ensure_ascii=False, indent=1)
    except OSError:
        traceback.print_exc()


def _tc(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def choix_moments(cache):
    choix = [("🌍 Partout dans cette vidéo", PARTOUT), ("♾️ Partout, dans toutes mes vidéos", TOUJOURS)]
    for k, p in enumerate((cache or {}).get("phrases", [])):
        texte = p["texte"] if len(p["texte"]) <= 70 else p["texte"][:68] + "…"
        choix.append((f"{_tc(p['deb'])}  ·  {texte}", str(k)))
    return choix


def lignes_corrections(corrections):
    lignes = []
    for n, c in enumerate(corrections or [], 1):
        moment = {PARTOUT: "Partout (cette vidéo)", TOUJOURS: "Toutes mes vidéos"}.get(
            c.get("portee"), _tc(c.get("t", 0)))
        lignes.append([n, moment, c.get("avant", ""), c.get("apres", "") or "— supprimé —"])
    return lignes or [[None, "", "", ""]]


def ouvrir_formulaire(cache):
    aide = ("" if cache else "ℹ️ Les moments précis apparaissent après la transcription "
                             "(premier clic sur **🎬 Monter la vidéo**).")
    return (gr.update(visible=True), gr.update(choices=choix_moments(cache), value=None),
            gr.update(choices=[], value=[], visible=False), gr.update(value="", interactive=True),
            gr.update(value=""), aide)


def fermer_formulaire():
    return gr.update(visible=False)


def choisir_moment(moment, cache):
    if moment in (None, PARTOUT, TOUJOURS) or not cache:
        return (gr.update(choices=[], value=[], visible=False),
                gr.update(value="", interactive=True, label="Mot(s) à corriger (tels que reconnus)"))
    ph = cache["phrases"][int(moment)]
    mots = cache["mots"]
    choix = [(f"{mots[i]['w']}", str(i)) for i in ph["idx"]]
    return (gr.update(choices=choix, value=[], visible=True),
            gr.update(value="", interactive=False, label="Mot(s) sélectionné(s)"))


def choisir_mots(selection, cache):
    if not selection or not cache:
        return ""
    idx = sorted(int(i) for i in selection)
    return " ".join(m["w"] for m in cache["mots"][idx[0]:idx[-1] + 1])


def ajouter_correction(moment, selection, avant, apres, corrections, cache):
    corrections = list(corrections or [])
    apres = (apres or "").strip()
    if moment in (PARTOUT, TOUJOURS):
        if not (avant or "").strip():
            raise gr.Error("Tapez le ou les mots à corriger, tels que l'outil les a reconnus.")
        corrections.append({"portee": moment, "avant": avant.strip(), "apres": apres})
        if moment == TOUJOURS:
            sauver_dico(corrections)
    elif moment is not None and cache:
        if not selection:
            raise gr.Error("Choisissez le ou les mots à corriger dans la phrase.")
        idx = sorted(int(i) for i in selection)
        i, j = idx[0], idx[-1]
        corrections.append({"portee": "moment", "i": i, "j": j, "cle": cache["cle"],
                            "t": cache["mots"][i]["s"], "avant": choisir_mots(selection, cache), "apres": apres})
    else:
        raise gr.Error("Choisissez d'abord le moment.")
    info = "✅ Correction ajoutée. Elle sera appliquée au prochain clic sur **🎬 Monter la vidéo**."
    return corrections, lignes_corrections(corrections), gr.update(visible=False), info


def supprimer_correction(corrections, ligne):
    corrections = list(corrections or [])
    if ligne is None or not (0 <= ligne < len(corrections)):
        raise gr.Error("Cliquez d'abord sur la ligne de la correction à supprimer.")
    retiree = corrections.pop(ligne)
    if retiree.get("portee") == TOUJOURS:
        sauver_dico(corrections)
    return corrections, lignes_corrections(corrections), None, "🗑 Correction supprimée."


def selectionner_correction(evt: gr.SelectData):
    return evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index


def ecouter_moment(moment, cache):
    if moment in (None, PARTOUT, TOUJOURS) or not cache:
        raise gr.Error("Choisissez un moment précis pour l'écouter.")
    return _jouer(cache["video"], cache["phrases"][int(moment)])


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


_lecture = {"proc": None}


def arreter_ecoute():
    p = _lecture.get("proc")
    if p and p.poll() is None:
        p.terminate()
    _lecture["proc"] = None


def _jouer(video, ph):
    """Extrait le passage (avec 0,3 s de marge) et le joue : haut-parleur du Mac, sinon lecteur audio."""
    extrait = os.path.join(SORTIES, ".ecoute.wav")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{max(0, ph['deb'] - 0.3):.2f}",
                    "-t", f"{ph['fin'] - ph['deb'] + 0.6:.2f}", "-i", video, "-vn", "-ac", "2", extrait])
    if sys.platform == "darwin":   # lecture directe sur le Mac (fiable même dans la fenêtre de l'app)
        arreter_ecoute()
        _lecture["proc"] = subprocess.Popen(["afplay", extrait])
        return None
    return extrait


def ecouter(analyse, evt: gr.SelectData):
    """Clic sur une ligne du tableau de validation : on écoute le passage."""
    if not analyse:
        return None
    ligne = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
    phrases = analyse["phrases"]
    if not (0 <= ligne < len(phrases)):
        return None
    return _jouer(analyse["video"], phrases[ligne])


def ouvrir_dossier():
    if sys.platform == "darwin":
        os.system(f'open "{SORTIES}"')


GR6 = int(gr.__version__.split(".")[0]) >= 6
# Même univers que l'éditeur : graphite sombre, turquoise de la marque pour l'action.
THEME = gr.themes.Base(
    primary_hue=gr.themes.colors.teal, neutral_hue=gr.themes.colors.slate, radius_size=gr.themes.sizes.radius_md,
    font=["-apple-system", "BlinkMacSystemFont", "SF Pro Text", "Segoe UI", "Helvetica", "Arial", "sans-serif"],
).set(
    body_background_fill_dark="#202029", background_fill_primary_dark="#272731", background_fill_secondary_dark="#202029",
    block_background_fill_dark="#272731", block_border_color_dark="rgba(255,255,255,0.075)",
    border_color_primary_dark="rgba(255,255,255,0.10)", panel_background_fill_dark="#272731",
    input_background_fill_dark="#1b1b23", input_border_color_dark="rgba(255,255,255,0.14)",
    body_text_color_dark="#f1f0f6", body_text_color_subdued_dark="#a6a5b7",
    block_label_text_color_dark="#a6a5b7", block_title_text_color_dark="#f1f0f6", block_label_background_fill_dark="#272731",
    button_primary_background_fill_dark="#0AC2A4", button_primary_background_fill_hover_dark="#19d4b5",
    button_primary_text_color_dark="#04261f", button_secondary_background_fill_dark="#30303b",
    button_secondary_background_fill_hover_dark="#383845", button_secondary_text_color_dark="#f1f0f6",
    color_accent_soft_dark="rgba(10,194,164,0.15)", link_text_color_dark="#0AC2A4",
    checkbox_background_color_selected_dark="#0AC2A4", slider_color_dark="#0AC2A4", block_shadow_dark="none",
)
# Toujours en sombre (comme l'éditeur) ; pied de page Gradio masqué.
TETE = ("<script>(function(){var u=new URL(location.href);if(u.searchParams.get('__theme')!=='dark')"
        "{u.searchParams.set('__theme','dark');location.replace(u.toString());}})();</script>")
CSS = "footer{display:none!important} .gradio-container{max-width:1200px!important}"


def _cols(n):
    return {"column_count": (n, "fixed")} if GR6 else {"col_count": (n, "fixed")}


CFG = C.charger_config()
ID0, CLES0 = CFG["identite"], CFG["cles"]
STYLE0 = C.charger_style(CFG["style_actif"])

with gr.Blocks(title="Montage automatique Locapay", **({} if GR6 else {"theme": THEME})) as app:
    # retour à l'éditeur (on revient sur le projet ouvert si on vient de là)
    gr.HTML("""<div style="display:flex;gap:10px;align-items:center;margin-bottom:4px">
      <a id="retour-editeur" href="/editeur"
         onclick="if (document.referrer.indexOf('/editeur') >= 0) { location.href = document.referrer; return false; }"
         style="position:fixed;top:14px;right:18px;z-index:1000;display:inline-flex;align-items:center;gap:6px;
                padding:9px 16px;border-radius:9px;background:#0AC2A4;color:#fff;font-weight:600;text-decoration:none;
                box-shadow:0 4px 14px rgba(0,0,0,.18)">← Retour à l'éditeur</a>
      <span style="opacity:.6;font-size:13px">Vos réglages sont enregistrés avec les boutons 💾 de chaque onglet.</span></div>""")
    gr.Markdown(f"# 🎬 Montage automatique Locapay <small style='opacity:.5'>{VERSION}</small>\n"
                "Glissez une vidéo brute face caméra (ou plusieurs, à assembler), cliquez sur **Monter la vidéo**, "
                "récupérez la vidéo prête à publier — puis retouchez-la si besoin dans "
                "[✂️ l'éditeur (timeline)](/editeur).")
    cache = gr.State(None)
    chemins_clips = gr.State([])
    derniere_video = gr.State(None)
    analyse = gr.State(None)
    illus = gr.State(None)
    illus_sel = gr.State(None)
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
                                           interactive=True, wrap=True, type="array", **_cols(6),
                                           label="Ordre et découpe")
                    bouton_assembler = gr.Button("🧩 Assembler les vidéos", variant="secondary")
                    info_pre = gr.Markdown()
            musique = gr.File(label="Musique de fond (facultatif)", file_types=["audio"], type="filepath")

            with gr.Accordion("⚙️ Paramètres", open=False, elem_id="acc-parametres") as acc_param:
                with gr.Tabs():
                    with gr.Tab("🎨 Identité visuelle"):
                        gr.Markdown("Votre marque : appliquée à **tous** les styles (couleurs des écrans, logo, polices).")
                        nom_marque = gr.Textbox(value=ID0.get("nom", ""), label="Nom de la marque")
                        with gr.Row():
                            c1 = gr.ColorPicker(value=ID0["couleur_1"], label="Couleur principale (écrans, fin)")
                            c2 = gr.ColorPicker(value=ID0["couleur_2"], label="Couleur secondaire")
                        logo = gr.Image(value=ID0["fichier_logo"], type="filepath", label="Logo (PNG transparent)",
                                        height=120, image_mode="RGBA", format="png")
                        with gr.Row():
                            police_serif = gr.File(label="Police du texte (.ttf/.otf)", file_types=[".ttf", ".otf"],
                                                   type="filepath")
                            police_grasse = gr.File(label="Police du mot clé (.ttf/.otf)", file_types=[".ttf", ".otf"],
                                                    type="filepath")
                        police_serif_ch = gr.State(ID0["police_serif"])
                        police_grasse_ch = gr.State(ID0["police_grasse"])
                        bouton_identite = gr.Button("💾 Enregistrer l'identité", size="sm")
                        info_identite = gr.Markdown(f"Polices actuelles : texte `{os.path.basename(ID0['police_serif'])}`, "
                                                    f"mot clé `{os.path.basename(ID0['police_grasse'])}`.")
                    with gr.Tab("🎞 Style"):
                        style_choisi = gr.Dropdown(choices=C.lister_styles(), value=CFG["style_actif"],
                                                   label="Style de montage")
                        desc_style = gr.Markdown(f"*{STYLE0.description}*" if STYLE0.description else "")
                        with gr.Accordion("🔍 Copier le style d'une vidéo", open=False):
                            gr.Markdown("Déposez une vidéo dont vous aimez le montage : l'outil mesure son rythme, ses "
                                        "sous-titres, ses couleurs… et crée un style, appliqué avec **votre** identité. "
                                        "Avec une clé Claude, l'analyse est plus fine.")
                            ref_video = gr.File(label="Vidéo de référence", file_types=["video"], type="filepath")
                            nom_ref = gr.Textbox(label="Nom du nouveau style", placeholder="ex. Style dynamique")
                            bouton_ref = gr.Button("🔍 Analyser et créer le style", variant="primary", size="sm")
                            rapport_ref = gr.Markdown()
                        with gr.Accordion("🎚 Ajuster le style", open=False):
                            cs = {}
                            cs["position_sous_titres"] = gr.Slider(0.1, 0.9, step=0.01, value=getattr(STYLE0, "position_sous_titres"), label="Hauteur des sous-titres (0 = haut, 1 = bas)")
                            cs["taille_texte"] = gr.Slider(0.5, 2.0, step=0.05, value=getattr(STYLE0, "taille_texte"), label="Taille des sous-titres")
                            cs["mots_par_groupe"] = gr.Slider(1, 6, step=1, value=getattr(STYLE0, "mots_par_groupe"), label="Mots affichés en même temps")
                            cs["mot_cle"] = gr.Checkbox(value=getattr(STYLE0, "mot_cle"), label="Un mot clé en GRAS CAPITALES par sous-titre")
                            cs["casse"] = gr.Radio(["normale", "majuscules", "minuscules"], value=getattr(STYLE0, "casse"), label="Casse des autres mots")
                            cs["animation"] = gr.Radio(["pop", "fondu", "aucune"], value=getattr(STYLE0, "animation"), label="Apparition des mots")
                            cs["style_etalonnage"] = gr.Dropdown(list(M.ETALONNAGES), value=getattr(STYLE0, "style_etalonnage"), label="Étalonnage (couleurs de l'image)")
                            cs["pause_max"] = gr.Slider(0.2, 1.0, step=0.05, value=getattr(STYLE0, "pause_max"), label="Blanc maximum conservé (s)")
                            cs["duree_plan_max"] = gr.Slider(0.8, 6.0, step=0.1, value=getattr(STYLE0, "duree_plan_max"), label="Durée max d'un plan avant recadrage (s)")
                            cs["zoom"] = gr.Slider(1.0, 1.3, step=0.01, value=getattr(STYLE0, "zoom"), label="Force des recadrages (zoom)")
                            cs["nb_ecrans_couleur"] = gr.Slider(0, 6, step=1, value=getattr(STYLE0, "nb_ecrans_couleur"), label="Écrans de couleur")
                            cs["effets_sonores"] = gr.Radio(["léger", "aucun"], value=getattr(STYLE0, "effets_sonores"), label="Effets sonores")
                            cs["ecran_fin"] = gr.Checkbox(value=getattr(STYLE0, "ecran_fin"), label="Écran de fin avec logo")
                            cs["logo_en_coin"] = gr.Checkbox(value=getattr(STYLE0, "logo_en_coin"), label="Logo en bas à gauche sur la fin")
                            cs["transition"] = gr.Radio(M.TRANSITIONS, value=getattr(STYLE0, "transition"), label="Transition entre les plans")
                            cs["duree_transition"] = gr.Slider(0.1, 0.8, step=0.05, value=getattr(STYLE0, "duree_transition"), label="Durée des transitions (s)")
                            cs["doodles"] = gr.Radio(M.TYPES_DOODLE, value=getattr(STYLE0, "doodles"), label="Doodles sur les mots clés (trait dessiné : souligné, entouré, mélange)")
                            cs["caler_sur_rythme"] = gr.Checkbox(value=getattr(STYLE0, "caler_sur_rythme"), label="Avec une musique : caler recadrages et écrans sur le rythme")
                            cs["illustrations_par_minute"] = gr.Slider(0, 15, step=0.5, value=getattr(STYLE0, "illustrations_par_minute"), label="Illustrations proposées par minute (0 = aucune)")
                            nouveau_style = gr.Textbox(label="Enregistrer sous un nouveau nom (facultatif)")
                            bouton_style = gr.Button("💾 Enregistrer le style", size="sm")
                            info_style = gr.Markdown()
                    with gr.Tab("🔑 Clés API"):
                        gr.Markdown("Facultatives. **Pexels** et **Pixabay** (gratuites) : recherche d'images et de vidéos "
                                    "d'illustration libres de droits — [pexels.com/api](https://www.pexels.com/api/), "
                                    "[pixabay.com/api/docs](https://pixabay.com/api/docs/). **IA** : **Ollama** (gratuite, sur ce Mac — "
                                    "installez-la avec « Installer IA locale (Ollama).command ») ou **Claude** (payante, quelques "
                                    "centimes par vidéo) pour un choix des moments à illustrer et une analyse de style plus fins — "
                                    "[console.anthropic.com](https://console.anthropic.com/). Les clés restent sur ce Mac.")
                        choix_ia = gr.Radio(list(CHOIX_IA), label="IA (choix des moments à illustrer, analyse de style)",
                                            value=next((k for k, v in CHOIX_IA.items()
                                                        if v == ((CFG.get("ia") or {}).get("fournisseur")
                                                                 or ("claude" if CLES0.get("anthropic") else "aucune"))),
                                                       "Aucune (règles automatiques, gratuit)"))
                        with gr.Row():
                            test_ollama = gr.Button("🔌 Tester Ollama", size="sm")
                            info_ollama = gr.Markdown()
                        cle_anthropic = gr.Textbox(value=CLES0.get("anthropic", ""), type="password", label="Clé Claude (Anthropic)")
                        cle_pexels = gr.Textbox(value=CLES0.get("pexels", ""), type="password", label="Clé Pexels")
                        cle_pixabay = gr.Textbox(value=CLES0.get("pixabay", ""), type="password", label="Clé Pixabay")
                        gr.Markdown("**✨ Illustrations créées par IA — gratuit avec Cloudflare** : au lieu de chercher des "
                                    "photos existantes, une IA (FLUX) crée pour chaque passage une image adaptée à ce qui est "
                                    "dit et à votre contexte. Gratuit jusqu'à ~170 images par jour, sans carte bancaire : "
                                    "créez un compte sur [dash.cloudflare.com](https://dash.cloudflare.com/sign-up), copiez "
                                    "l'**Account ID** (page d'accueil du compte), puis créez un **jeton d'API** avec le modèle "
                                    "« Workers AI » (Mon profil › Jetons d'API › Créer un jeton).")
                        with gr.Row():
                            cle_cf_compte = gr.Textbox(value=CLES0.get("cloudflare_compte", ""), label="Cloudflare — Account ID")
                            cle_cf_jeton = gr.Textbox(value=CLES0.get("cloudflare_jeton", ""), type="password", label="Cloudflare — jeton d'API")
                        with gr.Row():
                            test_cf = gr.Button("🔌 Tester Cloudflare", size="sm")
                            info_cf = gr.Markdown()
                        gr.Markdown("**✨ Illustrations créées par Gemini** (facultatif, payant) : au lieu de chercher des photos "
                                    "existantes, Gemini dessine pour chaque passage une image verticale adaptée à ce qui est dit "
                                    "et à votre contexte (Bénin, location…). Clé sur [aistudio.google.com/apikey]"
                                    "(https://aistudio.google.com/apikey) — la génération d'images demande d'activer la "
                                    "facturation Google (≈ 0,03 $ l'image, soit ≈ 0,20 $ pour une vidéo d'une minute).")
                        cle_gemini = gr.Textbox(value=CLES0.get("gemini", ""), type="password", label="Clé Gemini (Google AI Studio)")
                        with gr.Row():
                            test_gemini = gr.Button("🔌 Tester la clé Gemini", size="sm")
                            info_gemini = gr.Markdown()
                        source_ill = gr.Radio(list(SOURCES_ILL), label="Illustrations du montage automatique",
                                              value=next((k for k, v in SOURCES_ILL.items()
                                                          if v == (CFG.get("illustrations") or {}).get("source", "banques")),
                                                         list(SOURCES_ILL)[0]))
                        contexte_ill = gr.Textbox(value=(CFG.get("illustrations") or {}).get("contexte", C.CONTEXTE_DEFAUT),
                                                  lines=3, label="Contexte donné à l’IA qui crée les images (lieu, personnes, thème de vos vidéos)")
                        bouton_cles = gr.Button("💾 Enregistrer les clés", size="sm")
                        info_cles = gr.Markdown()
                    with gr.Tab("🔧 Avancé"):
                        hesit = gr.Checkbox(value=True, label="Couper les hésitations (euh, hum…)")
                        vol = gr.Slider(0.05, 0.50, value=0.18, step=0.01, label="Volume de la musique")
                        vocabulaire = gr.Textbox(value="Locapay, démarcheurs, loyer, propriétaire, locataire, Cotonou, Bénin",
                                                 label="Mots rares à bien reconnaître")
                        modele = gr.Radio(["Précis (recommandé)", "Rapide"], value="Précis (recommandé)", label="Transcription")
                        auto_qt = gr.Checkbox(value=(sys.platform == "darwin"), label="Ouvrir la vidéo dans QuickTime à la fin du montage")

            corrections = gr.State(charger_dico())
            corr_choisie = gr.State(None)
            with gr.Accordion("✏️ Corrections de mots", open=False) as acc_corr:
                table_corr = gr.Dataframe(headers=["N°", "Moment", "Reconnu", "Corrigé en"],
                                          datatype=["number", "str", "str", "str"], type="array",
                                          interactive=False, wrap=True, value=lignes_corrections(charger_dico()),
                                          column_widths=["9%", "27%", "32%", "32%"], label="Corrections")
                with gr.Row():
                    plus = gr.Button("➕ Ajouter une correction", variant="primary", size="sm")
                    moins = gr.Button("🗑 Supprimer la ligne sélectionnée", size="sm")
                info_corr = gr.Markdown()
                with gr.Group(visible=False) as formulaire:
                    moment = gr.Dropdown(label="1. Moment", choices=choix_moments(None), value=None,
                                         info="Une phrase précise (minutage) ou partout")
                    with gr.Row():
                        mots_sel = gr.Dropdown(label="2. Mot(s) à corriger", multiselect=True, choices=[],
                                               visible=False, scale=4,
                                               info="Cliquez sur le ou les mots, dans l'ordre de la phrase")
                        ecoute_moment = gr.Button("🔊 Écouter", size="sm", scale=1)
                    avant = gr.Textbox(label="Mot(s) à corriger (tels que reconnus)")
                    apres = gr.Textbox(label="3. Remplacer par", placeholder="Laisser vide pour supprimer ces mots")
                    with gr.Row():
                        ok_corr = gr.Button("✔ Ajouter", variant="primary", size="sm")
                        annuler_corr = gr.Button("Annuler", size="sm")
            valider = gr.Checkbox(value=True, label="Me faire valider avant le montage (passages douteux, fon, "
                                                    "illustrations proposées)")
            bouton = gr.Button("🎬 Monter la vidéo", variant="primary", size="lg")
        with gr.Column(scale=1):
            resultat = gr.Video(label="Vidéo montée", height=560)
            info = gr.Markdown()
            editer = gr.Button("✂️ Retoucher dans l'éditeur (timeline)", variant="primary", visible=False)
            chemin_projet = gr.Textbox(visible=False)
            with gr.Row():
                quicktime = gr.Button("▶️ Lire dans QuickTime", variant="secondary")
                dossier = gr.Button("📂 Ouvrir le dossier des montages")
            fichiers = gr.File(label="Fichiers (vidéo, sous-titres .srt, transcription)", file_count="multiple")
            with gr.Accordion("Transcription et plan de montage", open=False):
                transcription = gr.Textbox(label="Transcription", lines=5)
                plan = gr.Textbox(label="Plan (MAJUSCULES = mot en gras)", lines=12)

    with gr.Accordion("🔎 Validation des passages", open=False) as acc_valid:
        gr.Markdown("Chaque ligne est une phrase. **Cliquez sur une ligne pour l'écouter.** "
                    "Décochez **Garder** pour la supprimer, décochez **Sous-titres** pour la garder sans sous-titres. "
                    "Vous pouvez corriger le **texte** : pour un passage en fon, tapez la traduction française.")
        tableau_valid = gr.Dataframe(headers=M.COLONNES_VALIDATION,
                                     datatype=["number", "number", "number", "str", "str", "str", "bool", "bool"],
                                     interactive=True, wrap=True, type="array", **_cols(8),
                                     column_widths=["5%", "7%", "7%", "41%", "9%", "17%", "7%", "7%"],
                                     label="Passages")
        with gr.Row():
            ecoute = gr.Audio(label="Écoute du passage", autoplay=True, visible=(sys.platform != "darwin"))
            stop = gr.Button("⏹ Arrêter l'écoute", visible=(sys.platform == "darwin"))

    with gr.Accordion("🖼 Illustrations proposées", open=False) as acc_illus:
        gr.Markdown("Une image ou vidéo est proposée aux moments où l'on parle de quelque chose de concret. "
                    "**Cliquez sur une illustration** (galerie ou tableau) puis : **🔄 Autre proposition**, ou "
                    "**📁 Mon fichier** pour mettre la vôtre. Modifiez la **Recherche** (en anglais de préférence) puis "
                    "**🔍 Relancer**. Décochez **Garder** pour retirer une illustration.")
        galerie = gr.Gallery(label="Illustrations", columns=6, rows=1, height=300, object_fit="cover",
                             allow_preview=False, preview=False)
        table_illus = gr.Dataframe(headers=["N°", "Moment", "Mot", "Recherche (modifiable)", "Garder"],
                                   datatype=["number", "str", "str", "str", "bool"], interactive=True, wrap=True,
                                   type="array", **_cols(5), column_widths=["7%", "12%", "18%", "53%", "10%"],
                                   label="Moments illustrés")
        with gr.Row():
            autre = gr.Button("🔄 Autre proposition", size="sm")
            relancer = gr.Button("🔍 Relancer les recherches modifiées", size="sm")
            fichier_perso = gr.File(label="📁 Mon image ou vidéo pour l'illustration sélectionnée",
                                    file_types=["image", "video"], type="filepath", height=90)

    # ------------------------------------------------------------------ événements
    comps_style = [cs[k] for k in STYLE_CLES]
    comps_identite = [nom_marque, c1, c2, logo, police_serif_ch, police_grasse_ch]
    comps_cles = [cle_anthropic, cle_pexels, cle_pixabay, cle_gemini, cle_cf_compte, cle_cf_jeton]
    comps_avance = [hesit, vol, vocabulaire, modele, auto_qt]

    bouton.click(monter, [video, musique, *comps_identite, *comps_style, *comps_cles, *comps_avance,
                          corrections, cache, valider, analyse, tableau_valid, illus, table_illus],
                 [resultat, transcription, plan, fichiers, info, cache, derniere_video, analyse, tableau_valid,
                  acc_valid, moment, illus, table_illus, galerie, acc_illus, chemin_projet, editer])
    editer.click(None, [chemin_projet], None,
                 js="(p) => { if (p) window.location.href = '/editeur?p=' + encodeURIComponent(p); }")

    bouton_identite.click(sauver_identite, [nom_marque, c1, c2, logo, police_serif, police_grasse],
                          [info_identite, logo, police_serif_ch, police_grasse_ch])
    bouton_cles.click(sauver_cles, comps_cles + [choix_ia, source_ill, contexte_ill], [info_cles])
    def _cles_actuelles():           # relues à chaque ouverture de la page (sinon valeurs du démarrage de l'app)
        cfg = C.charger_config(); k = cfg["cles"]; ill = cfg.get("illustrations") or {}
        fourn = (cfg.get("ia") or {}).get("fournisseur") or ("claude" if k.get("anthropic") else "aucune")
        return (k.get("anthropic", ""), k.get("pexels", ""), k.get("pixabay", ""), k.get("gemini", ""),
                k.get("cloudflare_compte", ""), k.get("cloudflare_jeton", ""),
                next((n for n, v in CHOIX_IA.items() if v == fourn), list(CHOIX_IA)[0]),
                next((n for n, v in SOURCES_ILL.items() if v == ill.get("source", "banques")), list(SOURCES_ILL)[0]),
                ill.get("contexte") or C.CONTEXTE_DEFAUT)
    app.load(_cles_actuelles, None, comps_cles + [choix_ia, source_ill, contexte_ill])
    test_cf.click(lambda a, j: I.tester_cloudflare((a or "").strip(), (j or "").strip())[1], [cle_cf_compte, cle_cf_jeton], [info_cf])
    test_gemini.click(lambda k: I.tester_gemini((k or "").strip())[1], [cle_gemini], [info_gemini])
    test_ollama.click(tester_ollama_ui, None, [info_ollama])
    style_choisi.change(charger_style_ui, [style_choisi], comps_style + [desc_style])
    bouton_style.click(sauver_style_ui, [nouveau_style, style_choisi, *comps_style], [style_choisi, info_style])
    bouton_ref.click(analyser_reference, [ref_video, nom_ref, cle_anthropic],
                     [style_choisi, *comps_style, desc_style, rapport_ref])

    galerie.select(selection_illus, None, [illus_sel])
    table_illus.select(selection_illus, None, [illus_sel])
    autre.click(autre_proposition, [illus, illus_sel], [illus, galerie])
    relancer.click(relancer_recherches, [illus, table_illus, cle_pexels, cle_pixabay], [illus, galerie])
    fichier_perso.upload(mon_fichier, [fichier_perso, illus, illus_sel], [illus, galerie, fichier_perso])

    plus.click(ouvrir_formulaire, [cache], [formulaire, moment, mots_sel, avant, apres, info_corr])
    annuler_corr.click(fermer_formulaire, None, [formulaire])
    moment.change(choisir_moment, [moment, cache], [mots_sel, avant])
    mots_sel.change(choisir_mots, [mots_sel, cache], [avant])
    ecoute_moment.click(ecouter_moment, [moment, cache], [ecoute])
    ok_corr.click(ajouter_correction, [moment, mots_sel, avant, apres, corrections, cache],
                  [corrections, table_corr, formulaire, info_corr])
    table_corr.select(selectionner_correction, None, [corr_choisie])
    moins.click(supprimer_correction, [corrections, corr_choisie], [corrections, table_corr, corr_choisie, info_corr])
    app.load(lambda: (charger_dico(), lignes_corrections(charger_dico())), None, [corrections, table_corr])

    def _ouvrir_parametres(request: gr.Request):      # lien « ⚙️ Paramètres » de l'éditeur : /?parametres=1
        return gr.Accordion(open=bool(request and request.query_params.get("parametres")))
    app.load(_ouvrir_parametres, None, acc_param,
             js="() => { if (location.search.includes('parametres')) setTimeout(() => "
                "document.getElementById('acc-parametres')?.scrollIntoView({behavior: 'smooth'}), 600); }")
    tableau_valid.select(ecouter, [analyse], [ecoute])
    stop.click(arreter_ecoute)
    dossier.click(ouvrir_dossier)
    quicktime.click(lire_quicktime, [derniere_video], None)
    clips.change(lister_clips, [clips], [tableau, chemins_clips])
    bouton_assembler.click(assembler, [tableau, chemins_clips], [video, derniere_video, info_pre, onglets])


def _port_libre(prefere=7860):
    import socket
    for p in [prefere] + [0]:
        so = socket.socket()
        try:
            so.bind(("127.0.0.1", p))
            port = so.getsockname()[1]
            so.close()
            return port
        except OSError:
            so.close()
    return prefere


def lancer(port=None, navigateur=True, bloquant=True, page="editeur"):
    """Serveur unique : interface (/) + éditeur timeline (/editeur). Renvoie l'adresse."""
    import threading
    import webbrowser
    import uvicorn
    from fastapi import FastAPI
    import editeur as E

    racines = [SORTIES, I.DOSSIER_CACHE, C.DOSSIER, ICI]
    api = FastAPI()
    E.ajouter_routes(api, racines)
    api = gr.mount_gradio_app(api, app.queue(), path="/", allowed_paths=racines,
                              **({"theme": THEME, "head": TETE, "css": CSS} if GR6 else {}))
    port = port or _port_libre()
    url = f"http://127.0.0.1:{port}/"
    serveur = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=port, log_level="warning"))
    print(f"* Montage Locapay : {url}", flush=True)
    if bloquant:
        if navigateur:
            threading.Timer(2.0, lambda: webbrowser.open(url + page)).start()
        serveur.run()
    else:
        threading.Thread(target=serveur.run, daemon=True).start()
        for _ in range(200):
            if serveur.started:
                break
            time.sleep(0.1)
    return url


if __name__ == "__main__":
    lancer()
