"""Analyse d'une vidéo de référence → profil de style (ProfilStyle).

Mesures locales (gratuites) : rythme des coupes, écrans de couleur, écran de fin, étalonnage,
sous-titres par OCR (Apple Vision via « ocrmac » sur Mac, sinon Tesseract s'il est installé).
Avec une clé Claude : lecture visuelle d'images de la vidéo pour affiner (sous-titres, animation,
illustrations, mot clé), en plus des mesures.
"""
import os
import re
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image

import configuration as C
import ia


def _duree(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def images(video, fps, largeur=360):
    """Images de la vidéo (redressée) à `fps` images/s, largeur réduite."""
    dossier = tempfile.mkdtemp(prefix="ref_")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", video, "-vf", f"fps={fps},scale={largeur}:-2",
                    os.path.join(dossier, "%05d.jpg")], check=True)
    fichiers = sorted(os.listdir(dossier))
    ims = [(i / fps, Image.open(os.path.join(dossier, f)).convert("RGB")) for i, f in enumerate(fichiers)]
    for _, im in ims:
        im.load()
    shutil.rmtree(dossier, ignore_errors=True)
    return ims


def coupes(video, seuil=0.3):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", video, "-vf", f"select='gt(scene,{seuil})',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True)
    return [float(t) for t in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def est_ecran_uni(im):
    """Vrai si l'image est un aplat de couleur (éventuellement avec un peu de texte)."""
    a = np.asarray(im.resize((64, 112))).reshape(-1, 3).astype(int)
    med = np.median(a, axis=0)
    proche = (np.abs(a - med).max(axis=1) < 18).mean()
    return proche > 0.80, tuple(int(x) for x in med)


def mesures_image(ims):
    sat, con, chaud = [], [], []
    for _, im in ims:
        hsv = np.asarray(im.convert("HSV")).astype(float) / 255
        rgb = np.asarray(im).astype(float)
        luma = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        sat.append(hsv[..., 1].mean()); con.append(luma.std()); chaud.append((rgb[..., 0] - rgb[..., 2]).mean())
    return float(np.mean(sat)), float(np.mean(con)), float(np.mean(chaud))


def choisir_etalonnage(sat, con, chaud):
    if sat < 0.20:
        return "désaturé"
    if chaud > 14:
        return "chaud"
    if chaud < -6:
        return "froid"
    if con > 62:
        return "contrasté"
    return "naturel"


# ------------------------------------------------------------------ transitions entre plans
def _niveaux_gris(video, fps=10, w=48, h=86):
    brut = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", video, "-vf", f"fps={fps},scale={w}:{h}",
                           "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    n = len(brut) // (w * h)
    return np.frombuffer(brut[: n * w * h], np.uint8).reshape(n, h, w).astype(np.float32)


def transitions_detectees(video, fps=10):
    """Compte les coupes franches, fondus enchaînés et flashs blancs ({"coupe": n, "fondu": n, "flash": n})."""
    f = _niveaux_gris(video, fps)
    res = {"coupe": 0, "fondu": 0, "flash": 0}
    if len(f) < 4:
        return res
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))           # changement d'une image à la suivante
    luma = f.mean(axis=(1, 2))
    i, n = 1, len(d)
    while i < n - 1:
        # flash : image très claire entre deux images normales
        if luma[i] > 215 and luma[max(0, i - 3)] < 185 and luma[min(len(luma) - 1, i + 3)] < 185:
            res["flash"] += 1; i += 4; continue
        # coupe franche : un seul grand saut
        if d[i] > 22 and d[i - 1] < 0.4 * d[i] and d[i + 1] < 0.4 * d[i]:
            res["coupe"] += 1; i += 2; continue
        # fondu : plusieurs changements moyens d'affilée, et l'image du milieu est le mélange des deux bouts
        j = i
        while j < n and 4 < d[j] < 22:
            j += 1
        if 3 <= j - i <= 9:
            a, b, m = f[i - 1], f[min(len(f) - 1, j + 1)], f[(i + j) // 2]
            ecart = np.abs(a - b).mean()
            if ecart > 18 and np.abs(m - (a + b) / 2).mean() < 0.45 * ecart:
                res["fondu"] += 1; i = j + 1; continue
        i += 1
    return res


def transition_dominante(t):
    total = sum(t.values())
    if total and t["fondu"] >= max(2, 0.35 * total):
        return "fondu"
    if total and t["flash"] >= max(2, 0.35 * total):
        return "flash"
    return "coupe"


# ------------------------------------------------------------------ couleurs de la vidéo modèle
def _hex(rgb):
    return "#%02X%02X%02X" % tuple(int(v) for v in rgb)


def couleurs_modele(unis, ims):
    """Couleurs de marque de la vidéo modèle : celles des écrans de couleur, puis la couleur vive dominante."""
    cartes = []
    for (_, (uni, rgb)) in unis:
        if not uni or max(rgb) - min(rgb) < 25 and max(rgb) > 225:        # on ignore le blanc
            continue
        for c in cartes:
            if sum(abs(a - b) for a, b in zip(c[0], rgb)) < 60:
                c[1] += 1; break
        else:
            cartes.append([rgb, 1])
    couleurs = [_hex(c) for c, _ in sorted(cartes, key=lambda c: -c[1])][:2]
    if len(couleurs) < 2:
        vifs = []
        for _, im in ims[:: max(1, len(ims) // 20)]:
            a = np.asarray(im.resize((90, 160)).convert("HSV")).reshape(-1, 3).astype(int)
            rgb = np.asarray(im.resize((90, 160))).reshape(-1, 3)
            masque = (a[:, 1] > 150) & (a[:, 2] > 110)
            if masque.mean() > 0.01:
                vifs.append(rgb[masque])
        if vifs:
            px = np.concatenate(vifs)
            teinte = np.asarray(Image.fromarray(px.reshape(1, -1, 3).astype(np.uint8)).convert("HSV"))[0, :, 0] // 16
            dominante = np.bincount(teinte, minlength=16).argmax()
            c = _hex(np.median(px[teinte == dominante], axis=0))
            if c not in couleurs:
                couleurs.append(c)
    return couleurs[:2]


# ------------------------------------------------------------------ OCR
def _ocr_mac(im):
    from ocrmac import ocrmac  # Apple Vision (macOS)
    res = ocrmac.OCR(im, language_preference=["fr-FR"]).recognize()
    out = []
    for texte, conf, (x, y, w, h) in res:   # boîte normalisée, origine en bas à gauche
        if conf > 0.4:
            out.append((texte, x, 1 - y - h, w, h))
    return out


def _ocr_tesseract(im):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        im.save(f.name)
        chemin = f.name
    r = subprocess.run(["tesseract", chemin, "-", "-l", "fra", "--psm", "11", "tsv"],
                       capture_output=True, text=True)
    os.remove(chemin)
    out = []
    for ligne in r.stdout.splitlines()[1:]:
        c = ligne.split("\t")
        if len(c) == 12 and float(c[10]) > 65 and re.fullmatch(r"[A-Za-zÀ-ÿ'’-]{2,}[,.!?…]?", c[11].strip()):
            x, y, w, h = (int(v) for v in c[6:10])
            out.append((c[11].strip(), x / im.width, y / im.height, w / im.width, h / im.height))
    return out


def moteur_ocr():
    try:
        import ocrmac  # noqa: F401
        return _ocr_mac
    except Exception:
        pass
    if shutil.which("tesseract"):
        return _ocr_tesseract
    return None


def mesures_sous_titres(ims, ocr):
    """Position, taille, casse et nombre de mots des textes incrustés."""
    ys, hs, nmots, maj, mixte = [], [], [], 0, 0
    total = 0
    for _, im in ims:
        try:
            brut = ocr(im)
        except Exception as e:      # OCR indisponible ou image illisible : on ignore cette image
            print("OCR :", e)
            continue
        mots = [m for m in brut if re.fullmatch(r"[A-Za-zÀ-ÿ'’-]{2,}[,.!?…]?", m[0].strip())]
        if not mots:
            continue
        total += 1
        ys.append(float(np.median([y + h / 2 for _, _, y, _, h in mots])))
        hs.append(float(np.median([h for *_, h in mots])))
        nmots.append(sum(len(t.split()) for t, *_ in mots))
        lettres = "".join(t for t, *_ in mots if t.isalpha() or True)
        hautes = sum(1 for ch in lettres if ch.isupper())
        basses = sum(1 for ch in lettres if ch.islower())
        if hautes > 2 * max(1, basses):
            maj += 1
        if any(t.isupper() and len(t) > 2 for t, *_ in mots) and any(t.islower() for t, *_ in mots):
            mixte += 1
    if total < 3:
        return {}
    hauteur_ref = 0.030   # hauteur relative d'un mot de nos sous-titres (taille 1.0)
    return {"position_sous_titres": round(min(0.88, max(0.12, float(np.median(ys)))), 2),
            "taille_texte": round(min(1.5, max(0.6, float(np.median(hs)) / hauteur_ref)), 2),
            "mots_par_groupe": int(min(6, max(1, round(float(np.percentile(nmots, 80)))))),
            "casse": "majuscules" if maj / total > 0.6 else "normale",
            "mot_cle": mixte / total > 0.15,
            "_frames_texte": total}


# ------------------------------------------------------------------ analyse complète
CONSIGNE_IA = """Tu analyses le style de montage d'une courte vidéo verticale (Reels/TikTok) à partir de {n} images
prises à intervalles réguliers (dans l'ordre). Des mesures automatiques ont déjà été faites : {mesures}.
Décris le style pour qu'un outil de montage automatique le reproduise avec une autre marque.
Réponds UNIQUEMENT avec un objet JSON contenant ces clés (garde la valeur mesurée si tu n'es pas sûr) :
- "description": 1 à 2 phrases en français décrivant le style
- "position_sous_titres": hauteur du centre des sous-titres, 0 = haut, 1 = bas
- "taille_texte": taille relative des sous-titres (1.0 = moyen, 0.7 = petit, 1.4 = très gros)
- "mots_par_groupe": nombre de mots affichés en même temps (1 à 6)
- "mot_cle": true si un mot est mis en valeur (gras, couleur, capitales) dans chaque sous-titre
- "casse": "normale", "majuscules" ou "minuscules"
- "animation": "pop" (les mots apparaissent avec un petit rebond), "fondu" ou "aucune"
- "style_etalonnage": "naturel", "chaud", "contrasté", "froid" ou "désaturé"
- "illustrations_par_minute": nombre d'images/vidéos d'illustration (B-roll) insérées par minute
- "ecran_fin": true si la vidéo finit sur un écran avec logo
- "doodles": "aucun", "souligne" (trait dessiné sous des mots), "cercle" (mots entourés) ou "melange"
- "transition": "coupe", "fondu", "zoom", "flash" ou "glissement" (passage d'un plan à l'autre le plus fréquent)
"""


def analyser(video, cle_api="", ocr=True, rappel=None, details=None):
    """Renvoie (ProfilStyle, rapport lisible). `details` (dict) reçoit en plus les couleurs de la vidéo modèle."""
    def etape(f, txt):
        if rappel:
            rappel(f, txt)

    duree = _duree(video)
    etape(0.05, "Rythme des coupes…")
    ts = coupes(video)
    nb_plans = len(ts) + 1
    plan_moyen = duree / nb_plans if nb_plans else duree

    etape(0.25, "Couleurs et écrans…")
    ims = images(video, fps=4 if duree < 90 else 2)
    unis = [(t, est_ecran_uni(im)) for t, im in ims]
    cartes, en_carte = 0, False
    for t, (uni, _) in unis:
        if uni and not en_carte:
            cartes += 1
        en_carte = uni
    fin = [u for t, (u, _) in unis if t >= duree - 1.2]
    ecran_fin = bool(fin) and sum(fin) / len(fin) > 0.6
    sat, con, chaud = mesures_image([(t, im) for (t, im), (_, (u, _)) in zip(ims, unis) if not u] or ims)

    p = C.ProfilStyle()
    p.duree_plan_max = round(min(5.0, max(0.8, plan_moyen * 1.1)), 1)
    p.zoom = 1.15 if plan_moyen < 3 else 1.06
    p.pause_max = 0.35 if plan_moyen < 1.8 else 0.45 if plan_moyen < 4 else 0.7
    p.nb_ecrans_couleur = int(min(4, max(0, cartes - (1 if ecran_fin else 0))))
    p.ecran_fin = bool(ecran_fin)
    p.style_etalonnage = choisir_etalonnage(sat, con, chaud)
    p.effets_sonores = "léger"

    etape(0.35, "Transitions et rythme…")
    try:
        tr = transitions_detectees(video)
        p.transition = transition_dominante(tr)
    except Exception as e:
        print("Transitions :", e); tr = None
    cale = None
    try:                                     # les coupes tombent-elles sur les temps de la musique ?
        import rythme
        _, temps = rythme.temps_forts(video)
        if len(ts) >= 4 and temps:
            cale = float(np.mean([min(abs(np.asarray(temps) - c)) < 0.09 for c in ts]))
            p.caler_sur_rythme = True if cale >= 0.6 else p.caler_sur_rythme
    except Exception as e:
        print("Rythme :", e)
    couleurs = couleurs_modele(unis, ims)
    if details is not None:
        details["couleurs"] = couleurs
        details["images"] = ims
        details["mesures"] = {"duree_s": round(duree, 1), "plans": nb_plans, "ecrans_couleur": cartes}

    rapport = [f"Durée : {duree:.1f} s — {nb_plans} plans (≈ {plan_moyen:.1f} s par plan)",
               f"Écrans de couleur détectés : {cartes}" + (" (dont l'écran de fin)" if ecran_fin else ""),
               f"Étalonnage : {p.style_etalonnage} (saturation {sat:.2f}, contraste {con:.0f}, chaleur {chaud:+.0f})"]
    if tr is not None:
        rapport.append(f"Transitions : {tr['coupe']} coupe(s) franche(s), {tr['fondu']} fondu(s), {tr['flash']} flash(s) "
                       f"→ {p.transition}")
    if cale is not None:
        rapport.append(f"Coupes sur le rythme de la musique : {round(100 * cale)} %"
                       + (" → montage calé sur le rythme" if cale >= 0.6 else ""))
    if couleurs:
        rapport.append("Couleurs de la vidéo modèle : " + ", ".join(couleurs))

    if ocr:
        moteur = moteur_ocr()
        if moteur:
            etape(0.5, "Lecture des sous-titres (OCR)…")
            grandes = images(video, fps=2 if duree < 60 else 1, largeur=720)[:60]
            st = mesures_sous_titres([x for x in grandes if not est_ecran_uni(x[1])[0]], moteur)
            for k, v in st.items():
                if not k.startswith("_"):
                    setattr(p, k, v)
            if st:
                rapport.append(f"Sous-titres : à {round(100 * st['position_sous_titres'])} % de la hauteur, "
                               f"taille ×{st['taille_texte']}, {st['mots_par_groupe']} mot(s) à la fois, "
                               f"casse {st['casse']}, mot clé mis en valeur : {'oui' if st['mot_cle'] else 'non'}")
            else:
                rapport.append("Sous-titres : peu ou pas de texte détecté")
        else:
            rapport.append("Sous-titres : OCR indisponible (réglages par défaut conservés)")

    if cle_api:
        etape(0.75, f"Lecture visuelle des images par l’IA — {ia.nom_ia(cle_api)}…")
        choix = [im for _, im in ims[:: max(1, len(ims) // 10)]][:10]
        mesures = {k: getattr(p, k) for k in ("position_sous_titres", "taille_texte", "mots_par_groupe",
                                                 "casse", "style_etalonnage", "ecran_fin", "transition")}
        mesures.update({"plans": nb_plans, "duree_s": round(duree, 1), "ecrans_couleur": cartes})
        try:
            d = ia.demander_json(cle_api, CONSIGNE_IA.format(n=len(choix), mesures=mesures), choix)
            for k in ("description", "position_sous_titres", "taille_texte", "mots_par_groupe", "mot_cle", "casse",
                      "animation", "style_etalonnage", "illustrations_par_minute", "ecran_fin", "doodles", "transition"):
                if k in d:
                    setattr(p, k, d[k])
            p = C.ProfilStyle.depuis(_bornes(p.__dict__))
            rapport.append("Analyse visuelle (IA) : " + (p.description or "ok"))
        except Exception as e:
            rapport.append(f"Analyse Claude impossible ({e}) — mesures locales utilisées")
    if not p.description:
        p.description = f"Style analysé : plans de ≈{plan_moyen:.1f} s, étalonnage {p.style_etalonnage}."
    etape(1.0, "Terminé")
    return p, "\n".join(rapport)


def _bornes(d):
    d = dict(d)
    def f(k, lo, hi, typ=float):
        try:
            d[k] = typ(min(hi, max(lo, float(d[k]))))
        except (KeyError, TypeError, ValueError):
            d.pop(k, None)
    f("position_sous_titres", 0.1, 0.9); f("taille_texte", 0.5, 2.0); f("mots_par_groupe", 1, 6, int)
    f("illustrations_par_minute", 0, 20); f("nb_ecrans_couleur", 0, 6, int)
    if d.get("casse") not in ("normale", "majuscules", "minuscules"):
        d["casse"] = "normale"
    if d.get("animation") not in ("pop", "fondu", "aucune"):
        d["animation"] = "pop"
    if d.get("style_etalonnage") not in ("naturel", "chaud", "contrasté", "froid", "désaturé"):
        d["style_etalonnage"] = "naturel"
    for k in ("mot_cle", "ecran_fin"):
        d[k] = bool(d.get(k, True))
    if d.get("doodles") not in ("aucun", "souligne", "cercle", "melange"):
        d["doodles"] = "aucun"
    if d.get("transition") not in ("coupe", "fondu", "zoom", "flash", "glissement"):
        d["transition"] = "coupe"
    return d


# ------------------------------------------------------------------ analyse par Claude, dans la conversation (sans clé API)
FORMAT_STYLE = "raccord-style"

LISEZMOI_CLAUDE = """Paquet d'analyse de style — Raccord (outil de montage face caméra)

Pour Claude : ce paquet contient « planche.jpg » ({n} images de la vidéo modèle, dans l'ordre, de gauche à droite
puis de haut en bas) et « mesures.json » (mesures automatiques faites sur le Mac : rythme, écrans de couleur,
étalonnage, transitions, couleurs, sous-titres si l'OCR a fonctionné, et le style proposé).

Regarde les images, corrige le style proposé là où les mesures se trompent (surtout : place, taille, casse et
animation des sous-titres, mot mis en valeur, doodles, densité d'illustrations), puis renvoie UN fichier
« <nom>.raccord-style.json » à télécharger, de la forme :

{{"format": "raccord-style", "version": 1, "nom": "<nom court du style>",
  "profil": {{ ...toutes les clés de « style_propose » de mesures.json, corrigées... }},
  "couleurs": ["#RRGGBB", "#RRGGBB"],      (facultatif : couleurs principale et secondaire de la vidéo modèle)
  "notes": "2-3 phrases sur ce qui fait ce style"}}

Valeurs permises : position_sous_titres 0.1–0.9 (0 = haut) ; taille_texte 0.5–2.0 ; mots_par_groupe 1–6 ;
casse normale|majuscules|minuscules ; animation pop|fondu|aucune ; style_etalonnage naturel|chaud|contrasté|froid|
désaturé ; doodles aucun|souligne|cercle|melange ; transition coupe|fondu|zoom|flash|glissement ;
illustrations_par_minute 0–20 ; nb_ecrans_couleur 0–6 ; duree_plan_max (secondes par plan) ; zoom (1.0–1.4).

Pour l'utilisateur : glissez ce fichier .zip dans la conversation avec Claude, puis, dans Raccord,
« Copier un style › Importer la réponse de Claude » avec le fichier .json qu'il vous rend.
"""


def planche(ims, n=12, largeur=270):
    """Planche contact : n images régulièrement espacées, 4 par ligne."""
    choix = [im for _, im in ims[:: max(1, len(ims) // n)]][:n] if ims else []
    if not choix:
        return None
    h = int(largeur * 16 / 9)
    cols = 4
    lignes = (len(choix) + cols - 1) // cols
    out = Image.new("RGB", (cols * largeur + (cols - 1) * 6, lignes * h + (lignes - 1) * 6), (20, 20, 20))
    for i, im in enumerate(choix):
        im = im.copy()
        s = max(largeur / im.width, h / im.height)
        im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1))
        x0, y0 = (im.width - largeur) // 2, (im.height - h) // 2
        out.paste(im.crop((x0, y0, x0 + largeur, y0 + h)), ((i % cols) * (largeur + 6), (i // cols) * (h + 6)))
    return out, len(choix)


def preparer_pour_claude(video, dossier, nom=None, rappel=None):
    """Analyse locale + planche d'images → paquet .zip à déposer dans une conversation avec Claude."""
    import json
    import zipfile
    from dataclasses import asdict
    details = {}
    p, rapport = analyser(video, cle_api=None, rappel=rappel, details=details)
    nom = (nom or os.path.splitext(os.path.basename(video))[0])[:40]
    pl = planche(details.get("images") or [], n=12, largeur=270)
    if pl is None:
        raise RuntimeError("Impossible de lire des images dans cette vidéo.")
    image, n = pl
    os.makedirs(dossier, exist_ok=True)
    propre = re.sub(r"[^\w\- ]", "_", nom)
    chemin = os.path.join(dossier, f"Raccord — style {propre}.zip")
    mesures = {"format": "raccord-paquet-style", "version": 1, "nom": nom, **details.get("mesures", {}),
               "couleurs_detectees": details.get("couleurs", []), "rapport": rapport, "style_propose": asdict(p)}
    tmp = tempfile.mkdtemp()
    try:
        image.save(os.path.join(tmp, "planche.jpg"), quality=85)
        with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(os.path.join(tmp, "planche.jpg"), "planche.jpg")
            z.writestr("mesures.json", json.dumps(mesures, ensure_ascii=False, indent=1))
            z.writestr("LISEZMOI.txt", LISEZMOI_CLAUDE.format(n=n))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return chemin


def lire_style_claude(donnees):
    """Fichier rendu par Claude (dict) → {profil, couleurs, nom, rapport}, valeurs vérifiées et bornées."""
    from dataclasses import asdict
    if not isinstance(donnees, dict):
        raise ValueError("Ce fichier n'est pas un style Raccord.")
    profil = donnees.get("profil") if isinstance(donnees.get("profil"), dict) else donnees
    connus = {f for f in C.ProfilStyle.__dataclass_fields__}
    if not (set(profil) & connus):
        raise ValueError("Ce fichier ne contient aucun réglage de style reconnu.")
    p = C.ProfilStyle.depuis(_bornes({**asdict(C.ProfilStyle()), **profil}))
    couleurs = [c for c in (donnees.get("couleurs") or []) if isinstance(c, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", c)]
    nom = str(donnees.get("nom") or "Style de Claude")[:40]
    notes = str(donnees.get("notes") or p.description or "")
    return {"profil": asdict(p), "couleurs": couleurs[:2], "nom": nom, "rapport": "Analyse faite par Claude : " + notes,
            "ia": "Claude (conversation)"}
