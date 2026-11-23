"""Projet de montage éditable (timeline façon CapCut).

Un projet décrit le montage piste par piste. Les sous-titres, illustrations et écrans de couleur sont
ancrés sur le temps de la vidéo SOURCE (la voix) : si l'on raccourcit ou déplace un plan, ils suivent.

{
  "version": 1, "video": chemin source, "duree_source": s,
  "clips":        [{"id", "a", "b", "zoom"}]                 # piste vidéo, dans l'ordre de sortie
  "sous_titres":  [{"id", "deb", "fin", "mots": [{"w", "t"}], "cle": index|None}]
  "ecrans":       [{"id", "deb", "fin", "couleur": "#RRGGBB"}]
  "illustrations":[{"id", "deb", "fin", "fichier", "type"}]
  "musique":      {"fichier", "volume", "decalage"} | None
  "reglages":     {... Reglages ...}
}
"""
import hashlib
import json
import os
import shutil
import uuid
from dataclasses import asdict, fields

import montage_auto as M

import chemins

DOSSIER_SOURCES = os.path.join(chemins.DOSSIER_APP, ".sources")


def _id():
    return uuid.uuid4().hex[:8]


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(rgb)


def garder_source(chemin):
    """Copie la vidéo source à l'abri (les fichiers temporaires de l'interface sont effacés à la fermeture)."""
    racine = os.path.dirname(os.path.dirname(DOSSIER_SOURCES))
    if os.path.realpath(chemin).startswith(os.path.realpath(racine)):
        return chemin
    os.makedirs(DOSSIER_SOURCES, exist_ok=True)
    h = hashlib.md5(f"{os.path.basename(chemin)}{os.path.getsize(chemin)}".encode()).hexdigest()[:10]
    dest = os.path.join(DOSSIER_SOURCES, f"{h}_{os.path.basename(chemin)}")
    if not os.path.exists(dest):
        try:
            os.link(chemin, dest)
        except OSError:
            shutil.copyfile(chemin, dest)
    return dest


def creer(video, plan, R, musique=None):
    """Projet à partir d'un plan de montage automatique."""
    mots_cle = lambda g: g["cle"]
    reglages = {k: v for k, v in asdict(R).items() if k != "illustrations"}
    return {
        "version": 2,
        "video": video,
        "duree_source": M.duree_video(video),
        "clips": [{"id": _id(), "a": round(p["a"], 3), "b": round(p["b"], 3), "zoom": p["zoom"]} for p in plan["plans"]],
        "sous_titres": [{"id": _id(), "deb": round(g["deb"], 3), "fin": round(g["fin"], 3),
                         "mots": [{"w": w["w"], "t": round(w["s"], 3)} for w in g["mots"]], "cle": mots_cle(g)}
                        for g in plan["groupes"]],
        "ecrans": [{"id": _id(), "deb": round(g["deb"] - 0.04, 3), "fin": round(g["fin"], 3), "couleur": _hex(g["ecran"])}
                   for g in plan["groupes"] if g["ecran"] is not None],
        "illustrations": [{"id": _id(), "deb": it["deb"], "fin": it["fin"], "fichier": it["fichier"],
                           "type": it.get("type") or ("video" if it["fichier"].lower().endswith(M.EXT_VIDEO) else "image")}
                          for it in (R.illustrations or [])],
        "musique": ({"fichier": musique, "volume": R.volume_musique, "decalage": 0.0} if musique else None),
        "reglages": reglages,
        "alertes": [],
        "auto": {"fait": True},
    }


def vers_plan(proj):
    """(plan, Reglages) prêts pour montage_auto.monter."""
    noms = {f.name for f in fields(M.Reglages)}
    R = M.Reglages(**{k: v for k, v in (proj.get("reglages") or {}).items() if k in noms})
    R.illustrations = [dict(it) for it in proj.get("illustrations", []) if it.get("fichier")]
    mus = proj.get("musique") or {}
    R.volume_musique = float(mus.get("volume", R.volume_musique))
    R.decalage_musique = float(mus.get("decalage", 0.0))

    plans, o = [], 0.0
    for c in proj["clips"]:
        a, b = float(c["a"]), float(c["b"])
        if b - a < 1.0 / M.FPS:
            continue
        plans.append({"a": a, "b": b, "zoom": float(c.get("zoom", 1.0)), "o": o,
                      "transition": c.get("transition") or None})   # vers le plan suivant (None = style)
        o += b - a
    if not plans:
        raise ValueError("La piste vidéo est vide.")
    zones = []
    for p in plans:
        if zones and abs(zones[-1]["b"] - p["a"]) < 1e-3:
            zones[-1]["b"] = p["b"]
        else:
            zones.append({"a": p["a"], "b": p["b"]})

    ecrans = [(float(e["deb"]), float(e["fin"]), M.hex2rgb(e["couleur"])) for e in proj.get("ecrans", [])]
    groupes = []
    for st in sorted(proj.get("sous_titres", []), key=lambda s: s["deb"]):
        mots = [{"w": m["w"], "s": float(m["t"]), "e": float(m["t"]) + 0.3} for m in st.get("mots", []) if m.get("w")]
        if not mots:
            continue
        milieu = (float(st["deb"]) + float(st["fin"])) / 2
        couleur = next((c for a, b, c in ecrans if a <= milieu < b), None)
        cle = st.get("cle")
        groupes.append({"mots": mots, "deb": float(st["deb"]), "fin": float(st["fin"]),
                        "cle": cle if isinstance(cle, int) and 0 <= cle < len(mots) else None, "ecran": couleur,
                        "doodle": st.get("doodle") or None})
    corps = o
    plan = {"plans": plans, "zones": zones, "groupes": groupes, "ecrans": ecrans, "corps": corps,
            "mots": [m for g in groupes for m in g["mots"]],
            "total": corps + (R.duree_fin if R.ecran_fin else 0.0)}
    return plan, R


def rendre(proj, sortie, rappel=None):
    plan, R = vers_plan(proj)
    mus = (proj.get("musique") or {}).get("fichier")
    M.monter(proj["video"], plan, R, sortie, musique=mus if mus and os.path.exists(mus) else None,
             progression=False, rappel=rappel)
    M.ecrire_srt(plan, os.path.splitext(sortie)[0] + ".srt")
    return sortie


def sauver(proj, chemin):
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(proj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, chemin)
    return chemin


def charger(chemin):
    with open(chemin, encoding="utf-8") as f:
        proj = json.load(f)
    if proj.get("version", 1) < 2:
        # v0.12 mettait un fondu entre tous les plans par défaut : on revient aux coupes franches
        # (les transitions choisies plan par plan sont gardées)
        reg = proj.setdefault("reglages", {})
        if reg.get("transition") in (None, "fondu"):
            reg["transition"] = "coupe"
        proj["version"] = 2
    return proj


# ================================================================== démarrer par la timeline
DOSSIER_PROJETS = os.path.dirname(DOSSIER_SOURCES)
VOCABULAIRE_DEFAUT = ""          # par défaut : le nom de la marque (Paramètres › Avancé pour en ajouter)
FICHIER_DICO = os.path.join(DOSSIER_PROJETS, ".dictionnaire_corrections.json")


def _config_courante():
    import configuration as C
    cfg = C.charger_config()
    profil = C.charger_style(cfg["style_actif"])
    R = C.reglages(M, cfg["identite"], profil)
    return cfg, profil, R


def appliquer_style(proj, profil, couleurs=None):
    """Applique un style (ProfilStyle ou dict) au projet ; couleurs = [c1, c2] pour remplacer celles de l'identité.
    Le montage automatique doit ensuite être relancé pour recalculer coupes, sous-titres et écrans."""
    import configuration as C
    cfg = C.charger_config()
    profil = profil if isinstance(profil, C.ProfilStyle) else C.ProfilStyle.depuis(profil)
    identite = dict(cfg["identite"])
    if couleurs and len(couleurs) >= 1 and couleurs[0]:
        identite["couleur_1"] = couleurs[0]
    if couleurs and len(couleurs) >= 2 and couleurs[1]:
        identite["couleur_2"] = couleurs[1]
    R = C.reglages(M, identite, profil)
    ancien = proj.get("reglages") or {}
    proj["reglages"] = {k: v for k, v in asdict(R).items() if k != "illustrations"}
    for k in ("volume_musique",):                     # réglages propres au projet : conservés
        if k in ancien:
            proj["reglages"][k] = ancien[k]
    proj["style"] = asdict(profil)
    for c in proj.get("clips", []):                   # les transitions viennent désormais du style
        c.pop("transition", None)
    return proj


def nouveau(fichiers, nom=None, rappel=None):
    """Crée un projet à partir d'une ou plusieurs vidéos : elles sont posées telles quelles sur la piste vidéo."""
    import time
    fichiers = [f for f in fichiers if f and os.path.exists(f)]
    if not fichiers:
        raise ValueError("Aucune vidéo.")
    if len(fichiers) == 1:
        source = garder_source(fichiers[0])
        clips = [{"id": _id(), "a": 0.0, "b": round(M.duree_video(source), 3), "zoom": 1.0}]
    else:                    # plusieurs rushs : mis bout à bout dans une source unique (format vertical commun)
        os.makedirs(DOSSIER_SOURCES, exist_ok=True)
        source = os.path.join(DOSSIER_SOURCES, f"rushs_{time.strftime('%Y%m%d-%H%M%S')}.mp4")
        durees = [M.duree_video(f) for f in fichiers]
        M.premontage([(f, 0, None) for f in fichiers], source, rappel=rappel)
        clips, t = [], 0.0
        for d in durees:
            clips.append({"id": _id(), "a": round(t, 3), "b": round(t + d, 3), "zoom": 1.0})
            t += d
        clips[-1]["b"] = min(clips[-1]["b"], round(M.duree_video(source), 3))
    cfg, profil, R = _config_courante()
    proj = {"version": 2, "video": source, "duree_source": M.duree_video(source), "clips": clips,
            "sous_titres": [], "ecrans": [], "illustrations": [], "alertes": [], "musique": None,
            "reglages": {k: v for k, v in asdict(R).items() if k != "illustrations"},
            "style": asdict(profil)}
    base = nom or os.path.splitext(os.path.basename(fichiers[0]))[0]
    chemin = os.path.join(DOSSIER_PROJETS, f"{base}_{time.strftime('%Y%m%d-%H%M%S')}.projet.json")
    return sauver(proj, chemin)


def _dico():
    try:
        with open(FICHIER_DICO, encoding="utf-8") as f:
            return [c for c in json.load(f) if c.get("portee") == "toujours"]
    except (OSError, ValueError):
        return []


def auto(proj, rappel=None, transcrire=None, rechercher=None, telecharger=None, generer=None):
    """Montage automatique sur ce qui est gardé dans la timeline.

    Coupe les blancs et hésitations à l'intérieur de chaque plan, crée sous-titres, écrans de couleur et
    illustrations, et signale (sans rien couper) les passages incompris (fon…) et les reprises."""
    import illustrations as I
    from copy import deepcopy
    etape = rappel or (lambda f, t: None)
    cfg = _config_courante()[0]
    cles, style = cfg["cles"], proj.get("style") or {}
    transcrire = transcrire or M.transcrire
    rechercher = rechercher or I.rechercher
    telecharger = telecharger or I.telecharger
    generer = generer or I.generer
    proj = deepcopy(proj)
    R = vers_plan({**proj, "clips": proj["clips"] or [{"a": 0, "b": 1}]})[1]
    R.illustrations = []

    # 1) transcription (gardée dans le projet : on ne la refait pas)
    if proj.get("transcription_source") != proj["video"] or not proj.get("transcription"):
        etape(0.05, "Transcription de la voix… (la 1re fois, le modèle se télécharge)")
        proj["transcription"] = transcrire(proj["video"], modele="turbo", langue="fr",
                                           vocabulaire=cfg.get("vocabulaire") or VOCABULAIRE_DEFAUT
                                           or cfg["identite"].get("nom", ""))
        proj["transcription_source"] = proj["video"]
    etape(0.45, "Analyse des phrases…")
    mots = M.corriger(proj["transcription"], _dico())
    phrases = M.analyser(mots)

    # 2) passages signalés : gardés (sans sous-titres s'ils sont incompris), à valider dans la timeline
    lignes = M.lignes_validation(phrases)
    alertes = []
    for ph, ligne in zip(phrases, lignes):
        incompris = any("incompris" in a for a in ph["alertes"])
        ligne[6], ligne[7] = True, not incompris
        if ph["alertes"]:
            alertes.append({"id": _id(), "deb": round(ph["deb"], 3), "fin": round(ph["fin"], 3),
                            "type": "incompris" if incompris else "reprise",
                            "texte": " · ".join(ph["alertes"]), "phrase": ph["texte"]})
    mots_v = M.appliquer_validation(mots, phrases, lignes)

    # 3) plan par plan : coupe des blancs, sous-titres
    R_plan = deepcopy(R); R_plan.nb_ecrans_couleur = 0
    nouveaux, groupes = [], []
    for c in proj["clips"]:
        a, b = float(c["a"]), float(c["b"])
        # mots qui chevauchent le plan (un passage peut être coupé en deux par la limite entre deux rushs)
        ws = [dict(w, s=max(a, w["s"]), e=min(b, w["e"])) for w in mots_v if w["e"] > a and w["s"] < b]
        ws = [w for w in ws if w["e"] - w["s"] > 0.02 or w.get("st", True)]
        if not any(w.get("st", True) and w.get("w") for w in ws) and not ws:
            nouveaux.append(dict(c)); continue                   # plan sans parole : gardé tel quel
        try:
            plan = M.construire_plan(ws, b, R_plan)
        except ValueError:
            nouveaux.append(dict(c)); continue
        for p in plan["plans"]:
            aa, bb = max(a, p["a"]), min(b, p["b"])
            if bb - aa > 0.05:
                nouveaux.append({"id": _id(), "a": round(aa, 3), "b": round(bb, 3), "zoom": p["zoom"]})
        groupes += plan["groupes"]
    proj["clips"] = nouveaux or proj["clips"]

    def sortie(t):
        o = 0.0
        for c in proj["clips"]:
            if c["a"] <= t < c["b"]:
                return o + t - c["a"]
            o += c["b"] - c["a"]
        return None
    groupes = [g for g in groupes if sortie(g["deb"]) is not None]
    groupes.sort(key=lambda g: sortie(g["deb"]))
    M.choisir_ecrans(groupes, R, temps=lambda g: sortie(g["deb"]))
    M.choisir_doodles(groupes, getattr(R, "doodles", "aucun"))
    proj["sous_titres"] = [{"id": _id(), "deb": round(g["deb"], 3), "fin": round(g["fin"], 3),
                            "mots": [{"w": w["w"], "t": round(w["s"], 3)} for w in g["mots"]], "cle": g["cle"],
                            **({"doodle": g["doodle"]} if g.get("doodle") else {})}
                           for g in groupes]
    proj["ecrans"] = [{"id": _id(), "deb": round(g["deb"] - 0.04, 3), "fin": round(g["fin"], 3), "couleur": _hex(g["ecran"])}
                      for g in groupes if g["ecran"] is not None]
    proj["alertes"] = [al for al in alertes if any(c["a"] < al["fin"] and al["deb"] < c["b"] for c in proj["clips"])]

    # 4) illustrations (avec d'autres propositions gardées pour « Autre proposition »)
    proj["illustrations"] = []
    par_minute = float(style.get("illustrations_par_minute", 6.0))
    gardes = [w for w in mots_v if w.get("st", True) and w.get("w") and sortie(w["s"]) is not None]
    duree_sortie = sum(c["b"] - c["a"] for c in proj["clips"])
    reg_ill = cfg.get("illustrations") or {}
    fourn = I.fournisseur_images(cfg) if reg_ill.get("source") in ("gemini", "cloudflare") else None
    par_gemini = fourn is not None          # (nom historique : toute génération d'images sur mesure)
    if isinstance(proj.get("auto"), dict):
        proj["auto"].pop("erreur_gemini", None)
    if par_minute > 0:                       # Openverse ne demande pas de clé : toujours au moins une source
        import ia
        props = I.choisir_moments(gardes, duree_sortie, par_minute=par_minute, cle_api=ia.config_ia(cfg))
        for k, pr in enumerate(props):
            if par_gemini:                 # image créée sur mesure pour ce passage
                nom_f = "Cloudflare" if fourn == "cloudflare" else "Gemini"
                etape(0.6 + 0.35 * k / max(1, len(props)), f"Création des illustrations ({nom_f}) {k + 1}/{len(props)}…")
                consigne = I.prompt_illustration(pr, reg_ill.get("contexte") or "", fourn)
                try:
                    fichier = generer(consigne, cfg)
                    proj["illustrations"].append({"id": _id(), "deb": round(pr["deb"], 3), "fin": round(pr["fin"], 3),
                                                  "fichier": fichier, "type": "image", "requete": pr["requete"],
                                                  "phrase": pr.get("phrase", ""), "mot": pr.get("mot", ""),
                                                  "prompt": consigne, "generee": True})
                    continue
                except Exception as e:
                    print("Illustration Gemini impossible :", e)
                    proj.setdefault("auto", {})["erreur_gemini"] = f"{nom_f} : {str(e)[:500]}"
                    par_gemini = False           # inutile de réessayer pour chaque moment (quota, clé…)
                    if not (cles.get("pexels") or cles.get("pixabay")):
                        continue
            etape(0.6 + 0.35 * k / max(1, len(props)), "Recherche d'illustrations…")
            res = rechercher(pr["requete"], cles)
            if not res:
                continue
            if res[0].get("orientation") == "paysage":     # rien en vertical pour cette recherche : on passe
                print("Illustration ignorée (seulement du paysage) :", pr["requete"])
                continue
            try:
                fichier = telecharger(res[0])
            except Exception as e:
                print("Illustration non téléchargée :", e)
                continue
            proj["illustrations"].append({"id": _id(), "deb": round(pr["deb"], 3), "fin": round(pr["fin"], 3),
                                          "fichier": fichier, "type": res[0]["type"], "requete": pr["requete"],
                                          "phrase": pr.get("phrase", ""), "mot": pr.get("mot", ""),
                                          "credit_licence": res[0].get("credit_licence", ""),
                                          "alternatives": res[:8], "choix": 0})
    # 5) musique déjà choisie : recadrages et écrans calés sur les temps forts
    mus = proj.get("musique") or {}
    if mus.get("fichier") and os.path.exists(mus["fichier"]) and getattr(R, "caler_sur_rythme", True):
        try:
            import rythme
            etape(0.97, "Calage sur le rythme de la musique…")
            rythme.caler(proj)
        except Exception as e:
            print("Calage sur le rythme impossible :", e)
    erreur_gemini = (proj.get("auto") or {}).get("erreur_gemini")
    proj["auto"] = {"fait": True, "nb_alertes": len(proj["alertes"]),
                    "sans_cle_images": not (cles.get("pexels") or cles.get("pixabay") or par_gemini)}
    if erreur_gemini:
        proj["auto"]["erreur_gemini"] = erreur_gemini
    etape(1.0, "Terminé")
    return proj
