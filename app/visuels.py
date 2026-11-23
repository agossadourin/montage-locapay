"""Visuels de marque (posts et stories) : charte, gabarits, génération de variantes.

- La **charte** (couleurs par rôle, polices, ton, gabarits) est déduite d'exemples de visuels de l'entreprise :
  mesure locale (palette) + analyse fine par Claude dans la conversation (paquet .zip → .raccord-charte.json),
  ou charte par défaut construite depuis l'identité visuelle.
- Un **gabarit** décrit une mise en page en blocs positionnés en % du visuel (image, forme, texte, logo).
- **Générer** : à partir d'un contexte, écrit les textes (IA locale Ollama si configurée, sinon règles simples),
  trouve des images (banques, Openverse, ou image créée par IA) et assemble plusieurs variantes.
- Le rendu (aperçu, retouche, export PNG) est fait dans le navigateur (visuels.html), à partir du même JSON.
"""
import json
import os
import re
import shutil
import tempfile
import time
import uuid

import numpy as np
from PIL import Image

import chemins
import configuration as C
import illustrations as I

DOSSIER = os.path.join(chemins.DOSSIER_APP, "Visuels")
DOSSIER_EXEMPLES = os.path.join(DOSSIER, ".exemples")
FICHIER_CHARTE = os.path.join(chemins.DOSSIER_PARAMETRES, "charte.json")
FORMATS = {"carre": (1080, 1080), "portrait": (1080, 1350), "story": (1080, 1920)}
NOMS_FORMATS = {"carre": "Post carré", "portrait": "Post portrait", "story": "Story / statut"}
EXT_IMAGES = (".png", ".jpg", ".jpeg", ".webp")

# ------------------------------------------------------------------ gabarits par défaut
# Coordonnées en % de la largeur (x, w) et de la hauteur (y, h). « story » : valeurs propres au format vertical.
GABARITS_DEFAUT = [
    {"id": "photo-bas", "nom": "Photo plein cadre, titre en bas", "blocs": [
        {"type": "image", "role": "photo", "x": 0, "y": 0, "w": 100, "h": 100},
        {"type": "forme", "x": 0, "y": 45, "w": 100, "h": 55, "degrade": ["transparent", "sombre"], "opacite": 0.9},
        {"type": "logo", "x": 6, "y": 5, "w": 22, "h": 8, "story": {"y": 4}},
        {"type": "texte", "role": "titre", "x": 6, "y": 62, "w": 88, "h": 20, "police": "titre", "taille": 8.5,
         "couleur": "clair", "align": "left", "story": {"y": 64, "h": 16, "taille": 9.5}},
        {"type": "texte", "role": "sous_titre", "x": 6, "y": 82, "w": 80, "h": 8, "police": "corps", "taille": 3.6,
         "couleur": "clair", "align": "left", "story": {"y": 80, "h": 6}},
        {"type": "texte", "role": "cta", "x": 6, "y": 91, "w": 44, "h": 5.5, "police": "corps", "taille": 3.2,
         "couleur": "sombre", "fond": "accent", "rayon": 6, "align": "left", "story": {"y": 88, "h": 4}}]},
    {"id": "bandeau", "nom": "Photo en haut, bandeau de couleur", "blocs": [
        {"type": "image", "role": "photo", "x": 0, "y": 0, "w": 100, "h": 60, "story": {"h": 62}},
        {"type": "forme", "x": 0, "y": 60, "w": 100, "h": 40, "couleur": "fond", "story": {"y": 62, "h": 38}},
        {"type": "forme", "x": 6, "y": 66, "w": 14, "h": 1.2, "couleur": "accent", "rayon": 1, "story": {"y": 67, "h": 0.7}},
        {"type": "texte", "role": "titre", "x": 6, "y": 69, "w": 88, "h": 15, "police": "titre", "taille": 7,
         "couleur": "clair", "align": "left", "story": {"y": 69, "h": 12, "taille": 8}},
        {"type": "texte", "role": "sous_titre", "x": 6, "y": 85, "w": 62, "h": 9, "police": "corps", "taille": 3.4,
         "couleur": "clair", "align": "left", "story": {"y": 82, "h": 7}},
        {"type": "logo", "x": 72, "y": 87, "w": 22, "h": 8, "story": {"y": 90, "h": 5}}]},
    {"id": "message", "nom": "Message fort sur aplat", "blocs": [
        {"type": "forme", "x": 0, "y": 0, "w": 100, "h": 100, "couleur": "fond"},
        {"type": "image", "role": "photo", "x": 62, "y": 8, "w": 30, "h": 24, "rayon": 50, "story": {"x": 30, "y": 10, "w": 40, "h": 22.5}},
        {"type": "texte", "role": "titre", "x": 8, "y": 36, "w": 84, "h": 30, "police": "titre", "taille": 9.5,
         "couleur": "clair", "align": "left", "story": {"y": 38, "h": 26, "taille": 10.5}},
        {"type": "forme", "x": 8, "y": 68, "w": 16, "h": 1.2, "couleur": "accent", "rayon": 1, "story": {"y": 66, "h": 0.7}},
        {"type": "texte", "role": "sous_titre", "x": 8, "y": 72, "w": 80, "h": 10, "police": "corps", "taille": 3.6,
         "couleur": "clair", "align": "left", "story": {"y": 69, "h": 8}},
        {"type": "logo", "x": 8, "y": 88, "w": 24, "h": 7, "story": {"y": 90, "h": 5}}]},
    {"id": "cadre", "nom": "Photo encadrée sur fond clair", "blocs": [
        {"type": "forme", "x": 0, "y": 0, "w": 100, "h": 100, "couleur": "clair"},
        {"type": "texte", "role": "titre", "x": 7, "y": 6, "w": 86, "h": 18, "police": "titre", "taille": 7,
         "couleur": "fond", "align": "left", "story": {"y": 8, "h": 14, "taille": 8}},
        {"type": "image", "role": "photo", "x": 7, "y": 26, "w": 86, "h": 52, "rayon": 4, "story": {"y": 25, "h": 52}},
        {"type": "texte", "role": "sous_titre", "x": 7, "y": 80, "w": 58, "h": 12, "police": "corps", "taille": 3.4,
         "couleur": "sombre", "align": "left", "story": {"y": 80, "h": 8}},
        {"type": "texte", "role": "cta", "x": 66, "y": 82, "w": 27, "h": 6, "police": "corps", "taille": 2.9,
         "couleur": "clair", "fond": "accent", "rayon": 6, "align": "center", "story": {"y": 90, "x": 7, "w": 44, "h": 4}},
        {"type": "logo", "x": 7, "y": 92, "w": 18, "h": 5, "story": {"x": 72, "y": 91, "w": 21, "h": 3.5}}]},
    {"id": "partage", "nom": "Moitié couleur, moitié photo", "blocs": [
        {"type": "forme", "x": 0, "y": 0, "w": 100, "h": 100, "couleur": "fond"},
        {"type": "image", "role": "photo", "x": 50, "y": 0, "w": 50, "h": 100, "story": {"x": 0, "y": 50, "w": 100, "h": 50}},
        {"type": "logo", "x": 6, "y": 6, "w": 30, "h": 7, "story": {"y": 5, "w": 30, "h": 4}},
        {"type": "texte", "role": "titre", "x": 6, "y": 30, "w": 40, "h": 36, "police": "titre", "taille": 6.4,
         "couleur": "clair", "align": "left", "story": {"y": 14, "w": 88, "h": 20, "taille": 9}},
        {"type": "texte", "role": "sous_titre", "x": 6, "y": 68, "w": 40, "h": 16, "police": "corps", "taille": 3,
         "couleur": "clair", "align": "left", "story": {"y": 35, "w": 88, "h": 8, "taille": 3.6}},
        {"type": "texte", "role": "cta", "x": 6, "y": 87, "w": 38, "h": 6, "police": "corps", "taille": 2.8,
         "couleur": "sombre", "fond": "accent", "rayon": 6, "align": "left", "story": {"y": 44, "w": 44, "h": 3.6}}]},
]


POLICES_INTEGREES = {"gras": "Montserrat (sans-serif, 100 à 900)", "poppins": "Poppins (sans-serif, 400 à 900)",
                     "serif": "Playfair Display italique", "script": "Great Vibes (manuscrite)"}


def _hex_ok(c):
    return isinstance(c, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", c) is not None


def _clair(hexa):
    r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b > 150


def charte_defaut(cfg=None):
    """Charte construite depuis l'identité visuelle (utilisée tant qu'aucune charte n'a été importée)."""
    cfg = cfg or C.charger_config()
    ident = cfg["identite"]
    c1, c2 = ident.get("couleur_1") or "#1F2340", ident.get("couleur_2") or "#FFA41B"
    return {"format": "raccord-charte", "version": 1, "nom": f"Charte {ident.get('nom') or 'de la marque'}",
            "couleurs": {"fond": c1, "accent": c2, "clair": "#FFFFFF", "sombre": "#14141A",
                         "texte": "#FFFFFF" if not _clair(c1) else "#14141A"},
            "polices": {"titre": {"fichier": ident.get("police_grasse") or "gras", "graisse": 800, "casse": "normale",
                                  "interligne": 1.05},
                        "corps": {"fichier": ident.get("police_grasse") or "gras", "graisse": 500, "casse": "normale",
                                  "interligne": 1.3},
                        "script": {"fichier": "script", "graisse": 400, "casse": "normale", "interligne": 1.0}},
            "ton": "Clair, direct et chaleureux. Phrases courtes. Tutoiement ou vouvoiement selon la marque.",
            "cta": ["En savoir plus", "Contactez-nous", "Lien en bio"], "traitement_image": "naturel",
            "mots_images": [], "gabarits": GABARITS_DEFAUT, "source": "identité"}


def charger_charte():
    d = C._lire(FICHIER_CHARTE, None)
    if not d:
        return charte_defaut()
    base = charte_defaut()
    base.update({k: v for k, v in d.items() if v})
    return base


def sauver_charte(charte):
    C._ecrire(FICHIER_CHARTE, charte)
    return charte


def valider_charte(d):
    """Fichier rendu par Claude → charte vérifiée (couleurs, polices, gabarits bornés). Lève ValueError sinon."""
    if not isinstance(d, dict) or not (d.get("couleurs") or d.get("gabarits")):
        raise ValueError("Ce fichier n'est pas une charte Raccord (couleurs ou gabarits manquants).")
    base = charte_defaut()
    out = dict(base)
    out["nom"] = str(d.get("nom") or base["nom"])[:60]
    couleurs = dict(base["couleurs"])
    couleurs.update({k: v for k, v in (d.get("couleurs") or {}).items() if _hex_ok(v)})
    out["couleurs"] = couleurs
    polices = json.loads(json.dumps(base["polices"]))
    for role in ("titre", "corps", "script"):
        p = (d.get("polices") or {}).get(role) or {}
        if p.get("fichier") in POLICES_INTEGREES or (isinstance(p.get("fichier"), str) and os.path.exists(p["fichier"])):
            polices[role]["fichier"] = p["fichier"]
        if isinstance(p.get("graisse"), (int, float)):
            polices[role]["graisse"] = int(min(900, max(100, p["graisse"])))
        if p.get("casse") in ("normale", "majuscules", "minuscules"):
            polices[role]["casse"] = p["casse"]
        if isinstance(p.get("interligne"), (int, float)):
            polices[role]["interligne"] = float(min(2, max(0.8, p["interligne"])))
        if isinstance(p.get("italique"), bool):
            polices[role]["italique"] = p["italique"]
    out["polices"] = polices
    for k in ("ton", "traitement_image"):
        if isinstance(d.get(k), str):
            out[k] = d[k][:600]
    if out.get("traitement_image") not in ("naturel", "sombre", "chaud", "noir-blanc", "duotone"):
        out["traitement_image"] = "naturel"
    if isinstance(d.get("detourer_photos"), bool):
        out["detourer_photos"] = d["detourer_photos"]
    for k in ("cta", "mots_images", "exemples_textes"):
        if isinstance(d.get(k), list):
            out[k] = [str(x)[:120] for x in d[k][:12]]
    gab = [g for g in (valider_gabarit(g) for g in (d.get("gabarits") or [])) if g]
    out["gabarits"] = gab or base["gabarits"]
    out["source"] = d.get("source") if d.get("source") in ("identité", "claude", "manuel") else "claude"
    return out


def valider_gabarit(g):
    if not isinstance(g, dict) or not isinstance(g.get("blocs"), list):
        return None
    blocs = []
    for b in g["blocs"][:20]:
        if not isinstance(b, dict) or b.get("type") not in ("image", "forme", "texte", "logo"):
            continue
        nb = {k: v for k, v in b.items() if k in ("type", "role", "couleur", "degrade", "police", "align", "fond",
                                                   "opacite", "rayon", "taille", "texte", "story", "casse", "graisse",
                                                   "rotation", "contour", "motif", "couleur_motif", "ajustement",
                                                   "interlettre")}
        for k in ("x", "y", "w", "h"):
            try:
                nb[k] = float(min(100, max(-20, float(b.get(k, 0)))))
            except (TypeError, ValueError):
                nb[k] = 0.0
        blocs.append(nb)
    if not blocs:
        return None
    return {"id": re.sub(r"[^\w\-]", "-", str(g.get("id") or uuid.uuid4().hex[:6]))[:40],
            "nom": str(g.get("nom") or "Gabarit")[:60], "blocs": blocs,
            **({"formats": [f for f in g["formats"] if f in FORMATS]} if isinstance(g.get("formats"), list) else {})}


# ------------------------------------------------------------------ exemples de la marque
def palette(images, n=6):
    """Couleurs dominantes d'un ensemble d'images (k-moyennes simples), en hexa, des plus fréquentes aux moins."""
    px = []
    for im in images:
        a = np.asarray(im.convert("RGB").resize((80, 80))).reshape(-1, 3).astype(float)
        px.append(a)
    if not px:
        return []
    x = np.concatenate(px)
    rng = np.random.default_rng(0)
    centres = x[rng.choice(len(x), size=min(n * 2, len(x)), replace=False)]
    for _ in range(12):
        d = ((x[:, None, :] - centres[None, :, :]) ** 2).sum(-1)
        lab = d.argmin(1)
        centres = np.array([x[lab == k].mean(0) if (lab == k).any() else centres[k] for k in range(len(centres))])
    poids = np.bincount(lab, minlength=len(centres))
    ordre = np.argsort(-poids)
    out = []
    for k in ordre:
        c = centres[k]
        if all(np.abs(c - np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)])).sum() > 60 for h in out):
            out.append("#%02X%02X%02X" % tuple(int(v) for v in c))
        if len(out) >= n:
            break
    return out


def ajouter_exemples(fichiers):
    os.makedirs(DOSSIER_EXEMPLES, exist_ok=True)
    gardes = []
    for f in fichiers:
        if not f.lower().endswith(EXT_IMAGES):
            continue
        dest = os.path.join(DOSSIER_EXEMPLES, os.path.basename(f))
        if os.path.abspath(f) != os.path.abspath(dest):
            shutil.copy(f, dest)
        gardes.append(dest)
    return gardes


def lister_exemples():
    if not os.path.isdir(DOSSIER_EXEMPLES):
        return []
    return sorted(os.path.join(DOSSIER_EXEMPLES, f) for f in os.listdir(DOSSIER_EXEMPLES)
                  if f.lower().endswith(EXT_IMAGES))


def planches_exemples(fichiers, par_planche=12, largeur=300):
    """Planches contact des exemples (4 par ligne, format d'origine conservé)."""
    planches = []
    for i in range(0, len(fichiers), par_planche):
        lot = []
        for f in fichiers[i:i + par_planche]:
            try:
                im = Image.open(f).convert("RGB")
            except OSError:
                continue
            im.thumbnail((largeur, int(largeur * 16 / 9)))
            lot.append(im)
        if not lot:
            continue
        cols = 4
        lignes = [lot[j:j + cols] for j in range(0, len(lot), cols)]
        h_lignes = [max(im.height for im in l) for l in lignes]
        out = Image.new("RGB", (cols * (largeur + 8), sum(h_lignes) + 8 * len(lignes)), (235, 235, 235))
        y = 0
        for l, hl in zip(lignes, h_lignes):
            for j, im in enumerate(l):
                out.paste(im, (j * (largeur + 8), y))
            y += hl + 8
        planches.append(out)
    return planches


LISEZMOI_CHARTE = """Paquet charte graphique — Raccord (visuels de marque : posts et stories)

Pour Claude : « planche-*.jpg » montre {n} visuels existants de la marque « {marque} ». « mesures.json » donne
la palette mesurée, l'identité enregistrée, les polices disponibles et la charte actuelle (format complet).
Déduis la charte graphique et renvoie UN fichier téléchargeable « <marque>.raccord-charte.json » :

{{"format": "raccord-charte", "version": 1, "nom": "Charte <marque>",
  "couleurs": {{"fond": "#…", "texte": "#…", "accent": "#…", "accent2": "#…", "clair": "#…", "sombre": "#…"}},
  "polices": {{"titre": {{"fichier": "gras|serif|<chemin d'une police de mesures.json>", "graisse": 100-900,
                        "casse": "normale|majuscules|minuscules", "interligne": 0.8-2, "italique": false}},
              "corps": {{…même forme…}}}},
  "ton": "ton éditorial en 2-3 phrases", "cta": ["appels à l'action typiques"],
  "mots_images": ["recherches d'images typiques, en anglais"], "exemples_textes": ["titres typiques"],
  "traitement_image": "naturel|sombre|chaud|noir-blanc|duotone",
  "gabarits": [ 3 à 6 mises en page qui reproduisent les exemples ] }}

Gabarit : {{"id": "…", "nom": "…", "blocs": [ … du fond vers le premier plan … ]}}. Bloc :
 type image|forme|texte|logo ; x, y, w, h en % (x, w de la largeur ; y, h de la hauteur) ;
 image : role "photo", rayon (% de la largeur, 50 = cercle) ;
 forme : couleur (nom de rôle ci-dessus ou #hexa), degrade [haut, bas] (« transparent » permis), opacite 0-1, rayon ;
 texte : role titre|sous_titre|cta, police titre|corps, taille (% de la largeur ; 8 = gros titre), couleur,
         align left|center|right, fond (pastille derrière le texte), rayon ;
 logo : le logo de la marque, contenu dans la boîte ;
 "story": {{…}} : mêmes clés, valeurs propres au format vertical 1080×1920 (sinon celles du carré/portrait).
Formats : carré 1080×1080, portrait 1080×1350, story 1080×1920.

Pour l'utilisateur : glissez ce fichier .zip dans la conversation avec Claude, puis, dans Raccord › Visuels ›
Charte, « Importer la charte de Claude » avec le fichier .json rendu.
"""


def preparer_paquet_charte(dossier=None):
    """Exemples + mesures + consignes → .zip à déposer dans une conversation avec Claude."""
    import zipfile
    fichiers = lister_exemples()
    if not fichiers:
        raise RuntimeError("Ajoutez d'abord des exemples de visuels de la marque.")
    cfg = C.charger_config()
    ims = []
    for f in fichiers[:48]:
        try:
            ims.append(Image.open(f))
        except OSError:
            pass
    pl = planches_exemples(fichiers[:48])
    dossier = dossier or os.path.join(chemins.DOSSIER_APP, "Pour Claude")
    os.makedirs(dossier, exist_ok=True)
    marque = cfg["identite"].get("nom") or "marque"
    chemin = os.path.join(dossier, f"Raccord — charte {re.sub(r'[^0-9A-Za-zÀ-ÿ_ -]', '_', marque)}.zip")
    mesures = {"format": "raccord-paquet-charte", "version": 1, "marque": marque, "nb_exemples": len(fichiers),
               "palette_mesuree": palette(ims), "identite": {k: cfg["identite"].get(k) for k in ("nom", "couleur_1", "couleur_2")},
               "polices_disponibles": {**POLICES_INTEGREES,
                                       **{cfg["identite"][k]: "police de l'identité" for k in ("police_serif", "police_grasse")
                                          if cfg["identite"].get(k)}},
               "dimensions_exemples": [list(im.size) for im in ims], "charte_actuelle": charger_charte()}
    tmp = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as z:
            for i, p in enumerate(pl, 1):
                f = os.path.join(tmp, f"planche-{i}.jpg")
                p.save(f, quality=85)
                z.write(f, f"planche-{i}.jpg")
            z.writestr("mesures.json", json.dumps(mesures, ensure_ascii=False, indent=1))
            z.writestr("LISEZMOI.txt", LISEZMOI_CHARTE.format(n=len(fichiers), marque=marque))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return chemin


# ------------------------------------------------------------------ textes
def _phrases(texte):
    return [p.strip() for p in re.split(r"(?<=[.!?…])\s+|\n+", texte.strip()) if p.strip()]


def _couper(texte, mots):
    m = texte.split()
    return texte if len(m) <= mots else " ".join(m[:mots]).rstrip(",;:") + "…"


FAIBLES = {"de", "du", "des", "la", "le", "les", "sur", "par", "pour", "avec", "et", "à", "au", "aux", "en", "depuis",
           "sans", "d'", "un", "une", "votre", "vos", "notre", "nos", "fin", "l'"}


def _titre(t, maxi=9):
    """Accroche courte : au plus `maxi` mots, coupée avant un petit mot, sans points de suspension."""
    m = t.split()
    if len(m) <= maxi:
        return t.rstrip(".")
    m = m[:maxi - 1]
    while len(m) > 3 and m[-1].lower().strip(",;:") in FAIBLES:
        m.pop()
    return " ".join(m).rstrip(",;:")


CONSIGNE_TEXTES = """Tu écris les textes d'un visuel pour les réseaux sociaux ({format}) de la marque « {marque} ».
Ton de la marque : {ton}
Exemples de titres de la marque : {exemples}
Contexte donné par l'utilisateur : « {contexte} »
Réponds UNIQUEMENT avec un objet JSON :
{{"titre": "accroche de 1 à 7 mots, percutante", "sous_titre": "une phrase de 8 à 18 mots",
 "cta": "appel à l'action de 2 à 4 mots", "accroche": "1 à 3 mots en écriture manuscrite (ex. « Bonne rentrée », « Welcome ») ou vide",
 "filigrane": "un nombre ou un mot très court à afficher en très grand en fond (ex. « 05 », « 2027 ») ou vide",
 "requete_image": "2 à 4 mots en anglais pour chercher une photo d'illustration (une personne si possible)"}}"""


def ecrire_textes(contexte, charte, cfg=None, format="carre", demander=None):
    """Textes du visuel : IA (Ollama ou Claude via API) si configurée, sinon règles simples. Ne lève jamais."""
    cfg = cfg or C.charger_config()
    contexte = (contexte or "").strip()
    ph = _phrases(contexte) or [contexte or "Votre message ici"]
    # titre : la première proposition de la première phrase (avant la virgule), courte ; le reste en sous-titre
    morceaux = re.split(r"[,;:]\s+", ph[0], maxsplit=1)
    tete = morceaux[0].strip().rstrip(".!") if len(morceaux[0].split()) >= 3 else ph[0].rstrip(".")
    suite = (morceaux[1] if len(morceaux) > 1 and tete != ph[0].rstrip(".") else "")
    sous = " ".join(x for x in [suite[:1].upper() + suite[1:] if suite else "", *ph[1:]] if x)
    regles = {"titre": _titre(tete), "sous_titre": _couper(sous, 22),
              "cta": (charte.get("cta") or ["En savoir plus"])[0], "requete_image": requete_image(contexte, charte),
              "accroche": "", "filigrane": (re.findall(r"\b\d{1,4}\b", contexte) or [""])[0], "par": "règles"}
    import ia
    conf = ia.config_ia(cfg)
    if not conf and demander is None:
        return regles
    try:
        d = (demander or ia.demander_json)(conf, CONSIGNE_TEXTES.format(
            format=NOMS_FORMATS.get(format, format), marque=cfg["identite"].get("nom") or "la marque",
            ton=charte.get("ton", ""), exemples="; ".join(charte.get("exemples_textes") or []) or "—", contexte=contexte))
        out = {k: str(d.get(k) or regles[k]).strip()[:160] for k in ("titre", "sous_titre", "cta", "requete_image")}
        for k in ("accroche", "filigrane"):
            out[k] = str(d.get(k) or "").strip()[:40]
        out["par"] = ia.nom_ia(conf) if conf else "IA"
        return out
    except Exception as e:
        print("Textes par IA impossibles :", e)
        return regles


def requete_image(contexte, charte):
    """Recherche d'image (en anglais) d'après les mots du contexte (dictionnaire des illustrations)."""
    mots = [I._singulier(I._norm(m)) for m in re.findall(r"[\wÀ-ÿ'-]+", contexte or "")]
    for m in mots:
        if m in I.MOTS_IMAGES:
            return I.MOTS_IMAGES[m]
    return (charte.get("mots_images") or ["african people smiling smartphone"])[0]


# ------------------------------------------------------------------ génération
def nouveau_visuel(gabarit, format, textes, image, charte, contexte=""):
    W, H = FORMATS[format]
    blocs = []
    for b in gabarit["blocs"]:
        nb = {k: v for k, v in b.items() if k != "story"}
        if format == "story" and isinstance(b.get("story"), dict):
            nb.update(b["story"])
        nb["id"] = uuid.uuid4().hex[:8]
        if nb["type"] == "texte":
            nb["texte"] = nb.get("texte") or textes.get(nb.get("role"), "") or ""
            if not nb["texte"]:
                continue
        if nb["type"] == "image":
            if not image:
                nb = {**nb, "type": "forme", "couleur": "accent", "opacite": 0.25}
            else:
                plein = nb.get("w", 0) >= 95 and nb.get("h", 0) >= 95
                if image.get("detoure") and not plein and not nb.get("rayon"):
                    nb["fichier"], nb["ajustement"] = image["fichier"], "contenir-bas"     # personne détourée
                else:
                    nb["fichier"] = image.get("original") or image.get("fichier")       # photo entière
                nb["credit"] = image.get("credit_licence", "")
        blocs.append(nb)
    return {"id": uuid.uuid4().hex[:10], "format": format, "taille": [W, H], "gabarit": gabarit["id"],
            "nom_gabarit": gabarit.get("nom", ""), "blocs": blocs, "contexte": contexte, "textes": textes,
            "cree": time.strftime("%Y-%m-%d %H:%M"), "charte": charte.get("nom", "")}


def generer(contexte, format="carre", n=6, cfg=None, charte=None, rechercher=None, telecharger=None,
            generer_image=None, demander=None, image_ia=False, rappel=None):
    """Variantes de visuels pour un contexte : [visuel, …] (JSON prêts pour l'éditeur)."""
    def etape(f, t):
        if rappel:
            rappel(f, t)
    cfg = cfg or C.charger_config()
    charte = charte or charger_charte()
    format = format if format in FORMATS else "carre"
    rechercher = rechercher or I.rechercher
    telecharger = telecharger or I.telecharger
    etape(0.05, "Écriture des textes…")
    textes = ecrire_textes(contexte, charte, cfg, format, demander=demander)
    etape(0.25, "Recherche d'images…")
    images = []
    if image_ia and I.fournisseur_images(cfg):
        try:
            consigne = I.prompt_illustration({"phrase": contexte, "requete": textes["requete_image"]},
                                             (cfg.get("illustrations") or {}).get("contexte", ""), I.fournisseur_images(cfg))
            # sujet sur un fond uni de la couleur de la charte : il se fond dans le visuel, comme détouré
            consigne += (f" Plain solid flat background color {charte['couleurs'].get('fond')}, no texture, "
                         "subject isolated in soft studio light, centered, upper body visible.")
            images.append({"fichier": (generer_image or I.generer)(consigne, cfg), "credit_licence": ""})
        except Exception as e:
            print("Image IA impossible :", e)
    try:
        res = [r for r in rechercher(textes["requete_image"], cfg["cles"]) if r.get("type") == "image"]
    except Exception as e:
        print("Recherche d'images impossible :", e)
        res = []
    for k, r in enumerate(res[: max(0, min(n, 6) - len(images))]):
        etape(0.3 + 0.5 * k / max(1, n), "Téléchargement des images…")
        try:
            images.append({"fichier": telecharger(r), "credit_licence": r.get("credit_licence", "")})
            if charte.get("detourer_photos"):            # comme les visuels de la marque : personnes détourées
                try:
                    images[-1]["original"] = images[-1]["fichier"]
                    images[-1]["fichier"] = detourer(images[-1]["fichier"])
                    images[-1]["detoure"] = True
                except Exception as e:
                    print("Détourage impossible :", e)
        except Exception as e:
            print("Image ignorée :", e)
    gabarits = [g for g in charte["gabarits"] if not g.get("formats") or format in g["formats"]] or GABARITS_DEFAUT
    etape(0.9, "Mise en page…")
    out = []
    for i in range(max(1, n)):
        g = gabarits[i % len(gabarits)]
        img = images[(i // len(gabarits) + i) % len(images)] if images else None
        out.append(nouveau_visuel(g, format, textes, img, charte, contexte))
    return out


# ------------------------------------------------------------------ stockage
def sauver_visuel(v):
    os.makedirs(DOSSIER, exist_ok=True)
    v["modifie"] = time.strftime("%Y-%m-%d %H:%M")
    C._ecrire(os.path.join(DOSSIER, f"{v['id']}.visuel.json"), v)
    return v


def lister_visuels(limite=60):
    if not os.path.isdir(DOSSIER):
        return []
    fichiers = sorted((os.path.join(DOSSIER, f) for f in os.listdir(DOSSIER) if f.endswith(".visuel.json")),
                      key=os.path.getmtime, reverse=True)[:limite]
    return [d for d in (C._lire(f, None) for f in fichiers) if d]


def exporter_png(v, donnees_png):
    """Enregistre le PNG rendu par le navigateur à côté des visuels ; renvoie son chemin."""
    os.makedirs(DOSSIER, exist_ok=True)
    titre = re.sub(r"[^\w\- ]", "", (v.get("textes") or {}).get("titre", "") or "visuel")[:40].strip() or "visuel"
    fmt = {"carre": "carré", "portrait": "portrait", "story": "story"}.get(v.get("format"), "visuel")
    chemin = os.path.join(DOSSIER, f"{titre} — {fmt} {time.strftime('%Y%m%d-%H%M%S')}.png")
    with open(chemin, "wb") as f:
        f.write(donnees_png)
    credits = [b.get("credit") for b in v.get("blocs", []) if b.get("credit")]
    if credits:
        with open(os.path.splitext(chemin)[0] + "_credits.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(dict.fromkeys(credits)) + "\n")
    return chemin


# ------------------------------------------------------------------ détourage (retirer le fond d'une photo)
def detourer(fichier):
    """PNG avec fond transparent. Mac (macOS 14+) : Apple Vision, sur l'appareil ; sinon rembg s'il est installé."""
    dossier = os.path.join(DOSSIER, ".detoures")
    os.makedirs(dossier, exist_ok=True)
    sortie = os.path.join(dossier, os.path.splitext(os.path.basename(fichier))[0] + "_detoure.png")
    if os.path.exists(sortie):
        return sortie
    erreurs = []
    try:
        import Quartz
        import Vision
        from Foundation import NSURL
        gestion = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(fichier), None)
        requete = Vision.VNGenerateForegroundInstanceMaskRequest.alloc().init()
        ok, err = gestion.performRequests_error_([requete], None)
        resultats = requete.results() if ok else None
        if not resultats:
            raise RuntimeError("aucun sujet trouvé sur la photo")
        obs = resultats[0]
        masque, err = obs.generateMaskedImageOfInstances_fromRequestHandler_croppedToInstancesExtent_error_(
            obs.allInstances(), gestion, True, None)
        if masque is None:
            raise RuntimeError(str(err))
        image = Quartz.CIImage.imageWithCVPixelBuffer_(masque)
        contexte = Quartz.CIContext.contextWithOptions_(None)
        ok = contexte.writePNGRepresentationOfImage_toURL_format_colorSpace_options_error_(
            image, NSURL.fileURLWithPath_(sortie), Quartz.kCIFormatRGBA8, Quartz.CGColorSpaceCreateDeviceRGB(), None, None)
        if os.path.exists(sortie):
            return sortie
        raise RuntimeError("écriture du PNG impossible")
    except Exception as e:
        erreurs.append(f"Vision : {e}")
    try:
        from rembg import remove
        with open(fichier, "rb") as f:
            png = remove(f.read())
        with open(sortie, "wb") as f:
            f.write(png)
        return sortie
    except Exception as e:
        erreurs.append(f"rembg : {e}")
    raise RuntimeError("Détourage indisponible sur cet ordinateur (il demande macOS 14 Sonoma ou plus). "
                       + " ; ".join(erreurs)[:300])
