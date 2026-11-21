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

DOSSIER_SOURCES = os.path.join(os.path.expanduser("~"), "Movies", "Montages Locapay", ".sources")


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
        "version": 1,
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
        plans.append({"a": a, "b": b, "zoom": float(c.get("zoom", 1.0)), "o": o})
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
                        "cle": cle if isinstance(cle, int) and 0 <= cle < len(mots) else None, "ecran": couleur})
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
        return json.load(f)
