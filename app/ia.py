"""IA facultative : Ollama (local, gratuit) ou Claude (API Anthropic, payant).

`demander_json(ia, consigne, images)` : `ia` est soit une clé Claude (texte), soit une configuration
{"fournisseur": "ollama"|"claude", ...} obtenue avec `config_ia(config)`.
"""
import base64
import io
import json
import re

MODELE = "claude-sonnet-5-5"
URL = "https://api.anthropic.com/v1/messages"
OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODELE = "qwen2.5vl:3b"      # texte + images, ≈ 3 Go : adapté à un Mac avec 8 Go de mémoire


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


def config_ia(config):
    """Configuration d'IA à partir des paramètres enregistrés (None = pas d'IA, règles locales)."""
    cles = config.get("cles", {})
    ia = config.get("ia") or {}
    fournisseur = ia.get("fournisseur") or ("claude" if cles.get("anthropic") else "aucune")
    if fournisseur == "claude" and cles.get("anthropic"):
        return {"fournisseur": "claude", "cle": cles["anthropic"]}
    if fournisseur == "ollama":
        return {"fournisseur": "ollama", "url": ia.get("ollama_url") or OLLAMA_URL,
                "modele": ia.get("ollama_modele") or OLLAMA_MODELE}
    return None


def nom_ia(ia):
    if not ia:
        return "aucune"
    if isinstance(ia, str):
        return "Claude"
    return "Claude" if ia.get("fournisseur") == "claude" else f"Ollama ({ia.get('modele', OLLAMA_MODELE)})"


def tester_ollama(url=OLLAMA_URL, modele=OLLAMA_MODELE, client=None):
    """(ok, message) : Ollama répond-il et le modèle est-il téléchargé ?"""
    import httpx
    try:
        c = client or httpx.Client(timeout=5)
        tags = [m.get("name", "") for m in c.get(url.rstrip("/") + "/api/tags").json().get("models", [])]
    except Exception:
        return False, "Ollama ne répond pas : installez-le avec « Installer IA locale (Ollama) », puis réessayez."
    if not any(t == modele or t.split(":")[0] == modele.split(":")[0] and modele in t for t in tags):
        return False, f"Ollama fonctionne, mais le modèle {modele} n'est pas téléchargé (modèles présents : {', '.join(tags) or 'aucun'})."
    return True, f"✅ Ollama fonctionne avec le modèle {modele}."


def _ollama(ia, consigne, images, client=None):
    import httpx
    images = list(images)[:4]                       # mémoire limitée : 4 images au plus
    msg = {"role": "user", "content": consigne + "\nRéponds uniquement avec le JSON demandé, sans texte autour."}
    if images:
        msg["images"] = [_image_b64(im, largeur=448) for im in images]
    corps = {"model": ia.get("modele") or OLLAMA_MODELE, "messages": [msg], "stream": False,
             "keep_alive": 0,                       # libère la mémoire tout de suite après la réponse
             "options": {"temperature": 0.2, "num_ctx": 8192}}
    c = client or httpx.Client(timeout=600)
    try:
        r = c.post((ia.get("url") or OLLAMA_URL).rstrip("/") + "/api/chat", json=corps)
    except Exception as e:
        raise ErreurIA(f"Ollama injoignable ({e}). Est-il installé et lancé ?")
    if r.status_code != 200:
        raise ErreurIA(f"Ollama : erreur {r.status_code} — {r.text[:200]}")
    return extraire_json(r.json().get("message", {}).get("content", ""))


def demander_json(cle, consigne, images=(), max_tokens=2000, client=None):
    """Envoie une consigne (et éventuellement des images PIL) à l'IA choisie et renvoie le JSON de la réponse."""
    if isinstance(cle, dict):
        if cle.get("fournisseur") == "ollama":
            return _ollama(cle, consigne, images, client=client)
        cle = cle.get("cle", "")
    if not cle:
        raise ErreurIA("Aucune IA configurée.")
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
