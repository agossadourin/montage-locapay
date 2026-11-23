"""Paramètres persistants : identité visuelle, clés API, profils de style.

Tout est rangé dans ~/Movies/Raccord/.parametres/ (fichiers JSON lisibles).
"""
import json
import os
import re
from dataclasses import asdict, dataclass, fields

import chemins

chemins.migrer()                               # reprise d'une ancienne installation « Montage Locapay »
ICI = os.path.dirname(os.path.abspath(__file__))
DOSSIER = chemins.DOSSIER_PARAMETRES
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
    transition: str = "coupe"                  # entre deux plans : coupe / fondu / zoom / flash / glissement
    duree_transition: float = 0.25
    doodles: str = "aucun"                     # trait dessiné sur certains mots clés : aucun / souligne / cercle / melange
    caler_sur_rythme: bool = True              # avec une musique : recadrages et écrans calés sur les temps forts

    @classmethod
    def depuis(cls, d):
        noms = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in noms})


STYLE_BASE = "Face caméra"
STYLE_DEFAUT = ProfilStyle(description="Face caméra : sous-titres italiques + mot clé en gras, coupes rapides, "
                                       "écrans de couleur.")

IDENTITE_DEFAUT = {
    "nom": "Ma marque",
    "couleur_1": "#1F2340",
    "couleur_2": "#FFA41B",
    "fichier_logo": "",
    "police_serif": os.path.join(ICI, "polices", "serif.ttf"),
    "police_grasse": os.path.join(ICI, "polices", "gras.ttf"),
}

CONTEXTE_DEFAUT = ""          # décrit dans les Paramètres : lieu, personnes, thème des vidéos

CONFIG_DEFAUT = {"identite": IDENTITE_DEFAUT, "cles": {"anthropic": "", "pexels": "", "pixabay": "", "gemini": "",
                                                    "cloudflare_compte": "", "cloudflare_jeton": ""},
                 "illustrations": {"source": "banques", "contexte": CONTEXTE_DEFAUT},
                 "style_actif": STYLE_BASE}


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
    out["illustrations"].update({k: v for k, v in (c.get("illustrations") or {}).items() if v not in (None, "")})
    for k, v in c.items():                     # autres réglages (ex. choix de l'IA) : conservés tels quels
        if k not in out:
            out[k] = v
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
    noms = [STYLE_BASE]
    if os.path.isdir(DOSSIER_STYLES):
        for f in sorted(os.listdir(DOSSIER_STYLES)):
            if f.endswith(".json"):
                n = _lire(os.path.join(DOSSIER_STYLES, f), {}).get("_nom") or f[:-5]
                if n not in noms:
                    noms.append(n)
    return noms


def charger_style(nom):
    d = _lire(os.path.join(DOSSIER_STYLES, _nom_fichier(nom) + ".json"), None) if nom else None
    return ProfilStyle.depuis(d) if d else ProfilStyle(**asdict(STYLE_DEFAUT))


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
