# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Suite de tests — chaîne bout-en-bout (O2), rejeu DIMS (O3), reproductibilité (O4).

Les oracles structurels du moteur (`tests/test_engine.py`) parcourent `src/engine/` par
`os.listdir` : ils ne voient PAS `src/pipeline/`. Le nouveau paquet aurait donc échappé aux
gardes de non-circularité et C7 s'il n'apportait pas les siennes — c'est ce que fait la
section 1, et c'est la contrepartie assumée de l'avoir placé hors de la zone moteur.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "tools"))

import engine                                            # noqa: E402
from engine import clustering as clu                     # noqa: E402
from engine import llm_client as clt                     # noqa: E402
from engine import llm_review as rev                     # noqa: E402
import pipeline as pl                                    # noqa: E402
import derive_dimensions as dd                              # noqa: E402

_SRC_PIPELINE = os.path.join(_REPO_ROOT, "src", "pipeline")
_VECTEURS = os.path.join(_REPO_ROOT, "fixtures", "llm_review", "vecteurs_de_test.json")


def _sources_pipeline() -> dict:
    """Contenu des modules de `src/pipeline/`, avec garde de non-vacuité."""
    presents = sorted(f for f in os.listdir(_SRC_PIPELINE) if f.endswith(".py"))
    assert len(presents) >= 4, f"inventaire de src/pipeline/ suspect : {presents}"
    sources = {}
    for nom in presents:
        with open(os.path.join(_SRC_PIPELINE, nom), encoding="utf-8") as fh:
            sources[nom] = fh.read()
    return sources


def _modules_importes(source: str) -> set:
    noms = set()
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.Import):
            noms.update(a.name.split(".")[0] for a in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.level:
                noms.add(".")
            elif noeud.module:
                noms.add(noeud.module.split(".")[0])
    return noms


@pytest.fixture(scope="module")
def records():
    chemin = os.path.join(_REPO_ROOT, dd.CHEMIN_FIXTURE)
    if not os.path.exists(chemin):
        pytest.skip("FIXTURE_PACK_GT_V1_2.json absente de l'environnement")
    try:
        charges, _ = dd.charge_records(chemin)
    except ValueError as erreur:                          # empreinte divergente
        pytest.fail(f"fixture alteree : {erreur}")
    return charges


@pytest.fixture(scope="module")
def client():
    with open(_VECTEURS, encoding="utf-8") as fh:
        return pl.client_substitut_1b(json.load(fh))


@pytest.fixture(scope="module")
def point():
    return pl.point_depuis_artefact(pl.CHEMIN_DIMS_V2, racine=_REPO_ROOT)


@pytest.fixture(scope="module")
def sortie(records, point, client):
    return pl.execute_chaine(records, point, client)


# ==================== 1. Non-circularité / C7 structurels sur le NOUVEAU paquet ======
def test_cc1_le_pipeline_n_importe_jamais_le_scoreur():
    """La chaîne ORCHESTRE le moteur ; elle ne mesure pas ce qu'elle produit.

    C'est la condition de non-circularité de la preuve, et elle doit survivre à
    l'assemblage complet : c'est précisément au moment où tout est câblé ensemble qu'un
    import de commodité vers `scorer` deviendrait tentant.
    """
    for nom, source in _sources_pipeline().items():
        importes = _modules_importes(source)
        assert "scorer" not in importes, f"{nom} : le pipeline importe le scoreur"
        assert "splink" not in importes, f"{nom} : le pipeline importe la bibliotheque du banc"
    # Contrôle POSITIF : l'oracle voit un import qu'on lui soumet.
    assert "scorer" in _modules_importes("from scorer import metriques\n"), "oracle mort"


def _chaines_hors_docstring(source: str) -> list:
    """Toutes les chaînes littérales du module, SAUF les docstrings.

    La distinction est la même qu'en zone moteur, et elle est essentielle : une prose qui
    NOMME une dépendance pour dire qu'on ne l'utilise pas n'est pas une dépendance. Un
    oracle textuel confondrait les deux et interdirait de documenter une frontière — ce qui
    est exactement ce qu'il ne faut pas.
    """
    arbre = ast.parse(source)
    docstrings = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
            corps = getattr(noeud, "body", None)
            if (corps and isinstance(corps[0], ast.Expr)
                    and isinstance(corps[0].value, ast.Constant)
                    and isinstance(corps[0].value.value, str)):
                docstrings.add(id(corps[0].value))
    return [n.value for n in ast.walk(arbre)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings]


def test_cc1_le_pipeline_ne_lit_aucune_cle_de_verite_terrain():
    """Aucune clé de vérité terrain n'est LUE par le paquet.

    L'oracle porte sur les chaînes littérales hors docstring — donc sur ce qui pourrait
    servir à indexer un pack — et non sur le texte brut : les docstrings de ce paquet
    NOMMENT ces clés, précisément pour déclarer qu'elles sont hors de sa portée, et un grep
    confondrait la déclaration de la frontière avec son franchissement.

    Il ne s'agit pas d'une garde plus faible : `charge_records` (le seul chargeur que la
    chaîne emploie) ne rend QUE les records, si bien que le pack complet n'entre jamais
    dans ce paquet. Cet oracle ferme le chemin qui resterait — indexer soi-même.
    """
    interdits = ("ground_truth", "id_entite_vraie", "zone_intention_design")
    for nom, source in _sources_pipeline().items():
        for chaine in _chaines_hors_docstring(source):
            for jeton in interdits:
                assert jeton not in chaine, (
                    f"{nom} : cle de verite terrain dans une chaine executable -> {jeton}")
    # Contrôle POSITIF : l'oracle voit l'accès qu'on lui soumet, et ignore la docstring.
    assert 'ground_truth' in _chaines_hors_docstring(
        'x = pack["ground_truth"]\n')[0], "oracle mort"
    assert _chaines_hors_docstring('"""ground_truth est hors perimetre."""\n') == [], (
        "l'oracle confond une docstring avec un acces : il interdirait de documenter")


def test_c7_le_pipeline_n_importe_que_la_bibliotheque_standard():
    """Liste BLANCHE. `os` et `json` y sont — c'est la raison d'être du paquet séparé.

    La liste blanche du moteur les EXCLUT, parce qu'un module qui décide n'a rien à ouvrir.
    Un orchestrateur, lui, doit charger un point de fonctionnement publié. Loger la chaîne
    dans `src/engine/` aurait donc exigé d'élargir la liste blanche du cœur décisionnel ;
    la placer ici la laisse intacte, et c'est ce que ce test rend vérifiable.
    """
    autorises = {".", "__future__", "engine", "hashlib", "json", "os", "dataclasses",
                 "typing"}
    for nom, source in _sources_pipeline().items():
        importes = _modules_importes(source)
        assert importes <= autorises, (
            f"{nom} : import hors liste blanche -> {sorted(importes - autorises)}")


def test_le_pipeline_ne_recompte_aucune_metrique():
    """Le pipeline chaîne ; il ne mesure pas. Même frontière que le hook du dépôt."""
    interdits = ("precision", "recall", "f1_score", "true_positive", "false_positive")
    for nom, source in _sources_pipeline().items():
        for jeton in interdits:
            assert jeton not in source.lower(), f"{nom} : recompte de metrique -> {jeton}"


# ==================== 2. O2 — la chaîne bout-en-bout ================================
def test_o2_la_chaine_produit_des_enregistrements_dores(sortie):
    """Un point d'entrée, un pack de records, des enregistrements dorés."""
    assert sortie["golden_records"], "aucun enregistrement dore produit"
    assert len(sortie["golden_records"]) == len(sortie["partition"]), (
        "contrat de cardinalite rompu : un dore par entite")
    assert sortie["rapport"]["etages"] == list(pl.ETAGES)


def test_o2_la_chaine_traverse_bien_tous_les_etages(sortie):
    """Chaque étage a laissé sa trace : une chaîne muette serait indiscernable d'une chaîne
    qui saute une étape."""
    rapport = sortie["rapport"]
    assert rapport["blocking"]["n_paires"] == rapport["n_paires"]
    assert rapport["estimation"]["convergence"] is True
    assert sum(rapport["repartition_verdicts"].values()) == rapport["n_paires"]
    assert rapport["revue"]["n_zone_grise"] == rapport["repartition_verdicts"]["ZONE_GRISE"]
    assert rapport["n_entites"] == len(sortie["partition"])


def test_o2_la_partition_couvre_exactement_l_univers(sortie, records):
    """Aucun enregistrement perdu, aucun compté deux fois."""
    vus = [rid for groupe in sortie["partition"] for rid in groupe]
    assert sorted(vus) == sorted(r["record_id"] for r in records)
    assert len(vus) == len(set(vus)), "un enregistrement appartient a deux entites"


def test_o2_le_client_de_revue_est_obligatoire(records, point):
    """Un défaut silencieux ferait passer une chaîne sans revue pour une chaîne complète."""
    with pytest.raises(TypeError):
        pl.execute_chaine(records, point)          # noqa: E1120 — c'est l'objet du test


def test_o2_une_promotion_de_revue_entre_REELLEMENT_dans_la_partition():
    """RÉGRESSION — le défaut qui rendait l'étage de revue inopérant, en silence.

    `clustering.est_liante` comparait la décision de revue au jeton `MATCH` du moteur, que
    la revue n'émet jamais : sa branche « revue » était structurellement inatteignable, et
    une paire promue ne produisait AUCUNE arête. Rien ne le signalait — la partition était
    simplement trop fine, ce qui n'a l'air anormal nulle part.

    Ce test part du jeton que la revue émet RÉELLEMENT, et vérifie que deux enregistrements
    promus finissent dans la MÊME entité.
    """
    promue = {
        "record_id_a": "A", "record_id_b": "B", "verdict": engine.ZONE_GRISE,
        "poids_match": 0.0,
        "revue_zone_grise": {"statut": rev.REVUE, "decision": clt.MATCH_APRES_REVUE},
    }
    aretes = pl.aretes_de_l_ensemble_de_match([promue])
    assert aretes, "la promotion de revue ne produit aucune arete"
    assert engine.cloture_transitive([promue], ["A", "B"]) == [["A", "B"]], (
        "deux enregistrements promus par la revue restent dans deux entites distinctes")


class _AdjudicateurDeTest:
    """Double de test qui PROMEUT tout ce qu'on lui soumet. Jamais livré, jamais publié.

    Il n'existe que pour faire traverser à la chaîne son étage de revue avec de vraies
    promotions. Le substitut `1b` livré ne le peut pas sur cette population — sa table de
    rejeu porte sur des paires synthétiques — si bien que sans ce double, la branche
    « promotion » de `execute_chaine` ne serait jamais parcourue de bout en bout, et le
    défaut de jeton corrigé aurait pu se reformer sans qu'aucun test E2E ne bouge.
    """

    nom = "adjudicateur_de_test"
    cout_declare_par_appel = 0

    def repond(self, invite: str) -> str:
        # Le protocole RÉEL : la décision vit sur une ligne ANCRÉE. Répondre le jeton nu
        # donnerait `NON_TRANCHE` — l'abstention prudente — et le test passerait à côté de
        # ce qu'il croit éprouver. Le double parle donc la même langue que le vrai client.
        return f"DECISION: {clt.MATCH_APRES_REVUE}\nJUSTIFICATION: double de test"


def test_o2_la_chaine_ENTIERE_promeut_et_les_entites_fusionnent(records, point):
    """E2E RÉEL : des promotions traversent la chaîne et changent la partition.

    C'est le pendant bout-en-bout du test de régression ci-dessus. Il compare deux
    exécutions de `execute_chaine` — l'une avec un adjudicateur qui promeut, l'autre avec le
    substitut livré qui n'instruit rien — et exige que la première produise STRICTEMENT
    MOINS d'entités. Si le jeton de promotion divergeait à nouveau, les deux partitions
    seraient identiques et ce test rougirait.
    """
    with open(_VECTEURS, encoding="utf-8") as fh:
        muet = pl.client_substitut_1b(json.load(fh))

    sans = pl.execute_chaine(records, point, muet)
    avec = pl.execute_chaine(records, point, _AdjudicateurDeTest())

    trace = avec["rapport"]["revue"]
    assert trace["n_revues"] > 0, "l'adjudicateur de test n'a rien instruit"
    assert trace["decisions"][clt.MATCH_APRES_REVUE] > 0, "aucune promotion rendue"

    assert avec["rapport"]["n_aretes"] > sans["rapport"]["n_aretes"], (
        "les promotions n'ont produit AUCUNE arete supplementaire : le jeton de promotion "
        "ne traverse pas la chaine")
    assert avec["rapport"]["n_entites"] < sans["rapport"]["n_entites"], (
        "la partition est inchangee malgre les promotions : la revue est inoperante")
    assert len(avec["golden_records"]) == avec["rapport"]["n_entites"]
    # L'univers reste couvert : promouvoir fusionne des entités, n'en perd aucune.
    vus = [rid for groupe in avec["partition"] for rid in groupe]
    assert sorted(vus) == sorted(r["record_id"] for r in records)


def test_o2_un_refus_et_un_non_tranche_ne_lient_jamais():
    """R-20 tenu jusque dans la chaîne : le doute non tranché ne devient pas un lien."""
    for decision in (clt.NON_MATCH_APRES_REVUE, clt.NON_TRANCHE):
        corr = {"record_id_a": "A", "record_id_b": "B", "verdict": engine.ZONE_GRISE,
                "poids_match": 0.0,
                "revue_zone_grise": {"statut": rev.REVUE, "decision": decision}}
        assert pl.aretes_de_l_ensemble_de_match([corr]) == [], f"{decision} a lie"
        assert engine.cloture_transitive([corr], ["A", "B"]) == [["A"], ["B"]]


def test_o2_la_garde_de_conservation_leve_si_les_lectures_divergent(monkeypatch):
    """La jonction revue -> clôture a divergé une fois ; la garde doit mordre si ça recommence.

    On simule la divergence en faisant mentir `est_liante` — la garde doit lever plutôt que
    de laisser passer une partition trop fine.
    """
    promue = {"record_id_a": "A", "record_id_b": "B", "verdict": engine.ZONE_GRISE,
              "poids_match": 0.0,
              "revue_zone_grise": {"statut": rev.REVUE, "decision": clt.MATCH_APRES_REVUE}}
    monkeypatch.setattr(clu, "est_liante", lambda c: False)
    with pytest.raises(pl.ConservationRompue):
        pl.aretes_de_l_ensemble_de_match([promue])


def test_o2_le_substitut_1b_est_declare_pour_ce_qu_il_est(sortie):
    """Règle de vocabulaire / C7 : un substitut déterministe, jamais un modèle."""
    client_trace = sortie["rapport"]["revue"]["client"]
    assert client_trace["nom"] == "rejeu"
    assert (client_trace["provenance"] or {})["est_une_transcription_de_modele"] is False


# ==================== 3. O3 — rejeu DIMS sur DEUX populations ========================
def _deux_populations(records):
    """Deux populations DISTINCTES, dérivées de la fixture sans jamais l'écrire.

    La coupe est déterministe (ordre des `record_id`) et les deux moitiés se recouvrent
    partiellement : des populations disjointes seraient un cas trop facile — deux moitiés
    qui partagent des enregistrements mais pas leur distribution de `R` sont le cas réaliste
    d'un rejeu, celui où recopier les seuils est le plus tentant.
    """
    tries = sorted(records, key=lambda r: r["record_id"])
    coupe = len(tries) * 2 // 3
    return tries[:coupe], tries[len(tries) - coupe:]


def test_o3_les_seuils_sont_RE_DERIVES_sur_deux_populations(records):
    """Sur deux populations, deux points DIFFÉRENTS — re-dérivés, jamais recopiés."""
    a, b = _deux_populations(records)
    assert len(a) > 100 and len(b) > 100, "populations de rejeu trop petites"
    assert {r["record_id"] for r in a} != {r["record_id"] for r in b}

    point_a, _ = pl.point_depuis_records(a)
    point_b, _ = pl.point_depuis_records(b)

    assert point_a.derive_a_l_execution is True
    assert point_b.derive_a_l_execution is True
    assert (point_a.t_mu, point_a.t_lambda) != (point_b.t_mu, point_b.t_lambda), (
        "deux populations distinctes donnent les MEMES seuils : la re-derivation ne se "
        "declenche pas, ou elle recopie")


def test_o3_chaque_point_re_derive_porte_sa_provenance(records):
    """Un seuil sans provenance est un paramètre libre. Ceux-ci sont liés à leurs entrées."""
    a, _ = _deux_populations(records)
    point, amont = pl.point_depuis_records(a)
    prov = point.provenance
    assert prov["origine"] == "re-derivation"
    assert prov["empreinte_population"] == pl.empreinte_population(a)
    assert prov["empreinte_table_de_poids"] == pl.empreinte_table_de_poids(
        amont["rapport"]["poids"])
    for cle in ("budget_vise", "budget_atteint", "methode", "provisoire", "n_paires"):
        assert cle in prov, f"provenance incomplete : {cle} manquant"


def test_o3_un_point_presente_a_une_autre_population_est_REFUSE(records):
    """La dette §12.1, rendue bruyante : des seuils périmés lèvent au lieu de trancher."""
    a, b = _deux_populations(records)
    point_a, _ = pl.point_depuis_records(a)
    amont_b = engine.execute_moteur(b)
    with pytest.raises(pl.SeuilsPerimes) as capture:
        pl.verifie_provenance(point_a, b, amont_b["rapport"]["poids"])
    assert "perimes" in str(capture.value)
    # ... et il est ACCEPTÉ sur la sienne : la garde ne refuse pas tout.
    amont_a = engine.execute_moteur(a)
    rapport = pl.verifie_provenance(point_a, a, amont_a["rapport"]["poids"])
    assert rapport["concordant"] is True


def test_o3_un_point_charge_declare_sa_liaison_plus_faible(point, records, sortie):
    """L'artefact DIMS-v2 identifie sa population par un sha de fixture, pas par empreinte.

    La vérification le DIT (`verifiable: False`) au lieu de laisser croire à un contrôle
    qui n'a pas eu lieu. Une garde qui rend « conforme » sur une liaison qu'elle n'a pas
    vérifiée serait pire que pas de garde du tout.
    """
    rapport = sortie["rapport"]["provenance_du_point"]
    assert rapport["verifiable"] is False
    assert rapport["concordant"] is None
    assert "sha de fixture" in rapport["motif"]


def test_o3_l_empreinte_de_population_voit_une_modification_des_attributs_compares(records):
    """L'empreinte doit mordre sur ce que le moteur regarde, et seulement sur cela."""
    tries = sorted(records, key=lambda r: r["record_id"])
    cible = next((r for r in tries if r.get("nom")), None)
    assert cible is not None, "aucun enregistrement avec un nom : fixture inattendue"
    modifie = [dict(r) for r in tries]
    for rec in modifie:
        if rec["record_id"] == cible["record_id"]:
            rec["nom"] = (rec["nom"] or "") + "zz"
    assert pl.empreinte_population(modifie) != pl.empreinte_population(tries)
    # ... et PAS sur une colonne que le moteur ne compare jamais.
    indifferent = [dict(r, colonne_jamais_comparee="peu importe") for r in tries]
    assert pl.empreinte_population(indifferent) == pl.empreinte_population(tries)


# ==================== 4. O4 — reproductibilité bout-en-bout ==========================
def test_o4_deux_executions_dans_le_meme_processus_sont_identiques(records, point, client):
    """Le premier niveau : la chaîne ne dérive pas d'un appel à l'autre."""
    a = pl.execute_chaine(records, point, client)
    b = pl.execute_chaine(records, point, client)
    assert pl.content_sha256_e2e(a) == pl.content_sha256_e2e(b)


def test_o4_la_convention_de_canonicalisation_est_bien_celle_du_projet():
    """La forme canonique est celle du générateur, VERBATIM — éprouvé, pas supposé.

    Deux conventions qui se ressemblent sans être identiques produiraient deux empreintes
    également plausibles, et le jour où elles divergeraient, personne ne saurait laquelle
    avait raison. Le témoin est un objet quelconque : ce qui est comparé, c'est la RÈGLE de
    sérialisation, jamais un contenu de pack — ce fichier ne touche aucune clé de vérité
    terrain (cf. section 1).
    """
    temoin = {"b": [1, {"z": "é", "a": None}], "a": "x/y"}
    attendu = json.dumps(temoin, sort_keys=True, ensure_ascii=False,
                         separators=(", ", ": "))
    assert pl.serialisation_canonique(temoin) == attendu


def test_o4_la_charge_est_construite_par_selection_POSITIVE(sortie):
    """Une clé neuve n'entre dans l'empreinte que si quelqu'un l'y met délibérément."""
    charge = pl.payload_e2e(sortie)
    assert set(charge) == set(pl.CLES_PAYLOAD_E2E)
    avant = pl.content_sha256_e2e(sortie)
    # Une clé hors charge ne déplace pas l'empreinte...
    assert pl.content_sha256_e2e(dict(sortie, une_cle_neuve={"t": 1})) == avant
    # ... et une clé DANS la charge la déplace.
    dores = sortie["golden_records"]
    assert dores, "sortie sans enregistrement dore : le controle serait vide"
    mute = [dict(dores[0], record_id="ZZZ_MUTE")] + list(dores[1:])
    assert pl.content_sha256_e2e(dict(sortie, golden_records=mute)) != avant


def test_o4_les_seuils_et_la_methode_entrent_dans_l_empreinte(sortie):
    """Changer de point DOIT déplacer l'empreinte : sinon l'empreinte ne dit pas la décision.

    Les DEUX niveaux sont éprouvés — les seuils, et la façon dont ils ont été obtenus. Le
    second manquait : `methode`, `provisoire` et `gap` n'entraient pas dans la charge, si
    bien que deux chaînes dont l'une annonce des seuils PROVISOIRES et l'autre des
    seuils calibrés auraient rendu la même empreinte. Un commentaire affirmait le contraire ;
    ce test est ce qui rend l'affirmation vérifiable au lieu de la laisser à la lecture.
    """
    avant = pl.content_sha256_e2e(sortie)

    rapport = dict(sortie["rapport"])
    rapport["point"] = dict(rapport["point"], t_mu=rapport["point"]["t_mu"] + 1.0)
    assert pl.content_sha256_e2e(dict(sortie, rapport=rapport)) != avant, "seuil ignore"

    for cle, valeur in (("methode", "une autre methode"), ("provisoire", False),
                        ("gap", None)):
        rapport = dict(sortie["rapport"])
        point = dict(rapport["point"])
        point["provenance"] = dict(point.get("provenance") or {}, **{cle: valeur})
        rapport["point"] = point
        assert pl.content_sha256_e2e(dict(sortie, rapport=rapport)) != avant, (
            f"changer `{cle}` ne deplace pas l'empreinte : un changement de DECISION "
            f"passerait inapercu")

    # ... et le CONTEXTE, lui, ne doit PAS la déplacer : une empreinte qui bouge au
    # déplacement d'un fichier ne prouve plus rien.
    rapport = dict(sortie["rapport"])
    point = dict(rapport["point"])
    point["provenance"] = dict(point.get("provenance") or {}, chemin="ailleurs/dims.json")
    rapport["point"] = point
    assert pl.content_sha256_e2e(dict(sortie, rapport=rapport)) == avant, (
        "un chemin de fichier entre dans l'empreinte : elle cesse d'etre portable")


def test_o4_from_seed_la_graine_seule_determine_l_empreinte():
    """`from-seed -> content_sha256`, littéralement : d'une GRAINE, une empreinte.

    Le générateur est appelé ICI, dans le test, et jamais depuis `src/pipeline/` : il
    PRODUIT la vérité terrain, et l'importer dans la chaîne mettrait un producteur
    d'étiquettes à l'intérieur du chemin de décision. La projection sur `records` est faite
    à la frontière, exactement comme le fait `derive_dimensions.charge_records` pour la fixture.

    Deux graines DIFFÉRENTES doivent donner deux empreintes différentes : sans ce second
    volet, une empreinte constante — le défaut le plus bête et le plus indétectable —
    passerait le test.
    """
    from generator import generate_pack

    with open(_VECTEURS, encoding="utf-8") as fh:
        transcription = json.load(fh)

    def _depuis_graine(graine):
        pack = generate_pack(graine, n_entities=40)
        recs = pack["records"]
        point, _ = pl.point_depuis_records(recs)
        sortie = pl.execute_chaine(recs, point, pl.client_substitut_1b(transcription))
        return pl.content_sha256_e2e(sortie)

    a1 = _depuis_graine("U-B7::E2E::seed-0001")
    a2 = _depuis_graine("U-B7::E2E::seed-0001")
    b = _depuis_graine("U-B7::E2E::seed-0002")
    assert a1 == a2, "la meme graine produit deux sorties : determinisme viole"
    assert a1 != b, ("deux graines distinctes produisent la MEME empreinte : l'empreinte "
                     "ne depend pas de la population, elle ne prouve rien")
    assert len(a1) == 64


@pytest.mark.slow
def test_o4_reproductibilite_INTER_PROCESSUS_from_seed(records):
    """CRIT_AUTO_001 — d'une graine, la même empreinte, dans deux processus distincts.

    Deux `PYTHONHASHSEED` DIFFÉRENTS : lancer deux fois le même n'éprouverait rien, puisque
    c'est précisément la variation de l'aléa de hachage qui révèle un parcours d'ensemble
    non trié. C'est le motif déjà employé par `tests/test_engine.py` et
    `tests/test_clustering.py`, repris ici sur la chaîne ENTIÈRE plutôt que sur un étage.
    """
    programme = (
        "import json, os, sys\n"
        "sys.path.insert(0, os.path.join(%r, 'src'))\n"
        "sys.path.insert(0, os.path.join(%r, 'tools'))\n"
        "import pipeline as pl, derive_dimensions as dd\n"
        "records, _ = dd.charge_records(os.path.join(%r, dd.CHEMIN_FIXTURE))\n"
        "point = pl.point_depuis_artefact(pl.CHEMIN_DIMS_V2, racine=%r)\n"
        "with open(os.path.join(%r, 'fixtures', 'llm_review', 'vecteurs_de_test.json'),\n"
        "          encoding='utf-8') as fh:\n"
        "    client = pl.client_substitut_1b(json.load(fh))\n"
        "sortie = pl.execute_chaine(records, point, client)\n"
        "sys.stdout.write(pl.content_sha256_e2e(sortie))\n"
        % ((_REPO_ROOT,) * 5))
    empreintes = []
    for graine in ("0", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=graine, PYTHONIOENCODING="utf-8")
        sortie = subprocess.run([sys.executable, "-c", programme], capture_output=True,
                                text=True, env=env, cwd=_REPO_ROOT)
        assert sortie.returncode == 0, f"processus en echec : {sortie.stderr[-800:]}"
        empreintes.append(sortie.stdout.strip())
    assert len(empreintes[0]) == 64, f"empreinte inattendue : {empreintes[0]!r}"
    assert empreintes[0] == empreintes[1], (
        f"deux processus (PYTHONHASHSEED 0 puis 12345), deux empreintes bout-en-bout : "
        f"determinisme viole -- {empreintes}")


@pytest.mark.slow
def test_o4_reproductibilite_INTER_PROCESSUS_depuis_une_GRAINE():
    """CRIT_AUTO_001, sur le chemin FROM-SEED complet et entre deux processus.

    Le test ci-dessus part de la FIXTURE et du point PUBLIÉ : il n'exerce ni le générateur
    ni la re-dérivation DIMS. Or ce sont exactement les deux étages où un parcours
    d'ensemble non trié se cacherait le plus volontiers — l'un fabrique la population,
    l'autre en dérive des seuils par quantiles. Celui-ci prend donc la promesse au mot :
    graine -> génération -> re-dérivation des seuils -> chaîne -> empreinte, dans deux
    processus aux `PYTHONHASHSEED` DIFFÉRENTS.
    """
    programme = (
        "import json, os, sys\n"
        "sys.path.insert(0, os.path.join(%r, 'src'))\n"
        "from generator import generate_pack\n"
        "import pipeline as pl\n"
        "pack = generate_pack('U-B7::E2E::seed-0001', n_entities=40)\n"
        "records = pack['records']\n"
        "point, _ = pl.point_depuis_records(records)\n"
        "with open(os.path.join(%r, 'fixtures', 'llm_review', 'vecteurs_de_test.json'),\n"
        "          encoding='utf-8') as fh:\n"
        "    client = pl.client_substitut_1b(json.load(fh))\n"
        "sortie = pl.execute_chaine(records, point, client)\n"
        "sys.stdout.write(pl.content_sha256_e2e(sortie))\n"
        % ((_REPO_ROOT,) * 2))
    empreintes = []
    for graine in ("0", "98765"):
        env = dict(os.environ, PYTHONHASHSEED=graine, PYTHONIOENCODING="utf-8")
        res = subprocess.run([sys.executable, "-c", programme], capture_output=True,
                             text=True, env=env, cwd=_REPO_ROOT)
        assert res.returncode == 0, f"processus en echec : {res.stderr[-800:]}"
        empreintes.append(res.stdout.strip())
    assert len(empreintes[0]) == 64, f"empreinte inattendue : {empreintes[0]!r}"
    assert empreintes[0] == empreintes[1], (
        f"from-seed : deux processus (PYTHONHASHSEED 0 puis 98765) produisent deux "
        f"empreintes -- determinisme viole sur le chemin generateur + re-derivation {empreintes}")
