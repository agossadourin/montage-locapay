"""Musique de fond libre de droits via Openverse (gratuit, sans clé).

On ne garde que les morceaux dont la licence autorise un usage commercial (CC0, CC BY, CC BY-SA…).
Pour les licences « BY », il faut créditer l'artiste : `credit` donne le texte à mettre en description.
"""
import hashlib
import os
import re

API = "https://api.openverse.org/v1/audio/"
import chemins

DOSSIER = os.path.join(chemins.DOSSIER_APP, ".musique")

AMBIANCES = {
    "Dynamique": "upbeat corporate",
    "Afro": "afrobeat",
    "Inspirant": "inspiring motivational",
    "Joyeux": "happy upbeat",
    "Calme": "calm ambient",
    "Électro": "electronic beat",
}
LICENCES_OK = {"cc0", "pdm", "by", "by-sa"}          # usage commercial autorisé (pas NC, pas ND)


def _client():
    import httpx
    return httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "Raccord/1.0"})


def credit(r):
    lic = (r.get("licence") or "").upper()
    if lic in ("CC0", "PDM"):
        return ""
    return (f"Musique : « {r.get('titre', 'Sans titre')} » par {r.get('artiste', 'artiste inconnu')} — "
            f"licence CC {lic} {r.get('version', '')}".strip() + (f" — {r['page']}" if r.get("page") else ""))


def rechercher(requete, client=None, nombre=12):
    """Morceaux de musique libres pour usage commercial : [{titre, artiste, licence, url, page, duree, credit}]."""
    c = client or _client()
    r = c.get(API, params={"q": requete or "background music", "license_type": "commercial",
                           "category": "music", "page_size": nombre})
    if r.status_code != 200:
        raise RuntimeError(f"Openverse indisponible (erreur {r.status_code}).")
    out = []
    for x in r.json().get("results", []):
        lic = (x.get("license") or "").lower()
        if lic not in LICENCES_OK or not x.get("url"):
            continue
        duree = (x.get("duration") or 0) / 1000
        if duree and duree < 20:                         # trop court pour un fond musical
            continue
        res = {"titre": x.get("title") or "Sans titre", "artiste": x.get("creator") or "artiste inconnu",
               "licence": lic, "version": x.get("license_version") or "", "url": x["url"],
               "page": x.get("foreign_landing_url") or "", "duree": round(duree, 1), "source": x.get("source", "")}
        res["credit"] = credit(res)
        out.append(res)
    return out


def telecharger(res, client=None):
    os.makedirs(DOSSIER, exist_ok=True)
    ext = os.path.splitext(res["url"].split("?")[0])[1].lower()
    if ext not in (".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"):
        ext = ".mp3"
    nom = re.sub(r"[^\w-]+", "_", res.get("titre", "musique"))[:40] + "_" + \
        hashlib.md5(res["url"].encode()).hexdigest()[:8] + ext
    chemin = os.path.join(DOSSIER, nom)
    if not os.path.exists(chemin):
        c = client or _client()
        r = c.get(res["url"])
        r.raise_for_status()
        with open(chemin + ".part", "wb") as f:
            f.write(r.content)
        os.replace(chemin + ".part", chemin)
    return chemin
