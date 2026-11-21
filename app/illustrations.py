"""Illustrations automatiques (B-roll) : choisir les moments, chercher des images/vidéos libres de droits.

- Choix des moments : Claude (si une clé est configurée) ou dictionnaire de mots « illustrables ».
- Recherche : Pexels et/ou Pixabay (clés gratuites, usage commercial autorisé sans attribution obligatoire).
"""
import hashlib
import math
import os
import re

import ia

DOSSIER_CACHE = os.path.join(os.path.expanduser("~"), "Movies", "Montages Locapay", ".illustrations")

# mot (forme normalisée, singulier) -> recherche en anglais (les banques d'images répondent mieux en anglais)
MOTS_IMAGES = {
    "argent": "money cash", "billet": "banknotes", "loyer": "paying rent", "payer": "mobile payment",
    "paiement": "mobile payment", "payez": "mobile payment", "paie": "paying money", "facture": "bill invoice",
    "banque": "bank", "épargne": "savings piggy bank", "dépense": "spending money", "prix": "price tag",
    "maison": "house", "appartement": "apartment interior", "chambre": "bedroom", "logement": "housing apartment",
    "immeuble": "apartment building", "villa": "villa", "studio": "small studio apartment", "salon": "living room",
    "cuisine": "kitchen", "clé": "house keys", "clef": "house keys", "porte": "front door", "quartier": "neighborhood street",
    "ville": "african city", "cotonou": "Cotonou Benin city", "bénin": "Benin", "afrique": "africa city",
    "propriétaire": "landlord handshake", "locataire": "tenant moving in", "démarcheur": "real estate agent",
    "agent": "real estate agent", "agence": "real estate agency", "visite": "house visit", "contrat": "signing contract",
    "bail": "lease contract signing", "signature": "signing document", "document": "documents paperwork",
    "téléphone": "smartphone", "application": "mobile app smartphone", "appli": "mobile app smartphone",
    "internet": "browsing internet phone", "recherche": "searching on phone", "message": "texting phone",
    "transaction": "mobile money transaction", "sécurité": "security lock", "sécurisé": "secure payment",
    "confiance": "trust handshake", "famille": "african family home", "enfant": "children playing",
    "travail": "working office", "bureau": "office", "entreprise": "business team", "client": "customer service",
    "temps": "clock time", "stress": "stressed person", "problème": "frustrated person", "solution": "happy person phone",
    "voiture": "car", "taxi": "taxi city", "moto": "motorbike taxi africa", "déménagement": "moving boxes",
    "carton": "moving boxes", "marché": "african market", "école": "school", "étudiant": "student",
    "fête": "celebration", "merci": "thank you smile", "sourire": "smiling person", "avenir": "future sunrise",
    "électricité": "electricity", "eau": "water tap", "réparation": "home repair", "travaux": "renovation work",
    "arnaque": "scam fraud", "fraude": "fraud warning", "honnête": "honest handshake", "professionnel": "professional business",
}

CONSIGNE_IA = """Voici la transcription horodatée (en secondes) d'une vidéo face caméra en français :
{phrases}

Choisis jusqu'à {n} moments où une image ou une courte vidéo d'illustration (B-roll) renforcerait le propos :
objets, lieux, actions concrètes mentionnés (argent, maison, téléphone, signature de contrat…). Évite les toutes
premières et dernières secondes, espace les moments d'au moins {ecart:.0f} s, et chaque illustration dure 1,5 à 3 s.
Réponds UNIQUEMENT par un tableau JSON : [{{"deb": secondes, "fin": secondes, "mot": "mot de la phrase",
"requete": "recherche en anglais pour une banque d'images, 2 à 4 mots, concrète et visuelle"}}]"""


def _norm(t):
    t = re.sub(r"[^\wàâäéèêëîïôöùûüç'-]", "", t.lower())
    return t.split("'")[-1]


def _singulier(t):
    if t in MOTS_IMAGES:
        return t
    for fin in ("s", "x"):
        if t.endswith(fin) and t[:-1] in MOTS_IMAGES:
            return t[:-1]
    return t


def choisir_moments(mots, duree, par_minute=4.0, cle_api=""):
    """Propose des moments à illustrer : [{deb, fin, mot, requete, phrase}] (temps de la vidéo brute)."""
    mots = [m for m in mots if m.get("st", True) and m.get("w")]
    if not mots or par_minute <= 0:
        return []
    n = max(1, int(math.ceil(duree / 60 * par_minute - 0.05)))
    ecart = max(3.0, 60.0 / par_minute * 0.7)
    debut_min, fin_max = mots[0]["s"] + 1.5, mots[-1]["e"] - 2.0

    def phrase_autour(t):
        return " ".join(m["w"] for m in mots if abs(m["s"] - t) < 2.5)

    props = []
    if cle_api:
        lignes, cur, t0 = [], [], None
        for m in mots:
            if t0 is None:
                t0 = m["s"]
            cur.append(m["w"])
            if re.search(r"[.!?…]$", m["w"]) or len(cur) > 18:
                lignes.append(f"[{t0:.1f}-{m['e']:.1f}] {' '.join(cur)}"); cur, t0 = [], None
        if cur:
            lignes.append(f"[{t0:.1f}-{mots[-1]['e']:.1f}] {' '.join(cur)}")
        try:
            res = ia.demander_json(cle_api, CONSIGNE_IA.format(phrases="\n".join(lignes), n=n, ecart=ecart))
            for r in res if isinstance(res, list) else []:
                deb, fin = float(r["deb"]), float(r["fin"])
                if debut_min - 1 <= deb < fin and fin - deb <= 4 and r.get("requete"):
                    props.append({"deb": deb, "fin": min(fin, deb + 3.0), "mot": str(r.get("mot", "")),
                                  "requete": str(r["requete"]), "phrase": phrase_autour(deb)})
        except Exception as e:
            print("Illustrations : choix par Claude impossible →", e)
            props = []

    if not props:   # règles locales : mots « illustrables »
        for m in mots:
            k = _singulier(_norm(m["w"]))
            if k in MOTS_IMAGES and debut_min <= m["s"] <= fin_max:
                props.append({"deb": max(0.0, m["s"] - 0.1), "fin": m["s"] + 2.2, "mot": m["w"].strip(",.!?…"),
                              "requete": MOTS_IMAGES[k], "phrase": phrase_autour(m["s"])})

    # espacement + nombre maximum, en gardant les moments les mieux répartis
    props.sort(key=lambda p: p["deb"])
    gardes = []
    for p in props:
        if not gardes or p["deb"] - gardes[-1]["fin"] >= ecart - 2.2:
            gardes.append(p)
    if len(gardes) > n:
        pas = len(gardes) / n
        gardes = [gardes[int(i * pas)] for i in range(n)]
    return gardes


# ------------------------------------------------------------------ banques d'images
def _client():
    import httpx
    return httpx.Client(timeout=30, follow_redirects=True)


def _pexels(requete, cle, client):
    out = []
    h = {"Authorization": cle}
    r = client.get("https://api.pexels.com/videos/search", headers=h,
                   params={"query": requete, "orientation": "portrait", "per_page": 8})
    if r.status_code == 200:
        for v in r.json().get("videos", []):
            fichiers = sorted([f for f in v.get("video_files", []) if f.get("link") and (f.get("height") or 0) >= 720],
                              key=lambda f: f.get("height") or 0)
            if fichiers:
                out.append({"type": "video", "apercu": v.get("image"), "url": fichiers[0]["link"],
                            "id": f"pexels-v{v.get('id')}", "credit": (v.get("user") or {}).get("name", "Pexels")})
    r = client.get("https://api.pexels.com/v1/search", headers=h,
                   params={"query": requete, "orientation": "portrait", "per_page": 8})
    if r.status_code == 200:
        for p in r.json().get("photos", []):
            src = p.get("src") or {}
            if src.get("portrait") or src.get("large2x"):
                out.append({"type": "image", "apercu": src.get("medium") or src.get("small"),
                            "url": src.get("portrait") or src.get("large2x"), "id": f"pexels-p{p.get('id')}",
                            "credit": p.get("photographer", "Pexels")})
    return out


def _pixabay(requete, cle, client):
    out = []
    r = client.get("https://pixabay.com/api/videos/", params={"key": cle, "q": requete, "per_page": 8})
    if r.status_code == 200:
        for v in r.json().get("hits", []):
            fv = (v.get("videos") or {}).get("medium") or (v.get("videos") or {}).get("small") or {}
            if fv.get("url"):
                out.append({"type": "video", "apercu": fv.get("thumbnail"), "url": fv["url"],
                            "id": f"pixabay-v{v.get('id')}", "credit": v.get("user", "Pixabay")})
    r = client.get("https://pixabay.com/api/", params={"key": cle, "q": requete, "orientation": "vertical",
                                                       "image_type": "photo", "per_page": 8})
    if r.status_code == 200:
        for p in r.json().get("hits", []):
            if p.get("largeImageURL"):
                out.append({"type": "image", "apercu": p.get("webformatURL") or p.get("previewURL"),
                            "url": p["largeImageURL"], "id": f"pixabay-p{p.get('id')}",
                            "credit": p.get("user", "Pixabay")})
    return out


def rechercher(requete, cles, client=None):
    """Résultats (vidéos d'abord, puis photos) : [{type, apercu, url, id, credit}]."""
    c = client or _client()
    res = []
    try:
        if cles.get("pexels"):
            res += _pexels(requete, cles["pexels"], c)
        if cles.get("pixabay"):
            res += _pixabay(requete, cles["pixabay"], c)
    except Exception as e:
        print("Recherche d'illustrations impossible →", e)
    videos = [r for r in res if r["type"] == "video"]
    photos = [r for r in res if r["type"] == "image"]
    melange = []
    for i in range(max(len(videos), len(photos))):   # alterne vidéo / photo pour varier les propositions
        melange += videos[i:i + 1] + photos[i:i + 1]
    return melange


def telecharger(resultat, client=None):
    """Télécharge (avec cache) le média choisi et renvoie son chemin local."""
    os.makedirs(DOSSIER_CACHE, exist_ok=True)
    ext = os.path.splitext(resultat["url"].split("?")[0])[1].lower() or (".mp4" if resultat["type"] == "video" else ".jpg")
    nom = re.sub(r"[^\w-]", "_", resultat.get("id") or hashlib.md5(resultat["url"].encode()).hexdigest()) + ext
    chemin = os.path.join(DOSSIER_CACHE, nom)
    if not os.path.exists(chemin):
        c = client or _client()
        r = c.get(resultat["url"])
        r.raise_for_status()
        with open(chemin + ".part", "wb") as f:
            f.write(r.content)
        os.replace(chemin + ".part", chemin)
    return chemin
