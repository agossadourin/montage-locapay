"""Lance le montage automatique dans sa propre fenêtre.

1. Si Google Chrome (ou Edge, Brave) est installé : fenêtre « application » dédiée (sans barre d'adresse),
   avec un profil séparé — lecture vidéo fiable, idéale pour l'éditeur (timeline). Sur Windows, Edge est
   toujours présent.
2. Sinon : fenêtre native pywebview (WebKit) sur Mac, ou le navigateur par défaut.
"""
import os
import subprocess
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)
sys.path.insert(0, ICI)
import chemins  # noqa: E402

NOM = chemins.NOM_APP

_PF = [os.environ.get(v, "") for v in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
NAVIGATEURS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
] + [os.path.join(p, *s) for s in (("Google", "Chrome", "Application", "chrome.exe"),
                                   ("Microsoft", "Edge", "Application", "msedge.exe"),
                                   ("BraveSoftware", "Brave-Browser", "Application", "brave.exe")) for p in _PF if p]


def dossier_donnees():
    """Données propres à l'app (profil de la fenêtre, journal) : Library/Application Support ou %LOCALAPPDATA%."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.path.join(os.path.expanduser("~"), ".local", "share")
    d = os.path.join(base, NOM)
    os.makedirs(d, exist_ok=True)
    return d


def journal_si_sans_console():
    """Lancée sans console (pythonw sous Windows) : la sortie va dans un fichier journal."""
    if sys.stdout is None or sys.stderr is None:
        f = open(os.path.join(dossier_donnees(), f"{NOM}.log"), "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or f
        sys.stderr = sys.stderr or f

CHARGEMENT = """<html><body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
background:#202029;color:#f1f0f6;font-family:-apple-system,Helvetica,sans-serif">
<div style="text-align:center"><div style="font-size:30px;font-weight:600;font-style:italic;font-family:Georgia,serif">Raccord</div>
<div style="opacity:.6;margin-top:10px">Démarrage…</div></div></body></html>"""


def navigateur_app():
    return next((n for n in NAVIGATEURS if os.path.exists(n)), None)


def habiller_app_mac():
    """Nom et icône dans le Dock et la barre de menus (sinon macOS affiche « Python »)."""
    if sys.platform != "darwin":
        return
    try:
        from Foundation import NSBundle
        info = NSBundle.mainBundle().localizedInfoDictionary() or NSBundle.mainBundle().infoDictionary()
        info["CFBundleName"] = NOM
    except Exception:
        pass
    try:
        from AppKit import NSApplication, NSImage
        icone = os.path.join(RACINE, "macos", "AppIcon.png")
        if os.path.exists(icone):
            NSApplication.sharedApplication().setApplicationIconImage_(
                NSImage.alloc().initWithContentsOfFile_(icone))
    except Exception:
        pass


def avec_chrome(binaire):
    import interface as I
    url = I.lancer(navigateur=False, bloquant=False) + "editeur"     # on démarre sur la timeline
    profil = os.path.join(dossier_donnees(), "navigateur")
    os.makedirs(profil, exist_ok=True)
    proc = subprocess.Popen([binaire, f"--app={url}", f"--user-data-dir={profil}", "--window-size=1440,960",
                             "--no-first-run", "--no-default-browser-check", "--disable-features=Translate"])
    proc.wait()          # la fenêtre est fermée : on arrête tout
    os._exit(0)


def avec_pywebview():
    habiller_app_mac()
    import webview
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
    except Exception:
        pass
    fenetre = webview.create_window(NOM, html=CHARGEMENT, width=1440, height=960, min_size=(900, 640))

    def demarrer():
        import interface as I
        fenetre.title = f"{NOM} {I.VERSION}"
        fenetre.load_url(I.lancer(navigateur=False, bloquant=False) + "editeur")

    webview.start(demarrer)
    os._exit(0)


def main():
    journal_si_sans_console()
    binaire = navigateur_app() if os.environ.get("MONTAGE_FENETRE") != "webkit" else None
    if binaire:
        avec_chrome(binaire)
    elif sys.platform == "darwin":
        avec_pywebview()
    else:                                    # pas de navigateur reconnu : navigateur par défaut
        import interface as I
        I.lancer(navigateur=True, bloquant=True)


if __name__ == "__main__":
    main()
