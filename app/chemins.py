"""Nom de l'application et dossiers de travail.

Raccord range tout dans le dossier Vidéos de l'utilisateur : ~/Movies/Raccord sur Mac
(~/Videos/Raccord ailleurs). Les anciennes installations « Montage Locapay » sont reprises
automatiquement par `migrer()` (dossier renommé, projets, identité, dictionnaire).
"""
import json
import os
import shutil

NOM_APP = "Raccord"
SLOGAN = "Le montage face caméra, dans votre style."

_MAISON = os.path.expanduser("~")
_VIDEOS = os.path.join(_MAISON, "Movies") if os.path.isdir(os.path.join(_MAISON, "Movies")) or not \
    os.path.isdir(os.path.join(_MAISON, "Videos")) else os.path.join(_MAISON, "Videos")
DOSSIER_APP = os.path.join(_VIDEOS, NOM_APP)
DOSSIER_PARAMETRES = os.path.join(DOSSIER_APP, ".parametres")
ANCIEN_DOSSIER = os.path.join(_MAISON, "Movies", "Montages Locapay")
ICI = os.path.dirname(os.path.abspath(__file__))

# Ce que l'ancienne version appliquait par défaut : repris pour son utilisateur (et seulement pour lui).
_ANCIENS_REGLAGES = {
    "identite": {"nom": "Locapay", "couleur_1": "#2E2C51", "couleur_2": "#0AC2A4"},
    "contexte": ("Bénin, Cotonou, Afrique de l'Ouest. Personnes béninoises, quartiers et maisons typiques de Cotonou. "
                 "Thème : la location de logements (propriétaires, locataires, loyer payé par Mobile Money sur téléphone)."),
    "vocabulaire": "Locapay, démarcheurs, loyer, propriétaire, locataire, Cotonou, Bénin",
    "dictionnaire": [{"portee": "toujours", "avant": "Locapé", "apres": "Locapay"},
                     {"portee": "toujours", "avant": "Lokapay", "apres": "Locapay"}],
}


def _lire(chemin, defaut):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def _ecrire(chemin, donnees):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin + ".tmp", "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=1)
    os.replace(chemin + ".tmp", chemin)


def migrer(ancien=None, nouveau=None):
    """Reprend une installation « Montage Locapay » : renvoie True si quelque chose a été repris."""
    ancien, nouveau = ancien or ANCIEN_DOSSIER, nouveau or DOSSIER_APP
    if not os.path.isdir(ancien):
        return False
    if not os.path.exists(nouveau):
        os.makedirs(os.path.dirname(nouveau), exist_ok=True)
        shutil.move(ancien, nouveau)
    else:                                    # le nouveau dossier existe déjà (créé entre-temps) : on fusionne
        for racine, dossiers, fichiers in os.walk(ancien, topdown=False):
            cible = os.path.join(nouveau, os.path.relpath(racine, ancien))
            os.makedirs(cible, exist_ok=True)
            for f in fichiers:
                if not os.path.exists(os.path.join(cible, f)):
                    shutil.move(os.path.join(racine, f), os.path.join(cible, f))
        shutil.rmtree(ancien, ignore_errors=True)

    # 1) chemins enregistrés dans les projets, la configuration et les styles
    for racine, _, fichiers in os.walk(nouveau):
        for f in fichiers:
            if f.endswith((".projet.json", "config.json")) or (racine.endswith("styles") and f.endswith(".json")):
                p = os.path.join(racine, f)
                try:
                    texte = open(p, encoding="utf-8").read()
                except OSError:
                    continue
                for avant, apres in ((ancien, nouveau), (json.dumps(ancien)[1:-1], json.dumps(nouveau)[1:-1])):
                    texte = texte.replace(avant, apres)
                st = os.stat(p)
                with open(p, "w", encoding="utf-8") as out:
                    out.write(texte)
                os.utime(p, (st.st_atime, st.st_mtime))      # garde la date (tri des projets récents)

    # 2) l'identité Locapay, qui était celle par défaut, devient l'identité enregistrée de l'utilisateur
    param = os.path.join(nouveau, ".parametres")
    cfg_chemin = os.path.join(param, "config.json")
    cfg = _lire(cfg_chemin, {})
    ident = cfg.setdefault("identite", {})
    for k, v in _ANCIENS_REGLAGES["identite"].items():
        ident.setdefault(k, v)
    logo = ident.get("fichier_logo") or ""
    if not logo or not os.path.exists(logo) or os.path.basename(logo) == "logo_locapay.png":
        source = os.path.join(ICI, "migration", "logo_locapay.png")
        if os.path.exists(source):
            os.makedirs(param, exist_ok=True)
            shutil.copy(source, os.path.join(param, "logo.png"))
            ident["fichier_logo"] = os.path.join(param, "logo.png")
    cfg.setdefault("illustrations", {}).setdefault("contexte", _ANCIENS_REGLAGES["contexte"])
    cfg.setdefault("vocabulaire", _ANCIENS_REGLAGES["vocabulaire"])
    if cfg.get("style_actif") in (None, "", "Locapay") and not os.path.exists(os.path.join(param, "styles", "Locapay.json")):
        cfg["style_actif"] = "Face caméra"
    _ecrire(cfg_chemin, cfg)

    # 3) dictionnaire de corrections : l'ancien contenu par défaut est conservé
    dico = os.path.join(nouveau, ".dictionnaire_corrections.json")
    if not os.path.exists(dico):
        _ecrire(dico, _ANCIENS_REGLAGES["dictionnaire"])
    print(f"Ancien dossier « Montages Locapay » repris dans « {nouveau} ».", flush=True)
    return True
