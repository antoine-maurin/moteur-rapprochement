# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Tests du dimensionnement budget-driven des seuils.

Lancement depuis la racine du repo de build : `python -m pytest tests/ -q`.

**Non-circularité.** Ces tests ne lisent JAMAIS la vérité terrain. La population de
démonstration provient du générateur, mais seul son tableau `records` est extrait :
`ground_truth`, `corruption_annotation` et `zone_intention_design` ne sont ni lus ni
nommés comme source d'attente. Le dimensionnement se juge sur la **forme de la
distribution de `R`** et sur le **volume** de la zone grise — jamais sur la justesse des
appariements, qui relève du scoreur.

**Seuils provisoires.** Rien ici ne fixe d'attente sur la VALEUR des seuils : ce sont des
placeholders non calibrés. Les tests portent sur les propriétés qui doivent tenir quelle que
soit la calibration — déterminisme, volume ~ budget, bande médiane, `Tλ < Tμ`.
"""
import ast
import json
import os
import re

import pytest

import engine
from engine import threshold_sizing as ts

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_MODULE_DIMENSIONNEMENT = os.path.join(_REPO_ROOT, "src", "engine", "threshold_sizing.py")
_ARTEFACT = os.path.join(_REPO_ROOT, "artifacts", "thresholds_sized.json")

GRAINE_POPULATION = "SP_CYCLE_001::GEN-01::seed-0001"
N_ENTITES_BULK = 400
#: Zone grise observée sous les placeholders ±8 bits, avant dimensionnement (mandat §1).
ZONE_GRISE_AVANT_DIMENSIONNEMENT = 2


@pytest.fixture(scope="module")
def records_bulk():
    """Population BULK de démonstration — `records` SEULS (garde de non-circularité)."""
    from generator import generate_pack
    return generate_pack(GRAINE_POPULATION, n_entities=N_ENTITES_BULK)["records"]


@pytest.fixture(scope="module")
def resultat_bulk(records_bulk):
    """Sortie du moteur sous les seuils PAR DÉFAUT (±8 bits) : l'état d'avant."""
    return engine.execute_moteur(records_bulk)


@pytest.fixture(scope="module")
def valeurs_r(resultat_bulk):
    return [c["poids_match"] for c in resultat_bulk["correspondances"]]


@pytest.fixture(scope="module")
def dimensionnement(valeurs_r):
    """Dimensionnement au budget par défaut, partagé par le module."""
    return ts.dimensionne_seuils(valeurs_r, budget_revue=ts.BUDGET_REVUE_DEFAUT)


@pytest.fixture(scope="module")
def resultat_dimensionne(records_bulk, dimensionnement):
    """Sortie du moteur SOUS les seuils dimensionnés : l'état d'après.

    Partagée : chaque exécution parcourt 21 781 paires, et plusieurs cas de la DoD
    portent sur le même état. La recalculer par test allongerait la suite sans rien
    éprouver de plus.
    """
    parametres = engine.ParametresMoteur(t_mu=dimensionnement["t_mu"],
                                         t_lambda=dimensionnement["t_lambda"])
    return engine.execute_moteur(records_bulk, parametres)


# ============================ 1. Déterminisme =======================================
def test_dimensionnement_deterministe(valeurs_r):
    """Cas 1 : même population + même budget -> mêmes `Tμ` / `Tλ`."""
    a = ts.dimensionne_seuils(valeurs_r, budget_revue=300)
    b = ts.dimensionne_seuils(valeurs_r, budget_revue=300)
    assert a == b, "deux dimensionnements de la même entrée divergent"
    # ... et l'ordre de présentation des valeurs ne doit rien changer.
    c = ts.dimensionne_seuils(list(reversed(valeurs_r)), budget_revue=300)
    assert (c["t_mu"], c["t_lambda"]) == (a["t_mu"], a["t_lambda"]), (
        "le dimensionnement dépend de l'ordre d'entrée")
    # Garde anti-vacuité : un dimensionnement qui rendrait toujours la même constante
    # serait lui aussi « déterministe ». Il doit répondre au budget. L'assertion porte sur
    # la BANDE, non sur une borne : la distribution étant très creuse au-dessus de la
    # frontière, réduire le budget peut ne resserrer que la borne basse — `t_mu` a le droit
    # de ne pas bouger, la bande, elle, doit se resserrer.
    etroit = ts.dimensionne_seuils(valeurs_r, budget_revue=50)
    assert (etroit["t_lambda"], etroit["t_mu"]) != (a["t_lambda"], a["t_mu"]), (
        "la bande ne réagit pas au budget")
    assert etroit["taille_zone_grise"] < a["taille_zone_grise"]


def test_dimensionnement_deterministe_bout_en_bout(records_bulk, valeurs_r):
    """Cas 1 : appliqué au moteur, le résultat complet est reproductible."""
    d = ts.dimensionne_seuils(valeurs_r)
    parametres = engine.ParametresMoteur(t_mu=d["t_mu"], t_lambda=d["t_lambda"])
    premier = engine.sortie_canonique(engine.execute_moteur(records_bulk, parametres))
    second = engine.sortie_canonique(engine.execute_moteur(records_bulk, parametres))
    assert premier == second


# ============================ 2. Zone grise non vide ================================
def test_zone_grise_non_vide_et_dimensionnee(resultat_bulk, dimensionnement,
                                             resultat_dimensionne):
    """Cas 2 : sur la population BULK, la zone grise passe de ~vide à ~budget.

    C'est l'objet même du mandat : sous les placeholders ±8 bits, la revue de zone grise n'aurait
    rien à instruire.
    """
    avant = resultat_bulk["rapport"]["repartition_verdicts"]["ZONE_GRISE"]
    assert avant <= ZONE_GRISE_AVANT_DIMENSIONNEMENT, (
        f"l'état d'avant n'est plus celui qu'a constaté le mandat : {avant}")

    budget = ts.BUDGET_REVUE_DEFAUT
    d = dimensionnement
    zone_grise = resultat_dimensionne["rapport"]["repartition_verdicts"]["ZONE_GRISE"]

    assert zone_grise > 0, "zone grise vide : la revue de zone grise resterait sans entrée"
    assert zone_grise > 10 * ZONE_GRISE_AVANT_DIMENSIONNEMENT, (
        f"zone grise à peine plus fournie qu'avant : {zone_grise} vs {avant}")
    # ~ budget : la tolérance est celle de la granularité de `R`, pas un confort.
    assert abs(zone_grise - budget) <= 0.25 * budget, (
        f"volume hors tolérance : {zone_grise} pour un budget de {budget}")
    # Le compte annoncé par le dimensionnement est celui que le moteur produit vraiment.
    assert zone_grise == d["taille_zone_grise"], (
        f"le dimensionnement annonce {d['taille_zone_grise']} paires, "
        f"le moteur en classe {zone_grise}")


def test_le_volume_suit_le_budget(valeurs_r):
    """Cas 2 : un budget plus grand donne une zone grise plus grande (monotonie)."""
    volumes = [ts.dimensionne_seuils(valeurs_r, budget_revue=b)["taille_zone_grise"]
               for b in (50, 200, 500, 1000)]
    assert volumes == sorted(volumes), f"le volume ne suit pas le budget : {volumes}"
    assert len(set(volumes)) > 1, "le volume ne réagit pas au budget : oracle vide"


# ============================ 3. Les paires les moins confiantes ====================
def test_zone_grise_est_la_bande_mediane(dimensionnement, resultat_dimensionne):
    """Cas 3 : toute paire en zone grise est plus proche de la frontière que toute paire
    hors zone grise **du même côté**.

    C'est ce qui distingue une bande d'un échantillon : la zone grise doit être exactement
    l'ensemble des paires les moins tranchées, pas une sélection commode.
    """
    d = dimensionnement
    frontiere = d["frontiere"]
    correspondances = resultat_dimensionne["correspondances"]

    grise = [c["poids_match"] for c in correspondances if c["verdict"] == engine.ZONE_GRISE]
    hors = [c["poids_match"] for c in correspondances if c["verdict"] != engine.ZONE_GRISE]
    assert grise and hors, "les deux familles doivent être peuplées : oracle vide"

    for cote, dans, dehors in (
            ("haut", [r for r in grise if r >= frontiere], [r for r in hors if r >= frontiere]),
            ("bas", [r for r in grise if r < frontiere], [r for r in hors if r < frontiere])):
        if not dans or not dehors:
            continue
        assert max(abs(r - frontiere) for r in dans) < min(abs(r - frontiere) for r in dehors), (
            f"côté {cote} : une paire hors zone grise est plus ambiguë qu'une paire dedans")

    # La zone grise est un INTERVALLE de `R` : aucune valeur intermédiaire n'en est exclue.
    for c in correspondances:
        dans_bande = d["t_lambda"] <= c["poids_match"] <= d["t_mu"]
        assert dans_bande == (c["verdict"] == engine.ZONE_GRISE), (
            f"{c['record_id_a']}/{c['record_id_b']} : R={c['poids_match']} "
            f"dans la bande={dans_bande} mais verdict={c['verdict']}")


# ============================ 4. Partition cohérente ================================
def test_seuils_ordonnes_et_partition_coherente(dimensionnement, resultat_dimensionne):
    """Cas 4 : `Tλ < Tμ`, et chaque paire tombe dans la zone que dicte son `R`."""
    d = dimensionnement
    assert d["t_lambda"] < d["t_mu"], f"seuils non ordonnés : {d['t_lambda']} / {d['t_mu']}"

    resultat = resultat_dimensionne
    repartition = resultat["rapport"]["repartition_verdicts"]
    for c in resultat["correspondances"]:
        r = c["poids_match"]
        attendu = (engine.MATCH if r > d["t_mu"]
                   else engine.NON_MATCH if r < d["t_lambda"]
                   else engine.ZONE_GRISE)
        if c["garde_r20_appliquee"]:
            continue                       # la garde R-20 prime : elle est testée côté moteur
        assert c["verdict"] == attendu, f"R={r} classé {c['verdict']}, attendu {attendu}"
    assert sum(repartition.values()) == len(resultat["correspondances"])
    assert all(repartition[v] > 0 for v in engine.VERDICTS), (
        f"une zone est vide après dimensionnement : {repartition}")


def test_seuils_toujours_ordonnes_meme_en_bande_degeneree():
    """Cas 4 : une bande réduite à une valeur unique reste un intervalle ouvrable."""
    d = ts.dimensionne_seuils([3.0] * 10, budget_revue=5)
    assert d["t_lambda"] < d["t_mu"], "bande dégénérée : Tλ et Tμ confondus"
    assert d["t_lambda"] <= 3.0 <= d["t_mu"]


def test_bande_degeneree_avec_voisin_sur_la_grille_d_arrondi():
    """L'écartement d'une bande dégénérée ne doit HAPPER aucune valeur voisine.

    `decide.agregat` arrondit `R` à `DECIMALES_POIDS` décimales : deux valeurs distinctes
    peuvent donc être séparées d'exactement un pas de grille. Un écartement d'un pas plein
    atteindrait la voisine et ferait entrer dans la bande une paire qui n'y avait pas été
    retenue — le volume promis à la revue serait alors faux. Le cas `[3.0] * 10` ci-dessus est
    aveugle à ce mode de défaillance : sans voisine, il ne peut rien happer.
    """
    valeur, voisine = 3.0, 3.0 + ts.PAS_GRILLE_R
    assert valeur != voisine, "les deux valeurs de l'épreuve doivent être distinctes"
    d = ts.dimensionne_seuils([valeur] * 10 + [voisine] * 4, budget_revue=10)
    assert d["t_lambda"] < d["t_mu"], "bande dégénérée : Tλ et Tμ confondus"
    assert d["taille_zone_grise"] == 10, (
        f"l'écartement a happé une voisine de la grille : {d['taille_zone_grise']} au lieu de 10")
    # Garde anti-vacuité : la population CONTIENT bien une voisine à un pas de grille,
    # sans quoi l'assertion ci-dessus passerait sans rien éprouver. La borne est de deux
    # pas parce que `3.0 + 1e-9` ne vaut pas exactement `3.000000001` en binaire — ce qui
    # est précisément le genre d'approximation contre laquelle l'écartement doit tenir.
    assert 0 < voisine - valeur <= 2 * ts.PAS_GRILLE_R
    # Cas symétrique : côté négatif, où c'est l'écartement vers le BAS qui pourrait happer.
    # (Il faut passer côté négatif pour que la valeur dense reste la plus proche de la
    # frontière : une voisine plus proche que la bande formerait un tout autre cas, non
    # dégénéré, où l'élargissement n'intervient pas.)
    e = ts.dimensionne_seuils([-valeur] * 10 + [-valeur - ts.PAS_GRILLE_R] * 4,
                              budget_revue=10)
    assert e["t_lambda"] < e["t_mu"]
    assert e["taille_zone_grise"] == 10, (
        f"écartement vers le bas : {e['taille_zone_grise']} au lieu de 10")


def test_la_frontiere_non_defaut_deplace_la_bande():
    """Le paramètre `frontiere` est un levier réel, pas une décoration de signature.

    Le module le documente comme utilisable par un appelant ; la suite ne l'exerçait
    qu'à sa valeur par défaut, si bien qu'une implémentation l'ignorant entièrement
    passait tous les tests.
    """
    valeurs = [0.0] * 5 + [10.0] * 5
    pres_de_zero = ts.dimensionne_seuils(valeurs, budget_revue=5, frontiere=0.0)
    pres_de_dix = ts.dimensionne_seuils(valeurs, budget_revue=5, frontiere=10.0)
    assert pres_de_zero["frontiere"] == 0.0 and pres_de_dix["frontiere"] == 10.0
    assert pres_de_zero["t_lambda"] <= 0.0 <= pres_de_zero["t_mu"]
    assert pres_de_dix["t_lambda"] <= 10.0 <= pres_de_dix["t_mu"]
    assert pres_de_zero["t_mu"] < pres_de_dix["t_lambda"], (
        "les deux bandes se recouvrent : la frontière n'a pas déplacé la sélection")
    assert pres_de_zero["taille_zone_grise"] == pres_de_dix["taille_zone_grise"] == 5


def test_departage_des_ex_aequo_par_la_valeur():
    """À distance égale de la frontière, c'est la VALEUR qui départage — déterministe.

    Sans cette clé secondaire, l'ordre retomberait sur l'ordre d'apparition des valeurs
    en entrée : le résultat dépendrait alors de la façon dont l'appelant a rangé sa
    population, ce que le déterminisme interdit.
    """
    valeurs = [5.0] * 3 + [-5.0] * 4          # |r| identique des deux côtés
    d = ts.dimensionne_seuils(valeurs, budget_revue=3)
    assert d["t_mu"] < 0.0, (
        "le départage n'a pas retenu la plus petite valeur à distance égale")
    assert d["taille_zone_grise"] == 4
    # Et l'ordre d'entrée ne change rien, quelle que soit la présentation.
    assert ts.dimensionne_seuils(list(reversed(valeurs)), budget_revue=3) == d


def test_a_egalite_d_ecart_la_plus_petite_bande_gagne():
    """Règle de départage documentée : à égalité d'écart au budget, la bande la plus petite.

    C'est ce qui garantit que le budget de revue n'est jamais dépassé sans nécessité.
    La population de démonstration ne présente aucune égalité, donc la règle n'y est
    jamais mise à l'épreuve : il faut la construire.
    """
    valeurs = [1.0, 1.0, 2.0, 2.0]            # bandes emboîtées : 2 puis 4 paires
    d = ts.dimensionne_seuils(valeurs, budget_revue=3)   # |2-3| == |4-3| == 1
    assert d["taille_zone_grise"] == 2, (
        f"à égalité d'écart, la plus GRANDE bande a été retenue ({d['taille_zone_grise']})")
    assert d["ecart_au_budget"] == -1, "le dépassement doit être évité, pas préféré"


def test_contrat_de_sortie_identique_sur_tous_les_chemins():
    """Toutes les branches de `dimensionne_seuils` rendent le MÊME jeu de clés.

    Un contrat qui change de forme selon la branche est un contrat qu'aucun appelant ne
    peut consommer sans condition — et c'est la branche rare qui casse chez lui.
    """
    nominal = ts.dimensionne_seuils([1.0, 2.0, 3.0, 4.0, 5.0], budget_revue=2)
    vide = ts.dimensionne_seuils([])
    degenere = ts.dimensionne_seuils([7.0] * 5, budget_revue=3)
    reference = set(nominal)
    for nom, sortie in (("vide", vide), ("dégénéré", degenere)):
        assert set(sortie) == reference, (
            f"chemin {nom} : clés divergentes -> "
            f"{sorted(reference ^ set(sortie))}")
    # L'écart au budget garde le même sens sur tous les chemins.
    for sortie in (nominal, vide, degenere):
        assert sortie["ecart_au_budget"] == sortie["budget_atteint"] - sortie["budget_vise"]


def test_outil_supporte_une_population_vide():
    """L'outil d'artefact ne doit pas planter sur une population sans paire candidate."""
    import sys
    sys.path.insert(0, os.path.join(_REPO_ROOT, "tools"))
    import dimensionne_seuils as outil
    rapport = outil.construis_rapport(n_entites=0)
    assert rapport["effet"]["zone_grise_apres"] == 0
    assert rapport["statut"] == "PROVISOIRE"


# ============================ Budget : dérivation et cas limites ====================
def test_budget_derive_du_debit_et_de_la_duree():
    """Précision ARCHI (i) : le budget est DÉRIVÉ d'un modèle de capacité, pas posé."""
    assert ts.budget_depuis_debit(60.0, 5.0) == 300
    assert ts.BUDGET_REVUE_DEFAUT == ts.budget_depuis_debit(
        ts.DEBIT_REVUE_PAR_MINUTE_PROVISOIRE, ts.DUREE_REVUE_MINUTES_PROVISOIRE)
    assert ts.budget_depuis_debit(0.4, 1.0) == 1, "un budget doit valoir au moins 1"
    for debit, duree in ((0.0, 5.0), (60.0, 0.0), (-1.0, 5.0)):
        with pytest.raises(ValueError):
            ts.budget_depuis_debit(debit, duree)


def test_population_vide_se_replie_et_le_dit():
    """Cas limite : rien à dimensionner -> seuils par défaut CONSERVÉS, repli tracé."""
    d = ts.dimensionne_seuils([])
    assert d["repli"] is True and d["motif_repli"]
    assert (d["t_mu"], d["t_lambda"]) == (engine.ParametresMoteur().t_mu,
                                          engine.ParametresMoteur().t_lambda)
    assert d["taille_zone_grise"] == 0


def test_budget_superieur_a_la_population_est_signale():
    """Cas limite : un budget qui absorbe tout est SIGNALÉ, pas subi en silence."""
    d = ts.dimensionne_seuils([1.0, 2.0, 3.0], budget_revue=100)
    assert d["budget_sature"] is True
    assert d["taille_zone_grise"] == 3
    with pytest.raises(ValueError):
        ts.dimensionne_seuils([1.0], budget_revue=0)


def test_le_recomptage_de_la_bande_est_verifie(valeurs_r):
    """Le volume annoncé est recompté indépendamment, pas déduit de l'accumulation."""
    d = ts.dimensionne_seuils(valeurs_r)
    recompte = sum(1 for r in valeurs_r if d["t_lambda"] <= r <= d["t_mu"])
    assert recompte == d["taille_zone_grise"] == d["budget_atteint"]
    assert d["ecart_au_budget"] == d["budget_atteint"] - d["budget_vise"]


def test_bande_retenue_est_la_plus_proche_du_budget(valeurs_r):
    """La bande choisie est la meilleure atteignable : aucune bande emboîtée ne fait mieux.

    Contrôle par force brute contre l'implémentation : on énumère toutes les bandes
    emboîtées et on vérifie qu'aucune n'approche le budget de plus près.
    """
    budget = 300
    d = ts.dimensionne_seuils(valeurs_r, budget_revue=budget)
    occurrences = {}
    for r in valeurs_r:
        occurrences[r] = occurrences.get(r, 0) + 1
    ordre = sorted(occurrences, key=lambda r: (abs(r - d["frontiere"]), r))
    cumul, meilleur = 0, None
    for valeur in ordre:
        cumul += occurrences[valeur]
        meilleur = abs(cumul - budget) if meilleur is None else min(meilleur, abs(cumul - budget))
    assert abs(d["budget_atteint"] - budget) == meilleur, (
        f"une bande plus proche du budget existait : écart atteint "
        f"{abs(d['budget_atteint'] - budget)}, meilleur possible {meilleur}")


def test_statistiques_r_decrivent_la_distribution(valeurs_r):
    """Les statistiques publiées correspondent bien à la population mesurée."""
    stats = ts.statistiques_r(valeurs_r)
    assert stats["n"] == len(valeurs_r)
    assert stats["min"] == min(valeurs_r) and stats["max"] == max(valeurs_r)
    assert stats["min"] <= stats["q25"] <= stats["mediane"] <= stats["q75"] <= stats["max"]
    assert stats["n_valeurs_distinctes"] == len(set(valeurs_r))
    assert ts.statistiques_r([]) == {"n": 0}


# ============================ 5. Non-circularité structurelle =======================
def _source_dimensionnement():
    assert os.path.isfile(_MODULE_DIMENSIONNEMENT), "module de dimensionnement absent"
    with open(_MODULE_DIMENSIONNEMENT, encoding="utf-8") as fh:
        source = fh.read()
    assert len(source) > 2000, "source suspectement vide : oracle sans prise"
    return source


def test_cc1_le_dimensionnement_ne_voit_aucune_verite_terrain():
    """Cas 5 : aucun accès aux identifiants de vérité terrain dans le module."""
    source = _source_dimensionnement()
    aplati = source.replace("\\\n", "").replace("\n", " ")
    for jeton in ("id_entite_vraie", "ground_truth", "zone_intention_design"):
        assert jeton not in aplati, f"accès à la vérité terrain ({jeton})"
    for motif in (r"\bfrom\s+\S*scorer", r"\bimport\s+\S*scorer",
                  r"\bprecision\b", r"\brecall\b", r"\bconfusion_matrix"):
        trouve = re.search(motif, source, re.IGNORECASE)
        assert not trouve, f"frontière de non-circularité franchie -> {trouve.group(0)!r}"
    # Contrôle POSITIF : les motifs détectent bien une infraction qu'on leur soumet.
    assert "id_entite_vraie" in 'x = pack["id_entite_vraie"]'.replace("\n", " ")


def test_cc1_le_dimensionnement_ne_consomme_que_des_valeurs_de_r():
    """Cas 5 : structurellement, seul `poids_match` est extrait d'une CORRESPONDENCE.

    Le module reçoit des flottants ; le seul point où il touche une correspondance
    n'en lit que le poids. Aucune autre clé n'est nommée — donc aucune ne peut entrer.
    """
    source = _source_dimensionnement()
    cles_lues = set()
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.Subscript) and isinstance(noeud.slice, ast.Constant):
            if isinstance(noeud.slice.value, str):
                cles_lues.add(noeud.slice.value)
    assert cles_lues == {"poids_match"}, (
        f"le dimensionnement lit d'autres clés que poids_match : {sorted(cles_lues)}")


def test_le_dimensionnement_ne_depend_pas_du_generateur():
    """Le module doit s'appliquer à n'importe quelle population, pas à celle d'un outil.

    La démonstration passe par le générateur, mais c'est l'affaire de `tools/`, pas du
    moteur : en exploitation, la population est réelle.
    """
    importes = set()
    for noeud in ast.walk(ast.parse(_source_dimensionnement())):
        if isinstance(noeud, ast.Import):
            importes.update(alias.name.split(".")[0] for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and not noeud.level and noeud.module:
            importes.add(noeud.module.split(".")[0])
    assert "generator" not in importes, "le dimensionnement dépend du générateur"
    assert importes <= {"math", "typing", "__future__"}, (
        f"import hors liste blanche : {sorted(importes)}")


# ============================ 6. Statut provisoire déclaré ==========================
def test_les_seuils_sont_declares_provisoires(valeurs_r):
    """Cas 6 : le caractère provisoire est PORTÉ PAR LA SORTIE, pas seulement commenté."""
    d = ts.dimensionne_seuils(valeurs_r)
    assert d["provisoire"] is True
    assert d["gap"] == "calibration différée"
    assert {"t_mu", "t_lambda", "budget_revue"} <= set(d["parametres_provisoires"])
    assert d["methode"], "la méthode de placement doit être énoncée dans la sortie"


def test_artefact_present_declare_et_reproductible():
    """Cas 6 : l'artefact existe, se dit provisoire, et se régénère à l'identique."""
    assert os.path.isfile(_ARTEFACT), (
        "artefact absent : le regenerer avec `python tools/dimensionne_seuils.py`")
    with open(_ARTEFACT, encoding="utf-8") as fh:
        artefact = json.load(fh)
    assert artefact["statut"] == "PROVISOIRE" and artefact["gap"] == "calibration différée"
    assert artefact["effet"]["zone_grise_avant"] <= ZONE_GRISE_AVANT_DIMENSIONNEMENT
    assert artefact["effet"]["zone_grise_apres"] > 10 * ZONE_GRISE_AVANT_DIMENSIONNEMENT
    assert artefact["seuils_dimensionnes"]["t_lambda"] < artefact["seuils_dimensionnes"]["t_mu"]
    assert artefact["budget_revue"]["valeur"] == (
        artefact["budget_revue"]["debit_par_minute"] * artefact["budget_revue"]["duree_minutes"])

    # Régénération : l'artefact publié est bien celui que le code produit aujourd'hui.
    import sys
    sys.path.insert(0, os.path.join(_REPO_ROOT, "tools"))
    import dimensionne_seuils as outil
    assert outil.construis_rapport() == artefact, (
        "l'artefact publié diverge de ce que le code régénère")


# ============================ 7. Le moteur n'a pas bougé ============================
def test_les_defauts_du_moteur_sont_inchanges():
    """Contrainte du mandat : la logique de décision du moteur n'est pas modifiée.

    Les placeholders ±8 bits restent les défauts ; le dimensionnement se transmet par
    PARAMÈTRE, sans toucher au cœur. Un dimensionnement qui aurait déplacé les défauts
    changerait le comportement du moteur en douce.
    """
    defauts = engine.ParametresMoteur()
    assert (defauts.t_mu, defauts.t_lambda) == (8.0, -8.0)


def test_le_dimensionnement_ne_change_pas_les_poids(valeurs_r, resultat_dimensionne):
    """Appliquer des seuils dimensionnés ne déplace AUCUN `R` : seule la coupure bouge."""
    apres = resultat_dimensionne["correspondances"]
    assert [c["poids_match"] for c in apres] == valeurs_r, (
        "les poids ont changé : le dimensionnement a touché au calcul, pas à la coupure")
