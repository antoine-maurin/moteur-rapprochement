# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Tests des ouvertures O0a et O0b du banc de comparaison.

O0a — retrait de la passe `SDX_NOM` du blocking par défaut.
O0b — re-dérivation TRAÇABLE des seuils DIMS-v2 sur V1.2.

**Fichier DISTINCT de `tests/test_engine.py`, et c'est structurel.** La garde de non-circularité
(`test_les_tests_eux_memes_ne_lisent_pas_la_verite_terrain`) scanne son PROPRE fichier source
et échouerait si `ground_truth` y apparaissait. Or vérifier que le rappel de blocking est
inchangé EXIGE la vérité terrain : la mesure est faite ici, via le scoreur, exactement comme
`tests/test_scorer.py` le fait pour les métriques. Les deux gardes coexistent sans que l'une
n'affaiblisse l'autre.

**Anti-vacuité.** Chaque test consommant la vraie fixture vérifie d'abord qu'il travaille sur
une population non triviale : un test qui passerait sur zéro paire ne prouverait rien.
"""
import ast
import json
import os
import sys

import pytest

import engine
import scorer
from engine import blocking as blk

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_FIXTURE_CANDIDATES = [
    os.environ.get("GEN_FIXTURE_V1_2", ""),
    os.path.join(_REPO_ROOT, "fixtures", "FIXTURE_PACK_GT_V1_2.json"),
]
_CONTENT_SHA256_V1_2 = "66f627edb37022dcecab04dae9c327b342d8dfbb785533ffe8017919000117a2"

#: Rappel de blocking mesuré par le scoreur sous les TROIS passes, cité par le mandat (§2). Il sert
#: ici d'ancre : le retrait de `SDX_NOM` doit le laisser inchangé, et c'est cela qui est
#: vérifié — pas une valeur ré-atteinte par hasard.
RAPPEL_BLOCKING_TROIS_PASSES = 0.96679


def _chemin_fixture():
    for candidat in _FIXTURE_CANDIDATES:
        if candidat and os.path.isfile(candidat):
            return candidat
    return None


@pytest.fixture(scope="module")
def pack():
    chemin = _chemin_fixture()
    if chemin is None:
        pytest.skip("FIXTURE_PACK_GT_V1_2.json introuvable (pré-requis).")
    return scorer.charge_pack(chemin, _CONTENT_SHA256_V1_2)


@pytest.fixture(scope="module")
def nrecords(pack):
    return engine.normalise_records(pack["records"])


@pytest.fixture(scope="module")
def vraies(pack):
    return scorer.paires_vraies(pack["ground_truth"])


def _candidates(nrecs, passes):
    """Ensemble des clés de paires produites par un jeu de passes donné."""
    res = blk.genere_paires_candidates(nrecs, passes=passes)
    return {scorer.cle_paire(p["record_id_a"], p["record_id_b"]) for p in res["paires"]}


# ============================ O0a — retrait de SDX_NOM ==============================
def test_o0a_sdx_nom_absente_du_defaut():
    """La passe est ABSENTE du défaut — c'est l'acte demandé par le mandat (§2)."""
    assert "SDX_NOM" not in blk.PASSES_DEFAUT, (
        f"SDX_NOM est encore dans le défaut : {blk.PASSES_DEFAUT}")
    assert blk.PASSES_DEFAUT == ("CP", "PREF"), (
        f"passes par défaut inattendues : {blk.PASSES_DEFAUT}")


def test_o0a_le_retrait_est_declare_avec_sa_direction():
    """Un paramètre retiré sans trace serait un paramètre calibré en silence.

    Le retrait est motivé par une information de VÉRITÉ TERRAIN (contribution marginale nulle,
    mesurée par le scoreur). Il doit donc porter son statut et la DIRECTION de son biais, pour que
    l'artefact de comparaison puisse le déclarer plutôt que de le taire.
    """
    declaration = blk.PASSES_RETIREES_DU_DEFAUT["SDX_NOM"]
    assert declaration["statut"] == "choisie_apres_lecture_verite_terrain"
    assert declaration["direction_du_biais"] == "moteur_maison"
    for cle in ("retiree_en", "decide_par", "motif", "effet_attendu", "reversible"):
        assert declaration.get(cle), f"déclaration incomplète : {cle} manquant ou vide"


def test_o0a_la_passe_reste_appelable_donc_le_retrait_est_verifiable():
    """Retirer le CODE rendrait le retrait irréversible et invérifiable.

    C'est la réversibilité qui permet de contrôler l'effet du retrait : le test qui suit
    compare les deux configurations, ce qui suppose de pouvoir encore demander l'ancienne.
    """
    assert blk.soundex("lefebvre") == blk.soundex("lefevre"), "soundex n'est plus fonctionnel"
    cles = dict(blk.cles_de_blocking({"nom": "dubois", "prenom": "marie", "code_postal": "75001"},
                                     passes=("CP", "SDX_NOM", "PREF")))
    assert "SDX_NOM" in cles, "la passe n'est plus demandable explicitement"


def test_o0a_le_retrait_ne_coute_aucune_vraie_paire(nrecords, vraies):
    """DoD 4 : le rappel de blocking est INCHANGÉ — vérifié, jamais supposé.

    L'égalité est vérifiée sur les ENSEMBLES de vraies paires survivantes, pas sur leur
    cardinal : deux ensembles de même taille peuvent différer, et c'est précisément le cas
    qu'une mesure de rappel ne verrait pas.
    """
    avec = _candidates(nrecords, ("CP", "SDX_NOM", "PREF"))
    sans = _candidates(nrecords, ("CP", "PREF"))

    # Anti-vacuité : sans population, l'égalité qui suit serait vraie et ne prouverait rien.
    assert len(vraies) > 200, f"population de vraies paires suspectement faible : {len(vraies)}"
    assert len(sans) > 1000, f"ensemble candidat suspectement faible : {len(sans)}"

    vraies_avec = vraies & avec
    vraies_sans = vraies & sans
    perdues_par_le_retrait = sorted(vraies_avec - vraies_sans)
    assert not perdues_par_le_retrait, (
        f"le retrait de SDX_NOM coûte {len(perdues_par_le_retrait)} vraie(s) paire(s) : "
        f"{perdues_par_le_retrait[:10]}")

    rappel_avec = len(vraies_avec) / len(vraies)
    rappel_sans = len(vraies_sans) / len(vraies)
    assert rappel_sans == rappel_avec, (
        f"rappel de blocking modifié : {rappel_avec} -> {rappel_sans}")
    assert round(rappel_sans, 5) == RAPPEL_BLOCKING_TROIS_PASSES, (
        f"rappel de blocking {rappel_sans} != ancre {RAPPEL_BLOCKING_TROIS_PASSES}")


def test_o0a_le_retrait_reduit_effectivement_l_espace_candidat(nrecords):
    """Le retrait doit SERVIR à quelque chose, sinon il n'est qu'un changement gratuit.

    Le gain est publié comme un fait mécanique. Il joue en faveur du moteur (moins de faux
    positifs offerts à la décision) : c'est l'asymétrie que l'artefact déclare.
    """
    avec = _candidates(nrecords, ("CP", "SDX_NOM", "PREF"))
    sans = _candidates(nrecords, ("CP", "PREF"))
    assert sans < avec, "le retrait ne réduit pas l'ensemble candidat : il est sans effet"
    assert not (sans - avec), "le retrait AJOUTE des paires : impossible pour une union de passes"


def test_o0a_le_blocking_reste_deterministe(nrecords):
    """Le retrait ne doit pas introduire de dépendance à l'ordre d'entrée."""
    direct = blk.genere_paires_candidates(nrecords)["paires"]
    inverse = blk.genere_paires_candidates(list(reversed(nrecords)))["paires"]
    assert direct == inverse, "le blocking dépend de l'ordre d'entrée après le retrait"
    assert direct, "anti-vacuité : aucune paire produite"


# ==================== O0b — DIMS-v2 re-dérivé et TRAÇABLE ===========================
#: Seuils mesurés INFORMELLEMENT, sur l'ensemble candidat à TROIS passes.
#: Cités ici pour une seule raison : prouver qu'ils n'ont pas été recopiés.
SEUILS_INFORMELS_U_B5 = {"t_lambda": -2.411412107, "t_mu": 2.322127427}


def _outil_dims():
    sys.path.insert(0, os.path.join(_REPO_ROOT, "tools"))
    import derive_dimensions as outil
    return outil


def _artefact_dims():
    chemin = os.path.join(_REPO_ROOT, "artifacts", "dimensions.json")
    assert os.path.exists(chemin), "l'artefact DIMS-v2 n'est pas publié (objectif O0b)"
    with open(chemin, encoding="utf-8") as fh:
        return json.load(fh)


def test_o0b_les_seuils_viennent_d_un_re_run_pas_d_une_constante(pack):
    """DoD 3 : test de PROVENANCE — les seuils sont re-dérivés, jamais transcrits.

    Le contrôle est positif et non déclaratif : on rejoue le module DIMS depuis le moteur,
    indépendamment de l'outil, et on exige l'égalité. Un outil qui aurait codé les seuils en
    dur passerait tous les contrôles de forme et échouerait ici.
    """
    artefact = _artefact_dims()
    publies = artefact["seuils_dimensions"]

    params = engine.ParametresMoteur(passes_blocking=engine.PASSES_DEFAUT)
    corrs = engine.execute_moteur(pack["records"], params)["correspondances"]
    assert len(corrs) > 1000, f"anti-vacuité : {len(corrs)} correspondances seulement"

    rejoue = engine.dimensionne_depuis_correspondances(
        corrs, budget_revue=artefact["seuils_dimensions"]["budget_vise"], frontiere=0.0)

    assert publies["t_mu"] == rejoue["t_mu"], (
        f"T_mu publié {publies['t_mu']} != T_mu re-dérivé {rejoue['t_mu']} : "
        f"l'artefact ne provient pas du module DIMS")
    assert publies["t_lambda"] == rejoue["t_lambda"], (
        f"T_lambda publié {publies['t_lambda']} != T_lambda re-dérivé {rejoue['t_lambda']}")
    assert publies["budget_atteint"] == rejoue["budget_atteint"]


def test_o0b_les_seuils_ne_sont_pas_ceux_de_u_b5(nrecords):
    """Les seuils informels ne doivent PAS reparaître : ils décrivaient un autre moteur.

    Ils portaient sur l'ensemble candidat à trois passes, que O0a vient de réduire. Les
    retrouver à l'identique signifierait qu'ils ont été recopiés — c'est exactement ce que le
    mandat (§3) interdit.
    """
    publies = _artefact_dims()["seuils_dimensions"]
    assert publies["t_mu"] != SEUILS_INFORMELS_U_B5["t_mu"], "T_mu recopié"
    assert publies["t_lambda"] != SEUILS_INFORMELS_U_B5["t_lambda"], "T_lambda recopié"


def test_o0b_l_artefact_est_arrime_au_moteur_d_apres_o0a(nrecords):
    """L'artefact doit décrire le moteur POST-retrait, et le dire.

    Sans ce contrôle, un artefact dérivé avant O0a resterait publiable : ses seuils seraient
    « traçables » mais traceraient le mauvais moteur.
    """
    artefact = _artefact_dims()
    conf = artefact["configuration_moteur"]
    assert conf["passes_blocking"] == list(engine.PASSES_DEFAUT) == ["CP", "PREF"]
    assert "SDX_NOM" not in conf["passes_blocking"]
    attendu = len(_candidates(nrecords, ("CP", "PREF")))
    assert artefact["derivation"]["n_paires_notees"] == attendu, (
        f"l'artefact note {artefact['derivation']['n_paires_notees']} paires, le moteur "
        f"courant en produit {attendu} : l'artefact décrit un autre ensemble candidat")


def test_o0b_l_artefact_publie_est_reproductible():
    """L'artefact du dépôt est bien celui que le code régénère — sinon il a dérivé en silence."""
    outil = _outil_dims()
    regenere = outil.construis()
    publie = _artefact_dims()
    # La provenance porte le commit courant : elle change à chaque commit et n'est donc pas
    # comparée. Tout le reste — seuils, dérivation, configuration — doit coïncider.
    for cle in ("seuils_dimensions", "derivation", "configuration_moteur", "cc1"):
        assert regenere[cle] == publie[cle], f"l'artefact publié diverge sur « {cle} »"


def test_o0b_la_derivation_est_deterministe():
    """Deux dérivations consécutives donnent le même artefact canonique."""
    outil = _outil_dims()
    a = outil.serialisation_canonique(outil.construis())
    b = outil.serialisation_canonique(outil.construis())
    assert a == b, "la dérivation DIMS-v2 n'est pas reproductible"


def test_o0b_l_outil_est_structurellement_non_supervise():
    """DoD 5 : l'outil qui produit les seuils ne PEUT pas lire la vérité terrain.

    Contrôle par le code source, et non par la sortie : un programme qui n'importe pas le
    scoreur et ne nomme jamais `ground_truth` est non supervisé par construction. C'est une
    propriété plus forte qu'une promesse, parce qu'elle survit à une modification distraite.
    """
    chemin = os.path.join(_REPO_ROOT, "tools", "derive_dimensions.py")
    with open(chemin, encoding="utf-8") as fh:
        source = fh.read()
    arbre = ast.parse(source, filename=chemin)

    importes = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            importes |= {a.name.split(".")[0] for a in noeud.names}
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            importes.add(noeud.module.split(".")[0])
    interdits = importes & {"scorer", "splink", "duckdb", "pandas", "generator"}
    assert not interdits, f"l'outil de dimensionnement importe {sorted(interdits)}"

    # Contrôle STRUCTUREL, et non textuel : ce qui compte est un ACCÈS `x["ground_truth"]`,
    # pas une mention du mot dans une docstring — un test qui grepperait la prose se
    # déclencherait sur sa propre documentation, et serait désarmé dès la première fois qu'on
    # le trouverait agaçant. La seule occurrence légitime est la liste des clés canonicalisées
    # de l'empreinte, où le bloc est HACHÉ sans être lu : c'est un littéral dans un tuple, et
    # non un indice, donc il ne peut pas matcher ici.
    acces = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Subscript):
            indice = noeud.slice
            if isinstance(indice, ast.Constant) and indice.value == "ground_truth":
                acces.append(f"ligne {noeud.lineno}")
        if isinstance(noeud, ast.Attribute) and noeud.attr == "ground_truth":
            acces.append(f"ligne {noeud.lineno} (attribut)")
    assert not acces, f"accès direct à la vérité terrain dans l'outil : {acces}"

    # Contrôle positif de l'oracle : le test doit SAVOIR détecter une infraction, sinon son
    # silence ne prouve rien.
    infraction = ast.parse('etiquettes = pack["ground_truth"]\n')
    detectee = [n for n in ast.walk(infraction)
                if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
                and n.slice.value == "ground_truth"]
    assert detectee, "l'oracle ne detecte plus une infraction injectee : il est desarme"

    assert artefact_declare_cc1(), "l'artefact ne déclare pas sa frontière de non-circularité"


def artefact_declare_cc1() -> bool:
    """L'artefact affirme-t-il, et publie-t-il, sa propre frontière de non-circularité ?"""
    cc1 = _artefact_dims()["cc1"]
    return cc1["verite_terrain_lue"] is False and cc1["modules_importes"] == ["engine"]
