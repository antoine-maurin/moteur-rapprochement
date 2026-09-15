# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Tests d'unité (générateur GEN_001).

Lancement depuis la racine du repo de build : `python -m pytest tests/ -q`
(le `conftest.py` de la racine ajoute `src/` au sys.path — src-layout sans installation).

Le test de non-régression FX_001 charge la VRAIE fixture golden
`fixtures/FIXTURE_PACK_GT_V1_1.json` (chemin relatif à la racine du repo de
build), ou celle désignée par la variable d'environnement `GEN_FIXTURE`.
Il n'est JAMAIS skippé : la présence de la fixture est un pré-requis ; son absence
est un échec dur, pas un skip silencieux.
"""
import json
import os

from generator import generate_pack, verify_pack, content_sha256
from generator.generator import ATTRIBUTS_COMPARE, SOURCES

SEED = "SP_CYCLE_001::GEN-01::seed-0001"

# Empreintes scellées de FX_001.
FX001_CONTENT_SHA256 = "0c8a90994c8bd7c6b03bd1f25bb3b000b1482fefd53f3f0b56761b415446b937"
FX001_SEAL_SHA256_16 = "9ee258eba7ee1e38"

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_FIXTURE_CANDIDATES = [
    os.environ.get("GEN_FIXTURE", ""),
    os.path.join(_REPO_ROOT, "fixtures", "FIXTURE_PACK_GT_V1_1.json"),
]


def _load_fixture():
    """Charge FX_001. Échec DUR si introuvable (jamais de skip — mandat §6.1)."""
    tried = []
    for p in _FIXTURE_CANDIDATES:
        if not p:
            continue
        tried.append(os.path.normpath(p))
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
    raise AssertionError(
        "FIXTURE_PACK_GT_V1_1.json introuvable (pré-requis). "
        "Chemins essayés : " + " | ".join(tried))


def test_fx001_canonicalization_reproduite():
    """Non-régression FX_001 : les empreintes scellées se recomptent à l'identique."""
    fx = _load_fixture()
    assert "manifest" in fx, "FX_001 sans manifest : pack invalide"
    v = verify_pack(fx)
    assert v["content_ok"], v
    assert v["seal_ok"], v
    # Verrou explicite sur les valeurs du mandat §5, au-delà de l'auto-cohérence du manifest.
    assert v["content_sha256"] == FX001_CONTENT_SHA256, v
    assert v["seal_sha256_16"] == FX001_SEAL_SHA256_16, v


def test_determinisme():
    a = generate_pack(SEED, n_entities=40)
    b = generate_pack(SEED, n_entities=40)
    assert a["manifest"]["content_sha256"] == b["manifest"]["content_sha256"]
    assert a["records"] == b["records"]


def test_graines_distinctes_divergent():
    assert (generate_pack("seed-A", n_entities=40)["manifest"]["content_sha256"]
            != generate_pack("seed-B", n_entities=40)["manifest"]["content_sha256"])


def test_schema_source_record():
    pack = generate_pack(SEED, n_entities=40)
    ids = set()
    for r in pack["records"]:
        assert set(r.keys()) == {"record_id", "source_id", *ATTRIBUTS_COMPARE}
        assert r["record_id"] and r["record_id"] not in ids
        ids.add(r["record_id"])
        assert r["source_id"] in SOURCES
        assert r["code_postal"] is None or isinstance(r["code_postal"], str)
        assert r["telephone"] is None or isinstance(r["telephone"], str)


def test_dedup_1a1_intra_source():
    pack = generate_pack(SEED, n_entities=60)
    gt = {g["record_id"]: g["id_entite_vraie"] for g in pack["ground_truth"]}
    seen = {}
    for r in pack["records"]:
        key = (r["source_id"], gt[r["record_id"]])
        assert key not in seen, f"collision 1-à-1 {key}"
        seen[key] = r["record_id"]


def test_verite_terrain_partition():
    pack = generate_pack(SEED, n_entities=40)
    rec_ids = [r["record_id"] for r in pack["records"]]
    gt_ids = [g["record_id"] for g in pack["ground_truth"]]
    assert sorted(rec_ids) == sorted(gt_ids)
    assert len(gt_ids) == len(set(gt_ids))


def test_annotation_corruption_coherente():
    pack = generate_pack(SEED, n_entities=40)
    ann = {a["record_id"]: a for a in pack["corruption_annotation"]}
    for r in pack["records"]:
        a = ann[r["record_id"]]
        if a["categories_appliquees"] is None:
            assert a["record_id_origine"] is None
        else:
            assert "DOUBLON" in a["categories_appliquees"]
            assert a["record_id_origine"] is not None


def test_annotation_effet_observable():
    """Oracle d'effet (voie b) : zéro surdéclaration.

    Toute catégorie ≠ DOUBLON consignée dans `categories_appliquees` doit se traduire par
    au moins un des 8 attributs comparés qui diffère du record d'origine. L'annotation est
    un « support de preuve » (design GEN-01 §1 étape 5), pas une intention : un corrupteur
    resté sans effet ne doit pas y figurer. Ce test échoue sur l'annotation d'avant la
    voie (b) (5,6–12 % de doublons annotés corrompus mais byte-identiques à leur pivot).
    """
    pack = generate_pack(SEED, n_entities=400)
    recs = {r["record_id"]: r for r in pack["records"]}
    annotes, surdeclares = 0, []
    for a in pack["corruption_annotation"]:
        reelles = [c for c in (a["categories_appliquees"] or []) if c != "DOUBLON"]
        if not reelles:
            continue
        annotes += 1
        r, o = recs[a["record_id"]], recs[a["record_id_origine"]]
        if all(r[k] == o[k] for k in ATTRIBUTS_COMPARE):
            surdeclares.append((a["record_id"], a["record_id_origine"], reelles))
    # Garde anti-vacuité : un oracle qui n'inspecte rien passerait trivialement.
    assert annotes > 0, "aucun record annoté d'une catégorie réelle : oracle vide"
    assert not surdeclares, (
        f"{len(surdeclares)}/{annotes} records surdéclarés (annotés corrompus mais "
        f"byte-identiques à leur origine) — ex. {surdeclares[:3]}")


def test_content_sha256_stable():
    pack = generate_pack(SEED, n_entities=40)
    assert content_sha256(pack) == pack["manifest"]["content_sha256"]


def test_categories_couvrent_les_8_sur_grande_population():
    pack = generate_pack(SEED, n_entities=400)
    cats = set()
    for a in pack["corruption_annotation"]:
        if a["categories_appliquees"]:
            cats.update(a["categories_appliquees"])
    attendues = {"TYPO", "PHON", "FORMAT", "MANQUANT", "TRONC", "TRANSPO",
                 "BRUIT_STRUCT", "DOUBLON"}
    assert attendues <= cats, f"manquantes : {attendues - cats}"
