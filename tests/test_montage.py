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
