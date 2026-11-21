"""Paramètres persistants : identité visuelle, clés API, profils de style.

Tout est rangé dans ~/Movies/Montages Locapay/.parametres/ (fichiers JSON lisibles).
"""
import json
import os
import re
from dataclasses import asdict, dataclass, fields

ICI = os.path.dirname(os.path.abspath(__file__))
DOSSIER = os.path.join(os.path.expanduser("~"), "Movies", "Montages Locapay", ".parametres")
FICHIER = os.path.join(DOSSIER, "config.json")
DOSSIER_STYLES = os.path.join(DOSSIER, "styles")


@dataclass
class ProfilStyle:
    """Tout ce qui définit « le style » d'un montage, indépendamment de la marque."""
    description: str = ""
    position_sous_titres: float = 0.66
    taille_texte: float = 1.0
    mots_par_groupe: int = 4
    mot_cle: bool = True
    casse: str = "normale"
    animation: str = "pop"
    style_etalonnage: str = "chaud"
    pause_max: float = 0.45
    duree_plan_max: float = 2.4
    zoom: float = 1.15
    nb_ecrans_couleur: int = 2
    effets_sonores: str = "léger"
    ecran_fin: bool = True
    logo_en_coin: bool = True
    illustrations_par_minute: float = 6.0     # densité d'images d'illustration proposées
    transition: str = "fondu"                  # entre deux plans : coupe / fondu / zoom / flash / glissement
    duree_transition: float = 0.25

    @classmethod
    def depuis(cls, d):
        noms = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in noms})


STYLE_LOCAPAY = ProfilStyle(description="Style de référence Locapay : sous-titres italiques + mot clé en gras, "
                                        "coupes rapides, écrans de couleur.")

IDENTITE_DEFAUT = {
    "nom": "Locapay",
    "couleur_1": "#2E2C51",
    "couleur_2": "#0AC2A4",
    "fichier_logo": os.path.join(ICI, "logo_locapay.png"),
    "police_serif": os.path.join(ICI, "polices", "serif.ttf"),
    "police_grasse": os.path.join(ICI, "polices", "gras.ttf"),
}

CONFIG_DEFAUT = {"identite": IDENTITE_DEFAUT, "cles": {"anthropic": "", "pexels": "", "pixabay": ""},
                 "style_actif": "Locapay"}


def _lire(chemin, defaut):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def _ecrire(chemin, donnees):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=1)
    os.replace(tmp, chemin)


def charger_config():
    c = _lire(FICHIER, {})
    out = json.loads(json.dumps(CONFIG_DEFAUT))
    for k in ("identite", "cles"):
        out[k].update({kk: vv for kk, vv in (c.get(k) or {}).items() if vv not in (None,)})
    out["style_actif"] = c.get("style_actif") or out["style_actif"]
    # fichiers disparus (ex. dossier du projet déplacé) : retour aux valeurs par défaut
    for k in ("fichier_logo", "police_serif", "police_grasse"):
        if out["identite"].get(k) and not os.path.exists(out["identite"][k]):
            out["identite"][k] = IDENTITE_DEFAUT[k]
    return out


def sauver_config(config):
    _ecrire(FICHIER, config)


# ------------------------------------------------------------------ styles
def _nom_fichier(nom):
    return re.sub(r"[^\w\- ]", "_", nom).strip() or "style"


def lister_styles():
    noms = ["Locapay"]
    if os.path.isdir(DOSSIER_STYLES):
        for f in sorted(os.listdir(DOSSIER_STYLES)):
            if f.endswith(".json"):
                n = _lire(os.path.join(DOSSIER_STYLES, f), {}).get("_nom") or f[:-5]
                if n not in noms:
                    noms.append(n)
    return noms


def charger_style(nom):
    if nom in (None, "", "Locapay") and not os.path.exists(os.path.join(DOSSIER_STYLES, "Locapay.json")):
        return ProfilStyle(**asdict(STYLE_LOCAPAY))
    d = _lire(os.path.join(DOSSIER_STYLES, _nom_fichier(nom) + ".json"), None)
    return ProfilStyle.depuis(d) if d else ProfilStyle(**asdict(STYLE_LOCAPAY))


def sauver_style(nom, profil):
    d = asdict(profil)
    d["_nom"] = nom
    _ecrire(os.path.join(DOSSIER_STYLES, _nom_fichier(nom) + ".json"), d)
    return nom


def reglages(M, identite, profil, **extra):
    """Construit les Reglages du moteur à partir de l'identité visuelle et du profil de style."""
    d = {k: v for k, v in asdict(profil).items() if k not in ("description", "illustrations_par_minute")}
    d.update({k: identite[k] for k in ("couleur_1", "couleur_2", "fichier_logo", "police_serif", "police_grasse")
              if identite.get(k)})
    d.update(extra)
    noms = {f.name for f in fields(M.Reglages)}
    return M.Reglages(**{k: v for k, v in d.items() if k in noms})
