"""Appels (facultatifs) à Claude via l'API d'Anthropic — utilisés seulement si une clé est configurée."""
import base64
import io
import json
import re

MODELE = "claude-sonnet-5-5"
URL = "https://api.anthropic.com/v1/messages"


class ErreurIA(RuntimeError):
    pass


def _image_b64(img, largeur=512):
    im = img.convert("RGB")
    if im.width > largeur:
        im = im.resize((largeur, int(im.height * largeur / im.width)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def extraire_json(texte):
    """Récupère le premier objet ou tableau JSON d'une réponse (avec ou sans bloc ```json)."""
    m = re.search(r"```(?:json)?\s*(.+?)```", texte, re.S)
    if m:
        texte = m.group(1)
    paires = sorted((("{", "}"), ("[", "]")), key=lambda p: texte.find(p[0]) if p[0] in texte else 10 ** 9)
    for ouvrant, fermant in paires:
        i, j = texte.find(ouvrant), texte.rfind(fermant)
        if i != -1 and j > i:
            try:
                return json.loads(texte[i:j + 1])
            except ValueError:
                continue
    raise ErreurIA("Réponse de l'IA illisible.")


def demander_json(cle, consigne, images=(), max_tokens=2000, client=None):
    """Envoie une consigne (et éventuellement des images PIL) à Claude et renvoie le JSON de la réponse."""
    if not cle:
        raise ErreurIA("Aucune clé API Anthropic configurée.")
    import httpx
    contenu = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _image_b64(im)}}
               for im in images]
    contenu.append({"type": "text", "text": consigne})
    corps = {"model": MODELE, "max_tokens": max_tokens, "messages": [{"role": "user", "content": contenu}]}
    entetes = {"x-api-key": cle, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    c = client or httpx.Client(timeout=120)
    r = c.post(URL, json=corps, headers=entetes)
    if r.status_code != 200:
        raise ErreurIA(f"API Anthropic : erreur {r.status_code} — {r.text[:200]}")
    texte = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    return extraire_json(texte)
