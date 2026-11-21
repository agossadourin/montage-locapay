"""
Montage automatique « style Locapay »
-------------------------------------
Vidéo brute face caméra  ->  transcription (Whisper)  ->  découpe des blancs
->  sous-titres animés mot par mot (italique fin + mot clé en gras capitales)
->  recadrages alternés + léger zoom continu  ->  écrans de couleur de marque
->  logo  ->  effets sonores légers  ->  musique de fond (optionnelle, ducking)
->  MP4 vertical 1080x1920 prêt à publier (+ transcription .txt et .srt).
"""
import json, math, os, re, shutil, subprocess, wave
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
SR = 48000


# ============================================================ réglages
@dataclass
class Reglages:
    couleur_1: str = "#2E2C51"            # bleu nuit Locapay (écrans + fin)
    couleur_2: str = "#0AC2A4"            # vert Locapay
    position_sous_titres: float = 0.66    # 0 = haut, 1 = bas
    nb_ecrans_couleur: int = 2
    effets_sonores: str = "léger"         # "léger" ou "aucun"
    volume_musique: float = 0.18
    supprimer_hesitations: bool = True    # euh, hum, bah...
    pause_max: float = 0.45               # au-delà, le blanc est coupé (s)
    marge_avant: float = 0.10
    marge_apres: float = 0.15
    duree_plan_max: float = 2.4           # au-delà, un recadrage est inséré
    zoom: float = 1.15
    etalonnage: bool = True
    logo_en_coin: bool = True
    duree_fin: float = 1.8
    fichier_logo: str = ""
    police_serif: str = ""
    police_grasse: str = ""
    # --- profil de style
    taille_texte: float = 1.0             # multiplicateur de la taille des sous-titres
    mots_par_groupe: int = 4              # nombre max de mots affichés ensemble
    mot_cle: bool = True                  # un mot clé en GRAS CAPITALES par groupe
    casse: str = "normale"                # casse des autres mots : normale / majuscules / minuscules
    animation: str = "pop"                # apparition des mots : pop / fondu / aucune
    style_etalonnage: str = "chaud"       # naturel / chaud / contrasté / froid / désaturé
    ecran_fin: bool = True
    # --- illustrations (B-roll) : [{"deb", "fin" (temps source), "fichier", "type": image|video}]
    illustrations: list = field(default_factory=list)
    decalage_musique: float = 0.0         # la musique démarre à cette seconde du morceau


ETALONNAGES = {
    "naturel": "eq=contrast=1.03:saturation=1.03",
    "chaud": "eq=contrast=1.06:saturation=1.08:gamma=0.98,colorbalance=rs=0.03:bs=-0.03:rm=0.02:bm=-0.02",
    "contrasté": "eq=contrast=1.15:saturation=1.12:gamma=0.96",
    "froid": "eq=contrast=1.05:saturation=1.0,colorbalance=rs=-0.03:bs=0.04:bm=0.02",
    "désaturé": "eq=contrast=1.08:saturation=0.72",
}


def hex2rgb(h):
    h = h.strip().lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ============================================================ transcription
def _mots_depuis_segments(segments):
    mots = []
    for seg in segments:
        for w in seg.get("words", []) or []:
            t = str(w["word"]).strip()
            if t:
                m = {"w": t, "s": float(w["start"]), "e": float(w["end"])}
                if w.get("probability") is not None:
                    m["p"] = round(float(w["probability"]), 3)
                mots.append(m)
    return mots


def moteur_transcription():
    """mlx (Mac Apple Silicon), faster-whisper (Mac Intel / PC), openai-whisper (Colab)."""
    import importlib.util, platform
    if platform.system() == "Darwin" and platform.machine() == "arm64" and importlib.util.find_spec("mlx_whisper"):
        return "mlx"
    if importlib.util.find_spec("faster_whisper"):
        return "faster"
    if importlib.util.find_spec("whisper"):
        return "openai"
    raise RuntimeError("Aucun moteur de transcription installé (mlx-whisper, faster-whisper ou openai-whisper).")


MODELES_MLX = {"turbo": "mlx-community/whisper-large-v3-turbo", "small": "mlx-community/whisper-small-mlx",
               "medium": "mlx-community/whisper-medium-mlx", "large-v3": "mlx-community/whisper-large-v3-mlx"}
MODELES_FASTER = {"turbo": "large-v3-turbo", "small": "small", "medium": "medium", "large-v3": "large-v3"}


def transcrire(video, modele="turbo", langue="fr", vocabulaire=""):
    """Transcription Whisper avec horodatage mot par mot (moteur choisi selon la machine)."""
    moteur = moteur_transcription()
    if moteur == "mlx":
        import mlx_whisper
        print(f"Transcription (mlx, {modele})…", flush=True)
        r = mlx_whisper.transcribe(video, path_or_hf_repo=MODELES_MLX.get(modele, modele), language=langue,
                                   word_timestamps=True, initial_prompt=vocabulaire or None,
                                   condition_on_previous_text=False)
        return _mots_depuis_segments(r["segments"])
    if moteur == "faster":
        from faster_whisper import WhisperModel
        print(f"Transcription (faster-whisper, {modele})…", flush=True)
        m = WhisperModel(MODELES_FASTER.get(modele, modele), device="auto", compute_type="int8")
        segs, _ = m.transcribe(video, language=langue, word_timestamps=True, initial_prompt=vocabulaire or None,
                               condition_on_previous_text=False)
        return _mots_depuis_segments(
            [{"words": [{"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                        for w in (s.words or [])]} for s in segs])
    import torch
    import whisper
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    if dev == "cpu" and modele in ("turbo", "large", "large-v3", "medium"):
        print("⚠️  Pas de GPU : modèle 'small' utilisé (plus lent et moins précis). "
              "Activez un GPU : Exécution > Modifier le type d'exécution > T4 GPU.")
        modele = "small"
    print(f"Chargement du modèle Whisper « {modele} » sur {dev}…")
    m = whisper.load_model(modele, device=dev)
    r = m.transcribe(video, language=langue, word_timestamps=True,
                     initial_prompt=vocabulaire or None, fp16=(dev == "cuda"),
                     condition_on_previous_text=False, verbose=False)
    return _mots_depuis_segments(r["segments"])


HESITATIONS = {"euh", "heu", "euhh", "hum", "hmm", "mmh", "mh", "bah", "beuh", "eh"}
STOP = set("""le la les l un une des de du d et ou mais donc or ni car je tu il elle on nous vous ils elles
me te se moi toi lui leur leurs y en ce cet cette ces ça ca c qui que qu quoi dont où ou a à au aux
est sont suis es sommes êtes ai as avons avez ont ne pas plus très tres trop pour par avec sans sur sous
dans chez vers mon ton son ma ta sa mes tes ses notre votre nos vos si comme alors aussi bien tout
tous toute toutes hein oui non voilà voila là la ici être avoir fait faire c'est s'il qu'il qu'elle
j'ai n'est d'un d'une l'on parmi entre avant après apres depuis pendant encore déjà deja vraiment
juste même meme quand comment pourquoi peut peux veux veut dit dire""".split())
FAIBLES = set("""le la les l un une des de du d et ou mais à a au aux en dans sur pour par avec sans qui que qu
ne n je j tu il elle on nous vous ils elles ce cet cette ces c mon ton son ma ta sa mes tes ses notre votre
nos vos y se s me m te t très tres plus si comme parmi entre chez vers""".split())


def norm(t):
    return re.sub(r"[^\wàâäéèêëîïôöùûüç'’-]", "", t.lower()).replace("’", "'")


def appliquer_corrections(mots, corrections):
    """corrections : 'locapé=Locapay; démarcheur=démarcheurs'"""
    table = {}
    for paire in re.split(r"[;\n]", corrections or ""):
        if "=" in paire:
            a, b = paire.split("=", 1)
            if a.strip():
                table[norm(a.strip())] = b.strip()
    if not table:
        return mots
    out = []
    for m in mots:
        k = norm(m["w"])
        if k in table:
            ponct = re.findall(r"[,.!?;:…]+$", m["w"])
            m = dict(m, w=table[k] + (ponct[0] if ponct else ""))
        out.append(m)
    return out


def _repartir(texte, deb, fin, ponct_finale=""):
    """Transforme un texte en mots horodatés répartis sur [deb, fin] (selon leur longueur)."""
    nouveaux = texte.split()
    if not nouveaux:
        return []
    if ponct_finale and not re.search(r"[,.!?;:…]$", nouveaux[-1]):
        nouveaux[-1] += ponct_finale
    poids = [len(w) + 2 for w in nouveaux]
    total, t, out = sum(poids), deb, []
    for w, pw in zip(nouveaux, poids):
        d = (fin - deb) * pw / total
        out.append({"w": w, "s": round(t, 3), "e": round(t + max(0.05, d * 0.92), 3), "p": 1.0})
        t += d
    return out


def _ponct(w):
    p = re.findall(r"[,.!?;:…]+$", w)
    return p[0] if p else ""


def corriger(mots, corrections):
    """Applique une liste de corrections :
    - portée « moment » : remplace les mots n° i à j (une occurrence précise, choisie dans une phrase) ;
    - portée « video » ou « toujours » : remplace l'expression `avant` (un ou plusieurs mots) partout.
    Un remplacement vide supprime les mots (ils seront coupés au montage)."""
    mots = [dict(m) for m in mots]
    ciblees = [c for c in corrections or [] if c.get("portee") == "moment"]
    for c in sorted(ciblees, key=lambda c: -int(c["i"])):
        i, j = int(c["i"]), int(c["j"])
        if not (0 <= i <= j < len(mots)):
            continue
        span = mots[i:j + 1]
        mots[i:j + 1] = _repartir(c.get("apres", ""), span[0]["s"], span[-1]["e"], _ponct(span[-1]["w"]))
    for c in corrections or []:
        if c.get("portee") == "moment":
            continue
        cible = [t for t in (norm(x) for x in str(c.get("avant", "")).split()) if t]
        n = len(cible)
        if not n:
            continue
        out, k = [], 0
        while k < len(mots):
            if k + n <= len(mots) and [norm(mots[k + x]["w"]) for x in range(n)] == cible:
                span = mots[k:k + n]
                out += _repartir(c.get("apres", ""), span[0]["s"], span[-1]["e"], _ponct(span[-1]["w"]))
                k += n
            else:
                out.append(mots[k]); k += 1
        mots = out
    return mots


def texte_transcription(mots):
    return " ".join(m["w"] if m.get("st", True) else "[…]" for m in mots)


# ============================================================ validation des passages
SEUIL_CONFIANCE = 0.6


def _jetons(texte):
    return [t for t in (norm(x) for x in texte.split()) if t and t not in HESITATIONS]


def analyser(mots, seuil=SEUIL_CONFIANCE):
    """Découpe la transcription en phrases et signale celles à vérifier :
    - passage incompris (confiance Whisper faible : bruit, autre langue comme le fon…) ;
    - prise répétée (la même phrase est redite juste après : on propose de garder la dernière) ;
    - faux départ (début de phrase abandonné puis repris)."""
    phrases, cur = [], []
    for i, m in enumerate(mots):
        if cur:
            prev = mots[cur[-1]]
            if (m["s"] - prev["e"] > 0.6 or re.search(r"[.!?…]$", prev["w"])
                    or m["e"] - mots[cur[0]]["s"] > 12):
                phrases.append(cur); cur = []
        cur.append(i)
    if cur:
        phrases.append(cur)

    out = []
    for k, idx in enumerate(phrases):
        ws = [mots[i] for i in idx]
        probs = [w["p"] for w in ws if w.get("p") is not None]
        conf = sum(probs) / len(probs) if probs else None
        faibles = sum(1 for p in probs if p < 0.35) / len(probs) if probs else 0
        alertes = []
        if conf is not None and (conf < seuil or faibles >= 0.35):
            alertes.append("incompris (bruit ou autre langue ?)")
        out.append({"n": k + 1, "deb": ws[0]["s"], "fin": ws[-1]["e"], "idx": idx,
                    "texte": " ".join(w["w"] for w in ws), "conf": conf, "alertes": alertes,
                    "garder": not alertes, "st": not alertes})

    # prises répétées / faux départs : comparaison avec les 3 phrases suivantes
    from difflib import SequenceMatcher
    for k, a in enumerate(out):
        ja = _jetons(a["texte"])
        if len(ja) < 2:
            continue
        for b in out[k + 1:k + 4]:
            if b["deb"] - a["fin"] > 25:
                break
            jb = _jetons(b["texte"])
            sim = SequenceMatcher(None, ja, jb).ratio()
            debut_repris = len(ja) <= len(jb) and jb[:len(ja)] == ja
            if (sim >= 0.6 and len(ja) >= 3) or debut_repris:
                a["alertes"].append(f"reprise : redit en phrase {b['n']}" if not debut_repris
                                    else f"faux départ : repris en phrase {b['n']}")
                a["garder"] = False
                break
    return out


COLONNES_VALIDATION = ["N°", "Début", "Fin", "Texte (modifiable)", "Confiance", "À vérifier", "Garder", "Sous-titres"]


def lignes_validation(phrases):
    return [[p["n"], round(p["deb"], 1), round(p["fin"], 1), p["texte"],
             "" if p["conf"] is None else f"{round(100 * p['conf'])} %",
             ("⚠️ " + " · ".join(p["alertes"])) if p["alertes"] else "", p["garder"], p["st"]] for p in phrases]


def _vrai(x):
    return str(x).strip().lower() not in ("false", "0", "non", "no", "", "none")


def appliquer_validation(mots, phrases, lignes):
    """Applique les choix de l'utilisateur : supprimer, garder sans sous-titres, ou texte corrigé
    (ex. traduction française tapée pour un passage en fon, répartie sur la durée du passage)."""
    out = []
    for ph, ligne in zip(phrases, lignes or []):
        ligne = (list(ligne) + [None] * 8)[:8]
        texte, garder, st = str(ligne[3] or ""), _vrai(ligne[6]), _vrai(ligne[7])
        if not garder:
            continue
        if not st:
            out.append({"w": "", "s": ph["deb"], "e": ph["fin"], "st": False})
            continue
        if _jetons(texte) == _jetons(ph["texte"]):
            out.extend(dict(mots[i]) for i in ph["idx"])
            continue
        nouveaux = texte.split()
        if not nouveaux:
            out.append({"w": "", "s": ph["deb"], "e": ph["fin"], "st": False})
            continue
        poids = [len(w) + 2 for w in nouveaux]
        total, t = sum(poids), ph["deb"]
        for w, pw in zip(nouveaux, poids):
            d = (ph["fin"] - ph["deb"]) * pw / total
            out.append({"w": w, "s": round(t, 3), "e": round(t + d * 0.92, 3)})
            t += d
    # phrases au-delà du tableau (sécurité) : gardées telles quelles
    for ph in phrases[len(lignes or []):]:
        out.extend(dict(mots[i]) for i in ph["idx"])
    return out


# ============================================================ plan de montage
def construire_plan(mots, duree, R: Reglages):
    mots = [dict(m) for m in mots if m["e"] > m["s"] - 1e-3]
    if R.supprimer_hesitations:
        mots = [m for m in mots if not (m.get("st", True) and norm(m["w"]).strip("-") in HESITATIONS)]
    if not mots:
        raise ValueError("Aucune parole détectée dans la vidéo.")
    for m in mots:
        m["e"] = max(m["e"], m["s"] + 0.08)

    # --- zones de parole (on coupe les blancs > pause_max)
    zones = []
    for i, m in enumerate(mots):
        if zones and m["s"] - zones[-1]["fin_mot"] <= R.pause_max:
            zones[-1]["fin_mot"] = m["e"]; zones[-1]["mots"].append(i)
        else:
            zones.append({"deb_mot": m["s"], "fin_mot": m["e"], "mots": [i]})
    for z in zones:
        z["a"] = max(0.0, z["deb_mot"] - R.marge_avant)
        z["b"] = min(duree, z["fin_mot"] + R.marge_apres)
    fus = []
    for z in zones:
        if fus and z["a"] <= fus[-1]["b"] + 0.02:
            fus[-1]["b"] = max(fus[-1]["b"], z["b"]); fus[-1]["mots"] += z["mots"]
        else:
            fus.append(z)
    zones = fus
    for zi, z in enumerate(zones):
        for i in z["mots"]:
            mots[i]["zone"] = zi

    # --- plans (recadrages alternés, coupe supplémentaire si plan trop long)
    cycle = [1.0, R.zoom, 1.04, R.zoom + 0.03]
    plans = []
    for z in zones:
        a = z["a"]; idx = z["mots"]
        for k in range(1, len(idx)):
            m_prev, m = mots[idx[k - 1]], mots[idx[k]]
            if m["s"] - a > R.duree_plan_max * 0.75 and z["b"] - m["s"] > 0.7:
                cut = (m_prev["e"] + m["s"]) / 2
                plans.append([a, cut]); a = cut
        plans.append([a, z["b"]])
    plans = [{"a": a, "b": b, "zoom": cycle[i % len(cycle)]} for i, (a, b) in enumerate(plans)]
    t = 0.0
    for p in plans:
        p["o"] = t; t += p["b"] - p["a"]
    corps = t

    # --- groupes de sous-titres
    groupes, cur = [], []
    for i, m in enumerate(mots):
        if not m.get("st", True):      # passage gardé sans sous-titres
            if cur:
                groupes.append(cur); cur = []
            continue
        if cur:
            prev = mots[cur[-1]]
            nchar = sum(len(mots[j]["w"]) for j in cur) + len(m["w"])
            if (m["s"] - prev["e"] > 0.30 or re.search(r"[,.!?;:…]$", prev["w"])
                    or len(cur) >= max(1, R.mots_par_groupe) or nchar > 6 * max(1, R.mots_par_groupe)
                    or m["zone"] != prev["zone"]
                    or m["e"] - mots[cur[0]]["s"] > 1.8):
                groupes.append(cur); cur = []
        cur.append(i)
    if cur:
        groupes.append(cur)
    # ne pas finir un groupe sur un petit mot (« les », « et », « ne »…) : il passe au groupe suivant
    for gi in range(len(groupes) - 1):
        g, nx = groupes[gi], groupes[gi + 1]
        while (len(g) > 1 and len(nx) < R.mots_par_groupe + (1 if R.mots_par_groupe >= 3 else 0)
               and norm(mots[g[-1]]["w"]) in FAIBLES
               and not re.search(r"[,.!?;:…]$", mots[g[-1]]["w"])
               and mots[g[-1]]["zone"] == mots[nx[0]]["zone"]
               and mots[nx[0]]["s"] - mots[g[-1]]["e"] < 0.30):
            nx.insert(0, g.pop())

    G = []
    for gi, idx in enumerate(groupes):
        ws = [mots[i] for i in idx]
        z = zones[ws[0]["zone"]]
        deb = ws[0]["s"]
        nxt = mots[groupes[gi + 1][0]]["s"] if gi + 1 < len(groupes) else 1e9
        fin = min(nxt, ws[-1]["e"] + 0.6, z["b"])
        cands = [(len(norm(w["w"])), k) for k, w in enumerate(ws)
                 if norm(w["w"]) not in STOP and len(norm(w["w"])) >= 4]
        cle = max(cands)[1] if (cands and R.mot_cle) else None
        G.append({"mots": ws, "deb": deb, "fin": fin, "cle": cle, "ecran": None})

    # --- écrans de couleur (milieu de la vidéo, groupes courts)
    n = max(0, int(R.nb_ecrans_couleur))
    if n and len(G) >= 6:
        t0, t1 = G[0]["deb"], G[-1]["fin"]
        cand = [i for i in range(2, len(G) - 2) if 0.45 <= G[i]["fin"] - G[i]["deb"] <= 2.0]
        cibles = np.linspace(0.30, 0.62, n) if n > 1 else [0.45]
        pris = []
        for c in cibles:
            tc = t0 + c * (t1 - t0)
            libres = [i for i in cand if all(abs(i - p) > 1 for p in pris)]
            if not libres:
                break
            best = min(libres, key=lambda i: abs((G[i]["deb"] + G[i]["fin"]) / 2 - tc))
            pris.append(best)
        couleurs = [hex2rgb(R.couleur_1), hex2rgb(R.couleur_2)]
        for k, i in enumerate(sorted(pris)):
            G[i]["ecran"] = couleurs[k % 2]

    return {"mots": mots, "zones": zones, "plans": plans, "groupes": G, "corps": corps,
            "total": corps + (R.duree_fin if R.ecran_fin else 0.0)}


def src2out(plan, t):
    for p in plan["plans"]:
        if p["a"] - 1e-6 <= t < p["b"]:
            return p["o"] + t - p["a"]
    return None


# ============================================================ texte
def _police(chemin, taille, variation, repli):
    try:
        f = ImageFont.truetype(chemin, taille)
        try:
            f.set_variation_by_name(variation)
        except Exception:
            pass
        return f
    except Exception:
        return ImageFont.truetype(repli, taille)


def image_mot(texte, f):
    l, t, r, b = f.getbbox(texte)
    pad = 30
    w, h = r - l + 2 * pad, b - t + 2 * pad
    ombre = Image.new("L", (w, h), 0)
    ImageDraw.Draw(ombre).text((pad - l, pad - t + 4), texte, font=f, fill=150)
    ombre = ombre.filter(ImageFilter.GaussianBlur(9))
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); im.putalpha(ombre)
    txt = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(txt).text((pad - l, pad - t), texte, font=f, fill=(255, 255, 255, 255))
    im.alpha_composite(txt)
    return im, pad, r - l, b - t


class Polices:
    def __init__(self, R):
        def premier(*ch):
            return next((c for c in ch if os.path.exists(c)), ch[0])
        repli_s = premier("/System/Library/Fonts/Supplemental/Georgia Italic.ttf",
                          "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf")
        repli_b = premier("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        self.ps, self.pb, self.rs, self.rb = R.police_serif, R.police_grasse, repli_s, repli_b
        self.cache = {}

    def get(self, style, taille):
        k = (style, taille)
        if k not in self.cache:
            if style == "b":
                self.cache[k] = _police(self.pb, taille, "ExtraBold", self.rb)
            elif style == "c":
                self.cache[k] = _police(self.ps, taille, "Medium Italic", self.rs)
            else:
                self.cache[k] = _police(self.ps, taille, "Italic", self.rs)
        return self.cache[k]


def _casse(t, R):
    return t.upper() if R.casse == "majuscules" else t.lower() if R.casse == "minuscules" else t


def mise_en_page(G, R, polices):
    """Pré-calcule la position finale de chaque mot (aucun saut quand un mot apparaît)."""
    k_t = max(0.4, float(R.taille_texte or 1.0))
    for g in G:
        items = []
        if g["ecran"] is None:
            ws, k = g["mots"], g["cle"]
            if k is None:
                lignes = [[(_casse(w["w"], R), "s", w["s"]) for w in ws]]
            else:
                avant = [(_casse(w["w"], R), "s", w["s"]) for w in ws[:k]]
                cle = [(re.sub(r"[,.;:]+$", "", ws[k]["w"]).upper(), "b", ws[k]["s"])]
                apres = [(_casse(w["w"], R), "s", w["s"]) for w in ws[k + 1:]]
                lignes = [l for l in (avant, cle, apres) if l]
            rangs = []
            for ligne in lignes:
                for taille_s, taille_b in ((80, 84), (68, 72), (58, 62), (48, 52)):
                    taille_s, taille_b = int(taille_s * k_t), int(taille_b * k_t)
                    ims = [(image_mot(t, polices.get(st, taille_b if st == "b" else taille_s)), ts)
                           for t, st, ts in ligne]
                    esp = int(0.28 * taille_s)
                    lw = sum(i[0][2] for i in ims) + esp * (len(ims) - 1)
                    if lw <= W * 0.86:
                        break
                rangs.append((ims, lw, max(i[0][3] for i in ims), esp))
            ecart = 24
            th = sum(r[2] for r in rangs) + ecart * (len(rangs) - 1)
            y = int(H * R.position_sous_titres) - th // 2
            for ims, lw, lh, esp in rangs:
                x = (W - lw) // 2
                for (im, pad, ww, hh), ts in ims:
                    items.append((im, x - pad, y + (lh - hh) - pad, ts))
                    x += ww + esp
                y += lh + ecart
        else:
            ligne = [(w["w"], w["s"]) for w in g["mots"]]
            for taille in (96, 82, 70, 60):
                taille = int(taille * k_t)
                ims = [(image_mot(_casse(t, R), polices.get("c", taille)), ts) for t, ts in ligne]
                esp = int(0.26 * taille)
                lw = sum(i[0][2] for i in ims) + esp * (len(ims) - 1)
                if lw <= W * 0.86:
                    break
            lh = max(i[0][3] for i in ims)
            x, y = (W - lw) // 2, H // 2 - lh // 2
            for (im, pad, ww, hh), ts in ims:
                items.append((im, x - pad, y + (lh - hh) - pad, ts))
                x += ww + esp
        g["items"] = items


def _ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def coller_anime(canvas, im, x, y, p, animation="pop"):
    if p <= 0:
        return
    if animation == "aucune":
        canvas.alpha_composite(im, (int(x), int(y))); return
    e = _ease(p); sc = 0.82 + 0.18 * e if animation == "pop" else 1.0; a = min(1.0, p * 1.6)
    if sc < 0.999:
        nw, nh = max(1, int(im.width * sc)), max(1, int(im.height * sc))
        im2 = im.resize((nw, nh), Image.BILINEAR)
        x += (im.width - nw) // 2; y += (im.height - nh) // 2 + int(14 * (1 - e))
    else:
        im2 = im
    if a < 1:
        im2 = im2.copy(); im2.putalpha(im2.getchannel("A").point(lambda v: int(v * a)))
    canvas.alpha_composite(im2, (int(x), int(y)))


# ============================================================ effets sonores (synthétisés)
_rng = np.random.default_rng(7)


def _db(x):
    return 10 ** (x / 20)


def _passe_bande(bruit, f0, f1, q=1.2):
    n = len(bruit); fc = np.geomspace(f0, f1, n); out = np.zeros(n)
    low = band = 0.0; d = 1.0 / q
    for i in range(n):
        f = 2 * math.sin(math.pi * fc[i] / SR)
        high = bruit[i] - low - d * band
        band += f * high; low += f * band; out[i] = band
    return out


def sfx_whoosh(dur=0.5, pic=0.68, f0=250, f1=5000, niveau=-13):
    n = int(dur * SR); t = np.linspace(0, 1, n)
    env = np.where(t < pic, (t / pic) ** 2.2, ((1 - t) / (1 - pic)) ** 1.6)
    s = _passe_bande(_rng.standard_normal(n), f0, f1) * env
    return s / (np.abs(s).max() + 1e-9) * _db(niveau), pic * dur


def sfx_pop(niveau=-14):
    n = int(0.11 * SR); t = np.arange(n) / SR
    f = 260 + 900 * np.exp(-t / 0.018)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.035) * (1 - np.exp(-t / 0.0015))
    return s / np.abs(s).max() * _db(niveau), 0.0


def sfx_carillon():
    n = int(1.6 * SR); t = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * f * t) * np.exp(-t / (0.45 * (1 - 0.15 * k))) / (k + 1)
            for k, f in enumerate([1318.5, 1975.5, 2637, 3951]))
    s *= 1 - np.exp(-t / 0.003)
    return s / np.abs(s).max() * _db(-19), 0.0


def generer_sfx(evenements, total, chemin):
    n = int((total + 2) * SR); L = np.zeros(n); Rr = np.zeros(n)
    gens = {"whoosh": sfx_whoosh, "pop": sfx_pop, "carillon": sfx_carillon}
    for i, (nom, t) in enumerate(evenements):
        sig, off = gens[nom]()
        s = int((t - off) * SR)
        if s < 0:
            sig = sig[-s:]; s = 0
        e = min(n, s + len(sig))
        pan = (np.linspace(-0.5, 0.5, e - s) * (1 if i % 2 else -1)) if nom == "whoosh" else np.zeros(e - s)
        L[s:e] += sig[:e - s] * np.sqrt(0.5 * (1 - pan)); Rr[s:e] += sig[:e - s] * np.sqrt(0.5 * (1 + pan))
    st = np.clip(np.stack([L, Rr], 1)[:int(total * SR)], -1, 1)
    with wave.open(chemin, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())


# ============================================================ rendu
def _taille_affichee(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:stream_side_data=rotation:stream_tags=rotate",
                          "-of", "json", video], capture_output=True, text=True).stdout
    d = json.loads(out)["streams"][0]
    w, h = d["width"], d["height"]
    rot = 0
    for sd in d.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    rot = rot or int(d.get("tags", {}).get("rotate", 0) or 0)
    if abs(rot) % 180 == 90:
        w, h = h, w
    return w, h


def duree_video(video):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", video], capture_output=True, text=True).stdout.strip())


def a_du_son(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "csv=p=0", video], capture_output=True, text=True).stdout.strip()
    return bool(out)


# ============================================================ prémontage (plusieurs vidéos)
def premontage(morceaux, sortie, rappel=None):
    """Assemble plusieurs vidéos en une seule, prête pour le montage automatique.

    morceaux : liste de (chemin, debut_s, fin_s) dans l'ordre voulu ; fin_s=None = jusqu'à la fin.
    Chaque morceau est recadré en vertical 1080x1920, 30 i/s, son stéréo 48 kHz (silence ajouté
    s'il n'y a pas de son), puis les morceaux sont mis bout à bout.
    """
    if not morceaux:
        raise ValueError("Aucune vidéo à assembler.")
    dossier = sortie + ".morceaux"
    os.makedirs(dossier, exist_ok=True)
    parties = []
    for i, (chemin, deb, fin) in enumerate(morceaux):
        total = duree_video(chemin)
        deb = max(0.0, float(deb or 0))
        fin = total if fin in (None, "") else min(float(fin), total)
        if fin - deb < 0.2:
            raise ValueError(f"Morceau {i + 1} ({os.path.basename(chemin)}) : la fin doit être après le début.")
        part = os.path.join(dossier, f"{i:03d}.mp4")
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{deb:.3f}", "-t", f"{fin - deb:.3f}", "-i", chemin]
        son = a_du_son(chemin)
        if not son:
            cmd += ["-f", "lavfi", "-t", f"{fin - deb:.3f}", "-i", f"anullsrc=r={SR}:cl=stereo"]
        cmd += ["-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,format=yuv420p",
                "-af", f"aresample={SR},aformat=channel_layouts=stereo",
                "-map", "0:v:0", "-map", "0:a:0" if son else "1:a:0",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
                "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-shortest", part]
        subprocess.run(cmd, check=True)
        parties.append(part)
        if rappel:
            rappel((i + 1) / (len(morceaux) + 1))
    liste = os.path.join(dossier, "liste.txt")
    with open(liste, "w", encoding="utf-8") as f:
        for p in parties:
            f.write("file '" + p.replace("'", "'\\''") + "'\n")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", liste,
                    "-c", "copy", "-movflags", "+faststart", sortie], check=True)
    shutil.rmtree(dossier, ignore_errors=True)
    if rappel:
        rappel(1.0)
    return sortie


def _srt_temps(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ecrire_srt(plan, chemin):
    with open(chemin, "w", encoding="utf-8") as f:
        k = 1
        for g in plan["groupes"]:
            a, b = src2out(plan, g["deb"]), src2out(plan, g["fin"] - 1e-3)
            if a is None or b is None or b <= a:
                continue
            f.write(f"{k}\n{_srt_temps(a)} --> {_srt_temps(b)}\n{' '.join(w['w'] for w in g['mots'])}\n\n"); k += 1


EXT_VIDEO = (".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi")


class Illustration:
    """Image ou vidéo d'illustration (B-roll) affichée plein écran entre deb et fin (temps source)."""

    def __init__(self, item):
        self.deb, self.fin = float(item["deb"]), float(item["fin"])
        self.fichier = item["fichier"]
        self.type = item.get("type") or ("video" if self.fichier.lower().endswith(EXT_VIDEO) else "image")
        self.proc, self.img, self.idx, self.derniere = None, None, -1, None

    def image(self, st):
        frac = min(1.0, max(0.0, (st - self.deb) / max(1e-6, self.fin - self.deb)))
        if self.type == "image":
            if self.img is None:
                im = Image.open(self.fichier).convert("RGB")
                s = max(W / im.width, H / im.height) * 1.10
                self.img = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
            z = 1.0 + 0.08 * frac                      # effet Ken Burns : léger zoom avant
            cw, ch = W * 1.10 / z, H * 1.10 / z
            x0, y0 = (self.img.width - cw) / 2, (self.img.height - ch) / 2
            return self.img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch)).convert("RGBA")
        if self.proc is None:
            self.proc = subprocess.Popen(
                ["ffmpeg", "-loglevel", "error", "-i", self.fichier, "-an", "-vf",
                 f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        k = int((st - self.deb) * FPS)
        while self.idx < k:
            buf = self.proc.stdout.read(W * H * 3)
            if len(buf) < W * H * 3:
                break
            self.idx += 1
            self.derniere = buf
        if self.derniere is None:
            return Image.new("RGBA", (W, H), (0, 0, 0, 255))
        return Image.frombuffer("RGB", (W, H), self.derniere, "raw", "RGB", 0, 1).convert("RGBA")

    def fermer(self):
        if self.proc is not None:
            self.proc.kill(); self.proc = None
        self.img = None


def monter(video, plan, R: Reglages, sortie, musique=None, progression=True, rappel=None):
    polices = Polices(R)
    mise_en_page(plan["groupes"], R, polices)
    c1 = hex2rgb(R.couleur_1)
    total, corps = plan["total"], plan["corps"]
    plans = plan["plans"]

    logo_petit = logo_grand = None
    if R.fichier_logo and os.path.exists(R.fichier_logo):
        lg = Image.open(R.fichier_logo).convert("RGBA"); lg = lg.crop(lg.getbbox())
        logo_petit = lg.resize((300, max(1, int(300 * lg.height / lg.width))), Image.LANCZOS)
        lw = 720 if lg.width / lg.height > 1.6 else 420
        logo_grand = lg.resize((lw, max(1, int(lw * lg.height / lg.width))), Image.LANCZOS)
    logo_des = max(plans[-1]["a"], plans[-1]["b"] - 3.0)
    if len(plans) > 1:
        logo_des = min(logo_des, plans[-1]["a"])

    # écrans de couleur en temps source
    if plan.get("ecrans") is not None:          # projet édité : écrans de couleur indépendants
        ecrans = [(a, b, c) for a, b, c in plan["ecrans"]]
    else:
        ecrans = [(g["deb"] - 0.04, g["fin"], g["ecran"]) for g in plan["groupes"] if g["ecran"] is not None]
    illustrations = [Illustration(it) for it in (R.illustrations or [])
                     if it.get("fichier") and os.path.exists(it["fichier"])]

    # lecture de la source, déjà redressée, mise à l'échelle « cover » et étalonnée
    sw, sh = _taille_affichee(video)
    s = max(W / sw, H / sh)
    SW, SH = int(math.ceil(sw * s / 2) * 2), int(math.ceil(sh * s / 2) * 2)
    vf = f"fps={FPS},scale={SW}:{SH}:flags=bicubic"
    if R.etalonnage and R.style_etalonnage in ETALONNAGES:
        vf += "," + ETALONNAGES[R.style_etalonnage]
    taille = SW * SH * 3
    etat = {"idx": -1, "img": None, "proc": None}

    def ouvrir_lecteur(depuis_idx):
        """(Re)démarre la lecture de la source à l'image depuis_idx (retour en arrière ou grand saut)."""
        if etat["proc"] is not None:
            etat["proc"].kill()
        cmd = ["ffmpeg", "-loglevel", "error"]
        if depuis_idx > 0:
            cmd += ["-ss", f"{depuis_idx / FPS:.3f}"]
        etat["proc"] = subprocess.Popen(cmd + ["-i", video, "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                        stdout=subprocess.PIPE)
        etat["idx"] = depuis_idx - 1

    ouvrir_lecteur(0)

    def image_source(idx):
        if idx < etat["idx"] or idx - etat["idx"] > FPS * 4:
            ouvrir_lecteur(idx)
        while etat["idx"] < idx:
            lecteur = etat["proc"]
            buf = lecteur.stdout.read(taille)
            if len(buf) < taille:
                break
            etat["idx"] += 1
            if etat["idx"] == idx:
                etat["img"] = Image.frombuffer("RGB", (SW, SH), buf, "raw", "RGB", 0, 1)
        return etat["img"]

    tmp_v = sortie + ".video.mp4"
    ecrivain = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                 "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset",
                                 "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", tmp_v], stdin=subprocess.PIPE)
    nb = int(round(total * FPS)); j = 0
    for n in range(nb):
        ot = n / FPS
        if ot < corps:
            while j + 1 < len(plans) and plans[j + 1]["o"] <= ot + 1e-9:
                j += 1
            p = plans[j]
            st = p["a"] + (ot - p["o"])
            img = image_source(int(round(st * FPS)))
            ecran = next((c for a, b, c in ecrans if a <= st < b), None)
            ill = next((b for b in illustrations if b.deb <= st < b.fin), None) if ecran is None else None
            for b in illustrations:
                if b is not ill and st >= b.fin:
                    b.fermer()
            if ecran is not None or img is None:
                canvas = Image.new("RGBA", (W, H), (ecran or c1) + (255,))
            elif ill is not None:
                canvas = ill.image(st)
            else:
                frac = (st - p["a"]) / max(1e-6, p["b"] - p["a"])
                z = p["zoom"] * (1.0 + 0.025 * frac) * 1.03
                cw, ch = W / z, H / z
                x0 = min(max(SW / 2 - cw / 2, 0), SW - cw); y0 = min(max(SH * 0.5 - ch / 2, 0), SH - ch)
                canvas = img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch)).convert("RGBA")
            for g in plan["groupes"]:
                if g["deb"] - 0.001 <= st < g["fin"]:
                    for im, x, y, ts in g["items"]:
                        coller_anime(canvas, im, x, y, (st - ts) / 0.14, R.animation)
            if logo_petit is not None and R.logo_en_coin and st >= logo_des and ecran is None and ill is None:
                coller_anime(canvas, logo_petit, 70, H - 230, (st - logo_des) / 0.35)
        else:
            canvas = Image.new("RGBA", (W, H), c1 + (255,))
            if logo_grand is not None:
                coller_anime(canvas, logo_grand, (W - logo_grand.width) // 2, (H - logo_grand.height) // 2,
                             (ot - corps) / 0.5)
        ecrivain.stdin.write(canvas.convert("RGB").tobytes())
        if progression and n % (FPS * 5) == 0:
            print(f"  image {n}/{nb}  ({100 * n // nb} %)", flush=True)
        if rappel is not None and n % 15 == 0:
            rappel(n / nb)
    ecrivain.stdin.close(); ecrivain.wait(); etat["proc"].kill()
    for b in illustrations:
        b.fermer()

    # ---------------- audio
    evts = []
    if R.effets_sonores != "aucun":
        bornes = sorted({t for a, b, _ in ecrans for t in (a, b)})
        for t in bornes:
            o = src2out(plan, t + 1e-3)
            if o is not None:
                evts.append(("whoosh", o))
        cles = [g for g in plan["groupes"] if g["cle"] is not None and g["ecran"] is None]
        cles = sorted(cles, key=lambda g: -len(g["mots"][g["cle"]]["w"]))[:max(1, len(cles) // 4)][:6]
        for g in cles:
            o = src2out(plan, g["mots"][g["cle"]]["s"])
            if o is not None:
                evts.append(("pop", o))
        evts += [("whoosh", corps), ("carillon", corps + 0.1)]
    sfx = sortie + ".sfx.wav"
    generer_sfx(evts, total, sfx)

    zones = plan["zones"]
    parts, labels = [], []
    for k, z in enumerate(zones):
        d = z["b"] - z["a"]
        parts.append(f"[0:a]atrim={z['a']:.3f}:{z['b']:.3f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d=0.02,afade=t=out:st={max(0, d - 0.03):.3f}:d=0.03[a{k}]")
        labels.append(f"[a{k}]")
    f = ";".join(parts) + ";" + "".join(labels)
    f += (f"concat=n={len(zones)}:v=0:a=1,afade=t=out:st={max(0, corps - 0.25):.3f}:d=0.25,"
          f"apad=whole_dur={total:.3f},loudnorm=I=-14:TP=-2:LRA=11,aresample={SR},"
          f"aformat=channel_layouts=stereo,asplit=2[v][vk];"
          f"[1:a]aformat=channel_layouts=stereo,volume=0.55[s]")
    entrees = ["-i", video, "-i", sfx]
    if musique:
        entrees += ["-stream_loop", "-1", "-i", musique]
        dm = max(0.0, float(getattr(R, "decalage_musique", 0.0) or 0.0))
        f += (f";[2:a]atrim={dm:.3f}:{dm + total:.3f},asetpts=PTS-STARTPTS,aresample={SR},aformat=channel_layouts=stereo,"
              f"volume={R.volume_musique},afade=t=in:d=0.6,afade=t=out:st={max(0, total - 1.5):.3f}:d=1.5[m0];"
              f"[m0][vk]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=350[m];"
              f"[v][s][m]amix=inputs=3:normalize=0:duration=first,alimiter=limit=0.89[aout]")
    else:
        f += ";[vk]anullsink;[v][s]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.89[aout]"
    tmp_a = sortie + ".audio.m4a"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *entrees, "-filter_complex", f, "-map", "[aout]",
                    "-t", f"{total:.3f}", "-ar", str(SR), "-c:a", "aac", "-b:a", "192k", tmp_a], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", tmp_v, "-i", tmp_a, "-c", "copy", "-shortest",
                    "-movflags", "+faststart", sortie], check=True)
    for t in (tmp_v, tmp_a, sfx):
        try:
            os.remove(t)
        except OSError:
            pass
    return sortie


def resume_plan(plan):
    g = plan["groupes"]
    lignes = [f"Durée finale : {plan['total']:.1f} s ({len(plan['plans'])} plans, "
              f"{sum(1 for x in g if x['ecran'] is not None)} écrans de couleur)"]
    for x in g:
        mots = [w["w"].upper() if k == x["cle"] else w["w"] for k, w in enumerate(x["mots"])]
        tag = "  [écran couleur]" if x["ecran"] is not None else ""
        lignes.append(f"  {x['deb']:6.2f}s  {' '.join(mots)}{tag}")
    return "\n".join(lignes)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("sortie")
    ap.add_argument("--mots", help="JSON de mots horodatés (sinon Whisper)")
    ap.add_argument("--musique"); ap.add_argument("--logo", default="")
    ap.add_argument("--serif", default=""); ap.add_argument("--gras", default="")
    a = ap.parse_args()
    R = Reglages(fichier_logo=a.logo, police_serif=a.serif, police_grasse=a.gras)
    mots = json.load(open(a.mots)) if a.mots else transcrire(a.video)
    plan = construire_plan(mots, duree_video(a.video), R)
    print(resume_plan(plan))
    monter(a.video, plan, R, a.sortie, musique=a.musique)
    ecrire_srt(plan, os.path.splitext(a.sortie)[0] + ".srt")
    print("OK", a.sortie)
