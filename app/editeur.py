"""Serveur de l'éditeur (timeline) : page, projet, médias, export.

Ajouté au même serveur que l'interface principale (127.0.0.1 uniquement).
"""
import glob
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid

import numpy as np
from typing import List

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

import configuration as C
import illustrations as I
import montage_auto as M
import projet as P

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIES = os.path.join(os.path.expanduser("~"), "Movies", "Montages Locapay")
ENVOIS = os.path.join(SORTIES, ".envois")
_travaux = {}


def _autorise(chemin, racines):
    vrai = os.path.realpath(chemin)
    return any(vrai == os.path.realpath(r) or vrai.startswith(os.path.realpath(r) + os.sep) for r in racines)


def _projet_path(p, racines):
    if not p or not p.endswith(".projet.json") or not _autorise(p, racines):
        raise HTTPException(403, "Projet non autorisé")
    return p


def lancer_travail(fonction):
    """Exécute fonction(rappel) en tâche de fond ; rappel(fraction, texte) met à jour la progression."""
    job = uuid.uuid4().hex[:8]
    _travaux[job] = {"progression": 0.0, "texte": "", "fini": False, "resultat": None, "erreur": None, "sortie": None}

    def rappel(f, texte=None):
        _travaux[job]["progression"] = round(float(f), 3)
        if texte:
            _travaux[job]["texte"] = texte

    def travail():
        try:
            _travaux[job]["resultat"] = fonction(rappel)
            _travaux[job].update(progression=1.0, fini=True)
        except Exception as e:
            traceback.print_exc()
            _travaux[job].update(fini=True, erreur=str(e))
    threading.Thread(target=travail, daemon=True).start()
    return job


def formes_onde(video, pas=0.05):
    """Amplitudes (0..1) de la voix tous les `pas` secondes, pour dessiner la forme d'onde."""
    cache = os.path.join(SORTIES, ".sources", os.path.basename(video) + f".onde{int(pas * 1000)}.npy")
    if os.path.exists(cache):
        return np.load(cache).tolist()
    sr = 4000
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", video, "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le",
                          "-"], capture_output=True).stdout
    x = np.abs(np.frombuffer(raw, np.int16).astype(np.float32)) / 32768
    n = int(sr * pas)
    pics = x[: len(x) // n * n].reshape(-1, n).max(axis=1) if len(x) >= n else np.zeros(1)
    pics = np.round(np.clip(pics / max(1e-6, np.percentile(pics, 99)), 0, 1), 3)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    np.save(cache, pics)
    return pics.tolist()


def ajouter_routes(api: FastAPI, racines):
    racines = list(racines) + [SORTIES, ICI]

    @api.get("/editeur", response_class=HTMLResponse)
    def page():
        with open(os.path.join(ICI, "editeur.html"), encoding="utf-8") as f:
            return f.read()

    @api.get("/editeur/api/projets")
    def projets():
        fichiers = sorted(glob.glob(os.path.join(SORTIES, "*.projet.json")), key=os.path.getmtime, reverse=True)
        return [{"chemin": f, "nom": os.path.basename(f)[:-len(".projet.json")],
                 "date": time.strftime("%d/%m/%Y %H:%M", time.localtime(os.path.getmtime(f)))} for f in fichiers[:50]]

    @api.get("/editeur/api/projet")
    def lire(p: str):
        proj = P.charger(_projet_path(p, racines))
        cfg = C.charger_config()
        r = proj.get("reglages", {})
        ident = cfg["identite"]
        return {"projet": proj, "identite": {
            "couleurs": [r.get("couleur_1", ident["couleur_1"]), r.get("couleur_2", ident["couleur_2"])],
            "logo": r.get("fichier_logo") or ident["fichier_logo"],
            "police_serif": r.get("police_serif") or ident["police_serif"],
            "police_grasse": r.get("police_grasse") or ident["police_grasse"]}}

    @api.put("/editeur/api/projet")
    async def ecrire(p: str, req: Request):
        proj = await req.json()
        P.sauver(proj, _projet_path(p, racines))
        return {"ok": True}

    @api.get("/editeur/api/onde")
    def onde(f: str):
        if not _autorise(f, racines):
            raise HTTPException(403)
        return {"pas": 0.05, "pics": formes_onde(f)}

    @api.get("/editeur/media")
    def media(f: str):
        if not _autorise(f, racines) or not os.path.exists(f):
            raise HTTPException(404)
        return FileResponse(f)          # gère les requêtes partielles (Range) nécessaires à la lecture vidéo

    @api.post("/editeur/api/envoyer")
    async def envoyer(fichier: UploadFile = File(...)):
        os.makedirs(ENVOIS, exist_ok=True)
        nom = f"{int(time.time())}_{os.path.basename(fichier.filename or 'fichier')}"
        dest = os.path.join(ENVOIS, nom)
        with open(dest, "wb") as out:
            shutil.copyfileobj(fichier.file, out)
        typ = "video" if dest.lower().endswith(M.EXT_VIDEO) else (
            "audio" if dest.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")) else "image")
        duree = M.duree_video(dest) if typ in ("video", "audio") else None
        return {"chemin": dest, "type": typ, "duree": duree}

    @api.post("/editeur/api/exporter")
    async def exporter(p: str, req: Request):
        chemin = _projet_path(p, racines)
        proj = await req.json()
        P.sauver(proj, chemin)
        base = os.path.basename(chemin)[:-len(".projet.json")]
        sortie = os.path.join(SORTIES, f"{base}_edit_{time.strftime('%Y%m%d-%H%M%S')}.mp4")
        job = lancer_travail(lambda rappel: P.rendre(proj, sortie, rappel=lambda x: rappel(x, "Montage…")))
        _travaux[job]["sortie"] = sortie
        return {"job": job}

    @api.get("/editeur/api/etat")
    def etat(job: str):
        if job not in _travaux:
            raise HTTPException(404)
        return _travaux[job]

    @api.post("/editeur/api/nouveau")
    async def nouveau(fichiers: List[UploadFile] = File(...)):
        os.makedirs(ENVOIS, exist_ok=True)
        chemins = []
        for f in fichiers:
            dest = os.path.join(ENVOIS, f"{int(time.time() * 1000)}_{os.path.basename(f.filename or 'video.mp4')}")
            with open(dest, "wb") as out:
                shutil.copyfileobj(f.file, out)
            chemins.append(dest)
        nom = os.path.splitext(os.path.basename(fichiers[0].filename or "projet"))[0][:40]
        return {"job": lancer_travail(lambda rappel: P.nouveau(
            chemins, nom=nom, rappel=lambda x: rappel(0.05 + 0.9 * x, "Préparation des vidéos…")))}

    @api.post("/editeur/api/auto")
    async def auto(p: str, req: Request):
        chemin = _projet_path(p, racines)
        proj = await req.json()
        P.sauver(proj, chemin)

        def travail(rappel):
            nouveau_proj = P.auto(proj, rappel=rappel)
            P.sauver(nouveau_proj, chemin)
            return {"ok": True}
        return {"job": lancer_travail(travail)}

    @api.get("/editeur/api/config")
    def config():
        cfg = C.charger_config()
        return {"style": cfg["style_actif"], "images": bool(cfg["cles"].get("pexels") or cfg["cles"].get("pixabay")),
                "claude": bool(cfg["cles"].get("anthropic"))}

    @api.post("/editeur/api/chercher")
    async def chercher(req: Request):
        d = await req.json()
        cles = C.charger_config()["cles"]
        if not (cles.get("pexels") or cles.get("pixabay")):
            raise HTTPException(400, "Ajoutez une clé Pexels ou Pixabay (gratuite) dans les Paramètres.")
        return I.rechercher(str(d.get("requete", "")).strip(), cles)

    @api.post("/editeur/api/prendre")
    async def prendre(req: Request):
        r = await req.json()
        return {"fichier": I.telecharger(r), "type": r.get("type", "image")}

    @api.post("/editeur/api/ouvrir")
    def ouvrir(f: str, mode: str = "lire"):
        if not _autorise(f, racines) or not os.path.exists(f):
            raise HTTPException(404)
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-a", "QuickTime Player", f] if mode == "lire" else ["open", "-R", f])
        return {"ok": True}

    return api
