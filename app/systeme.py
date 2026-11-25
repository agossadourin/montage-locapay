"""Ce qui dépend du système (Mac, Windows, Linux) : ouvrir un fichier, montrer un dossier, jouer un son.

Le reste de Raccord est identique partout.
"""
import os
import subprocess
import sys

MAC = sys.platform == "darwin"
WINDOWS = sys.platform == "win32"
LECTURE_DIRECTE = MAC or WINDOWS          # le son d'un passage se joue sans lecteur dans la page
NOM_LECTEUR = "QuickTime" if MAC else "le lecteur vidéo" if WINDOWS else "le lecteur"
NOM_EXPLORATEUR = "Finder" if MAC else "l'Explorateur" if WINDOWS else "le gestionnaire de fichiers"


def sans_fenetres_console():
    """Windows : ffmpeg & co. ne doivent pas ouvrir une fenêtre noire à chaque appel quand l'app tourne sans console."""
    if not WINDOWS or getattr(subprocess.Popen, "_raccord", False):
        return
    base = subprocess.Popen

    class PopenSansConsole(base):
        _raccord = True

        def __init__(self, *a, **k):
            k.setdefault("creationflags", 0x08000000)            # CREATE_NO_WINDOW
            super().__init__(*a, **k)

    subprocess.Popen = PopenSansConsole


sans_fenetres_console()


def ouvrir_fichier(chemin):
    """Ouvre le fichier avec l'application par défaut (QuickTime sur Mac, Films et TV / VLC sur Windows)."""
    if MAC:
        subprocess.Popen(["open", "-a", "QuickTime Player", chemin])
    elif WINDOWS:
        os.startfile(chemin)                                       # noqa: S606 (fichier local de l'utilisateur)
    else:
        subprocess.Popen(["xdg-open", chemin])


def montrer(chemin):
    """Montre le fichier sélectionné dans son dossier (Finder / Explorateur)."""
    if MAC:
        subprocess.Popen(["open", "-R", chemin])
    elif WINDOWS:
        subprocess.Popen(["explorer", "/select,", os.path.normpath(chemin)])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(chemin)])


def ouvrir_dossier(dossier):
    if MAC:
        subprocess.Popen(["open", dossier])
    elif WINDOWS:
        os.startfile(dossier)                                      # noqa: S606
    else:
        subprocess.Popen(["xdg-open", dossier])


_son = {"proc": None}


def jouer_wav(fichier):
    """Joue un .wav tout de suite (sans bloquer). Renvoie False si le système ne sait pas le faire."""
    arreter_son()
    if MAC:
        _son["proc"] = subprocess.Popen(["afplay", fichier])
        return True
    if WINDOWS:
        import winsound
        winsound.PlaySound(fichier, winsound.SND_FILENAME | winsound.SND_ASYNC)
        return True
    return False


def arreter_son():
    p = _son.get("proc")
    if p and p.poll() is None:
        p.terminate()
    _son["proc"] = None
    if WINDOWS:
        import winsound
        winsound.PlaySound(None, 0)
