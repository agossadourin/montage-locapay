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
    R = M.Reglages(fichier_logo=os.path.join(RACINE, "app", "logo_locapay.png"), duree_fin=0.5,
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
    nb = json.load(open(os.path.join(RACINE, "colab", "Montage_auto_Locapay.ipynb"), encoding="utf-8"))
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
                            "-vf", "crop=10:10:20:20,scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           capture_output=True)
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
