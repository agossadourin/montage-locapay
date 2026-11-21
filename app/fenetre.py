"""Lance le montage automatique dans sa propre fenêtre.

1. Si Google Chrome (ou Edge, Brave) est installé : fenêtre « application » dédiée (sans barre d'adresse),
   avec un profil séparé — lecture vidéo fiable, idéale pour l'éditeur (timeline).
2. Sinon : fenêtre native pywebview (WebKit).
"""
import os
import subprocess
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)
sys.path.insert(0, ICI)
NOM = "Montage Locapay"

NAVIGATEURS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
]

CHARGEMENT = """<html><body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
background:#2E2C51;color:#fff;font-family:-apple-system,Helvetica,sans-serif">
<div style="text-align:center"><div style="font-size:26px;font-weight:600">Montage Locapay</div>
<div style="opacity:.7;margin-top:10px">Démarrage…</div></div></body></html>"""


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
    profil = os.path.join(os.path.expanduser("~"), "Library", "Application Support", NOM, "navigateur")
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
    binaire = navigateur_app() if os.environ.get("MONTAGE_FENETRE") != "webkit" else None
    if binaire:
        avec_chrome(binaire)
    else:
        avec_pywebview()


if __name__ == "__main__":
    main()
