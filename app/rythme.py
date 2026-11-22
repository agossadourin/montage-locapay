"""Temps forts d'une musique et montage calé sur le rythme.

`temps_forts` utilise librosa s'il est installé, sinon un détecteur intégré (numpy) :
enveloppe d'attaques (flux spectral) → tempo (autocorrélation) → suivi des temps (programmation dynamique,
méthode d'Ellis 2007, celle de librosa).

`caler(proj)` ajuste un projet de l'éditeur :
- la musique démarre sur un temps fort ;
- les changements de cadrage à l'intérieur d'une même prise (punch-in) tombent sur les temps ;
- les écrans de couleur commencent sur un temps.
Les coupes entre deux prises différentes ne bougent pas (elles suivent la parole).
"""
import os
import subprocess

import numpy as np

SR = 11025
_cache = {}


def _audio(fichier, sr=SR, duree_max=600):
    brut = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", fichier, "-t", str(duree_max), "-vn", "-ac", "1",
                           "-ar", str(sr), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(brut, np.float32).astype(np.float64)


def enveloppe_attaques(y, sr=SR, n_fft=1024, hop=256):
    """Force des attaques (flux spectral en échelle log) ; une valeur par trame de `hop` échantillons."""
    if len(y) < n_fft * 2:
        return np.zeros(1), sr / hop
    n = 1 + (len(y) - n_fft) // hop
    fen = np.hanning(n_fft)
    spec = np.empty((n, n_fft // 2 + 1), np.float32)
    for i in range(0, n, 2048):                                   # par morceaux (mémoire limitée)
        idx = np.arange(n_fft)[None, :] + hop * np.arange(i, min(n, i + 2048))[:, None]
        spec[i:i + len(idx)] = np.abs(np.fft.rfft(y[idx] * fen, axis=1))
    lg = np.log1p(100 * spec)
    flux = np.maximum(0.0, np.diff(lg, axis=0)).sum(axis=1)
    flux = np.concatenate([[0.0], flux])
    k = max(3, int(sr / hop * 0.5))                               # on retire la moyenne locale (≈ 0,5 s)
    flux = np.maximum(0.0, flux - np.convolve(flux, np.ones(k) / k, mode="same"))
    return flux / (flux.std() + 1e-9), sr / hop


def tempo(env, fps, bpm_min=60, bpm_max=180, centre=120):
    """Période (en trames) la plus probable, avec une préférence douce autour de 120 BPM."""
    env = env - env.mean()
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    lags = np.arange(max(1, int(fps * 60 / bpm_max)), int(fps * 60 / bpm_min) + 1)
    lags = lags[lags < len(ac)]
    if not len(lags):
        return fps * 0.5
    bpm = 60 * fps / lags
    poids = np.exp(-0.5 * (np.log2(bpm / centre) / 0.9) ** 2)
    return float(lags[np.argmax(ac[lags] * poids)])


def suivre(env, periode, serre=100.0):
    """Suivi des temps par programmation dynamique : temps réguliers qui tombent sur les attaques."""
    n = len(env)
    score, prec = env.astype(float).copy(), -np.ones(n, int)
    lo, hi = int(round(-2 * periode)), int(round(-periode / 2))
    decal = np.arange(lo, hi + 1)
    cout = -serre * np.log(-decal / periode) ** 2
    for i in range(n):
        j = i + decal
        ok = j >= 0
        if not ok.any():
            continue
        cand = score[j[ok]] + cout[ok]
        m = int(np.argmax(cand))
        score[i] = env[i] + cand[m]
        prec[i] = j[ok][m]
    # dernier temps : le meilleur score parmi la fin (dans la dernière période)
    fin = int(np.argmax(score[max(0, n - int(periode) - 1):])) + max(0, n - int(periode) - 1)
    temps = [fin]
    while prec[temps[-1]] >= 0:
        temps.append(prec[temps[-1]])
    return np.array(temps[::-1])


def temps_forts(fichier):
    """(tempo en BPM, liste des temps en secondes depuis le début du morceau). Mis en cache."""
    cle = (fichier, os.path.getmtime(fichier) if os.path.exists(fichier) else 0)
    if cle in _cache:
        return _cache[cle]
    try:
        import librosa
        y, sr = librosa.load(fichier, sr=22050, mono=True, duration=600)
        bpm, cadres = librosa.beat.beat_track(y=y, sr=sr, units="time")
        res = (float(np.atleast_1d(bpm)[0]), [round(float(t), 3) for t in cadres])
    except Exception:
        y = _audio(fichier)
        env, fps = enveloppe_attaques(y)
        if env.max() <= 0:
            res = (0.0, [])
        else:
            per = tempo(env, fps)
            cadres = suivre(env, per)
            res = (round(60 * fps / per, 1), [round(float(c) / fps + 512 / SR, 3) for c in cadres])
    _cache[cle] = res
    return res


def _proche(temps, t, marge):
    if not len(temps):
        return None
    i = int(np.argmin(np.abs(np.asarray(temps) - t)))
    return temps[i] if abs(temps[i] - t) <= marge else None


def caler(proj, temps_musique=None, duree_min=0.6, marge=0.4):
    """Cale le projet sur les temps forts de sa musique. Renvoie le nombre d'éléments déplacés."""
    mus = proj.get("musique") or {}
    if not mus.get("fichier"):
        return 0
    if temps_musique is None:
        bpm, temps_musique = temps_forts(mus["fichier"])
        mus["tempo"] = bpm
    mus["temps_forts"] = list(temps_musique)
    if not temps_musique:
        return 0
    # 1) la musique démarre sur un temps fort (le plus proche du départ choisi)
    dec = float(mus.get("decalage", 0.0))
    dec2 = min(temps_musique, key=lambda b: abs(b - dec))
    mus["decalage"] = round(max(0.0, dec2), 3)
    temps = [b - mus["decalage"] for b in temps_musique if b - mus["decalage"] >= 0]
    bouge = 0

    # 2) changements de cadrage dans une même prise → sur le temps le plus proche
    clips = proj.get("clips") or []
    o = 0.0
    for i, c in enumerate(clips):
        o += c["b"] - c["a"]
        if i + 1 >= len(clips):
            break
        n = clips[i + 1]
        if abs(n["a"] - c["b"]) > 1e-3:
            continue
        cible = _proche(temps, o, marge)
        if cible is None:
            continue
        d = cible - o
        if abs(d) < 0.02 or c["b"] + d - c["a"] < duree_min or n["b"] - (n["a"] + d) < duree_min:
            continue
        c["b"] = n["a"] = round(c["b"] + d, 3)
        o += d
        bouge += 1

    # 3) écrans de couleur : ils commencent sur un temps
    def sortie(s):
        oo = 0.0
        for c in clips:
            if c["a"] <= s < c["b"]:
                return oo + s - c["a"], c
            oo += c["b"] - c["a"]
        return None, None
    for e in proj.get("ecrans") or []:
        so, c = sortie(float(e["deb"]))
        if so is None:
            continue
        cible = _proche(temps, so, 0.3)
        if cible is None:
            continue
        nd = float(e["deb"]) + (cible - so)
        if c["a"] <= nd < c["b"] and nd < float(e["fin"]) - 0.4 and abs(cible - so) >= 0.02:
            e["deb"] = round(nd, 3)
            bouge += 1
    return bouge
