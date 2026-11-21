"""Lance le montage automatique dans une fenêtre Mac native (pywebview / WebKit), sans navigateur."""
import os
import socket
import sys
import time
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)
sys.path.insert(0, ICI)
NOM = "Montage Locapay"

CHARGEMENT = """<html><body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
background:#2E2C51;color:#fff;font-family:-apple-system,Helvetica,sans-serif">
<div style="text-align:center"><div style="font-size:26px;font-weight:600">Montage Locapay</div>
<div style="opacity:.7;margin-top:10px">Démarrage…</div></div></body></html>"""


def port_libre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


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


def main():
    habiller_app_mac()
    import webview

    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
    except Exception:
        pass

    port = port_libre()
    url = f"http://127.0.0.1:{port}/"
    fenetre = webview.create_window(NOM, html=CHARGEMENT, width=1280, height=900, min_size=(900, 640))

    def demarrer_serveur():
        import interface as I
        fenetre.title = f"{NOM} {I.VERSION}"
        I.lancer(port=port, navigateur=False, bloquant=False)
        for _ in range(200):  # attend que le serveur réponde (≤ 20 s)
            try:
                urllib.request.urlopen(url, timeout=1)
                break
            except Exception:
                time.sleep(0.1)
        fenetre.load_url(url)

    webview.start(demarrer_serveur)
    os._exit(0)  # ferme aussi le serveur quand on ferme la fenêtre


if __name__ == "__main__":
    main()
