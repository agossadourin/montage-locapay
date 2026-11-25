"""Vérifie une installation Windows de Raccord (utilisé par GitHub Actions après l'installation réelle).

python -X utf8 windows/verifier.py [dossier_installe]
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

RACINE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(RACINE, "app"))
os.chdir(RACINE)


def etape(nom):
    print(f"-- {nom}", flush=True)


etape("ffmpeg embarqué")
import interface as I                                      # noqa: E402  (ajoute outils\ffmpeg\bin au PATH)
ff = shutil.which("ffmpeg")
assert ff and os.path.join("outils", "ffmpeg") in ff, ff
print("  ", ff)

etape("fenêtre : navigateur trouvé")
import fenetre                                             # noqa: E402
nav = fenetre.navigateur_app()
assert nav, "ni Edge ni Chrome trouvés"
print("  ", nav)

etape("dossier des vidéos")
import chemins                                             # noqa: E402
print("  ", chemins.DOSSIER_APP)
assert os.path.isdir(chemins.DOSSIER_APP)

etape("serveur et pages")
url = I.lancer(navigateur=False, bloquant=False)
for page in ("", "editeur", "visuels", "visuels/api/etat", "editeur/icone.png",
             "editeur/polices/poppins/Poppins-Bold.ttf"):
    with urllib.request.urlopen(url + page, timeout=60) as r:
        assert r.status == 200, (page, r.status)
        print(f"   /{page} : {r.status} ({len(r.read())} octets)")

etape("transcription (faster-whisper, petit modèle)")
with tempfile.TemporaryDirectory() as d:
    wav = os.path.join(d, "son.wav")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", wav], check=True)
    from faster_whisper import WhisperModel
    t = time.time()
    segments, info = WhisperModel("tiny", device="cpu", compute_type="int8").transcribe(wav, language="fr")
    list(segments)
    print(f"   ok en {time.time() - t:.1f} s")

etape("détourage (facultatif)")
try:
    import rembg                                           # noqa: F401
    print("   rembg disponible")
except Exception as e:                                     # noqa: BLE001
    print("   absent :", e)

print("Installation Windows vérifiée.", flush=True)
os._exit(0)
