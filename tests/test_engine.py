# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Tests d'unité (cœur du moteur, bloc B2).

Lancement depuis la racine du repo de build : `python -m pytest tests/ -q`
(le `conftest.py` de la racine ajoute `src/` au `sys.path` — src-layout sans installation).

**Non-circularité.** Ces tests ne lisent JAMAIS la vérité terrain. Le chargeur
`records_fx001()` ne rend que le tableau `records` de la fixture : les tableaux
`ground_truth`, `corruption_annotation` et `zone_intention_design` ne sont pas exposés,
et rien ici ne les nomme comme source d'attente. `zone_intention_design` est écarté au
même titre : c'est une annotation d'intention de conception, donc de la vérité déguisée —
s'en servir ferait de la DoD un test circulaire. Aucune métrique de qualité (P/R/F) n'est
calculée ici : c'est l'objet du scoreur, indépendant par construction.

**Paramètres non calibrés.** Les cutoffs et les seuils sont des placeholders déclarés.
Les tests qui portent sur la décision dérivent donc leurs seuils de la
distribution observée, plutôt que de dépendre des valeurs par défaut : ils resteront
valides après la calibration au lieu de casser silencieusement.
"""
import ast
import copy
import json
import os
import re
import subprocess
import sys

import pytest

from engine import (ACCORD_FORT, ACCORD_PARTIEL, DESACCORD, INDETERMINE_MANQUANT,
                    MATCH, NON_MATCH, ZONE_GRISE, NIVEAUX, VERDICTS, COMPOSANTES,
                    ParametresMoteur, execute_moteur, sortie_canonique)
from engine import blocking as blk
from engine import compare as cmp
from engine import decide as dec
from engine import normalize as nrm

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_SRC = os.path.join(_REPO_ROOT, "src")
_FIXTURE_CANDIDATES = [
    os.environ.get("GEN_FIXTURE", ""),
    os.path.join(_REPO_ROOT, "fixtures", "FIXTURE_PACK_GT_V1_1.json"),
]
#: Les six modules du bloc B2 d'origine. Les mandats ultérieurs ajoutent les leurs
#: ci-dessous, nommément : la zone moteur s'agrandit par édition délibérée, jamais par
#: tolérance en bloc.
_MODULES_B2 = ("__init__.py", "normalize.py", "blocking.py",
               "compare.py", "decide.py", "engine.py")
#: Modules ajoutés à la zone moteur par les mandats ULTÉRIEURS au cœur décisionnel. Ils sont
#: listés NOMMÉMENT plutôt que tolérés en bloc : l'inventaire de `src/engine/` est clos, donc
#: aucun module ne peut y apparaître sans une édition délibérée de ce test.
_MODULES_DIMS = ("threshold_sizing.py",)
_MODULES_U_B4 = ("clustering.py", "fusion.py")
_MODULES_U_B3 = ("llm_client.py", "llm_review.py")
#: Exigés présents, et couverts par les oracles structurels comme le cœur l'est.
_MODULES_MOTEUR = _MODULES_B2 + _MODULES_DIMS + _MODULES_U_B4
#: Inventaire CLOS de `src/engine/` : 11 modules, revue de zone grise comprise.
_MODULES_ENGINE_ATTENDUS = _MODULES_MOTEUR + _MODULES_U_B3

#: Surface publique du paquet `engine`, GELÉE. La revue du doute n'y figure pas :
#: elle s'importe nommément. Geler la liste rend la proposition « la surface du moteur est
#: inchangée » vérifiable, au lieu de la laisser à l'appréciation d'un relecteur.
#:
#: ÉTENDUE de 37 à 69 noms, jamais réduite. Les 32 ajouts ne réexportent PAS la revue de
#: zone grise (qui reste hors surface) : 30 sont les exports de `clustering` et `fusion`, et 2
#: — `PASSES_DEFAUT`, `PASSES_RETIREES_DU_DEFAUT` — ceux que O0a a ajoutés à
#: `blocking` en sortant `SDX_NOM` du jeu de passes par défaut. `SDX_NOM` lui-même n'a
#: jamais été un export : c'est une clé de passe de blocking, sortie du DÉFAUT et restée
#: explicitement demandable — la surface n'a donc rien à en retirer.
#: L'ordre est celui de `engine.__all__` : l'égalité gelée porte sur un tuple, donc sur
#: l'ordre autant que sur le contenu.
_SURFACE_PUBLIQUE_GELEE = (
    "ParametresMoteur", "execute_moteur", "sortie_canonique",
    "ATTRIBUTS_COMPARE", "normalise_record", "normalise_records",
    "genere_paires_candidates", "soundex", "cles_de_blocking",
    "PASSES_DEFAUT", "PASSES_RETIREES_DU_DEFAUT",
    "ACCORD_FORT", "ACCORD_PARTIEL", "DESACCORD", "INDETERMINE_MANQUANT",
    "NIVEAUX", "NIVEAUX_INFORMATIFS", "COMPOSANTES",
    "composantes", "vecteur_comparaison", "vecteurs_comparaison",
    "MATCH", "NON_MATCH", "ZONE_GRISE", "VERDICTS", "GRAINE_EM_SCELLEE",
    "estime_m_u", "oriente_classes", "table_de_poids", "agregat", "verdict_3_zones",
    "correspondance", "correspondances",
    "FRONTIERE_NEUTRE", "BUDGET_REVUE_DEFAUT", "budget_depuis_debit",
    "statistiques_r", "dimensionne_seuils", "dimensionne_depuis_correspondances",
    "cle_paire", "est_liante", "aretes_liantes", "univers_depuis_records",
    "cloture_transitive", "couverture_transitive",
    "MAJORITE", "COMPLETUDE", "SOURCE_PRIORITAIRE", "ORDRE_CANONIQUE", "REGLES",
    "REGLE_TERMINALE", "AUCUN_CANDIDAT", "CANDIDAT_UNIQUE", "MOTIFS", "CODES_SELECTION",
    "POLITIQUE_DEFAUT", "POLITIQUE_COMPLETUDE_DABORD", "PARAMETRES_NON_CALIBRES",
    "valide_politique", "valeurs_candidates", "regle_majorite", "regle_completude",
    "regle_source_prioritaire", "regle_ordre_canonique", "forme_retenue",
    "arbitre_attribut", "trace_selection", "consolide_entite", "consolide_partition",
)


def _chemin_fixture():
    tentes = []
    for p in _FIXTURE_CANDIDATES:
        if not p:
            continue
        tentes.append(os.path.normpath(p))
        if os.path.exists(p):
            return p
    raise AssertionError(
        "FIXTURE_PACK_GT_V1_1.json introuvable (jeu d'entrée). "
        "Chemins essayés : " + " | ".join(tentes))


def records_fx001():
    """Les 18 SOURCE_RECORD de FX_001 — et RIEN d'autre (garde de non-circularité,
    cf. docstring du module)."""
    with open(_chemin_fixture(), encoding="utf-8") as fh:
        return json.load(fh)["records"]


@pytest.fixture(scope="module")
def records():
    return records_fx001()


@pytest.fixture(scope="module")
def resultat(records):
    return execute_moteur(records)


# ============================ 1. Normalisation ======================================
def test_normalisation_pure_et_deterministe(records):
    """Cas 1 : la normalisation est pure (n'altère pas l'entrée) et reproductible."""
    avant = copy.deepcopy(records)
    premier = nrm.normalise_records(records)
    second = nrm.normalise_records(records)
    assert premier == second, "normalisation non reproductible sur la même entrée"
    assert records == avant, "la normalisation a muté son entrée (effet de bord)"
    # Garde anti-vacuité : une normalisation qui rendrait tout à None passerait le test ci-dessus.
    assert any(n["nom"] for n in premier), "aucune valeur normalisée : oracle vide"


def test_normalisation_replie_casse_accents_et_ponctuation():
    """Cas 1 : casse, accents et ponctuation ne distinguent plus deux formes d'un même nom."""
    assert nrm.nom("DUBOIS") == nrm.nom("Dubois") == "dubois"
    assert nrm.ville("PARIS") == nrm.ville("Paris") == "paris"
    assert nrm.adresse("3 r. du Marché") == nrm.adresse("3 rue du Marche") == "3 rue du marche"
    assert nrm.email("Marie.Dubois@example.fr") == "marie.dubois@example.fr"
    # La ponctuation SÉPARE (elle n'est pas supprimée) : « Jean-Pierre » ne devient pas un mot.
    assert nrm.prenom("Jean-Pierre") == "jean pierre"


def test_normalisation_abreviations_de_voie():
    """Cas 1 : les abréviations de voie du mandat §2 sont dépliées, token à token."""
    assert nrm.adresse("5 av. Victor Hugo") == nrm.adresse("5 avenue Victor Hugo")
    assert nrm.adresse("17 bd de la République") == nrm.adresse("17 boulevard de la Republique")
    assert nrm.adresse("2 imp. des Lilas") == "2 impasse des lilas"
    # L'expansion ne mord JAMAIS en sous-chaîne : « bdx » n'est pas un boulevard.
    assert nrm.adresse("4 bdx machin") == "4 bdx machin"


def test_normalisation_formes_juridiques_et_sigles():
    """Cas 1 : « SARL X » et « X S.A.R.L. » désignent la même entité après normalisation."""
    assert nrm.nom("SARL Boulangerie du Coin") == nrm.nom("Boulangerie du Coin S.A.R.L.")
    # Garde : un nom réduit à sa seule forme juridique n'est pas rendu manquant.
    assert nrm.nom("SARL") == "sarl"


def test_normalisation_telephone_et_date():
    """Cas 1 : téléphones et dates convergent vers une forme unique et déterministe."""
    formes = {"01 45 67 89 01", "0145678901", "+33 1 45 67 89 01", "0033145678901"}
    assert len({nrm.telephone(f) for f in formes}) == 1
    assert nrm.telephone("01 45 67 89 01") == "0145678901"
    assert nrm.date_naissance("12/03/1985") == nrm.date_naissance("1985-03-12") == "1985-03-12"
    # Une chaîne non reconnue n'est jamais devinée : elle est rendue en forme texte.
    assert nrm.date_naissance("mars 1985") == "mars 1985"
    assert nrm.telephone(None) is None and nrm.date_naissance(None) is None


def test_normalisation_projette_defensivement(records):
    """Non-circularité structurelle : une colonne surnuméraire n'atteint jamais le moteur."""
    pollue = dict(records[0])
    pollue["colonne_interdite"] = "valeur qui ne doit pas franchir la frontière"
    normalise = nrm.normalise_record(pollue)
    assert set(normalise) == {"record_id", "source_id", *nrm.ATTRIBUTS_COMPARE}
    assert "colonne_interdite" not in normalise


# ============================ 2. Blocking ===========================================
def test_blocking_paires_non_ordonnees_sans_auto_paire(records):
    """Cas 2 : `a < b` strict, aucune auto-paire, aucun doublon de paire, origine tracée."""
    paires = blk.genere_paires_candidates(nrm.normalise_records(records))["paires"]
    assert paires, "aucune paire candidate : oracle vide"
    vues = set()
    for p in paires:
        a, b = p["record_id_a"], p["record_id_b"]
        assert a < b, f"paire non ordonnée ou auto-paire : {a} / {b}"
        assert (a, b) not in vues, f"paire produite deux fois : {a} / {b}"
        vues.add((a, b))
        assert p["bloc_origine"], f"paire sans bloc_origine tracé : {a} / {b}"
        assert p["bloc_origine"] == sorted(p["bloc_origine"]), "bloc_origine non trié"


def test_blocking_deterministe(records):
    """Cas 2 : même entrée -> même ensemble de paires, dans le même ordre."""
    normalises = nrm.normalise_records(records)
    assert (blk.genere_paires_candidates(normalises)
            == blk.genere_paires_candidates(normalises))
    # ... y compris si l'ordre des enregistrements en entrée change.
    inverse = blk.genere_paires_candidates(list(reversed(normalises)))["paires"]
    direct = blk.genere_paires_candidates(normalises)["paires"]
    assert inverse == direct, "le blocking dépend de l'ordre d'entrée"


def test_blocking_union_des_passes(records):
    """Cas 2 : une paire trouvée par plusieurs passes conserve TOUTES ses provenances."""
    paires = blk.genere_paires_candidates(nrm.normalise_records(records))["paires"]
    multi = [p for p in paires if len(p["bloc_origine"]) > 1]
    assert multi, "aucune paire multi-passes : l'union des passes n'est pas éprouvée"
    passes_vues = {o.split(":", 1)[0] for p in paires for o in p["bloc_origine"]}
    assert passes_vues == set(blk.PASSES_DEFAUT), (
        f"passes inertes : attendu {set(blk.PASSES_DEFAUT)}, observé {passes_vues}")


def test_blocking_cle_absente_ne_forme_pas_de_seau(records):
    """Cas 2 : un record sans nom est ÉCARTÉ des passes nominales, jamais mis en seau « vide ».

    Sans cette règle, tous les enregistrements dépourvus de nom seraient appariés entre eux.
    """
    anonymes = [{"record_id": f"AN_{i}", "source_id": "SRC_A", "nom": None, "prenom": None,
                 "date_naissance": None, "adresse": None, "code_postal": str(10000 + i),
                 "ville": None, "email": None, "telephone": None} for i in range(5)]
    res = blk.genere_paires_candidates(nrm.normalise_records(anonymes))
    assert res["paires"] == [], f"seau de clés vides formé : {res['paires']}"
    assert blk.soundex(None) is None and blk.soundex("") is None
    assert blk.cle_prefixe({"nom": None, "prenom": "marie"}) is None


def test_soundex_regroupe_les_variantes_phonetiques():
    """Cas 2 : le code phonétique fait son travail de CLÉ (et rien d'autre)."""
    assert blk.soundex("lefevre") == blk.soundex("lefebvre")
    assert blk.soundex("benali") == blk.soundex("ben ali")   # segmentation ignorée
    assert blk.soundex("dubois") != blk.soundex("moreau")    # garde anti-vacuité
    assert len(blk.soundex("dubois")) == blk.SOUNDEX_LONGUEUR


# ============================ 3. Comparateurs =======================================
def test_noyaux_de_similarite():
    """Les noyaux écrits à la main respectent leurs propriétés élémentaires."""
    assert cmp.jaro_winkler("martin", "martin") == 1.0
    assert cmp.jaro_winkler("", "") == 1.0
    assert cmp.jaro_winkler("martin", "") == 0.0
    assert cmp.jaro_winkler("dubois", "duboi") == cmp.jaro_winkler("duboi", "dubois")
    assert 0.0 < cmp.jaro_winkler("dubois", "duboi") < 1.0
    assert cmp.jaro_winkler("dubois", "duboi") > cmp.jaro_winkler("dubois", "moreau")
    assert cmp.levenshtein("fontaine", "fontane") == 1
    assert cmp.levenshtein("abc", "abc") == 0 and cmp.levenshtein("", "abc") == 3
    assert cmp.dice_qgrammes("rue des lilas", "rue des lilas") == 1.0
    assert 0.0 <= cmp.dice_qgrammes("rue nationale", "chemin des vignes") < 0.5


def test_vecteur_8_composantes_dans_enum_fermee(resultat, records):
    """Cas 3 : exactement 8 composantes `accord_<attribut>`, chacune dans l'énum fermée."""
    normalises = nrm.normalise_records(records)
    index = {n["record_id"]: n for n in normalises}
    paires = blk.genere_paires_candidates(normalises)["paires"]
    vecteurs = cmp.vecteurs_comparaison(paires, index)
    assert vecteurs, "aucun vecteur de comparaison : oracle vide"
    attendues = {"accord_" + a for a in nrm.ATTRIBUTS_COMPARE}
    for v in vecteurs:
        presentes = {k for k in v if k.startswith("accord_")}
        assert presentes == attendues, f"composantes inattendues : {presentes ^ attendues}"
        assert len(cmp.composantes(v)) == 8
        for cle, niveau in cmp.composantes(v).items():
            assert niveau in NIVEAUX, f"{cle} hors énumération fermée : {niveau!r}"
    assert set(COMPOSANTES) == attendues


def test_indetermine_sur_champ_nul(records):
    """Cas 3 : un champ nul d'un seul côté donne INDETERMINE_MANQUANT — pas un désaccord."""
    index = {n["record_id"]: n for n in nrm.normalise_records(records)}
    # REC_0003 n'a pas d'email ; REC_0001 en a un.
    v = cmp.vecteur_comparaison({"record_id_a": "REC_0001", "record_id_b": "REC_0003"}, index)
    assert index["REC_0003"]["email"] is None and index["REC_0001"]["email"] is not None
    assert v["accord_email"] == INDETERMINE_MANQUANT
    assert v["similarites"]["email"] is None
    # Garde anti-vacuité : les champs renseignés des deux côtés, eux, sont déterminés.
    assert v["accord_nom"] != INDETERMINE_MANQUANT
    assert v["accord_telephone"] == ACCORD_FORT


def test_cutoffs_appliques_dans_le_bon_sens():
    """Cas 3 : le mapping s -> niveau suit exactement les cutoffs (bornes comprises)."""
    assert cmp.niveau(0.95, 0.90, 0.70) == ACCORD_FORT
    assert cmp.niveau(0.90, 0.90, 0.70) == ACCORD_FORT      # borne haute incluse
    assert cmp.niveau(0.80, 0.90, 0.70) == ACCORD_PARTIEL
    assert cmp.niveau(0.70, 0.90, 0.70) == ACCORD_PARTIEL    # borne basse incluse
    assert cmp.niveau(0.69, 0.90, 0.70) == DESACCORD
    assert cmp.niveau(None, 0.90, 0.70) == INDETERMINE_MANQUANT


# ============================ 4-5. EM, poids et agrégat =============================
def _vecteurs_fx001(records):
    normalises = nrm.normalise_records(records)
    index = {n["record_id"]: n for n in normalises}
    paires = blk.genere_paires_candidates(normalises)["paires"]
    return cmp.vecteurs_comparaison(paires, index)


def test_em_deterministe_a_graine_scellee(records):
    """Cas 4 : à graine scellée, deux estimations donnent les MÊMES m/u/p."""
    vecteurs = _vecteurs_fx001(records)
    a = dec.estime_m_u(vecteurs)
    b = dec.estime_m_u(vecteurs)
    assert a["m"] == b["m"] and a["u"] == b["u"] and a["p"] == b["p"]
    assert a["iterations"] == b["iterations"]
    # Garde anti-vacuité : un EM qui se replierait aurait aussi deux sorties identiques.
    assert a["convergence"] and not a["repli"], (
        f"l'EM ne converge pas sur FX_001 : {a['motif_repli']}")
    assert a["graine"] == dec.GRAINE_EM_SCELLEE
    # Garde de sensibilité aux DONNÉES : un estimateur qui renverrait toujours ses a priori
    # serait lui aussi parfaitement « déterministe ». Il doit apprendre, et donc bouger.
    assert any(a["m"][j] != dec.PRIORS_M for j in nrm.ATTRIBUTS_COMPARE), (
        "les tables estimées sont restées les a priori : l'EM n'a rien appris")
    assert dec.estime_m_u(vecteurs[:-1])["m"] != a["m"], (
        "l'estimation ne réagit pas au retrait d'une paire : elle ne dépend pas des données")


def test_em_graine_derivee_sans_hash_sale():
    """Cas 4 : la graine entière vient de SHA-256, donc elle est stable d'un processus à l'autre."""
    assert dec.graine_entiere("abc") == dec.graine_entiere("abc")
    assert dec.graine_entiere("abc") != dec.graine_entiere("abd")
    # Valeur figée : elle ne doit pas dépendre du PYTHONHASHSEED du processus.
    assert dec.graine_entiere(dec.GRAINE_EM_SCELLEE) == (
        int(__import__("hashlib").sha256(dec.GRAINE_EM_SCELLEE.encode("utf-8")).hexdigest(), 16)
        % (2 ** 32))


def test_em_repli_trace_si_non_convergence(records):
    """Cas 4 : la non-convergence déclenche un repli SUR LES A PRIORI, et le DIT.

    Le budget d'itérations est un paramètre de production, pas une trappe de test : le
    réduire éprouve le chemin de repli réel, sans altérer le code du moteur ni affaiblir
    quoi que ce soit.
    """
    vecteurs = _vecteurs_fx001(records)
    # `tolerance=0.0` rend la convergence IMPOSSIBLE par construction (l'écart entre deux
    # itérations est toujours >= 0), donc la route de repli est atteinte à coup sûr — plutôt
    # qu'avec une tolérance minuscule qu'un pas de chance pourrait franchir.
    replie = dec.estime_m_u(vecteurs, max_iter=3, tolerance=0.0)
    assert replie["repli"] is True
    assert replie["convergence"] is False
    assert replie["motif_repli"], "repli non motivé : il serait appliqué en silence"
    assert "non-convergence" in replie["motif_repli"]
    # La trace dit le travail RÉELLEMENT fourni : annoncer 0 itération serait un faux témoignage.
    assert replie["iterations"] == 3, f"itérations mal tracées : {replie['iterations']}"
    assert replie["provenance_priors"], "a priori sans provenance déclarée"
    for j in nrm.ATTRIBUTS_COMPARE:
        assert replie["m"][j] == dec.PRIORS_M and replie["u"][j] == dec.PRIORS_U
    # Épreuve croisée : le repli doit être DISTINCT de l'estimation convergée, sans quoi
    # « se replier » et « estimer » seraient indiscernables et le test ne prouverait rien.
    assert replie["m"] != dec.estime_m_u(vecteurs)["m"]


def test_em_repli_si_paires_insuffisantes(records):
    """Cas 4 : sous le seuil d'identifiabilité, on se replie plutôt que d'inventer."""
    maigre = dec.estime_m_u(_vecteurs_fx001(records)[:2])
    assert maigre["repli"] is True and "insuffisantes" in maigre["motif_repli"]


def test_em_repli_par_champ_jamais_observe(records):
    """Cas 4 : un attribut jamais observé reçoit les a priori — et figure dans `champs_repli`."""
    vecteurs = copy.deepcopy(_vecteurs_fx001(records))
    for v in vecteurs:
        v["accord_email"] = INDETERMINE_MANQUANT
        v["similarites"]["email"] = None
    est = dec.estime_m_u(vecteurs)
    assert not est["repli"], "l'EM global ne devrait pas se replier ici"
    assert "email" in est["champs_repli"]
    assert est["m"]["email"] == dec.PRIORS_M and est["u"]["email"] == dec.PRIORS_U
    # Garde anti-vacuité : les autres champs, eux, sont bien estimés (donc différents des a priori).
    assert any(est["m"][j] != dec.PRIORS_M
               for j in nrm.ATTRIBUTS_COMPARE if j != "email")


def test_poids_nul_sur_indetermine(records):
    """Cas 5 : `w = 0` sur INDETERMINE_MANQUANT — une absence n'apporte aucune preuve."""
    est = dec.estime_m_u(_vecteurs_fx001(records))
    poids = dec.table_de_poids(est["m"], est["u"])
    for j in nrm.ATTRIBUTS_COMPARE:
        assert poids[j][INDETERMINE_MANQUANT] == 0.0
        assert set(poids[j]) == set(NIVEAUX)
    # Garde anti-vacuité : une table entièrement nulle satisferait aussi l'assertion ci-dessus.
    assert any(poids[j][l] != 0.0
               for j in nrm.ATTRIBUTS_COMPARE for l in cmp.NIVEAUX_INFORMATIFS)


def test_poids_bornes_par_le_lissage(records):
    """Cas 5 : le lissage de Dirichlet borne |w| — aucun poids infini ni NaN."""
    import math
    vecteurs = _vecteurs_fx001(records)
    est = dec.estime_m_u(vecteurs)
    poids = dec.table_de_poids(est["m"], est["u"])
    borne = math.log2((len(vecteurs) + dec.PSEUDO_COMPTE_DIRICHLET)
                      / dec.PSEUDO_COMPTE_DIRICHLET)
    for j in nrm.ATTRIBUTS_COMPARE:
        for l in cmp.NIVEAUX_INFORMATIFS:
            w = poids[j][l]
            assert math.isfinite(w), f"poids non fini sur {j}/{l}"
            assert abs(w) <= borne + 1e-9, f"|w|={abs(w)} dépasse la borne annoncée {borne}"


def test_agregat_est_la_somme_des_poids(resultat):
    """Cas 5 : `R = Σ_j w_j`, et les composantes indéterminées y contribuent pour zéro."""
    assert resultat["correspondances"], "aucune correspondance : oracle vide"
    for corr in resultat["correspondances"]:
        contributions = corr["poids_par_champ"]
        assert set(contributions) == set(nrm.ATTRIBUTS_COMPARE)
        somme = round(sum(contributions[j] for j in nrm.ATTRIBUTS_COMPARE),
                      dec.DECIMALES_POIDS)
        assert somme == corr["poids_match"], (
            f"{corr['record_id_a']}/{corr['record_id_b']} : R={corr['poids_match']} "
            f"mais Σw={somme}")
        for j in nrm.ATTRIBUTS_COMPARE:
            if corr["composantes"]["accord_" + j] == INDETERMINE_MANQUANT:
                assert contributions[j] == 0.0
    # Garde anti-vacuité : au moins une paire porte réellement une composante indéterminée.
    assert any(INDETERMINE_MANQUANT in c["composantes"].values()
               for c in resultat["correspondances"])


# ============================ 6. Décision 3 zones ===================================
def test_verdict_3_zones_bornes():
    """Cas 6 : `R > Tμ` -> MATCH, `R < Tλ` -> NON_MATCH, bornes incluses -> ZONE_GRISE."""
    assert dec.verdict_3_zones(2.0, t_mu=1.0, t_lambda=-1.0) == MATCH
    assert dec.verdict_3_zones(-2.0, t_mu=1.0, t_lambda=-1.0) == NON_MATCH
    assert dec.verdict_3_zones(0.0, t_mu=1.0, t_lambda=-1.0) == ZONE_GRISE
    assert dec.verdict_3_zones(1.0, t_mu=1.0, t_lambda=-1.0) == ZONE_GRISE
    assert dec.verdict_3_zones(-1.0, t_mu=1.0, t_lambda=-1.0) == ZONE_GRISE
    with pytest.raises(ValueError):
        dec.verdict_3_zones(0.0, t_mu=-1.0, t_lambda=1.0)


def test_les_3_verdicts_sont_atteignables(records, resultat):
    """Cas 6 : les 3 verdicts sont atteignables sur des données réelles.

    Les seuils sont DÉRIVÉS de la distribution des R observée, et non des placeholders par
    défaut : le test éprouve donc la mécanique de partition en trois zones, et il survivra
    à la calibration au lieu de casser dès que les seuils bougeront.
    """
    valeurs = sorted({c["poids_match"] for c in resultat["correspondances"]})
    assert len(valeurs) >= 3, "moins de 3 valeurs de R distinctes : partition non éprouvable"
    parametres = ParametresMoteur(t_lambda=valeurs[1], t_mu=valeurs[-2])
    rendus = execute_moteur(records, parametres)["correspondances"]
    obtenus = {c["verdict"] for c in rendus}
    assert obtenus == set(VERDICTS), f"verdicts inatteignables : {set(VERDICTS) - obtenus}"


def test_cardinalite_une_correspondance_par_paire(records, resultat):
    """Cas 6 : exactement UNE CORRESPONDENCE par CANDIDATE_PAIR."""
    paires = blk.genere_paires_candidates(nrm.normalise_records(records))["paires"]
    attendues = [(p["record_id_a"], p["record_id_b"]) for p in paires]
    obtenues = [(c["record_id_a"], c["record_id_b"]) for c in resultat["correspondances"]]
    assert obtenues == attendues, "les correspondances ne suivent pas 1-1 les paires"
    assert len(obtenues) == len(set(obtenues)), "une paire porte plusieurs correspondances"
    for corr in resultat["correspondances"]:
        assert corr["verdict"] in VERDICTS
        assert corr["record_id_a"] < corr["record_id_b"]


def test_revue_zone_grise_ssi_zone_grise(records, resultat):
    """Cas 6 : `revue_zone_grise` est renseigné SI ET SEULEMENT SI le verdict est ZONE_GRISE."""
    valeurs = sorted({c["poids_match"] for c in resultat["correspondances"]})
    parametres = ParametresMoteur(t_lambda=valeurs[1], t_mu=valeurs[-2])
    rendus = execute_moteur(records, parametres)["correspondances"]
    for corr in rendus:
        renseigne = corr["revue_zone_grise"] is not None
        assert renseigne == (corr["verdict"] == ZONE_GRISE), (
            f"{corr['record_id_a']}/{corr['record_id_b']} : verdict={corr['verdict']} "
            f"mais revue_zone_grise renseigné={renseigne}")
        if renseigne:
            # Laissé en attente : l'instruction du doute revient à la revue de zone grise.
            assert corr["revue_zone_grise"]["statut"] == "en_attente"
            assert corr["revue_zone_grise"]["decision"] is None
    # Garde anti-vacuité : l'équivalence doit être éprouvée dans LES DEUX sens.
    verdicts = {c["verdict"] for c in rendus}
    assert ZONE_GRISE in verdicts and verdicts - {ZONE_GRISE}


def test_aucune_paire_sans_preuve_ne_peut_etre_match(resultat):
    """Cas 6 (R-20) : une paire dont AUCUN champ n'est informatif ne peut pas être MATCH.

    Le test place volontairement les seuils de façon à ce que `R = 0` tomberait DANS la
    zone MATCH sans la garde : c'est la seule manière de prouver que la garde agit, plutôt
    que d'observer une abstention qui viendrait des seuils par défaut.
    """
    vecteur_aveugle = {"record_id_a": "REC_X", "record_id_b": "REC_Y", "bloc_origine": [],
                       **{"accord_" + j: INDETERMINE_MANQUANT for j in nrm.ATTRIBUTS_COMPARE}}
    poids = dec.table_de_poids(*dec._tables_a_priori())
    corr = dec.correspondance(vecteur_aveugle, poids, t_mu=-100.0, t_lambda=-200.0)
    assert corr["poids_match"] == 0.0
    assert corr["n_composantes_informatives"] == 0
    assert corr["garde_r20_appliquee"] is True
    assert corr["verdict"] != MATCH, "paire sans aucune preuve déclarée MATCH (R-20 violé)"
    # Contre-épreuve : sans la garde, ces seuils DONNERAIENT bien MATCH.
    assert dec.verdict_3_zones(0.0, t_mu=-100.0, t_lambda=-200.0) == MATCH
    # Et sur le jeu réel, aucune correspondance MATCH n'est dépourvue de preuve.
    for c in resultat["correspondances"]:
        if c["n_composantes_informatives"] == 0:
            assert c["verdict"] != MATCH


# ============================ 7. Déterminisme d'ensemble ============================
_SCRIPT_ENFANT = """\
import json, sys
sys.path.insert(0, {src!r})
import engine
with open({fixture!r}, encoding='utf-8') as fh:
    records = json.load(fh)['records']
sortie = engine.sortie_canonique(engine.execute_moteur(records))
sys.stdout.buffer.write(sortie.encode('utf-8'))
"""


def test_determinisme_inter_processus(tmp_path, records, resultat):
    """Cas 7 : deux PROCESSUS distincts produisent une sortie canonique identique.

    Les deux processus tournent sous des `PYTHONHASHSEED` **DIFFÉRENTS**. Lancer deux fois
    la même graine de hachage rendrait le test aveugle à sa propre cible : le `hash()` des
    chaînes est salé par processus, donc un moteur qui en dépendrait produirait quand même
    deux sorties identiques sous une graine commune, et le test passerait au vert en ne
    prouvant rien. Faire varier la graine est ce qui rend l'assertion mordante.

    L'enfant écrit sur `stdout.buffer` en UTF-8 explicite : sur cette plateforme, la couche
    texte par défaut est en cp1252 et lèverait `UnicodeEncodeError` sur un accent.
    """
    script = tmp_path / "run_moteur.py"
    script.write_text(_SCRIPT_ENFANT.format(src=_SRC, fixture=_chemin_fixture()),
                      encoding="utf-8")
    graines_de_hachage = ("0", "12345")
    sorties = []
    for graine in graines_de_hachage:
        env = dict(os.environ, PYTHONHASHSEED=graine, PYTHONIOENCODING="utf-8")
        proc = subprocess.run([sys.executable, str(script)], capture_output=True, env=env)
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
        sorties.append(proc.stdout)
    assert sorties[0], "sortie enfant vide : oracle vide"
    assert sorties[0] == sorties[1], (
        f"deux processus (PYTHONHASHSEED {graines_de_hachage[0]} puis "
        f"{graines_de_hachage[1]}), deux sorties : déterminisme violé")
    # Et l'exécution en cours coïncide avec celle des enfants.
    assert sortie_canonique(resultat).encode("utf-8") == sorties[0]


def test_determinisme_intra_processus(records):
    """Cas 7 : deux exécutions successives dans le même processus sont identiques."""
    assert sortie_canonique(execute_moteur(records)) == sortie_canonique(execute_moteur(records))


# ============================ 8. Comportemental (sans vérité terrain) ===============
def test_le_moteur_ordonne_les_paires_par_ressemblance(records, resultat):
    """Cas 8 : `R` d'une paire quasi identique dépasse `R` d'une paire manifestement dissemblable.

    La qualification se lit sur les ENREGISTREMENTS eux-mêmes, jamais sur une annotation
    de vérité : REC_0001 et REC_0002 s'accordent sur les 8 attributs après normalisation ;
    REC_0012 (Rousseau, Claire, Lille) et REC_0013 (Moreau, Luc, Dijon) les contredisent
    tous les 8. Ce second couple ne partage AUCUNE clé de blocking — c'est bien le propre
    d'une paire manifestement dissemblable — donc son vecteur est formé explicitement :
    l'évaluer suppose de le construire, pas de le trouver parmi les candidats.

    L'assertion ne dépend d'AUCUN seuil : elle porte sur l'ordre ET sur le signe de `R`,
    qui doivent tenir quels que soient des placeholders non calibrés. Le signe importe :
    un rapport de vraisemblance positif penche vers le lien, négatif contre lui, et cette
    lecture-là est intrinsèque au modèle, pas au réglage.
    """
    index = {n["record_id"]: n for n in nrm.normalise_records(records)}
    est = dec.estime_m_u(_vecteurs_fx001(records))
    poids = dec.table_de_poids(est["m"], est["u"])
    dissemblable = cmp.vecteur_comparaison(
        {"record_id_a": "REC_0012", "record_id_b": "REC_0013", "bloc_origine": []}, index)
    assert all(dissemblable["accord_" + a] == DESACCORD for a in nrm.ATTRIBUTS_COMPARE), (
        "le pôle dissemblable n'est pas en désaccord sur les 8 attributs : "
        f"{cmp.composantes(dissemblable)}")

    r = {(c["record_id_a"], c["record_id_b"]): c["poids_match"]
         for c in resultat["correspondances"]}
    quasi_identiques = r[("REC_0001", "REC_0002")]
    dissemblables = dec.agregat(dissemblable, poids)
    assert quasi_identiques > dissemblables, (
        f"ordre inversé : R(0001,0002)={quasi_identiques} <= R(0012,0013)={dissemblables}")
    assert quasi_identiques > 0.0 > dissemblables, (
        f"les deux pôles doivent tomber de part et d'autre de zéro : "
        f"{quasi_identiques} et {dissemblables}")

    # Renfort : l'ordre ne tient pas que sur une paire choisie. Toutes les paires dont les
    # 8 attributs observés s'accordent fortement dominent toutes celles qui portent au
    # moins trois désaccords francs.
    accordantes, discordantes = [], []
    for corr in resultat["correspondances"]:
        niveaux = list(corr["composantes"].values())
        if DESACCORD not in niveaux and ACCORD_PARTIEL not in niveaux:
            accordantes.append(corr["poids_match"])
        elif niveaux.count(DESACCORD) >= 3:
            discordantes.append(corr["poids_match"])
    assert accordantes and discordantes, "les deux familles de paires doivent être peuplées"
    assert min(accordantes) > max(discordantes), (
        f"chevauchement : min(accord)={min(accordantes)} <= max(désaccord)={max(discordantes)}")


def test_poids_croit_avec_le_nombre_de_champs_en_accord(records):
    """Cas 8 : ajouter un désaccord ne peut pas faire monter R (monotonie du modèle)."""
    est = dec.estime_m_u(_vecteurs_fx001(records))
    poids = dec.table_de_poids(est["m"], est["u"])
    base = {"record_id_a": "A", "record_id_b": "B", "bloc_origine": [],
            **{"accord_" + j: ACCORD_FORT for j in nrm.ATTRIBUTS_COMPARE}}
    degrade = dict(base, accord_email=DESACCORD)
    assert dec.agregat(base, poids) > dec.agregat(degrade, poids)


def test_le_piege_du_faux_jumeau_est_ecarte(resultat):
    """Cas 8 : deux homonymes à la même adresse ne doivent pas primer sur un vrai doublon.

    REC_0004 et REC_0018 partagent nom, adresse et ville — tout ce qu'un rapprochement
    naïf regarde — mais divergent sur prénom, date de naissance, email et téléphone.
    C'est le piège que le modèle doit trancher ; il est isolé ici, séparé du pôle
    « manifestement dissemblable » du cas 8, qu'il n'est pas.
    """
    r = {(c["record_id_a"], c["record_id_b"]): c["poids_match"]
         for c in resultat["correspondances"]}
    composantes_piege = {c["record_id_a"] + c["record_id_b"]: c["composantes"]
                         for c in resultat["correspondances"]}["REC_0004REC_0018"]
    # Le piège est bien un piège : il s'accorde fortement sur plusieurs attributs.
    assert list(composantes_piege.values()).count(ACCORD_FORT) >= 3
    assert r[("REC_0004", "REC_0018")] < r[("REC_0004", "REC_0005")], (
        "l'homonyme à la même adresse pèse autant que le vrai doublon")
    assert r[("REC_0004", "REC_0018")] < 0.0, "le faux jumeau ne penche pas vers l'absence de lien"


def test_orientation_des_classes_est_effective():
    """Cas 4 : la règle d'orientation ÉCHANGE réellement les classes quand il le faut.

    Sur données réelles l'échange ne se produit pratiquement jamais — l'initialisation part
    déjà des a priori dans le bon sens — si bien qu'un test de bout en bout laisserait cette
    branche muette. Elle est donc sollicitée directement, avec des tables où la masse
    d'accord fort est du mauvais côté.
    """
    a_l_envers_m = {j: dict(dec.PRIORS_U) for j in nrm.ATTRIBUTS_COMPARE}
    a_l_envers_u = {j: dict(dec.PRIORS_M) for j in nrm.ATTRIBUTS_COMPARE}
    m, u, p, echange = dec.oriente_classes(a_l_envers_m, a_l_envers_u, 0.2)
    assert echange is True, "l'échange n'a pas eu lieu alors que les classes sont inversées"
    assert m == a_l_envers_u and u == a_l_envers_m, "les tables n'ont pas été échangées"
    assert p == pytest.approx(0.8), "le poids de mélange doit suivre l'échange"
    # Après orientation, l'accord fort pèse POSITIVEMENT : c'est tout l'objet de la règle.
    assert dec.table_de_poids(m, u)["nom"][ACCORD_FORT] > 0.0
    # Contre-épreuve : dans le bon sens, aucun échange et rien n'est touché.
    m2, u2, p2, echange2 = dec.oriente_classes(a_l_envers_u, a_l_envers_m, 0.2)
    assert echange2 is False and m2 == a_l_envers_u and p2 == 0.2


def test_em_repli_si_melange_degenere():
    """Cas 4 : troisième route de repli — les deux classes ne se séparent pas.

    Vingt paires rigoureusement identiques ne portent aucune information de séparation :
    le mélange s'effondre sur une seule classe. Le moteur doit le DIRE, plutôt que de
    livrer des poids tirés d'un optimum dégénéré.
    """
    identiques = [{"record_id_a": f"A{i}", "record_id_b": f"B{i}", "bloc_origine": [],
                   **{"accord_" + j: ACCORD_FORT for j in nrm.ATTRIBUTS_COMPARE}}
                  for i in range(20)]
    est = dec.estime_m_u(identiques)
    assert est["repli"] is True
    assert "degenere" in est["motif_repli"], est["motif_repli"]
    for j in nrm.ATTRIBUTS_COMPARE:
        assert est["m"][j] == dec.PRIORS_M and est["u"][j] == dec.PRIORS_U


def test_blocking_n_est_pas_le_produit_cartesien(records):
    """Cas 2 : le blocking RÉDUIT réellement l'espace des paires.

    Un « blocking » qui rendrait toutes les paires satisferait tous les autres tests
    structurels — ordre, unicité, origine tracée — sans avoir rien bloqué.
    """
    normalises = nrm.normalise_records(records)
    paires = blk.genere_paires_candidates(normalises)["paires"]
    n = len(normalises)
    cartesien = n * (n - 1) // 2
    assert 0 < len(paires) < cartesien, (
        f"{len(paires)} paires sur {cartesien} possibles : le blocking ne bloque rien")
    # Symétrique : il ne doit pas non plus tout jeter — les variantes évidentes survivent.
    couples = {(p["record_id_a"], p["record_id_b"]) for p in paires}
    for attendu in (("REC_0001", "REC_0002"), ("REC_0006", "REC_0007"),
                    ("REC_0008", "REC_0009"), ("REC_0010", "REC_0011")):
        assert attendu in couples, f"variante évidente perdue par le blocking : {attendu}"


def test_comparateurs_symetriques(records):
    """Comparer (a, b) ou (b, a) doit donner la même similarité — sur les 8 attributs."""
    index = {n["record_id"]: n for n in nrm.normalise_records(records)}
    identifiants = sorted(index)
    n_comparaisons = 0
    for i, a in enumerate(identifiants):
        for b in identifiants[i + 1:]:
            for attribut in nrm.ATTRIBUTS_COMPARE:
                va, vb = index[a][attribut], index[b][attribut]
                assert cmp.similarite(attribut, va, vb) == cmp.similarite(attribut, vb, va), (
                    f"{attribut} asymétrique entre {a} et {b}")
                n_comparaisons += 1
    assert n_comparaisons > 500, f"oracle trop maigre : {n_comparaisons} comparaisons"


def test_determinisme_structurel_aucun_alea_non_scelle():
    """Déterminisme structurel : aucune source d'aléa ni de hachage salé hors de la graine scellée.

    `hash()` est salé par processus et `random.<fonction>()` au niveau module puise dans un
    état global non scellé : l'un comme l'autre ruineraient la reproductibilité entre deux
    processus. Seul `random.Random(<graine>)`, instancié explicitement, est admis.
    """
    for nom_fichier, source in _sources_moteur().items():
        for noeud in ast.walk(ast.parse(source)):
            if not isinstance(noeud, ast.Call):
                continue
            fonction = noeud.func
            if isinstance(fonction, ast.Name) and fonction.id == "hash":
                raise AssertionError(f"{nom_fichier} : appel à hash(), salé par processus")
            if (isinstance(fonction, ast.Attribute)
                    and isinstance(fonction.value, ast.Name)
                    and fonction.value.id == "random"):
                assert fonction.attr == "Random", (
                    f"{nom_fichier} : random.{fonction.attr}() puise dans l'état global non scellé")


def test_pas_de_chemin_absolu_os_dans_le_moteur():
    """Chemins relatifs au repo, jamais de chemin absolu propre à un OS."""
    motifs = [r"[A-Za-z]:[\\/]{1,2}[A-Za-z]", r"/(usr|home|etc|var|opt|mnt)/"]
    for nom_fichier, source in _sources_moteur().items():
        for motif in motifs:
            trouve = re.search(motif, source)
            assert not trouve, f"{nom_fichier} : chemin absolu OS -> {trouve.group(0)!r}"


def test_les_tests_eux_memes_ne_lisent_pas_la_verite_terrain():
    """Non-circularité côté DoD : les jetons de vérité terrain n'apparaissent ici QUE
    comme aiguilles.

    Les tests DOIVENT nommer ces jetons — c'est ce qu'ils cherchent dans `src/engine/`. La
    ligne à ne pas franchir est de s'en SERVIR : aucun accès indexé au pack de fixture, et
    un seul point d'entrée de lecture, qui ne rend que `records`.
    """
    with open(__file__, encoding="utf-8") as fh:
        source_du_test = fh.read()
    # L'aiguille est assemblée à l'exécution : écrite en clair, elle se compterait
    # elle-même et l'oracle mesurerait sa propre présence plutôt que celle du chargeur.
    aiguille = "json.load(fh)[" + '"records"' + "]"
    assert source_du_test.count(aiguille) == 1, (
        f"la fixture doit être lue en un seul endroit et n'en rendre que les records "
        f"({source_du_test.count(aiguille)} lectures trouvées)")
    for jeton in ("id_entite_vraie", "ground_truth", "zone_intention_design"):
        assert f'["{jeton}"]' not in source_du_test, f"accès indexé à {jeton} dans les tests"
        assert f"['{jeton}']" not in source_du_test, f"accès indexé à {jeton} dans les tests"


# ============================ 9. Non-circularité / C7 structurels ===================
def _sources_moteur():
    """Contenu des modules de `src/engine/`, avec garde : `_MODULES_MOTEUR` doit exister."""
    dossier = os.path.join(_SRC, "engine")
    assert os.path.isdir(dossier), f"zone moteur absente : {dossier}"
    presents = sorted(f for f in os.listdir(dossier) if f.endswith(".py"))
    manquants = set(_MODULES_MOTEUR) - set(presents)
    assert not manquants, f"modules attendus absents : {sorted(manquants)}"
    sources = {}
    for nom_fichier in presents:
        with open(os.path.join(dossier, nom_fichier), encoding="utf-8") as fh:
            sources[nom_fichier] = fh.read()
    # Garde anti-vacuité : un grep sur des fichiers vides passerait tout.
    assert sum(len(t) for t in sources.values()) > 5000, "sources moteur suspectement vides"
    return sources


def test_cc1_aucun_couplage_au_scoreur():
    """Cas 9 : `src/engine/` n'importe pas le scoreur — dans aucun sens d'écriture."""
    interdits = [r"\bfrom\s+\S*scorer", r"\bimport\s+\S*scorer", r"\bfrom\s+scorer\b"]
    for nom_fichier, source in _sources_moteur().items():
        for motif in interdits:
            trouve = re.search(motif, source, re.IGNORECASE)
            assert not trouve, f"{nom_fichier} : couplage au scoreur -> {trouve.group(0)!r}"
    # Contrôle POSITIF : un grep qui ne détecterait plus rien passerait au vert sur
    # n'importe quel code. On lui soumet donc une infraction réelle, qu'il doit voir.
    infraction = "from src.scorer import mesure\nimport scorer.metriques\n"
    assert any(re.search(motif, infraction, re.IGNORECASE) for motif in interdits), (
        "les motifs de non-circularité ne détectent plus une infraction évidente : oracle mort")


def test_cc1_aucun_acces_a_la_verite_terrain():
    """Cas 9 : aucune trace des identifiants de vérité terrain dans la zone moteur."""
    interdits = ("id_entite_vraie", "ground_truth", "zone_intention_design")
    for nom_fichier, source in _sources_moteur().items():
        # Comparaison sur la source dont on a retiré les retours à la ligne et les
        # continuations : un identifiant coupé en deux lignes ne passe pas au travers.
        aplati = source.replace("\\\n", "").replace("\n", " ")
        for jeton in interdits:
            assert jeton not in aplati, f"{nom_fichier} : accès à la vérité terrain ({jeton})"
    # Contrôle POSITIF : l'aplatissement doit rattraper un identifiant coupé par une
    # continuation de ligne, sinon la garde se contourne d'un simple antislash.
    coupe = 'verite = pack["id_entite_\\\n' + 'vraie"]'
    assert "id_entite_vraie" in coupe.replace("\\\n", "").replace("\n", " "), (
        "l'aplatissement ne rattrape plus un identifiant coupé : oracle mort")


def test_cc1_aucun_recompte_de_metrique():
    """Cas 9 : le moteur décide ; il ne mesure pas sa propre qualité (P/R/F = le scoreur)."""
    interdits = [r"\bprecision\b", r"\brecall\b", r"\bf1[_ ]?score\b",
                 r"\btrue_positive", r"\bfalse_positive", r"\bconfusion_matrix"]
    for nom_fichier, source in _sources_moteur().items():
        for motif in interdits:
            trouve = re.search(motif, source, re.IGNORECASE)
            assert not trouve, f"{nom_fichier} : recompte de métrique -> {trouve.group(0)!r}"
    # Contrôle POSITIF, aligné sur le hook `precommit_anti_business_code.py` : ces motifs
    # sont ceux qui bloquent l'écriture, le test doit refléter exactement la même frontière.
    infraction = "rappel = true_positives / (true_positives + false_negatives)\n"
    assert any(re.search(motif, infraction, re.IGNORECASE) for motif in interdits), (
        "les motifs anti-métrique ne détectent plus une infraction évidente : oracle mort")


def _modules_importes(source):
    """Modules de premier niveau importés, lus dans l'AST.

    L'AST plutôt qu'un `grep` : une prose qui NOMME une dépendance pour dire qu'on ne
    l'utilise pas n'est pas une dépendance. Un oracle textuel confondrait les deux et
    interdirait de documenter une frontière — ici, seule une importation réelle compte.
    """
    noms = set()
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.Import):
            noms.update(alias.name.split(".")[0] for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.level:
                noms.add(".")                      # importation relative, interne au paquet
            elif noeud.module:
                noms.add(noeud.module.split(".")[0])
    return noms


def _definitions(source):
    """Noms des fonctions et classes DÉFINIES dans un module (AST)."""
    types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    return {n.name for n in ast.walk(ast.parse(source)) if isinstance(n, types)}


def test_c7_offline_le_moteur_n_importe_que_la_bibliotheque_standard():
    """C7 : offline strict au runtime, par construction.

    L'assertion est en liste BLANCHE : le moteur n'importe que des modules de la
    bibliothèque standard (plus ses propres modules). Une liste noire laisserait passer
    toute dépendance à laquelle on n'aurait pas pensé ; une liste blanche impose que
    chaque ajout soit une décision.
    """
    autorises = {".", "__future__", "hashlib", "json", "math", "random", "re",
                 "unicodedata", "dataclasses", "typing"}
    for nom_fichier, source in _sources_moteur().items():
        importes = _modules_importes(source)
        assert importes <= autorises, (
            f"{nom_fichier} : import hors liste blanche -> {sorted(importes - autorises)}")
    # Garde anti-vacuité : le lecteur d'AST voit bien quelque chose.
    assert "hashlib" in _modules_importes(_sources_moteur()["decide.py"])


def test_pas_de_splink_ni_de_reseau_dans_le_moteur():
    """C7 / loyauté : aucune dépendance réseau, et pas de Splink — c'est le banc d'essai."""
    proscrits = {"socket", "requests", "httpx", "urllib", "http", "urllib3",
                 "splink", "duckdb", "networkx", "igraph"}
    for nom_fichier, source in _sources_moteur().items():
        fautifs = _modules_importes(source) & proscrits
        assert not fautifs, f"{nom_fichier} : dépendance proscrite -> {sorted(fautifs)}"


def _importations_relatives(source):
    """Modules relatifs importés, NOMMÉS un par un (`.decide`, `.llm_review`, …).

    `_modules_importes` replie toute importation relative sur un unique « . » — utile pour
    la liste blanche C7, aveugle pour le périmètre : `from .llm_review import …` glissé dans
    `decide.py` n'y produirait aucune trace. Cet oracle-ci lit le nom.

    **Les DEUX formes sont lues**, et l'oublier rendait cet oracle inerte là où il comptait
    le plus. `from .decide import MATCH` porte le module dans `node.module` ; mais
    `from . import decide as dec` a `node.module is None` et porte le module dans les
    ALIAS — et c'est précisément la forme qu'emploie `engine.py`, l'orchestrateur, donc le
    module le plus susceptible d'atteindre une passe aval. Ne lire que la première forme
    laissait le cœur de la chaîne hors de portée des deux clauses ci-dessous.
    """
    noms = set()
    for noeud in ast.walk(ast.parse(source)):
        if not isinstance(noeud, ast.ImportFrom) or not noeud.level:
            continue
        prefixe = "." * noeud.level
        if noeud.module:
            noms.add(prefixe + noeud.module)
        else:
            # `from . import a, b` : chaque alias EST un module du paquet.
            noms.update(prefixe + alias.name for alias in noeud.names)
    return noms


def test_perimetre_le_coeur_decisionnel_ne_depend_d_aucune_passe_aval():
    """Périmètre, RECADRÉ UNE FOIS POUR TOUTES : le sens de la dépendance, pas l'existence.

    Les deux versions précédentes de ce test affirmaient une proposition sur le MONDE —
    « la revue de zone grise n'est pas construite », « le clustering et la fusion ne sont
    pas construits ». La chaîne de bout en bout rend les deux fausses : les quatre modules
    vivent désormais dans `src/engine/`. Une garde qui ne peut
    plus qu'être vraie ne garde rien, et les deux motifs passaient déjà par ACCIDENT DE
    NOMMAGE — vérifié : ni `_llm|llm_|revue_zone_grise` ni `clust|fusion|golden` ne mord sur
    une seule définition des 11 modules, parce que la revue, le clustering et la fusion nomment en
    français (`revue_des_correspondances`, `cloture_transitive`, `consolide_entite`). La première
    fonction légitimement nommée `fusionne_*` les aurait fait rougir sans aucun défaut.

    Ce qui reste VRAI, et que rien ne gardait, c'est le SENS de la dépendance : le cœur
    décisionnel (les six modules) est en AMONT. Il ne doit connaître ni la revue du
    doute, ni la clôture, ni la fusion — sans quoi la sortie du bloc B2, que la suite du moteur
    épingle, dépendrait de ce qui la consomme, et la chaîne deviendrait circulaire.

    Cet oracle ne pouvait PAS être écrit avec `_modules_importes`, qui replie toute
    importation relative sur « . » : `from .llm_review import …` ajouté à `decide.py` serait
    passé sous les cinq gardes structurelles de ce fichier sans en réveiller aucune. C'est
    exactement le trou que ce recadrage ferme, et il est plus large que ce qu'il remplace.

    La frontière est BILATÉRALE, et l'autre sens est tenu ailleurs :
    `tests/test_clustering.py::test_perimetre_u_b4_ne_reconstruit_pas_le_coeur_decisionnel`
    interdit au clustering et à la fusion de redéfinir la normalisation, le blocking, la
    comparaison ou la décision.
    """
    sources = _sources_moteur()
    revue = {".llm_review", ".llm_client"}
    consolidation = {".clustering", ".fusion"}

    #: DEUX clauses, de portées différentes, parce que la chaîne a deux étages en aval et
    #: qu'ils ne sont pas au même endroit de l'ordre.
    #:
    #: (1) PERSONNE, dans tout le paquet, ne dépend de la revue — hormis la revue elle-même.
    #:     Elle est la passe la plus en aval : rien de ce qui la précède ne peut la
    #:     connaître sans rendre la chaîne circulaire. Cette clause porte donc sur les 8
    #:     modules hors revue, `clustering` et `fusion` COMPRIS — c'est précisément pourquoi
    #:     `clustering` RE-DÉCLARE `MATCH_APRES_REVUE` au lieu de l'importer.
    #: (2) Le cœur décisionnel (les 5 modules calculatoires) ne dépend en outre pas
    #:     de la consolidation, qui lui est postérieure.
    #:
    #: `__init__.py` est écarté des deux, et pour une raison, pas par commodité : le fichier
    #: de paquet n'est pas un module du cœur, c'est l'AGRÉGAT — réexporter la consolidation est
    #: exactement son travail, et la surface qu'il expose est gelée séparément par
    #: `test_surface_publique_du_paquet_engine_gelee`.
    hors_revue = tuple(m for m in _MODULES_ENGINE_ATTENDUS
                       if m not in _MODULES_U_B3 and m != "__init__.py")
    assert len(hors_revue) == 8, "l'inventaire a bougé sans édition de ce test"
    for nom_fichier in hors_revue:
        fautifs = sorted(_importations_relatives(sources[nom_fichier]) & revue)
        assert not fautifs, (
            f"{nom_fichier} : dépendance vers la revue du doute -> {fautifs}. La revue est "
            f"la passe la plus en aval ; rien de ce qui la précède ne peut la connaître.")

    #: Clause (2) couvre le cœur ET le dimensionnement : `threshold_sizing` DÉRIVE ses
    #: seuils de la distribution des agrégats, donc il est en amont de la consolidation au
    #: même titre que la décision. L'en exclure aurait laissé une inversion DIMS ->
    #: consolidation passer sans bruit.
    coeur = tuple(m for m in _MODULES_B2 + _MODULES_DIMS if m != "__init__.py")
    assert len(coeur) == 6, "le cœur décisionnel a changé de taille sans édition de ce test"
    for nom_fichier in coeur:
        fautifs = sorted(_importations_relatives(sources[nom_fichier]) & consolidation)
        assert not fautifs, (
            f"{nom_fichier} : le cœur décisionnel importe une passe AVAL -> {fautifs}. "
            f"La chaîne doit couler dans un seul sens.")

    # Garde anti-vacuité : les définitions attendues sont bien là, dans chaque étage.
    assert {"estime_m_u", "verdict_3_zones", "correspondance"} <= _definitions(
        sources["decide.py"])
    assert {"cloture_transitive"} <= _definitions(sources["clustering.py"])
    assert {"consolide_entite"} <= _definitions(sources["fusion.py"])

    # Contrôle POSITIF, sur une source SYNTHÉTIQUE : aucun fichier du produit n'est touché,
    # et l'oracle doit voir l'infraction qu'on lui soumet.
    assert _importations_relatives(
        "from .llm_review import revue_des_correspondances\n") == {".llm_review"}, (
        "l'oracle ne lit plus le nom d'une importation relative : oracle mort")
    # ... et sur l'AUTRE forme, celle qu'emploie `engine.py`. Sans cette lecture, les deux
    # clauses ci-dessus étaient inertes sur l'orchestrateur lui-même.
    assert _importations_relatives("from . import llm_review as rev\n") == {".llm_review"}, (
        "l'oracle est aveugle a `from . import X` : la forme qu'emploie engine.py")
    assert _importations_relatives("from . import blocking as blk, compare as cmp\n") == {
        ".blocking", ".compare"}, "l'oracle ne lit qu'un alias sur plusieurs"
    # Garde de non-vacuité : la forme employée par `engine.py` est bien celle-là, sans quoi
    # le contrôle ci-dessus éprouverait une forme que le produit n'emploie pas.
    assert ".decide" in _importations_relatives(sources["engine.py"]), (
        "engine.py n'importe plus .decide sous la forme attendue : le controle est a revoir")
    # ... et il ne doit PAS mordre sur les dépendances légitimes du cœur.
    assert not (_importations_relatives(sources["decide.py"]) & (revue | consolidation))
    assert ".decide" in _importations_relatives(sources["clustering.py"]), (
        "l'aval a cessé de dépendre de l'amont : la chaîne n'est plus orientée")
    # La revue, elle, dépend légitimement de l'amont : la clause (1) l'exclut à raison.
    assert ".decide" in _importations_relatives(sources["llm_review.py"]), (
        "la revue ne dépend plus de la décision : elle ne consomme donc plus ses verdicts")


def test_inventaire_clos_de_la_zone_moteur():
    """`src/engine/` ne contient QUE des modules nommément attendus.

    Reprend, en plus large, ce que gardait l'alternance `_llm` retirée ci-dessus : une
    liste noire n'attrape que ce à quoi on a pensé, un inventaire clos attrape tout le
    reste. Ajouter un module à la zone moteur devient une décision qui passe par ce test.
    """
    dossier = os.path.join(_SRC, "engine")
    # Parcours RÉCURSIF : `os.listdir` ne descend pas, si bien qu'un sous-paquet
    # `src/engine/<pkg>/` serait invisible à l'inventaire — donc aussi aux gardes de
    # non-circularité, C7 et de périmètre qui s'appuient sur la même énumération. Un angle
    # mort dans un inventaire « clos » vaut moins que pas d'inventaire, puisqu'il rassure à tort.
    presents = sorted(
        os.path.relpath(os.path.join(racine, nom), dossier).replace(os.sep, "/")
        for racine, _, fichiers in os.walk(dossier) if "__pycache__" not in racine
        for nom in fichiers if nom.endswith(".py"))
    assert presents == sorted(_MODULES_ENGINE_ATTENDUS), (
        f"inventaire de src/engine/ non conforme : présents={presents}, "
        f"attendus={sorted(_MODULES_ENGINE_ATTENDUS)}")


def test_surface_publique_du_paquet_engine_gelee():
    """La revue du doute n'entre PAS dans la surface publique du paquet.

    Le paquet réexporte le bloc B2 et le dimensionnement ; il ne réexporte pas la revue, qui
    s'importe nommément. Sans ce gel, « la surface du moteur est inchangée » resterait une
    affirmation ; ici, c'est une comparaison.
    """
    import engine as paquet
    assert tuple(paquet.__all__) == _SURFACE_PUBLIQUE_GELEE, (
        f"surface publique modifiée : {sorted(set(paquet.__all__) ^ set(_SURFACE_PUBLIQUE_GELEE))}")
    for interdit in ("llm_review", "llm_client", "revue_des_correspondances",
                     "ClientRejeu", "MATCH_APRES_REVUE"):
        assert interdit not in paquet.__all__, (
            f"revue de zone grise réexportée par le paquet engine : {interdit}")


def test_parametres_non_calibres_sont_declares(resultat):
    """Les paramètres non calibrés sont ANNONCÉS dans la sortie, pas dissimulés."""
    rapport = resultat["rapport"]
    declares = set(rapport["parametres_non_calibres"])
    assert {"c_fort", "c_partiel", "t_mu", "t_lambda"} <= declares
    assert rapport["estimation"]["provenance_priors"], "a priori sans provenance déclarée"
    assert set(rapport["parametres"]) >= declares, "paramètre déclaré mais non exposé"


def test_contrat_de_sortie_du_rapport_gele(resultat):
    """Le jeu de clés du `rapport` est GELÉ — c'est un contrat lu en aval.

    Motivé par un constat de revue : la revue de zone grise a modifié `hors_perimetre_u_b2` et
    ajouté `instruit_en_aval` sans qu'aucun test n'ait eu à bouger. La sortie du moteur est ce que
    consomment les unités suivantes ; la laisser dériver librement, alors même que
    `__all__` est gelé, garde la mauvaise moitié du contrat. Toute unité qui touchera au
    rapport passera désormais par une édition délibérée de ce test.
    """
    cles_gelees = ("blocking", "estimation", "hors_perimetre_u_b2", "instruit_en_aval",
                   "n_paires", "n_records", "parametres", "parametres_non_calibres",
                   "poids", "repartition_verdicts")
    assert tuple(sorted(resultat["rapport"])) == cles_gelees, (
        f"contrat de sortie modifié : "
        f"{sorted(set(resultat['rapport']) ^ set(cles_gelees))}")
    # Les DEUX champs doivent rester VRAIS après chaque unité livrée. Correction d'un
    # décalage que le merge a rendu visible : `hors_perimetre_u_b2` rangeait encore la consolidation
    # parmi ce qui n'est « pas encore là », alors que `clustering.py` et `fusion.py` sont
    # dans le paquet depuis leur merge. Le partage est désormais explicite — construit et
    # en aval d'un côté, hors du paquet par construction de l'autre — et l'égalité reste
    # EXACTE des deux côtés : c'est ce qui force l'édition délibérée à la prochaine unité.
    assert resultat["rapport"]["hors_perimetre_u_b2"] == [
        "mesure de qualite P/R/F : hors de ce paquet par construction, "
        "c'est la condition de non-circularite de la preuve",
        "comparaison a l'etat de l'art : depend de ce paquet, "
        "jamais l'inverse",
    ], "contenu de hors_perimetre_u_b2 modifié sans édition de ce test"
    assert resultat["rapport"]["instruit_en_aval"] == [
        "revue zone grise : passe posterieure, "
        "consomme cette sortie sans la modifier",
        "clustering et fusion : passes posterieures, "
        "consomment cette sortie sans la modifier",
    ], "contenu de instruit_en_aval modifié sans édition de ce test"
    # Ce que les deux listes affirment doit rester vérifiable, pas seulement lisible :
    # ce qui est dit « en aval » est construit, ce qui est dit « hors paquet » ne l'est pas.
    for module in ("llm_review.py", "clustering.py", "fusion.py"):
        assert module in _MODULES_ENGINE_ATTENDUS, (
            f"{module} est annoncé en aval mais absent de l'inventaire du paquet")
    assert not (set(_MODULES_ENGINE_ATTENDUS) & {"metriques.py", "criteres.py"}), (
        "un module de mesure est entré dans le paquet : hors_perimetre_u_b2 devient faux")


def test_rapport_trace_le_blocking_et_lestimation(resultat):
    """La sortie porte de quoi auditer la décision sans ré-exécuter le moteur."""
    rapport = resultat["rapport"]
    assert rapport["blocking"]["n_paires"] == len(resultat["correspondances"])
    assert rapport["blocking"]["blocs_ecartes"] == [], "troncature silencieuse de blocs"
    assert rapport["estimation"]["convergence"] is True
    assert sum(rapport["repartition_verdicts"].values()) == len(resultat["correspondances"])


def test_parametres_incoherents_sont_refuses():
    """Un paramétrage impossible échoue à la construction, pas au milieu d'un calcul."""
    with pytest.raises(ValueError):
        ParametresMoteur(c_fort=0.5, c_partiel=0.8)
    with pytest.raises(ValueError):
        ParametresMoteur(t_mu=-1.0, t_lambda=1.0)


def test_record_id_duplique_est_refuse(records):
    """Un identifiant dupliqué rend l'indexation ambiguë : échec net plutôt que silencieux."""
    with pytest.raises(ValueError):
        execute_moteur(list(records) + [dict(records[0])])
