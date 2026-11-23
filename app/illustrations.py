"""Illustrations automatiques (B-roll) : choisir les moments, chercher des images/vidéos libres de droits.

- Choix des moments : Claude (si une clé est configurée) ou dictionnaire de mots « illustrables ».
- Recherche : Pexels et/ou Pixabay (clés gratuites, usage commercial autorisé sans attribution obligatoire).
- Génération : Cloudflare Workers AI (FLUX.1 schnell, gratuit jusqu'à ~170 images/jour) ou Gemini (payant).
"""
import base64
import hashlib
import math
import os
import re

import ia

import chemins

DOSSIER_CACHE = os.path.join(chemins.DOSSIER_APP, ".illustrations")

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
                   params={"query": requete, "orientation": "portrait", "size": "medium", "per_page": 15})
    if r.status_code == 200:
        for v in r.json().get("videos", []):
            fichiers = [f for f in v.get("video_files", []) if f.get("link") and (f.get("width") or f.get("height"))]
            if not fichiers:
                continue
            wh = lambda f: (f.get("width") or f.get("height"), f.get("height") or f.get("width"))
            # le fichier le plus léger d'au moins 720 px sur le petit côté (sinon le plus grand)
            assez = sorted([f for f in fichiers if min(wh(f)) >= 720], key=lambda f: wh(f)[0] * wh(f)[1])
            f = assez[0] if assez else max(fichiers, key=lambda f: wh(f)[0] * wh(f)[1])
            w, h = (f.get("width"), f.get("height")) if f.get("width") and f.get("height") else (v.get("width"), v.get("height"))
            out.append({"type": "video", "apercu": v.get("image"), "url": f["link"], "w": w, "h": h,
                        "id": f"pexels-v{v.get('id')}", "credit": (v.get("user") or {}).get("name", "Pexels")})
    r = client.get("https://api.pexels.com/v1/search", headers=h,
                   params={"query": requete, "orientation": "portrait", "per_page": 8})
    if r.status_code == 200:
        for p in r.json().get("photos", []):
            src = p.get("src") or {}
            if src.get("portrait") or src.get("large2x"):
                # « portrait » = version recadrée 800×1200 fournie par Pexels
                w, h = (800, 1200) if src.get("portrait") else (p.get("width"), p.get("height"))
                out.append({"type": "image", "apercu": src.get("medium") or src.get("small"),
                            "url": src.get("portrait") or src.get("large2x"), "id": f"pexels-p{p.get('id')}",
                            "w": w, "h": h, "credit": p.get("photographer", "Pexels")})
    return out


def _pixabay(requete, cle, client):
    out = []
    # (l'API vidéo de Pixabay n'a pas de filtre d'orientation : on en demande plus et on trie ensuite)
    r = client.get("https://pixabay.com/api/videos/", params={"key": cle, "q": requete, "per_page": 20})
    if r.status_code == 200:
        for v in r.json().get("hits", []):
            fv = (v.get("videos") or {}).get("medium") or (v.get("videos") or {}).get("small") or {}
            if fv.get("url"):
                out.append({"type": "video", "apercu": fv.get("thumbnail"), "url": fv["url"],
                            "w": fv.get("width"), "h": fv.get("height"),
                            "id": f"pixabay-v{v.get('id')}", "credit": v.get("user", "Pixabay")})
    r = client.get("https://pixabay.com/api/", params={"key": cle, "q": requete, "orientation": "vertical",
                                                       "image_type": "photo", "per_page": 8})
    if r.status_code == 200:
        for p in r.json().get("hits", []):
            if p.get("largeImageURL"):
                out.append({"type": "image", "apercu": p.get("webformatURL") or p.get("previewURL"),
                            "url": p["largeImageURL"], "id": f"pixabay-p{p.get('id')}",
                            "w": p.get("imageWidth"), "h": p.get("imageHeight"),
                            "credit": p.get("user", "Pixabay")})
    return out


OPENVERSE_IMAGES = "https://api.openverse.org/v1/images/"


def credit_image(x):
    """Texte de crédit à mettre en description (licence CC BY) ; vide si aucune attribution n'est exigée."""
    lic = (x.get("licence") or "").lower()
    if lic in ("cc0", "pdm", ""):
        return ""
    return (f"Image : « {x.get('titre') or 'Sans titre'} » par {x.get('credit') or 'auteur inconnu'} — "
            f"licence CC {lic.upper()} {x.get('version', '')}".strip() + (f" — {x['page']}" if x.get("page") else ""))


def _openverse(requete, c):
    """Images Openverse sous licence libre, usage commercial, sans clé (CC0, domaine public, CC BY)."""
    r = c.get(OPENVERSE_IMAGES, params={"q": requete, "license": "cc0,pdm,by", "aspect_ratio": "tall",
                                        "page_size": 12, "mature": "false"})
    out = []
    if r.status_code == 200:
        for x in r.json().get("results", []):
            if not x.get("url"):
                continue
            res = {"type": "image", "apercu": x.get("thumbnail") or x["url"], "url": x["url"],
                   "id": f"openverse-{x.get('id')}", "w": x.get("width"), "h": x.get("height"),
                   "credit": x.get("creator") or "Openverse", "licence": (x.get("license") or "").lower(),
                   "version": x.get("license_version") or "", "titre": x.get("title") or "",
                   "page": x.get("foreign_landing_url") or "", "source": "openverse"}
            res["credit_licence"] = credit_image(res)
            out.append(res)
    return out


def rechercher(requete, cles, client=None):
    """Résultats (vidéos d'abord, puis photos) : [{type, apercu, url, id, credit}].
    Pexels / Pixabay si une clé est fournie ; Openverse (sans clé) en complément."""
    c = client or _client()
    res = []
    for nom, f in (("pexels", lambda: _pexels(requete, cles["pexels"], c)),
                   ("pixabay", lambda: _pixabay(requete, cles["pixabay"], c)),
                   ("openverse", lambda: _openverse(requete, c))):
        if nom != "openverse" and not cles.get(nom):
            continue
        try:
            res += f()
        except Exception as e:
            print(f"Recherche d'illustrations ({nom}) impossible →", e)
    for r in res:
        r["orientation"] = orientation(r.get("w"), r.get("h"))
    verticaux = [r for r in res if r["orientation"] != "paysage"]
    videos = [r for r in verticaux if r["type"] == "video"]
    photos = [r for r in verticaux if r["type"] == "image"]
    melange = []
    for i in range(max(len(videos), len(photos))):   # alterne vidéo / photo pour varier les propositions
        melange += videos[i:i + 1] + photos[i:i + 1]
    # les médias en paysage (qu'il faudrait trop zoomer) viennent en dernier
    return melange + [r for r in res if r["orientation"] == "paysage"]


def orientation(w, h):
    """« portrait », « carre » ou « paysage » (inconnu = portrait : les recherches demandent du vertical)."""
    try:
        r = float(w) / float(h)
    except (TypeError, ValueError, ZeroDivisionError):
        return "portrait"
    return "paysage" if r > 1.15 else ("carre" if r > 0.8 else "portrait")


# ------------------------------------------------------------------ génération d'images (Gemini)
GEMINI_MODELE = "gemini-3.1-flash-lite-image"     # le moins cher (~0,03 $ l'image 1K) ; voir README
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent"


def fournisseur_images(cfg):
    """Générateur d'images à utiliser : celui choisi dans les Paramètres s'il est configuré, sinon le premier
    configuré (Cloudflare d'abord, gratuit). None si aucun."""
    cles = cfg.get("cles") or {}
    dispo = {"cloudflare": bool(cles.get("cloudflare_compte") and cles.get("cloudflare_jeton")),
             "gemini": bool(cles.get("gemini"))}
    choix = (cfg.get("illustrations") or {}).get("source")
    if dispo.get(choix):
        return choix
    return next((f for f in ("cloudflare", "gemini") if dispo[f]), None)


def generer(prompt, cfg, fournisseur=None, client=None):
    """Crée une image avec le générateur configuré et renvoie son chemin."""
    fournisseur = fournisseur or fournisseur_images(cfg)
    cles = cfg.get("cles") or {}
    if fournisseur == "cloudflare":
        return generer_image_cloudflare(prompt, cles["cloudflare_compte"], cles["cloudflare_jeton"], client=client)
    if fournisseur == "gemini":
        return generer_image(prompt, cles["gemini"], client=client)
    raise RuntimeError("Aucun générateur d'images configuré : ajoutez Cloudflare (gratuit) ou Gemini dans "
                       "⚙️ Paramètres › Clés API.")


def prompt_illustration(moment, contexte, fournisseur="gemini"):
    """Consigne à partir du moment à illustrer (phrase prononcée + mot) et du contexte de la marque.
    FLUX (Cloudflare) comprend mieux l'anglais : la consigne y est rédigée en anglais."""
    phrase = (moment.get("phrase") or "").strip()
    mot = (moment.get("mot") or "").strip()
    if fournisseur == "cloudflare":
        sujet = (moment.get("requete") or mot).strip()
        p = "Authentic realistic photograph, vertical composition, main subject centered in the frame."
        if sujet:
            p += f" Scene: {sujet}."
        if phrase:
            p += f" It illustrates this sentence (in French): \"{phrase}\"."
        if contexte:
            p += f" Context (in French): {contexte.strip()}"
        return p + " Natural light, warm colors, candid. No text, no letters, no logo, no watermark."
    p = "Photographie réaliste, format vertical 9:16, pour illustrer ce passage d'une vidéo"
    p += f" : « {phrase} »." if phrase else "."
    if mot:
        p += f" Sujet principal : {mot}."
    if contexte:
        p += f" Contexte : {contexte.strip()}"
    return p + (" Style : photo authentique prise sur le vif, lumière naturelle, couleurs chaudes, sujet bien centré. "
                "Aucun texte, aucune écriture, aucun logo, aucun filigrane.")


def _image_de_reponse(donnees):
    for cand in donnees.get("candidates") or []:
        for part in ((cand.get("content") or {}).get("parts") or []):
            d = part.get("inlineData") or part.get("inline_data")
            if d and d.get("data"):
                return base64.b64decode(d["data"]), d.get("mimeType") or d.get("mime_type") or "image/png"
    raise RuntimeError("Gemini n'a pas renvoyé d'image" + (
        f" ({donnees['candidates'][0].get('finishReason')})" if donnees.get("candidates") else
        f" ({(donnees.get('promptFeedback') or {}).get('blockReason', 'réponse vide')})"))


def generer_image(prompt, cle, client=None, modele=None):
    """Génère une image verticale (9:16) avec Gemini et renvoie son chemin local (mise en cache par consigne)."""
    os.makedirs(DOSSIER_CACHE, exist_ok=True)
    modele = modele or GEMINI_MODELE
    empreinte = hashlib.md5(f"{modele}|{prompt}".encode()).hexdigest()[:16]
    deja = [f for f in os.listdir(DOSSIER_CACHE) if f.startswith(f"gemini-{empreinte}.")]
    if deja:
        return os.path.join(DOSSIER_CACHE, deja[0])
    c = client or _client()
    url = GEMINI_URL.format(modele=modele)
    base = {"contents": [{"parts": [{"text": prompt}]}]}
    # deux écritures du format d'image selon les versions de l'API : on essaie la plus courante d'abord
    variantes = [{"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "9:16"}},
                 {"responseModalities": ["TEXT", "IMAGE"], "responseFormat": {"image": {"aspectRatio": "9:16"}}}]
    erreur = None
    for gen in variantes:
        r = c.post(url, headers={"x-goog-api-key": cle, "Content-Type": "application/json"},
                   json={**base, "generationConfig": gen}, timeout=120)
        if r.status_code == 200:
            donnees, typ = _image_de_reponse(r.json())
            ext = {"image/jpeg": ".jpg", "image/webp": ".webp"}.get(typ, ".png")
            chemin = os.path.join(DOSSIER_CACHE, f"gemini-{empreinte}{ext}")
            with open(chemin + ".part", "wb") as f:
                f.write(donnees)
            os.replace(chemin + ".part", chemin)
            return chemin
        try:
            message = r.json().get("error", {}).get("message", "")
        except ValueError:
            message = r.text[:200]
        erreur = f"Gemini a refusé la demande ({r.status_code}) : {message}"
        if r.status_code == 429 and ("free_tier" in message or "limit: 0" in message or "billing" in message):
            erreur = ("Votre clé Gemini est en offre gratuite : la création d'images n'y est pas incluse. "
                      "Dans Google AI Studio, cliquez sur « Set up billing » à côté du projet de la clé et ajoutez "
                      "au moins 5 $ de crédit, puis réessayez quelques minutes plus tard (si l'erreur persiste, "
                      "créez une nouvelle clé dans ce projet). Détail : " + message[:160])
        elif r.status_code in (401, 403):
            erreur = f"Clé Gemini refusée ({r.status_code}) : vérifiez-la dans ⚙️ Paramètres › Clés API. Détail : {message[:160]}"
        if r.status_code != 400:          # clé invalide, quota, facturation… : inutile d'essayer l'autre écriture
            break
    raise RuntimeError(erreur)


CLOUDFLARE_MODELE = "@cf/black-forest-labs/flux-1-schnell"   # licence Apache 2.0 : usage commercial permis
CLOUDFLARE_URL = "https://api.cloudflare.com/client/v4/accounts/{compte}/ai/run/{modele}"


def generer_image_cloudflare(prompt, compte, jeton, client=None, modele=None):
    """Image FLUX.1 schnell via Cloudflare Workers AI (offre gratuite : 10 000 « neurones » par jour,
    soit environ 170 images). Image carrée 1024 px : montrée en entier sur fond flou dans la vidéo verticale."""
    os.makedirs(DOSSIER_CACHE, exist_ok=True)
    modele = modele or CLOUDFLARE_MODELE
    empreinte = hashlib.md5(f"{modele}|{prompt}".encode()).hexdigest()[:16]
    chemin = os.path.join(DOSSIER_CACHE, f"flux-{empreinte}.jpg")
    if os.path.exists(chemin):
        return chemin
    c = client or _client()
    # paramètres acceptés par le modèle : prompt (+ steps) ; s'il refuse un champ, on réessaie avec la consigne seule
    for corps in ({"prompt": prompt[:2048], "steps": 4}, {"prompt": prompt[:2048]}):
        r = c.post(CLOUDFLARE_URL.format(compte=compte.strip(), modele=modele),
                   headers={"Authorization": f"Bearer {jeton.strip()}"}, json=corps, timeout=120)
        try:
            d = r.json()
        except ValueError:
            d = {}
        if not (r.status_code == 400 and "propert" in r.text):
            break
    if r.status_code != 200 or not (d.get("result") or {}).get("image"):
        message = "; ".join(e.get("message", "") for e in d.get("errors") or []) or r.text[:200]
        if r.status_code == 429 or "neurons" in message.lower() or "limit" in message.lower():
            raise RuntimeError("Quota gratuit Cloudflare du jour atteint (environ 170 images par jour). "
                               f"Il se renouvelle à 1 h du matin (heure de Paris). Détail : {message[:160]}")
        if r.status_code in (401, 403):
            raise RuntimeError("Cloudflare refuse l'accès : vérifiez l'identifiant de compte et le jeton (permission "
                               f"« Workers AI ») dans ⚙️ Paramètres › Clés API. Détail : {message[:160]}")
        raise RuntimeError(f"Cloudflare n'a pas créé l'image ({r.status_code}) : {message[:200]}")
    with open(chemin + ".part", "wb") as f:
        f.write(base64.b64decode(d["result"]["image"]))
    os.replace(chemin + ".part", chemin)
    return chemin


def tester_cloudflare(compte, jeton, client=None):
    if not (compte and jeton):
        return False, "Ajoutez l'identifiant de compte et le jeton Cloudflare."
    try:
        c = client or _client()
        r = c.get("https://api.cloudflare.com/client/v4/user/tokens/verify", headers={"Authorization": f"Bearer {jeton.strip()}"})
        if r.status_code == 200 and r.json().get("success"):
            return True, "✅ Jeton Cloudflare valide (vérifiez qu'il a bien la permission « Workers AI »)"
        return False, f"❌ Jeton refusé ({r.status_code})"
    except Exception as e:
        return False, f"❌ Cloudflare injoignable : {e}"


def tester_gemini(cle, client=None):
    """(ok, message) — vérifie que la clé Gemini est acceptée (liste des modèles, sans rien générer)."""
    if not cle:
        return False, "Ajoutez d'abord une clé Gemini."
    try:
        c = client or _client()
        r = c.get("https://generativelanguage.googleapis.com/v1beta/models", headers={"x-goog-api-key": cle})
        if r.status_code == 200:
            noms = [m.get("name", "") for m in r.json().get("models", [])]
            image = any("image" in n for n in noms)
            return True, "✅ Clé Gemini acceptée" + ("" if image else " (aucun modèle d'image listé pour ce compte)")
        return False, f"❌ Clé refusée ({r.status_code}) : {r.json().get('error', {}).get('message', '')}"
    except Exception as e:
        return False, f"❌ Gemini injoignable : {e}"


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
