"""Tests du moteur de montage (sans transcription ni interface).

Lancer :  python -m pytest -q
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "app"))
import montage_auto as M  # noqa: E402

MOTS = json.load(open(os.path.join(os.path.dirname(__file__), "mock_words.json"), encoding="utf-8"))


def test_corrections():
    mots = [{"w": "Locapé,", "s": 0, "e": 0.3}, {"w": "super", "s": 0.4, "e": 0.6}]
    out = M.appliquer_corrections(mots, "locapé=Locapay; x=y")
    assert out[0]["w"] == "Locapay,"
    assert out[1]["w"] == "super"


def test_plan_coupe_les_blancs_et_hesitations():
    plan = M.construire_plan(MOTS, 19.06, M.Reglages())
    assert plan["corps"] < 19.06 - 3          # les blancs sont coupés
    textes = [w["w"] for g in plan["groupes"] for w in g["mots"]]
    assert "Euh" not in textes                 # hésitation supprimée
    assert len(textes) == len(MOTS) - 1


def test_plan_ecrans_et_mots_cles():
    plan = M.construire_plan(MOTS, 19.06, M.Reglages(nb_ecrans_couleur=2))
    ecrans = [g for g in plan["groupes"] if g["ecran"] is not None]
    assert len(ecrans) == 2
    cles = {g["mots"][g["cle"]]["w"].strip(",.").lower() for g in plan["groupes"] if g["cle"] is not None}
    assert {"respecter", "démarcheurs", "véridiques", "professionnels"} <= cles


def test_groupes_ne_finissent_pas_sur_un_petit_mot():
    plan = M.construire_plan(MOTS, 19.06, M.Reglages())
    for g in plan["groupes"][:-1]:
        dernier = M.norm(g["mots"][-1]["w"])
        assert not (dernier in M.FAIBLES and len(g["mots"]) > 1), [w["w"] for w in g["mots"]]


def test_plans_contigus_et_zooms_alternes():
    plan = M.construire_plan(MOTS, 19.06, M.Reglages())
    p = plan["plans"]
    for a, b in zip(p, p[1:]):
        assert abs(b["o"] - (a["o"] + a["b"] - a["a"])) < 1e-9
        assert a["zoom"] != b["zoom"]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_rendu_complet(tmp_path):
    """Rendu d'une vraie vidéo à partir d'un clip synthétique (mire + voix simulée)."""
    src = tmp_path / "brut.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=30:d=6",
                    "-f", "lavfi", "-i", "sine=frequency=220:duration=6", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", "-shortest", str(src)], check=True)
    mots = [{"w": w, "s": s, "e": s + 0.3} for w, s in
            [("Bonjour", 0.3), ("à", 0.7), ("tous,", 0.9), ("bienvenue", 2.4), ("chez", 2.8), ("Locapay.", 3.1)]]
    R = M.Reglages(fichier_logo=os.path.join(RACINE, "macos", "AppIcon.png"), duree_fin=0.5,
                   police_serif=os.path.join(RACINE, "app", "polices", "serif.ttf"),
                   police_grasse=os.path.join(RACINE, "app", "polices", "gras.ttf"))
    plan = M.construire_plan(mots, M.duree_video(str(src)), R)
    out = tmp_path / "monte.mp4"
    M.monter(str(src), plan, R, str(out), progression=False)
    M.ecrire_srt(plan, str(tmp_path / "monte.srt"))
    assert out.exists() and out.stat().st_size > 10_000
    assert abs(M.duree_video(str(out)) - plan["total"]) < 0.3
    assert "Bonjour" in (tmp_path / "monte.srt").read_text(encoding="utf-8")


def test_notebook_colab_a_jour():
    """Le moteur intégré au notebook Colab doit être identique à app/montage_auto.py."""
    import base64, gzip, re
    nb = json.load(open(os.path.join(RACINE, "colab", "Raccord.ipynb"), encoding="utf-8"))
    code = "".join(nb["cells"][1]["source"])
    blob = re.search(r'montage_auto\.py", "wb"\)\.write\(gzip\.decompress\(base64\.b64decode\("([^"]+)"\)\)\)', code).group(1)
    integre = gzip.decompress(base64.b64decode(blob))
    attendu = open(os.path.join(RACINE, "app", "montage_auto.py"), "rb").read()
    assert integre == attendu, "Notebook Colab pas à jour : lancez  python colab/build_nb.py"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_premontage(tmp_path):
    """Deux clips (paysage sans son, portrait avec son) coupés puis assemblés en 1080x1920."""
    a, b = tmp_path / "a.mp4", tmp_path / "b.mov"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25:d=5",
                    "-c:v", "libx264", "-preset", "ultrafast", str(a)], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=720x1280:rate=30:d=4",
                    "-f", "lavfi", "-i", "sine=frequency=330:duration=4", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", "-shortest", str(b)], check=True)
    out = tmp_path / "pre.mp4"
    M.premontage([(str(b), 0.5, 3.0), (str(a), 1.0, None)], str(out))
    assert abs(M.duree_video(str(out)) - (2.5 + 4.0)) < 0.25
    assert M.a_du_son(str(out))
    w, h = M._taille_affichee(str(out))
    assert (w, h) == (1080, 1920)


def _mots(phrase, debut, p=0.9, pas=0.3):
    return [{"w": w, "s": round(debut + k * pas, 2), "e": round(debut + k * pas + 0.25, 2), "p": p}
            for k, w in enumerate(phrase.split())]


MOTS_VALIDATION = (
    _mots("Bonjour à tous, je suis Guérin.", 0.5)
    + _mots("Locapay vous aide à payer votre loyer", 3.0)          # 1re prise
    + _mots("Locapay vous aide à payer votre loyer simplement.", 6.0)  # reprise
    + _mots("Mi kú dé wá xwé", 10.0, p=0.2)                        # passage en fon, mal compris
    + _mots("Merci et à bientôt.", 13.0)
)


def test_analyse_signale_reprise_et_passage_incompris():
    ph = M.analyser(MOTS_VALIDATION)
    assert [p["garder"] for p in ph] == [True, False, True, False, True]
    assert "reprise" in ph[1]["alertes"][0] or "faux départ" in ph[1]["alertes"][0]
    assert "incompris" in ph[3]["alertes"][0]
    assert ph[3]["st"] is False


def test_validation_traduction_et_sans_sous_titres():
    ph = M.analyser(MOTS_VALIDATION)
    lignes = M.lignes_validation(ph)
    lignes[3][6] = True                                          # garder le passage en fon…
    lignes[3][3] = "Bienvenue à la maison"                        # …avec sa traduction en sous-titres
    lignes[3][7] = True
    lignes[0][7] = False                                          # 1re phrase : sans sous-titres
    mots = M.appliquer_validation(MOTS_VALIDATION, ph, lignes)
    textes = [m["w"] for m in mots if m.get("st", True)]
    assert "Bienvenue" in textes and "Mi" not in textes and "Bonjour" not in textes
    assert textes.count("Locapay") == 1                            # la 1re prise est supprimée
    plan = M.construire_plan(mots, 16.0, M.Reglages(nb_ecrans_couleur=0))
    sous_titres = " ".join(w["w"] for g in plan["groupes"] for w in g["mots"])
    assert "Bonjour" not in sous_titres and "Bienvenue" in sous_titres
    assert plan["zones"][0]["a"] < 0.5                            # l'audio de la 1re phrase est gardé
    assert plan["corps"] < 16.0 - 2.5                              # la prise ratée est coupée


def test_corrections_ciblees_et_globales():
    mots = _mots("Bienvenue chez Loca pay, Loca pay simplifie le loyer.", 0.0)
    # « Loca pay » (mots 2-3) corrigé seulement à ce moment-là, puis « le loyer » partout
    corr = [{"portee": "moment", "i": 2, "j": 3, "avant": "Loca pay,", "apres": "Locapay"},
            {"portee": "video", "avant": "le loyer", "apres": "votre loyer"}]
    out = M.corriger(mots, corr)
    textes = [m["w"] for m in out]
    assert textes[:3] == ["Bienvenue", "chez", "Locapay,"]          # ponctuation conservée
    assert textes[3:5] == ["Loca", "pay"]                          # l'autre occurrence n'est pas touchée
    assert textes[-2:] == ["votre", "loyer."]
    assert out[2]["s"] == mots[2]["s"] and out[2]["e"] <= mots[3]["e"]  # même moment
    # correction globale multi-mots + suppression (remplacement vide)
    out2 = M.corriger(mots, [{"portee": "toujours", "avant": "loca pay", "apres": "Locapay"},
                             {"portee": "video", "avant": "Bienvenue", "apres": ""}])
    assert [m["w"] for m in out2][:3] == ["chez", "Locapay,", "Locapay"]


# ---------------------------------------------------------------- v0.6 : style, illustrations, IA
sys.path.insert(0, os.path.join(RACINE, "app"))
import illustrations as I  # noqa: E402
import ia  # noqa: E402
import configuration as C  # noqa: E402


def test_moments_a_illustrer_mots_cles():
    mots = (_mots("Bonjour à tous, aujourd'hui on parle du loyer.", 0.0)
            + _mots("Avec Locapay vous payez depuis votre téléphone en toute sécurité.", 4.0)
            + _mots("Plus besoin de courir après le propriétaire avec de l'argent.", 9.0)
            + _mots("Merci et à bientôt.", 14.0))
    props = I.choisir_moments(mots, 16.0, par_minute=12)
    requetes = [p["requete"] for p in props]
    assert props and all(props[i + 1]["deb"] >= props[i]["fin"] for i in range(len(props) - 1))
    assert any("smartphone" in r or "rent" in r or "money" in r for r in requetes)
    assert all(p["deb"] >= 1.0 for p in props)


def test_recherche_pexels_simulee():
    import httpx

    def reponse(req):
        if "videos/search" in str(req.url):
            return httpx.Response(200, json={"videos": [{"id": 1, "image": "https://x/t.jpg", "user": {"name": "A"},
                                                         "video_files": [{"link": "https://x/v.mp4", "height": 1920},
                                                                         {"link": "https://x/s.mp4", "height": 360}]}]})
        return httpx.Response(200, json={"photos": [{"id": 2, "photographer": "B",
                                                     "src": {"portrait": "https://x/p.jpg", "medium": "https://x/m.jpg"}}]})
    client = httpx.Client(transport=httpx.MockTransport(reponse))
    res = I.rechercher("money", {"pexels": "cle"}, client=client)
    assert [r["type"] for r in res] == ["video", "image"]
    assert res[0]["url"] == "https://x/v.mp4"          # la plus petite définition HD (≥ 720 px)


def test_ia_reponse_json_simulee():
    import httpx
    texte = 'Voici :\n```json\n[{"deb": 3.0, "fin": 5.0, "mot": "loyer", "requete": "paying rent"}]\n```'
    client = httpx.Client(transport=httpx.MockTransport(
        lambda req: httpx.Response(200, json={"content": [{"type": "text", "text": texte}]})))
    assert ia.demander_json("cle", "?", client=client)[0]["requete"] == "paying rent"


def test_profil_de_style_et_identite(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "DOSSIER_STYLES", str(tmp_path))
    p = C.ProfilStyle(position_sous_titres=0.5, mots_par_groupe=2, casse="majuscules", animation="fondu")
    C.sauver_style("Mon style", p)
    assert "Mon style" in C.lister_styles()
    q = C.charger_style("Mon style")
    R = C.reglages(M, {"couleur_1": "#112233"}, q, volume_musique=0.3)
    assert (R.position_sous_titres, R.mots_par_groupe, R.casse, R.animation, R.couleur_1, R.volume_musique) == \
        (0.5, 2, "majuscules", "fondu", "#112233", 0.3)
    plan = M.construire_plan(MOTS, 19.06, R)
    assert max(len(g["mots"]) for g in plan["groupes"]) <= 2


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_rendu_avec_illustrations_et_style(tmp_path):
    src = tmp_path / "brut.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:size=720x1280:rate=30:d=6",
                    "-f", "lavfi", "-i", "sine=frequency=220:duration=6", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", "-shortest", str(src)], check=True)
    img = tmp_path / "photo.jpg"
    from PIL import Image as Img
    Img.new("RGB", (1200, 800), (200, 30, 30)).save(img)
    vid = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:size=1280x720:rate=25:d=3",
                    "-c:v", "libx264", "-preset", "ultrafast", str(vid)], check=True)
    mots = [{"w": w, "s": s, "e": s + 0.3} for w, s in
            [("Le", 0.3), ("loyer", 0.6), ("se", 0.9), ("paie", 1.2), ("ici", 1.5), ("avec", 2.6), ("Locapay", 2.9),
             ("et", 3.8), ("votre", 4.1), ("téléphone", 4.4)]]
    R = M.Reglages(nb_ecrans_couleur=0, duree_fin=0.5, style_etalonnage="froid", animation="fondu", casse="majuscules",
                   illustrations=[{"deb": 0.6, "fin": 1.6, "fichier": str(img)},
                                  {"deb": 4.0, "fin": 5.0, "fichier": str(vid)}])
    plan = M.construire_plan(mots, 6.0, R)
    out = tmp_path / "monte.mp4"
    M.monter(str(src), plan, R, str(out), progression=False)
    def pixel(t):
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t}", "-i", str(out), "-frames:v", "1",
                            "-vf", "crop=10:10:535:955,scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           capture_output=True)       # centre de l'image (les médias en paysage sont sur fond flou)
        return tuple(r.stdout)
    o_img, o_vid = M.src2out(plan, 1.0), M.src2out(plan, 4.6)
    assert pixel(o_img)[0] > 150 and pixel(o_img)[2] < 90      # photo rouge à l'écran
    assert pixel(o_vid)[2] > 150 and pixel(o_vid)[0] < 90      # vidéo bleue à l'écran


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_analyse_de_style_reference(tmp_path):
    import analyse_style as A
    ref = tmp_path / "ref.mp4"
    filtre = ("[0][1][2][3]concat=n=4:v=1:a=0[v]")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=25:d=2",
                    "-f", "lavfi", "-i", "color=c=0x2E2C51:size=360x640:rate=25:d=1",
                    "-f", "lavfi", "-i", "mandelbrot=size=360x640:rate=25,trim=duration=2",
                    "-f", "lavfi", "-i", "color=c=0x0AC2A4:size=360x640:rate=25:d=1.5",
                    "-filter_complex", filtre, "-map", "[v]", "-c:v", "libx264", "-preset", "ultrafast",
                    str(ref)], check=True)
    p, rapport = A.analyser(str(ref), ocr=False)
    assert p.ecran_fin is True
    assert p.nb_ecrans_couleur == 1
    assert 0.8 <= p.duree_plan_max <= 3.0


# ---------------------------------------------------------------- v0.7 : projet éditable (timeline)
import projet as P  # noqa: E402


def test_projet_aller_retour():
    R = M.Reglages(nb_ecrans_couleur=2)
    plan = M.construire_plan(MOTS, 19.06, R)
    import unittest.mock as um
    with um.patch.object(M, "duree_video", return_value=19.06):
        proj = P.creer("/x/brut.mp4", plan, R)
    assert len(proj["clips"]) == len(plan["plans"]) and len(proj["ecrans"]) == 2
    plan2, R2 = P.vers_plan(json.loads(json.dumps(proj)))          # passe par du JSON, comme l'éditeur
    assert abs(plan2["corps"] - plan["corps"]) < 1e-6
    assert [g["cle"] for g in plan2["groupes"]] == [g["cle"] for g in plan["groupes"]]
    assert sum(1 for g in plan2["groupes"] if g["ecran"] is not None) == 2
    # éditions : supprimer un plan, couper un autre en deux
    proj["clips"].pop(1)
    c = proj["clips"][0]; milieu = (c["a"] + c["b"]) / 2
    proj["clips"][0:1] = [dict(c, b=milieu), dict(c, id="x", a=milieu)]
    plan3, _ = P.vers_plan(proj)
    assert abs(plan3["corps"] - (plan["corps"] - (plan["plans"][1]["b"] - plan["plans"][1]["a"]))) < 1e-6


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_rendu_projet_plans_inverses(tmp_path):
    """Plans remis dans le désordre (la source doit être relue en arrière) + écran ajouté + musique décalée."""
    src = tmp_path / "brut.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=30:d=6",
                    "-f", "lavfi", "-i", "sine=frequency=220:duration=6", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", "-shortest", str(src)], check=True)
    mus = tmp_path / "m.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=20", str(mus)],
                   check=True)
    proj = {"version": 1, "video": str(src), "duree_source": 6.0,
            "clips": [{"id": "1", "a": 4.0, "b": 5.5, "zoom": 1.0}, {"id": "2", "a": 0.5, "b": 2.0, "zoom": 1.15}],
            "sous_titres": [{"id": "s", "deb": 4.1, "fin": 5.4, "mots": [{"w": "Bonjour", "t": 4.1},
                                                                          {"w": "Locapay", "t": 4.6}], "cle": 1}],
            "ecrans": [{"id": "e", "deb": 1.0, "fin": 1.6, "couleur": "#2E2C51"}],
            "illustrations": [], "musique": {"fichier": str(mus), "volume": 0.2, "decalage": 5.0},
            "reglages": {"duree_fin": 0.5, "nb_ecrans_couleur": 0}}
    out = tmp_path / "edit.mp4"
    P.rendre(proj, str(out))
    assert abs(M.duree_video(str(out)) - 3.5) < 0.25
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", "2.0", "-i", str(out), "-frames:v", "1",
                        "-vf", "crop=10:10:20:20,scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True)
    assert tuple(r.stdout) == (0x2E, 0x2C, 0x51) or abs(r.stdout[2] - 0x51) < 12   # écran bleu nuit à 2,0 s


def test_serveur_editeur(tmp_path):
    """Routes de l'éditeur : page, projet (lecture/écriture), média en lecture partielle, export."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import editeur as E
    src = tmp_path / "brut.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=30:d=3",
                    "-f", "lavfi", "-i", "sine=frequency=220:duration=3", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", "-shortest", str(src)], check=True)
    proj = {"version": 1, "video": str(src), "duree_source": 3.0,
            "clips": [{"id": "1", "a": 0.2, "b": 2.0, "zoom": 1.0}], "sous_titres": [], "ecrans": [],
            "illustrations": [], "musique": None, "reglages": {"duree_fin": 0.3}}
    chemin = tmp_path / "essai.projet.json"
    P.sauver(proj, str(chemin))
    E.SORTIES = str(tmp_path)
    api = FastAPI(); E.ajouter_routes(api, [str(tmp_path)])
    c = TestClient(api)
    assert "timeline" in c.get("/editeur").text.lower() or c.get("/editeur").status_code == 200
    assert c.get("/editeur/api/projet", params={"p": str(chemin)}).json()["projet"]["clips"][0]["b"] == 2.0
    proj["clips"][0]["b"] = 1.5
    assert c.put("/editeur/api/projet", params={"p": str(chemin)}, json=proj).json()["ok"]
    assert P.charger(str(chemin))["clips"][0]["b"] == 1.5
    r = c.get("/editeur/media", params={"f": str(src)}, headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100
    assert c.get("/editeur/media", params={"f": "/etc/passwd"}).status_code == 404
    assert c.get("/editeur/api/projet", params={"p": "/etc/passwd"}).status_code == 403
    assert len(c.get("/editeur/api/onde", params={"f": str(src)}).json()["pics"]) > 10
    job = c.post("/editeur/api/exporter", params={"p": str(chemin)}, json=proj).json()["job"]
    import time as _t
    for _ in range(120):
        e = c.get("/editeur/api/etat", params={"job": job}).json()
        if e["fini"]:
            break
        _t.sleep(0.5)
    assert e["erreur"] is None and abs(M.duree_video(e["sortie"]) - 1.6) < 0.25


# ---------------------------------------------------------------- v0.8 : démarrer par la timeline
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_nouveau_projet_et_montage_auto(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "DOSSIER_SOURCES", str(tmp_path / ".sources"))
    monkeypatch.setattr(P, "DOSSIER_PROJETS", str(tmp_path))
    monkeypatch.setattr(C, "FICHIER", str(tmp_path / "config.json"))
    monkeypatch.setattr(C, "DOSSIER_STYLES", str(tmp_path / "styles"))
    rushs = []
    for k, (taille, d) in enumerate([("720x1280", 8), ("1280x720", 6)]):
        f = tmp_path / f"rush{k}.mp4"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={taille}:rate=30:d={d}",
                        "-f", "lavfi", "-i", f"sine=frequency=300:duration={d}", "-c:v", "libx264", "-preset",
                        "ultrafast", "-c:a", "aac", "-shortest", str(f)], check=True)
        rushs.append(str(f))
    chemin = P.nouveau(rushs, nom="essai")
    proj = P.charger(chemin)
    assert [round(c["b"] - c["a"]) for c in proj["clips"]] == [8, 6]
    assert abs(proj["duree_source"] - 14) < 0.3

    # transcription simulée : une reprise, un passage incompris (fon), des blancs
    mots = (_mots("Bonjour je suis Guérin", 0.5) + _mots("Locapay vous aide à payer", 2.5)
            + _mots("Locapay vous aide à payer le loyer.", 4.6) + _mots("Mi kú dé wá", 9.0, p=0.15)
            + _mots("Merci à tous et à bientôt.", 11.5))
    proj["clips"][1]["b"] = 13.9
    auto = P.auto(proj, transcrire=lambda *a, **k: mots, rechercher=lambda *a, **k: [], telecharger=None)
    types = sorted(a["type"] for a in auto["alertes"])
    assert types == ["incompris", "reprise"]
    textes = " ".join(w["w"] for s in auto["sous_titres"] for w in s["mots"])
    assert "Mi" not in textes and "Bonjour" in textes and textes.count("Locapay") == 2   # rien n'est coupé d'office
    duree_avant = sum(c["b"] - c["a"] for c in proj["clips"])
    duree_apres = sum(c["b"] - c["a"] for c in auto["clips"])
    assert duree_apres < duree_avant - 2                                                  # blancs coupés
    fon = next(a for a in auto["alertes"] if a["type"] == "incompris")
    assert any(c["a"] <= fon["deb"] + 0.2 < c["b"] for c in auto["clips"])                # passage fon gardé
    assert auto["transcription"] and P.auto(auto, transcrire=lambda *a, **k: 1 / 0, rechercher=lambda *a, **k: [])


def test_montage_auto_passage_a_cheval_sur_deux_rushs(monkeypatch, tmp_path):
    """Un passage incompris qui chevauche la limite entre deux rushs est gardé en entier."""
    monkeypatch.setattr(C, "FICHIER", str(tmp_path / "config.json"))
    mots = _mots("Bonjour à tous je suis là", 0.5) + _mots("Mi kú dé wá xwé gbé", 4.0, p=0.1, pas=0.5) + \
        _mots("Merci à tous et à bientôt.", 8.0)
    proj = {"version": 1, "video": "/x.mp4", "duree_source": 10.0, "musique": None, "reglages": {},
            "clips": [{"id": "a", "a": 0.0, "b": 5.0, "zoom": 1.0}, {"id": "b", "a": 5.0, "b": 10.0, "zoom": 1.0}],
            "sous_titres": [], "ecrans": [], "illustrations": [], "alertes": []}
    auto = P.auto(proj, transcrire=lambda *a, **k: mots, rechercher=lambda *a, **k: [])
    fon = next(a for a in auto["alertes"] if a["type"] == "incompris")
    garde = sum(min(c["b"], fon["fin"]) - max(c["a"], fon["deb"]) for c in auto["clips"]
                if c["b"] > fon["deb"] and c["a"] < fon["fin"])
    assert garde > (fon["fin"] - fon["deb"]) - 0.1


# ---------------------------------------------------------------- v0.9 : IA locale (Ollama)
def test_ia_ollama_simulee():
    import httpx
    vus = {}

    def reponse(req):
        if req.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5vl:3b"}]})
        vus["corps"] = json.loads(req.content)
        return httpx.Response(200, json={"message": {"content": 'Voici [{"deb": 2, "fin": 4, "requete": "money"}]'}})
    client = httpx.Client(transport=httpx.MockTransport(reponse))
    cfg = {"cles": {"anthropic": ""}, "ia": {"fournisseur": "ollama"}}
    iac = ia.config_ia(cfg)
    assert iac["fournisseur"] == "ollama" and ia.nom_ia(iac).startswith("Ollama")
    from PIL import Image as Img
    res = ia.demander_json(iac, "?", images=[Img.new("RGB", (800, 600))] * 6, client=client)
    assert res[0]["requete"] == "money"
    assert vus["corps"]["keep_alive"] == 0 and len(vus["corps"]["messages"][0]["images"]) == 4
    assert ia.tester_ollama(client=client)[0] is True
    assert ia.config_ia({"cles": {"anthropic": "k"}})["fournisseur"] == "claude"     # compatibilité
    assert ia.config_ia({"cles": {}, "ia": {"fournisseur": "aucune"}}) is None


def test_musique_libre_openverse_simulee(tmp_path, monkeypatch):
    import httpx
    import musique as MU
    monkeypatch.setattr(MU, "DOSSIER", str(tmp_path))
    def reponse(req):
        if req.url.path.startswith("/v1/audio"):
            assert req.url.params["license_type"] == "commercial"
            return httpx.Response(200, json={"results": [
                {"title": "Sunny", "creator": "Ana", "license": "by", "license_version": "4.0", "url": "https://x/a.mp3",
                 "foreign_landing_url": "https://x/page", "duration": 95000},
                {"title": "Interdit", "creator": "B", "license": "by-nc", "url": "https://x/b.mp3", "duration": 90000},
                {"title": "Libre", "creator": "C", "license": "cc0", "url": "https://x/c.mp3", "duration": 60000},
                {"title": "Court", "creator": "D", "license": "cc0", "url": "https://x/d.mp3", "duration": 5000}]})
        return httpx.Response(200, content=b"ID3fake")
    client = httpx.Client(transport=httpx.MockTransport(reponse))
    res = MU.rechercher("upbeat", client=client)
    assert [r["titre"] for r in res] == ["Sunny", "Libre"]                 # pas de NC, pas de morceau trop court
    assert "Ana" in res[0]["credit"] and "CC BY" in res[0]["credit"] and res[1]["credit"] == ""
    chemin = MU.telecharger(res[0], client=client)
    assert open(chemin, "rb").read() == b"ID3fake" and chemin.endswith(".mp3")


def _pixel(video, t):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                        "-vf", "crop=40:40:520:700,scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True)
    return tuple(r.stdout[:3])


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
@pytest.mark.parametrize("transition", ["fondu", "coupe"])
def test_transition_entre_deux_plans(tmp_path, transition):
    """Saut dans la vidéo (rouge → bleu) : en fondu, l'image à la frontière mélange les deux plans."""
    src = tmp_path / "brut.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=red:size=360x640:rate=30:d=2",
                    "-f", "lavfi", "-i", "color=blue:size=360x640:rate=30:d=2", "-f", "lavfi",
                    "-i", "sine=frequency=220:duration=4", "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                    "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(src)], check=True)
    proj = {"version": 1, "video": str(src), "duree_source": 4.0,
            "clips": [{"id": "1", "a": 0.0, "b": 1.0, "zoom": 1.0}, {"id": "2", "a": 3.0, "b": 4.0, "zoom": 1.0}],
            "sous_titres": [], "ecrans": [], "illustrations": [], "musique": None,
            "reglages": {"duree_fin": 0.3, "ecran_fin": False, "logo_en_coin": False, "style_etalonnage": "naturel",
                         "transition": transition, "duree_transition": 0.3}}
    out = tmp_path / "t.mp4"
    P.rendre(proj, str(out))
    rouge, milieu, bleu = _pixel(out, 0.4), _pixel(out, 1.0), _pixel(out, 1.6)
    assert rouge[0] > 180 and rouge[2] < 60 and bleu[2] > 180 and bleu[0] < 60
    if transition == "fondu":
        assert 50 < milieu[0] < 210 and 50 < milieu[2] < 210, milieu
    else:
        assert milieu[2] > 180 and milieu[0] < 60, milieu


def test_fonctions_de_transition():
    from PIL import Image
    a = Image.new("RGBA", (M.W, M.H), (255, 0, 0, 255)); b = Image.new("RGBA", (M.W, M.H), (0, 0, 255, 255))
    for typ in M.TRANSITIONS:
        assert M.transition(a, b, 0.0, typ).getpixel((10, 10))[:3] in ((255, 0, 0), (255, 0, 0))
        assert M.transition(a, b, 1.0, typ).getpixel((M.W - 10, 10))[:3] == (0, 0, 255)
    assert M.transition(a, b, 0.5, "flash").getpixel((5, 5))[1] > 200          # pic blanc
    g = M.transition(a, b, 0.5, "glissement")
    assert g.getpixel((5, 5))[:3] == (255, 0, 0) and g.getpixel((M.W - 5, 5))[:3] == (0, 0, 255)


def test_recherche_illustrations_verticales_d_abord():
    """Pixabay renvoie surtout des vidéos en paysage : elles passent après les médias verticaux."""
    import httpx

    def reponse(req):
        u = str(req.url)
        if "pixabay.com/api/videos" in u:
            return httpx.Response(200, json={"hits": [
                {"id": 1, "user": "L", "videos": {"medium": {"url": "https://x/paysage.mp4", "width": 1920, "height": 1080}}},
                {"id": 2, "user": "P", "videos": {"medium": {"url": "https://x/portrait.mp4", "width": 1080, "height": 1920}}}]})
        return httpx.Response(200, json={"hits": [{"id": 3, "user": "I", "largeImageURL": "https://x/i.jpg",
                                                   "imageWidth": 1280, "imageHeight": 1920}]})
    res = I.rechercher("house", {"pixabay": "cle"}, client=httpx.Client(transport=httpx.MockTransport(reponse)))
    assert [r["url"] for r in res] == ["https://x/portrait.mp4", "https://x/i.jpg", "https://x/paysage.mp4"]
    assert res[-1]["orientation"] == "paysage" and I.orientation(1080, 1920) == "portrait"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_illustration_paysage_entiere_sur_fond_flou(tmp_path):
    """Une illustration en paysage n'est pas zoomée : elle est montrée en entier, sur un fond flou."""
    from PIL import Image
    img = Image.new("RGB", (1600, 900), (230, 30, 30))
    img.paste((30, 30, 230), (0, 0, 120, 900))                    # bande bleue sur le bord gauche
    chemin = tmp_path / "paysage.jpg"; img.save(chemin)
    ill = M.Illustration({"deb": 0, "fin": 2, "fichier": str(chemin), "type": "image"})
    assert ill.mode == "adapter"
    im = ill.image(0.0)
    assert im.size == (M.W, M.H)
    haut, centre = im.getpixel((M.W // 2, 40)), im.getpixel((M.W // 2, M.H // 2))
    assert centre[0] > 200 and haut[0] < 170                          # image nette au centre, fond assombri en haut
    assert im.getpixel((20, M.H // 2))[2] > 150                        # le bord gauche de l'image est visible (pas rogné)
    # vidéo en paysage : même traitement
    vid = tmp_path / "paysage.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=red:size=640x360:rate=30:d=1",
                    "-pix_fmt", "yuv420p", str(vid)], check=True)
    iv = M.Illustration({"deb": 0, "fin": 1, "fichier": str(vid), "type": "video"})
    assert iv.mode == "adapter" and M.dimensions_media(str(vid)) == (640, 360)
    fr = iv.image(0.2); iv.fermer()
    assert fr.getpixel((M.W // 2, M.H // 2))[0] > 200 and fr.getpixel((M.W // 2, 40))[0] < 170
    # forcé en plein écran
    assert M.Illustration({"deb": 0, "fin": 2, "fichier": str(chemin), "cadrage": "remplir"}).mode == "remplir"


def test_coupes_franches_par_defaut(tmp_path):
    """Par défaut, coupes franches ; un ancien projet (fondu par défaut de la v0.12) revient aux coupes."""
    assert M.Reglages().transition == "coupe" and C.ProfilStyle().transition == "coupe"
    ancien = {"version": 1, "reglages": {"transition": "fondu"}, "clips": [{"a": 0, "b": 1, "transition": "flash"}]}
    chemin = tmp_path / "ancien.projet.json"
    chemin.write_text(json.dumps(ancien), encoding="utf-8")
    proj = P.charger(str(chemin))
    assert proj["reglages"]["transition"] == "coupe" and proj["clips"][0]["transition"] == "flash"


def _png_b64():
    import base64, io
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (576, 1024), (10, 200, 160)).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_generation_gemini_simulee(tmp_path, monkeypatch):
    """Image Gemini : consigne contextualisée, format 9:16, seconde écriture si la première est refusée, cache."""
    import httpx
    monkeypatch.setattr(I, "DOSSIER_CACHE", str(tmp_path / "cache"))
    appels = []

    def reponse(req):
        corps = json.loads(req.content)
        appels.append(corps)
        assert req.headers["x-goog-api-key"] == "cle-g" and "generateContent" in str(req.url)
        if "imageConfig" in corps["generationConfig"]:
            return httpx.Response(400, json={"error": {"message": "Unknown name imageConfig"}})
        assert corps["generationConfig"]["responseFormat"]["image"]["aspectRatio"] == "9:16"
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [
            {"text": "voici"}, {"inlineData": {"mimeType": "image/png", "data": _png_b64()}}]}}]})
    client = httpx.Client(transport=httpx.MockTransport(reponse))
    consigne = I.prompt_illustration({"phrase": "vous payez votre loyer sur votre téléphone", "mot": "loyer"}, "Cotonou, Bénin")
    assert "Cotonou" in consigne and "loyer" in consigne and "9:16" in consigne
    f = I.generer_image(consigne, "cle-g", client=client)
    from PIL import Image
    assert os.path.exists(f) and Image.open(f).size == (576, 1024) and len(appels) == 2
    assert I.generer_image(consigne, "cle-g", client=client) == f and len(appels) == 2       # cache : pas de 2e paiement
    refus = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403, json={"error": {"message": "billing"}})))
    with pytest.raises(RuntimeError, match="billing"):
        I.generer_image("autre", "cle-g", client=refus)


def test_montage_auto_illustrations_gemini(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "FICHIER", str(tmp_path / "config.json"))
    monkeypatch.setattr(C, "DOSSIER_STYLES", str(tmp_path / "styles"))
    cfg = C.charger_config()
    cfg["cles"]["gemini"] = "cle-g"; cfg["illustrations"]["source"] = "gemini"; cfg["ia"] = {"fournisseur": "ollama"}
    C.sauver_config(cfg)
    assert C.charger_config()["ia"]["fournisseur"] == "ollama"          # le choix de l'IA est bien conservé
    img = tmp_path / "g.png"
    from PIL import Image
    Image.new("RGB", (576, 1024)).save(img)
    consignes = []
    mots = _mots("Avec Locapay vous payez votre loyer depuis votre téléphone sans vous déplacer", 0.5)
    proj = {"version": 2, "video": "x.mp4", "duree_source": 8.0, "clips": [{"id": "c", "a": 0.0, "b": 8.0, "zoom": 1.0}],
            "sous_titres": [], "ecrans": [], "illustrations": [], "alertes": [], "musique": None, "reglages": {}}
    monkeypatch.setattr(I, "choisir_moments", lambda *a, **k: [{"deb": 1.0, "fin": 3.0, "mot": "loyer", "requete": "rent",
                                                                 "phrase": "vous payez votre loyer"}])
    auto = P.auto(proj, transcrire=lambda *a, **k: mots, rechercher=lambda *a, **k: 1 / 0,
                  generer=lambda c, cle: (consignes.append(c), str(img))[1])
    ill = auto["illustrations"]
    assert len(ill) == 1 and ill[0]["generee"] and ill[0]["fichier"] == str(img) and "loyer" in consignes[0]


def test_gemini_offre_gratuite_message_clair(tmp_path, monkeypatch):
    import httpx
    monkeypatch.setattr(I, "DOSSIER_CACHE", str(tmp_path / "cache"))
    msg = ("You exceeded your current quota, please check your plan and billing details. * Quota exceeded for metric: "
           "generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0")
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429, json={"error": {"message": msg}})))
    with pytest.raises(RuntimeError, match="offre gratuite"):
        I.generer_image("x", "cle", client=c)


def test_generation_cloudflare_gratuite_simulee(tmp_path, monkeypatch):
    """Cloudflare Workers AI (FLUX.1 schnell) : image base64 → fichier ; quota du jour → message clair ; choix du générateur."""
    import httpx
    monkeypatch.setattr(I, "DOSSIER_CACHE", str(tmp_path / "cache"))
    vus = []

    def reponse(req):
        vus.append(req)
        assert req.headers["authorization"] == "Bearer jeton" and "/accounts/compte1/ai/run/@cf/black-forest-labs/flux-1-schnell" in str(req.url)
        corps = json.loads(req.content)
        if "steps" in corps:                 # le service refuse un champ : on doit réessayer avec la consigne seule
            return httpx.Response(400, json={"success": False, "errors": [{"message": "AiError: Bad input: Error: "
                                  "Additional or unevaluated properties '/steps' at '/' not allowed"}]})
        assert set(corps) == {"prompt"}
        return httpx.Response(200, json={"success": True, "result": {"image": _png_b64()}})
    cfg = {"cles": {"cloudflare_compte": "compte1", "cloudflare_jeton": "jeton", "gemini": "g"},
           "illustrations": {"source": "banques"}}
    assert I.fournisseur_images(cfg) == "cloudflare"                       # gratuit d'abord
    assert I.fournisseur_images({**cfg, "illustrations": {"source": "gemini"}}) == "gemini"
    assert I.fournisseur_images({"cles": {}}) is None
    consigne = I.prompt_illustration({"phrase": "payez votre loyer", "requete": "paying rent"}, "Cotonou, Bénin", "cloudflare")
    assert consigne.startswith("Authentic realistic photograph") and "paying rent" in consigne
    f = I.generer(consigne, cfg, client=httpx.Client(transport=httpx.MockTransport(reponse)))
    assert os.path.exists(f) and len(vus) == 2
    assert I.generer(consigne, cfg, client=httpx.Client(transport=httpx.MockTransport(reponse))) == f and len(vus) == 2
    quota = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(
        429, json={"success": False, "errors": [{"message": "you have used up your daily free allocation of 10,000 neurons"}]})))
    with pytest.raises(RuntimeError, match="Quota gratuit Cloudflare"):
        I.generer("autre", cfg, client=quota)


# ------------------------------------------------------------------ v0.16 : doodles, rythme, copie de style, Openverse
def test_doodles_choix_et_rendu():
    from PIL import Image
    gs = [{"mots": [{"w": w, "s": i}], "cle": 0, "ecran": None, "deb": i, "fin": i + 1}
          for i, w in enumerate(["loyer", "propriétaire", "a", "téléphone", "maison", "b", "c", "d"])]
    M.choisir_doodles(gs, "melange")
    marques = [g for g in gs if g["doodle"]]
    assert [g["mots"][0]["w"] for g in marques] == ["propriétaire", "téléphone"]          # les plus longs, ~1 sur 4
    assert [g["doodle"] for g in marques] == ["souligne", "cercle"]
    M.choisir_doodles(gs, "aucun")
    assert not any(g["doodle"] for g in gs)
    toile = Image.new("RGBA", (M.W, M.H), (0, 0, 0, 255))
    M.dessiner_doodle(toile, (300, 900, 400, 100, 0), "souligne", 1.0, (10, 194, 164))
    vert = [toile.getpixel((x, y)) for x in range(320, 680, 40) for y in range(1000, 1040)]
    assert any(p[1] > 150 and p[0] < 80 for p in vert)
    assert M._ease_rebond(0.7) > 1.0 and abs(M._ease_rebond(1.0) - 1) < 1e-9                # léger dépassement


def test_doodle_dans_le_rendu(tmp_path):
    src = tmp_path / "brut.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=gray:size=360x640:rate=30:d=2",
                    "-f", "lavfi", "-i", "sine=frequency=220:duration=2", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src)], check=True)
    proj = {"version": 2, "video": str(src), "duree_source": 2.0, "clips": [{"id": "1", "a": 0.0, "b": 2.0, "zoom": 1.0}],
            "sous_titres": [{"id": "s", "deb": 0.1, "fin": 1.9, "mots": [{"w": "payez", "t": 0.1}, {"w": "loyer", "t": 0.3},
                                                                         {"w": "facilement", "t": 0.6}], "cle": 1,
                             "doodle": "souligne"}],
            "ecrans": [], "illustrations": [], "musique": None,
            "reglages": {"duree_fin": 0.3, "ecran_fin": False, "logo_en_coin": False, "couleur_2": "#00FF00",
                         "style_etalonnage": "naturel"}}
    plan, R = P.vers_plan(proj)
    assert plan["groupes"][0]["doodle"] == "souligne"
    out = tmp_path / "d.mp4"
    P.rendre(proj, str(out))
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", "1.2", "-i", str(out), "-frames:v", "1", "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    import numpy as np
    im = np.frombuffer(r, np.uint8).reshape(M.H, M.W, 3).astype(int)
    vert = (im[..., 1] > 180) & (im[..., 0] < 90) & (im[..., 2] < 90)
    assert vert.sum() > 500                                   # le trait vert est bien dessiné sous le mot clé


def test_rythme_detection_et_calage(tmp_path):
    import rythme
    wav = tmp_path / "beat.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "aevalsrc='0.8*sin(2*PI*90*t)*exp(-30*mod(t-0.2,60/112))':s=22050:d=20", str(wav)], check=True)
    bpm, temps = rythme.temps_forts(str(wav))
    assert abs(bpm - 112) < 3 and len(temps) > 30
    ecart = np.diff(temps) if (np := __import__("numpy")) else None
    assert abs(float(np.median(ecart)) - 60 / 112) < 0.02
    proj = {"clips": [{"id": "1", "a": 0.0, "b": 2.3}, {"id": "2", "a": 2.3, "b": 5.0}, {"id": "3", "a": 9.0, "b": 11.0}],
            "ecrans": [{"id": "e", "deb": 9.33, "fin": 10.5, "couleur": "#000000"}],
            "musique": {"fichier": str(wav), "decalage": 0.3}}
    battements = [0.5 * k + 0.1 for k in range(40)]
    n = rythme.caler(proj, temps_musique=battements)
    assert proj["musique"]["decalage"] == 0.1                       # départ sur un temps
    assert proj["clips"][0]["b"] == proj["clips"][1]["a"] == 2.5    # recadrage de la même prise : temps le plus proche
    assert proj["clips"][2] == {"id": "3", "a": 9.0, "b": 11.0}     # coupe entre deux prises : intouchée
    assert proj["ecrans"][0]["deb"] == 9.5 and n == 2               # écran : sortie 5.33 → 5.5


def test_analyse_transitions_et_couleurs(tmp_path):
    import analyse_style as A
    fondus = tmp_path / "f.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=180x320:rate=30:d=3",
                    "-f", "lavfi", "-i", "color=0x2E2C51:size=180x320:rate=30:d=3", "-f", "lavfi",
                    "-i", "smptebars=size=180x320:rate=30:d=3", "-filter_complex",
                    "[0][1]xfade=transition=fade:duration=0.5:offset=2.5[a];[a][2]xfade=transition=fade:duration=0.5:offset=5,format=yuv420p",
                    "-c:v", "libx264", "-preset", "ultrafast", str(fondus)], check=True)
    t = A.transitions_detectees(str(fondus))
    assert t["fondu"] >= 2 and A.transition_dominante(t) == "fondu"
    coupes = tmp_path / "c.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=180x320:rate=30:d=2",
                    "-f", "lavfi", "-i", "color=0x2E2C51:size=180x320:rate=30:d=2", "-f", "lavfi",
                    "-i", "smptebars=size=180x320:rate=30:d=2", "-filter_complex", "[0][1][2]concat=n=3:v=1,format=yuv420p",
                    "-c:v", "libx264", "-preset", "ultrafast", str(coupes)], check=True)
    assert A.transition_dominante(A.transitions_detectees(str(coupes))) == "coupe"
    from PIL import Image
    unis = [(0, (True, (46, 44, 81)))] * 5 + [(1, (True, (10, 194, 164)))] * 3 + [(2, (True, (255, 255, 255)))] * 9
    assert A.couleurs_modele(unis, [(0, Image.new("RGB", (90, 160), (120, 110, 100)))]) == ["#2E2C51", "#0AC2A4"]


def test_appliquer_style_au_projet(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "FICHIER", str(tmp_path / "config.json"))
    monkeypatch.setattr(C, "DOSSIER_STYLES", str(tmp_path / "styles"))
    proj = {"clips": [{"a": 0, "b": 1, "transition": "flash"}], "reglages": {"volume_musique": 0.3, "couleur_1": "#111111"}}
    profil = C.ProfilStyle(duree_plan_max=1.2, transition="fondu", doodles="cercle", taille_texte=1.3)
    P.appliquer_style(proj, C.asdict(profil) if hasattr(C, "asdict") else profil.__dict__, ["#AA0000", "#00BB00"])
    r = proj["reglages"]
    assert r["duree_plan_max"] == 1.2 and r["transition"] == "fondu" and r["doodles"] == "cercle"
    assert r["couleur_1"] == "#AA0000" and r["couleur_2"] == "#00BB00" and r["volume_musique"] == 0.3
    assert "transition" not in proj["clips"][0] and proj["style"]["taille_texte"] == 1.3


def test_openverse_images_sans_cle():
    import httpx

    def reponse(req):
        assert "api.openverse.org/v1/images" in str(req.url) and "cc0" in str(req.url)
        return httpx.Response(200, json={"results": [
            {"id": "a", "url": "https://x/a.jpg", "thumbnail": "https://x/a_t.jpg", "width": 800, "height": 1200,
             "creator": "Awa", "license": "by", "license_version": "4.0", "title": "Maison", "foreign_landing_url": "https://f/a"},
            {"id": "b", "url": "https://x/b.jpg", "width": 1200, "height": 800, "creator": "Kofi", "license": "cc0"}]})
    res = I.rechercher("house", {}, client=httpx.Client(transport=httpx.MockTransport(reponse)))
    assert [r["id"] for r in res] == ["openverse-a", "openverse-b"]                       # portrait d'abord
    assert "Awa" in res[0]["credit_licence"] and "CC BY 4.0" in res[0]["credit_licence"]
    assert res[1]["credit_licence"] == ""                                                  # CC0 : rien à créditer


def test_reprise_ancienne_installation_locapay(tmp_path):
    """« Montages Locapay » → Raccord : dossier repris, chemins des projets réécrits, identité Locapay conservée."""
    import chemins
    ancien, nouveau = tmp_path / "Movies" / "Montages Locapay", tmp_path / "Movies" / "Raccord"
    (ancien / ".sources").mkdir(parents=True)
    (ancien / ".sources" / "rush.mp4").write_bytes(b"x")
    (ancien / "essai.projet.json").write_text(json.dumps({"video": str(ancien / ".sources" / "rush.mp4")}), encoding="utf-8")
    os.utime(ancien / "essai.projet.json", (1_700_000_000, 1_700_000_000))
    (ancien / ".parametres").mkdir()
    (ancien / ".parametres" / "config.json").write_text(json.dumps({"cles": {"pexels": "k"}, "style_actif": "Locapay"}),
                                                       encoding="utf-8")
    assert chemins.migrer(str(ancien), str(nouveau))
    assert not ancien.exists() and (nouveau / ".sources" / "rush.mp4").exists()
    assert json.loads((nouveau / "essai.projet.json").read_text())["video"] == str(nouveau / ".sources" / "rush.mp4")
    assert os.path.getmtime(nouveau / "essai.projet.json") == 1_700_000_000         # date conservée
    cfg = json.loads((nouveau / ".parametres" / "config.json").read_text())
    assert cfg["cles"]["pexels"] == "k" and cfg["identite"]["nom"] == "Locapay" and cfg["identite"]["couleur_2"] == "#0AC2A4"
    assert os.path.exists(cfg["identite"]["fichier_logo"]) and cfg["style_actif"] == "Face caméra"
    assert "Cotonou" in cfg["illustrations"]["contexte"] and "Locapay" in cfg["vocabulaire"]
    assert json.loads((nouveau / ".dictionnaire_corrections.json").read_text())[0]["apres"] == "Locapay"
    assert not chemins.migrer(str(ancien), str(nouveau))                 # une seule fois


def test_application_neutre_par_defaut():
    assert C.IDENTITE_DEFAUT["nom"] == "Ma marque" and C.IDENTITE_DEFAUT["fichier_logo"] == ""
    assert C.lister_styles()[0] == "Face caméra" and C.charger_style("Face caméra").mot_cle


def test_paquet_pour_claude_et_import(tmp_path):
    """Sans clé API : paquet (planche + mesures + consignes) → fichier rendu par Claude → style applicable."""
    import zipfile
    import analyse_style as A
    src = tmp_path / "modele.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=30:d=3",
                    "-f", "lavfi", "-i", "color=0x2E2C51:size=360x640:rate=30:d=2", "-filter_complex",
                    "[0][1]concat=n=2:v=1,format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", str(src)], check=True)
    z = A.preparer_pour_claude(str(src), str(tmp_path / "Pour Claude"), nom="Modèle test")
    with zipfile.ZipFile(z) as f:
        assert set(f.namelist()) == {"planche.jpg", "mesures.json", "LISEZMOI.txt"}
        m = json.loads(f.read("mesures.json"))
        assert m["style_propose"]["duree_plan_max"] > 0 and "raccord-style" in f.read("LISEZMOI.txt").decode()
    reponse = {"format": "raccord-style", "version": 1, "nom": "Punchy", "couleurs": ["#112233", "pas une couleur"],
               "profil": {**m["style_propose"], "taille_texte": 9, "casse": "majuscules", "doodles": "cercle", "inconnu": 1},
               "notes": "Gros texte, mots entourés."}
    r = A.lire_style_claude(reponse)
    assert r["profil"]["taille_texte"] == 2.0 and r["profil"]["casse"] == "majuscules" and r["profil"]["doodles"] == "cercle"
    assert r["couleurs"] == ["#112233"] and r["nom"] == "Punchy" and "inconnu" not in r["profil"]
    with pytest.raises(ValueError):
        A.lire_style_claude({"rien": 1})


# ------------------------------------------------------------------ visuels (posts et stories)
def test_visuels_generation_charte_et_paquet(tmp_path, monkeypatch):
    import zipfile
    from PIL import Image
    import visuels as V
    monkeypatch.setattr(V, "DOSSIER", str(tmp_path / "Visuels"))
    monkeypatch.setattr(V, "DOSSIER_EXEMPLES", str(tmp_path / "Visuels" / ".exemples"))
    monkeypatch.setattr(V, "FICHIER_CHARTE", str(tmp_path / "charte.json"))
    photo = tmp_path / "p.jpg"; Image.new("RGB", (900, 1200), (200, 120, 60)).save(photo)
    cfg = {"identite": {"nom": "Marque", "couleur_1": "#2E2C51", "couleur_2": "#0AC2A4"}, "cles": {}, "illustrations": {}}
    charte = V.charte_defaut(cfg)
    assert charte["couleurs"]["fond"] == "#2E2C51" and len(charte["gabarits"]) >= 5
    vs = V.generer("Payez votre loyer par Mobile Money, sans vous déplacer. Simple et sûr.", "story", n=6, cfg=cfg, charte=charte,
                   rechercher=lambda q, c: [{"type": "image", "url": "x", "credit_licence": "Image : par Awa — CC BY 4.0"}],
                   telecharger=lambda r: str(photo))
    assert len(vs) == 6 and len({v["gabarit"] for v in vs}) >= 5 and vs[0]["taille"] == [1080, 1920]
    titres = [b["texte"] for b in vs[0]["blocs"] if b.get("role") == "titre"]
    assert titres == ["Payez votre loyer par Mobile Money"]
    assert any(b["type"] == "image" and b["fichier"] == str(photo) for v in vs for b in v["blocs"])
    story = next(b for b in vs[0]["blocs"] if b.get("role") == "titre")
    assert story["y"] == 45                                                     # valeurs propres au format vertical
    # textes rédigés par l'IA (Ollama) quand elle répond
    t = V.ecrire_textes("x", charte, cfg, demander=lambda conf, consigne: {"titre": "Loyer payé en 1 clic", "cta": "Essayer"})
    assert t["titre"] == "Loyer payé en 1 clic" and t["cta"] == "Essayer" and t["sous_titre"] == ""
    # charte rendue par Claude : vérifiée et bornée
    ch = V.valider_charte({"nom": "Charte X", "couleurs": {"fond": "#111111", "accent": "rouge"},
                           "polices": {"titre": {"fichier": "serif", "graisse": 2000}},
                           "gabarits": [{"id": "a b", "blocs": [{"type": "texte", "role": "titre", "x": 500, "y": 10, "w": 80, "h": 20},
                                                                 {"type": "virus"}]}]})
    assert ch["couleurs"]["fond"] == "#111111" and ch["couleurs"]["accent"] == V.charte_defaut()["couleurs"]["accent"]
    assert ch["polices"]["titre"] == {**ch["polices"]["titre"], "fichier": "serif", "graisse": 900}
    assert len(ch["gabarits"]) == 1 and ch["gabarits"][0]["blocs"][0]["x"] == 100 and ch["source"] == "claude"
    with pytest.raises(ValueError):
        V.valider_charte({"rien": 1})
    # exemples → paquet pour Claude
    for i, c in enumerate([(46, 44, 81), (10, 194, 164), (250, 250, 250)]):
        Image.new("RGB", (1080, 1350), c).save(tmp_path / f"ex{i}.png")
    V.ajouter_exemples([str(tmp_path / f"ex{i}.png") for i in range(3)])
    assert len(V.lister_exemples()) == 3 and "#2E2C51" in V.palette([Image.open(f) for f in V.lister_exemples()])
    z = V.preparer_paquet_charte(str(tmp_path / "Pour Claude"))
    with zipfile.ZipFile(z) as f:
        assert {"planche-1.jpg", "mesures.json", "LISEZMOI.txt"} <= set(f.namelist())
        assert "raccord-charte" in f.read("LISEZMOI.txt").decode()
    # export : PNG + crédits
    avec_photo = next(v for v in vs if any(b["type"] == "image" for b in v["blocs"]))
    avec_photo["textes"]["titre"] = "Loyer / payé"
    png = V.exporter_png(avec_photo, b"\x89PNG fake")
    assert os.path.exists(png) and os.path.exists(os.path.splitext(png)[0] + "_credits.txt")


def test_charte_poppins_script_et_effets():
    import visuels as V
    ch = V.valider_charte({"couleurs": {"fond": "#12B09A"}, "detourer_photos": True,
                           "polices": {"titre": {"fichier": "poppins", "graisse": 800}, "script": {"fichier": "script"}},
                           "gabarits": [{"id": "g", "blocs": [
                               {"type": "texte", "role": "filigrane", "x": 0, "y": 0, "w": 100, "h": 40, "opacite": 0.15, "rotation": -6,
                                "contour": "clair"},
                               {"type": "forme", "x": 0, "y": 0, "w": 100, "h": 100, "motif": "volutes"},
                               {"type": "image", "x": 40, "y": 10, "w": 60, "h": 90}]}]})
    assert ch["polices"]["titre"]["fichier"] == "poppins" and ch["polices"]["script"]["fichier"] == "script"
    b = ch["gabarits"][0]["blocs"]
    assert b[0]["rotation"] == -6 and b[0]["contour"] == "clair" and b[1]["motif"] == "volutes" and ch["detourer_photos"]
    for f in ("Poppins-ExtraBold.ttf", "Poppins-Medium.ttf"):
        assert os.path.exists(os.path.join(RACINE, "app", "polices", "poppins", f))
    # photo détourée : personne entière posée en bas ; photo d'origine pour un plein cadre ou une forme arrondie
    img = {"fichier": "/x_detoure.png", "original": "/x.jpg", "detoure": True}
    g = {"id": "t", "blocs": [{"type": "image", "x": 40, "y": 10, "w": 60, "h": 90}, {"type": "image", "x": 0, "y": 0, "w": 100, "h": 100},
                              {"type": "image", "x": 5, "y": 5, "w": 30, "h": 30, "rayon": 50}]}
    v = V.nouveau_visuel(g, "carre", {}, img, ch)
    assert [(x["fichier"], x.get("ajustement")) for x in v["blocs"]] == [("/x_detoure.png", "contenir-bas"), ("/x.jpg", None), ("/x.jpg", None)]


def test_gabarits_epures_detourage_et_chiffre():
    import visuels as V
    ch = V.valider_charte({"couleurs": {"fond": "#12B09A"}, "polices": {"titre": {"fichier": "poppins", "interlettre": -0.5}},
                           "gabarits": V.GABARITS_DEFAUT})
    assert ch["polices"]["titre"]["interlettre"] == -0.1                       # borné
    ids = [g["id"] for g in ch["gabarits"]]
    assert ids == ["titre", "photo-arrondie", "plein-cadre", "couleur-personne", "chiffre", "moitie"]
    chiffre = ch["gabarits"][ids.index("chiffre")]
    assert chiffre["requiert"] == ["filigrane"]
    assert all(b.get("valign") in (None, "haut", "milieu", "bas") for g in ch["gabarits"] for b in g["blocs"])
    # photo non détourée → boîte de repli ; détourée → posée en bas ; « couvrir » → jamais détourée
    perso = ch["gabarits"][ids.index("couleur-personne")]
    v = V.nouveau_visuel(perso, "carre", {"titre": "Loyer"}, {"fichier": "/x.jpg"}, ch)
    im = next(b for b in v["blocs"] if b["type"] == "image")
    assert (im["x"], im["w"], im["ajustement"]) == (54, 46, "couvrir") and "sans_detourage" not in im
    v = V.nouveau_visuel(perso, "story", {"titre": "Loyer"}, {"fichier": "/x_d.png", "original": "/x.jpg", "detoure": True}, ch)
    im = next(b for b in v["blocs"] if b["type"] == "image")
    assert im["ajustement"] == "contenir-bas" and im["fichier"] == "/x_d.png" and im["y"] == 40
    moitie = ch["gabarits"][ids.index("moitie")]
    v = V.nouveau_visuel(moitie, "carre", {"titre": "Loyer"}, {"fichier": "/x_d.png", "original": "/x.jpg", "detoure": True}, ch)
    assert next(b for b in v["blocs"] if b["type"] == "image")["fichier"] == "/x.jpg"
    # pas de chiffre dans le contexte → le gabarit « chiffre » n'est pas proposé
    vis = V.generer("Paie ton loyer sans te déplacer", n=6, charte=ch, rechercher=lambda *a: [], telecharger=lambda r: None,
                    demander=lambda *a, **k: None, cfg={**__import__("configuration").charger_config(), "cles": {}})
    assert vis and "chiffre" not in [x["gabarit"] for x in vis]
