# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Tests d'unité de la fusion, consolidation en enregistrements dorés (DoD 2/3/4/5/7/8).

Lancement depuis la racine du repo de build : `python -m pytest tests/ -q`.

**DATA-INDÉPENDANCE STRICTE.** Aucun enregistrement doré d'un jeu réel n'est figé ici. Tous
les cas sont des groupes de 2 à 5 enregistrements écrits à la main, dont la valeur attendue
se déduit de la cascade par lecture, pas par observation. Motif : les seuils du moteur vont
bouger, donc les groupes formés sur un jeu réel vont changer, donc les enregistrements dorés
correspondants aussi — alors que la RÈGLE, elle, ne change pas. Un méta-test (§8) fait de
cette contrainte un oracle.

**Le test qui porte la traçabilité est le REJEU.** Pour chaque attribut, un ré-arbitrage
alimenté UNIQUEMENT par la trace — passée par un aller-retour JSON, jamais par les
enregistrements — doit retrouver la valeur et sa provenance. Son contrôle NÉGATIF est aussi
important que lui : retirer un champ de la trace doit CASSER le rejeu, faute de quoi ce
champ est décoratif et l'oracle est mort.

**Fichier distinct de `tests/test_clustering.py`, et c'est structurel** : les deux gardes de
data-indépendance scannent chacune leur propre source, et la consolidation s'éprouve sur des
groupes littéraux sans jamais passer par la clôture — c'est ce qui prouve que la fusion ne
dépend que de la FORME d'un groupe.
"""
import ast
import inspect
import itertools
import json
import os
import re
import subprocess
import sys

import pytest

from engine import fusion as fus
from engine import normalize as nrm

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_SRC = os.path.join(_REPO_ROOT, "src")
_ENGINE = os.path.join(_SRC, "engine")

_ATTRIBUTS = ("nom", "prenom", "date_naissance", "adresse",
              "code_postal", "ville", "email", "telephone")
_CLES_DORE = ("record_ids_sources",) + _ATTRIBUTS + ("origines",)
#: Schéma FERMÉ d'un groupe de bulletin. Le fermer est le seul oracle capable de dénoncer
#: un champ AJOUTÉ : le contrôle négatif du rejeu, lui, ne voit que les champs consommés
#: par la cascade, et reste donc muet sur les champs de lecture comme sur un champ mort.
_CLES_GROUPE = ("valeur_normalisee", "longueur_normalisee", "formes_brutes", "record_ids",
                "source_ids", "source_inconnue", "n_records", "n_sources", "rang_source")
_CLES_BULLETIN = ("attribut", "n_membres", "n_candidats", "n_groupes", "groupes")
#: Ceux que la cascade consomme réellement. La partition est ASSERTÉE par un test dédié :
#: la docstring du module la déclare, elle ne doit pas rester déclarative.
_CHAMPS_PORTEURS = ("valeur_normalisee", "longueur_normalisee", "formes_brutes",
                    "n_sources", "rang_source")


# ============================ outils de test =========================================
def garde_non_vacuite(**quantites):
    """Refuse un test qui passerait sur une population vide."""
    for nom, valeur in quantites.items():
        assert valeur, f"oracle vide : {nom} = {valeur!r} (le test ne prouverait rien)"


def _rec(rid, source=None, **surcharges):
    """Enregistrement source minimal : les 8 attributs présents, à `None` par défaut.

    Les attributs sont TOUS posés, y compris à `None` : un enregistrement dont une clé
    manque et un enregistrement dont la valeur est nulle doivent se comporter pareil, et
    c'est un test distinct qui le vérifie.
    """
    record = {"record_id": rid, "source_id": source}
    for attribut in _ATTRIBUTS:
        record[attribut] = None
    record.update(surcharges)
    return record


def _source_module(nom_fichier):
    with open(os.path.join(_ENGINE, nom_fichier), encoding="utf-8") as fh:
        return fh.read()


def _reference_independante(bulletin, politique):
    """Ré-implémentation NAÏVE de la CASCADE, alimentée par la seule trace.

    Portée exacte, à ne pas surestimer : elle est un second chemin de calcul pour
    l'ARBITRAGE, pas pour le bulletin. Partant du bulletin, elle reproduirait fidèlement
    toute erreur de `valeurs_candidates` — le regroupement et les poids ne sont donc PAS
    couverts par elle, mais par les tests de la section 3 et par le bulletin écrit à la main
    de `test_l_arbitrage_d_un_bulletin_ecrit_a_la_main`.

    Ce qu'elle prouve, et c'est ce qu'on lui demande : la trace SUFFIT à un tiers qui n'a
    pas le module pour retrouver la valeur et sa provenance.
    """
    survivants = list(bulletin["groupes"])
    if not survivants:
        return None, None
    if len(survivants) > 1:
        for nom_regle in politique:
            avant = survivants
            if nom_regle == fus.MAJORITE:
                sommet = max(g["n_sources"] for g in avant)
                survivants = [g for g in avant if g["n_sources"] == sommet]
            elif nom_regle == fus.COMPLETUDE:
                sommet = max(g["longueur_normalisee"] for g in avant)
                survivants = [g for g in avant if g["longueur_normalisee"] == sommet]
            elif nom_regle == fus.SOURCE_PRIORITAIRE:
                meilleur = min(g["rang_source"] for g in avant)
                survivants = [g for g in avant if g["rang_source"] == meilleur]
            else:
                survivants = [sorted(avant, key=lambda g: g["valeur_normalisee"])[0]]
            if len(survivants) == 1:
                break
    groupe = survivants[0]
    ecritures = sorted(groupe["formes_brutes"],
                       key=lambda f: (-f["n_records"], f["record_id_min"]))
    return ecritures[0]["forme"], ecritures[0]["record_id_min"]


def verifie_bulletin(bulletin):
    """Ferme le schéma d'un bulletin et de ses groupes, appliqué à tous les cas du fichier."""
    assert set(bulletin) == set(_CLES_BULLETIN), (
        f"schema de bulletin variable : {sorted(set(bulletin) ^ set(_CLES_BULLETIN))}")
    for groupe in bulletin["groupes"]:
        assert set(groupe) == set(_CLES_GROUPE), (
            f"schema de groupe variable : {sorted(set(groupe) ^ set(_CLES_GROUPE))}")
        assert groupe["record_ids"] == sorted(groupe["record_ids"]), "record_ids non trié"
        assert groupe["source_ids"] == sorted(groupe["source_ids"]), "source_ids non trié"
        assert groupe["n_records"] == len(groupe["record_ids"])
        assert groupe["source_inconnue"] == (
            len(groupe["source_ids"]) < groupe["n_sources"]), "source_inconnue incohérent"
    assert [g["valeur_normalisee"] for g in bulletin["groupes"]] == sorted(
        g["valeur_normalisee"] for g in bulletin["groupes"]), "groupes non triés"


def verifie_dore(dore, membres):
    """Propriétés portées par TOUT enregistrement doré, appliquées à tous les cas du fichier."""
    assert set(dore) == set(_CLES_DORE), (
        f"schema variable : {sorted(set(dore) ^ set(_CLES_DORE))}")
    assert dore["record_ids_sources"] == sorted(r["record_id"] for r in membres), (
        "record_ids_sources doit être EXACTEMENT les membres, pas un sous-ensemble")
    for attribut in _ATTRIBUTS:
        valeur, origine = dore[attribut], dore["origines"][attribut]
        assert (origine is None) == (valeur is None), (
            f"{attribut} : provenance et valeur ne se répondent plus")
        if valeur is not None:
            assert valeur in [r.get(attribut) for r in membres], (
                f"{attribut} : valeur INVENTÉE {valeur!r} — la consolidation sélectionne")
            assert origine in dore["record_ids_sources"]
            assert dict(membres[[r["record_id"] for r in membres].index(origine)])[
                attribut] == valeur, f"{attribut} : la provenance ne porte pas la valeur"


# =================== 1. Cardinalité et schéma constant — DoD-3 =======================
def test_un_enregistrement_dore_par_entite_et_pas_un_de_plus():
    """DoD-3 : `len(sortie) == len(partition)`, le contrat de cardinalité du mandat."""
    records = [_rec("R1", "A", nom="Dupont"), _rec("R2", "B", nom="Dupont"),
               _rec("R3", "C", nom="Martin"), _rec("R4", "A", nom="Durand")]
    partition = [["R1", "R2"], ["R3"], ["R4"]]
    dores = fus.consolide_partition(partition, records)
    assert len(dores) == len(partition) == 3
    for dore, membres in zip(dores, partition):
        assert dore["record_ids_sources"] == membres


def test_le_schema_est_constant_sur_tous_les_chemins():
    """Singleton, désaccord total, tout absent, groupe de cinq : toujours les 10 mêmes clés.

    Un contrat qui change de forme selon la branche est un contrat qu'aucun appelant ne peut
    consommer sans condition. Le message par différence symétrique nomme l'écart exact.
    """
    chemins = {
        "singleton": [_rec("R1", "A", nom="Dupont", ville="Paris")],
        "desaccord_total": [_rec("R1", "A", nom="Dupont"), _rec("R2", "B", nom="Martin")],
        "tout_absent": [_rec("R1", "A"), _rec("R2", "B")],
        "groupe_de_cinq": [_rec(f"R{n}", f"S{n}", nom="Dupont", ville="Lyon")
                           for n in range(1, 6)],
    }
    for nom, membres in sorted(chemins.items()):
        dore = fus.consolide_entite(membres)
        assert set(dore) == set(_CLES_DORE), (
            f"{nom} : schema variable -> {sorted(set(dore) ^ set(_CLES_DORE))}")
        verifie_dore(dore, membres)
    garde_non_vacuite(chemins=chemins)


def test_un_groupe_sans_aucune_valeur_reste_un_enregistrement_valide():
    """Huit attributs nuls, huit provenances nulles, aucune exception."""
    membres = [_rec("R1", "A"), _rec("R2", "B")]
    dore = fus.consolide_entite(membres)
    assert dore["record_ids_sources"] == ["R1", "R2"]
    assert all(dore[a] is None for a in _ATTRIBUTS)
    assert all(dore["origines"][a] is None for a in _ATTRIBUTS)


def test_un_singleton_est_la_projection_de_son_enregistrement():
    """Aucun chemin de conflit n'est exercé : la valeur est celle du seul membre."""
    membres = [_rec("R1", "A", nom="Dupont", ville="Paris", code_postal="75011")]
    dore = fus.consolide_entite(membres)
    assert (dore["nom"], dore["ville"], dore["code_postal"]) == ("Dupont", "Paris", "75011")
    assert dore["origines"]["nom"] == "R1"
    assert fus.trace_selection(membres, "nom")["decision"]["regle"] == fus.CANDIDAT_UNIQUE


# =================== 2. L'ambiguïté du mandat, tranchée et éprouvée — DoD-4 ==========
_CONTRE_EXEMPLE = [_rec("R1", "SRC_A", nom="Dupont"),
                   _rec("R2", "SRC_B", nom="Dupont"),
                   _rec("R3", "SRC_C", nom="Dupont Xk")]


def test_les_deux_lectures_du_mandat_different_bien_sur_le_contre_exemple():
    """Le mandat énonce l'ordre deux fois et pas dans le même sens (§0 et §3).

    Ce test asserte D'ABORD que les deux politiques DIVERGENT : sans cela, on ne prouverait
    pas que le choix par défaut est un choix réel. Puis il fige la lecture retenue —
    majorité d'abord — et le contre-exemple qui la motive.
    """
    par_defaut = fus.consolide_entite(_CONTRE_EXEMPLE)
    autre = fus.consolide_entite(_CONTRE_EXEMPLE,
                                 politique=fus.POLITIQUE_COMPLETUDE_DABORD)
    assert par_defaut["nom"] != autre["nom"], (
        "les deux politiques coincident : le contre-exemple ne separe rien, oracle mort")
    assert par_defaut["nom"] == "Dupont", "la majorite doit l'emporter par defaut"
    assert autre["nom"] == "Dupont Xk"
    assert fus.POLITIQUE_DEFAUT[0] == fus.MAJORITE


def test_sur_un_groupe_de_deux_les_deux_ordres_coincident():
    """Le désaccord entre les deux lectures ne vit qu'à partir de trois membres.

    Sur deux membres la majorité est toujours à égalité 1–1 et n'élimine personne : c'est ce
    qui rend le choix de l'ordre peu coûteux, et c'est vérifié plutôt qu'affirmé.
    """
    membres = [_rec("R1", "SRC_A", nom="Dupont"), _rec("R2", "SRC_B", nom="Dupont Xk")]
    assert (fus.consolide_entite(membres)["nom"]
            == fus.consolide_entite(membres, politique=fus.POLITIQUE_COMPLETUDE_DABORD)["nom"])
    decision = fus.trace_selection(membres, "nom")["decision"]
    assert fus.MAJORITE in decision["regles_abstenues"], "la majorite aurait dû s'abstenir"


# =================== 3. Le vote porte sur les FORMES NORMALISÉES — DoD-4 =============
def test_le_regroupement_par_forme_normalisee_ne_renverse_pas_la_majorite():
    """Sans regroupement, la majorité ne serait pas affaiblie : elle serait INVERSÉE.

    Quatre écritures d'un même prénom (une voix chacune) perdraient face à une cinquième
    valeur portée par deux sources. Le regroupement rétablit 4 contre 2.
    """
    membres = [_rec("R1", "S1", prenom="Jean-Pierre"), _rec("R2", "S2", prenom="JEAN PIERRE"),
               _rec("R3", "S3", prenom="jean pierre"), _rec("R4", "S4", prenom="Jean Pierre"),
               _rec("R5", "S5", prenom="Marc"), _rec("R6", "S6", prenom="Marc")]
    bulletin = fus.trace_selection(membres, "prenom")["bulletin"]
    assert bulletin["n_groupes"] == 2, "les écritures d'un même prénom n'ont pas été réunies"
    poids = {g["valeur_normalisee"]: g["n_sources"] for g in bulletin["groupes"]}
    assert poids == {"jean pierre": 4, "marc": 2}
    assert fus.consolide_entite(membres)["prenom"] == "Jean-Pierre"


def test_la_completude_ne_departage_jamais_deux_ecritures_d_une_meme_valeur():
    """« Plus complet » porte sur la forme NORMALISÉE, jamais sur la longueur BRUTE.

    Le test qui tue la longueur brute : deux écritures d'un même numéro tombent dans UN seul
    groupe, donc la complétude n'a rien à départager. Avec la longueur brute, l'écriture la
    plus ponctuée gagnerait — un classement par densité de ponctuation.
    """
    for attribut, ecritures in (("telephone", ("01 45 67 89 01", "0033145678901")),
                                ("date_naissance", ("1970-3-7", "07/03/1970"))):
        membres = [_rec("R1", "S1", **{attribut: ecritures[0]}),
                   _rec("R2", "S2", **{attribut: ecritures[1]})]
        trace = fus.trace_selection(membres, attribut)
        assert trace["bulletin"]["n_groupes"] == 1, f"{attribut} : écritures non réunies"
        assert trace["decision"]["regle"] == fus.CANDIDAT_UNIQUE, attribut
        longueurs = {len(e) for e in ecritures}
        assert len(longueurs) == 2, "les deux écritures ont la même longueur brute : oracle mort"


def test_la_completude_compare_des_longueurs_NORMALISEES_et_non_brutes():
    """LE cas qui sépare les deux grandeurs : un couple dont les deux ordres sont INVERSES.

    Le test précédent montre que deux écritures d'une même valeur ne se départagent pas —
    mais dans ce cas la règle de complétude n'est même pas atteinte, il n'y a qu'un seul
    seau. Il ne peut donc rien dire de la grandeur sur laquelle la règle compare.

    Ici, le retrait de la forme juridique par le normaliseur inverse les deux ordres :
    « S.A.R.L. Boulanger » est plus long en BRUT et plus court une fois NORMALISÉ. Substituer
    l'une des grandeurs à l'autre change la valeur retenue — c'est exactement le défaut que
    la docstring du module déclare combattre.
    """
    court_en_brut, long_en_brut = "Charcuterie", "S.A.R.L. Boulanger"
    assert len(court_en_brut) < len(long_en_brut), "ordre BRUT : oracle mort"
    normalise = nrm.NORMALISEURS["nom"]
    assert len(normalise(court_en_brut)) > len(normalise(long_en_brut)), (
        "ordre NORMALISE non inverse : le couple ne separe plus les deux grandeurs")
    membres = [_rec("R1", "S1", nom=court_en_brut), _rec("R2", "S2", nom=long_en_brut)]
    trace = fus.trace_selection(membres, "nom")
    assert {g["valeur_normalisee"]: g["longueur_normalisee"]
            for g in trace["bulletin"]["groupes"]} == {"boulanger": 9, "charcuterie": 11}
    assert trace["decision"]["regle"] == fus.COMPLETUDE
    assert fus.consolide_entite(membres)["nom"] == court_en_brut


def test_les_diacritiques_cohabitent_dans_un_groupe_et_la_plus_frequente_est_emise():
    """La normalisation replie les accents : il faut encore choisir l'écriture à émettre."""
    membres = [_rec("R1", "S1", ville="Marché"), _rec("R2", "S2", ville="Marche"),
               _rec("R3", "S3", ville="Marche")]
    bulletin = fus.trace_selection(membres, "ville")["bulletin"]
    assert bulletin["n_groupes"] == 1
    assert fus.consolide_entite(membres)["ville"] == "Marche"
    assert fus.consolide_entite(membres)["origines"]["ville"] == "R2"


def test_l_eligibilite_suit_la_convention_de_manquant_du_moteur():
    """Un candidat est celui dont la forme normalisée n'est pas nulle. Jamais `if valeur`.

    Trois pièges en un : la chaîne vide et les blancs ne sont pas des candidats ; un code
    postal réduit à « 0 » en est un — un test de vérité booléenne le ferait disparaître.
    """
    membres = [_rec("R1", "S1", ville=""), _rec("R2", "S2", ville="   "),
               _rec("R3", "S3", ville="Lyon")]
    trace = fus.trace_selection(membres, "ville")
    assert trace["bulletin"]["n_candidats"] == 1, "le vide a été compté comme un candidat"
    assert trace["decision"]["regle"] == fus.CANDIDAT_UNIQUE
    assert fus.consolide_entite(membres)["ville"] == "Lyon"

    vides = [_rec("R1", "S1", ville=""), _rec("R2", "S2", ville="-")]
    decision = fus.trace_selection(vides, "ville")["decision"]
    assert decision["regle"] == fus.AUCUN_CANDIDAT
    assert decision["valeur"] is None and decision["rang_regle"] is None

    zero = [_rec("R1", "S1", code_postal="0"), _rec("R2", "S2")]
    assert fus.consolide_entite(zero)["code_postal"] == "0", "« 0 » a été pris pour un vide"


def test_un_attribut_present_chez_un_seul_membre_est_conserve():
    """Le dénominateur est le nombre de CANDIDATS : une absence n'est pas un vote contre.

    Sinon un attribut présent chez un seul membre sur trois serait « non résolu », et la
    consolidation détruirait la seule information dont l'entité dispose.
    """
    membres = [_rec("R1", "S1", email="a@x.fr"), _rec("R2", "S2"), _rec("R3", "S3")]
    dore = fus.consolide_entite(membres)
    assert dore["email"] == "a@x.fr" and dore["origines"]["email"] == "R1"
    assert fus.trace_selection(membres, "email")["bulletin"]["n_membres"] == 3


def test_une_cle_absente_et_une_valeur_nulle_se_comportent_pareil():
    """Un enregistrement tronqué ne doit pas se distinguer d'un enregistrement à trou."""
    complet = [_rec("R1", "S1", nom="Dupont"), _rec("R2", "S2")]
    tronque = [_rec("R1", "S1", nom="Dupont"), {"record_id": "R2", "source_id": "S2"}]
    assert fus.consolide_entite(complet) == fus.consolide_entite(tronque)


# =================== 4. Le vote pèse des SOURCES, pas des enregistrements — DoD-4 ====
def test_la_majorite_compte_les_sources_distinctes_et_non_les_enregistrements():
    """Deux enregistrements d'UNE même source ne pèsent qu'une voix.

    Motif propre à ce projet : deux enregistrements d'une même source dans une même entité
    ne peuvent venir que d'un sur-regroupement. Compter leurs voix séparément laisserait une
    erreur d'appariement piloter le contenu du produit. Le test pince la RÈGLE, pas son
    effet : il asserte les DEUX lectures — 1 contre 1 en sources, 2 contre 1 en records.
    """
    membres = [_rec("R1", "SRC_A", ville="Lyon"), _rec("R2", "SRC_A", ville="Lyon"),
               _rec("R3", "SRC_B", ville="Nice")]
    bulletin = fus.trace_selection(membres, "ville")["bulletin"]
    poids = {g["valeur_normalisee"]: (g["n_sources"], g["n_records"])
             for g in bulletin["groupes"]}
    assert poids == {"lyon": (1, 2), "nice": (1, 1)}, "le vote a compté des enregistrements"
    decision = fus.trace_selection(membres, "ville")["decision"]
    assert fus.MAJORITE in decision["regles_abstenues"], "la majorité aurait dû s'abstenir"


def test_metamorphique_dupliquer_un_enregistrement_de_source_connue_ne_change_rien():
    """Ajouter un doublon de source laisse les 8 valeurs ET les 8 règles inchangées.

    Seule `record_ids_sources` bouge, et c'est légitime : le groupe a bien un membre de plus.
    """
    base = [_rec("R1", "SRC_A", nom="Dupont", ville="Lyon"),
            _rec("R3", "SRC_B", nom="Martin", ville="Nice")]
    avec_doublon = base + [_rec("R2", "SRC_A", nom="Dupont", ville="Lyon")]
    dore_base, dore_double = fus.consolide_entite(base), fus.consolide_entite(
        sorted(avec_doublon, key=lambda r: r["record_id"]))
    for attribut in _ATTRIBUTS:
        assert dore_base[attribut] == dore_double[attribut], attribut
        regle_base = fus.trace_selection(base, attribut)["decision"]["regle"]
        regle_double = fus.trace_selection(avec_doublon, attribut)["decision"]["regle"]
        assert regle_base == regle_double, f"{attribut} : la règle a changé"
    assert dore_base["record_ids_sources"] != dore_double["record_ids_sources"]


def test_un_enregistrement_sans_source_pese_une_voix_et_une_seule():
    """Le seau « source inconnue » vote — une fois, pas zéro, pas deux.

    Ne compter que les sources NOMMÉES priverait de tout droit de vote la classe entière des
    enregistrements sans `source_id` : ici la valeur retenue basculerait de Lyon à Nice. Le
    test asserte les trois voies à la fois — poids, abstention, valeur — et couvre au
    passage `record_ids`, `source_ids` et `source_inconnue`.
    """
    membres = [_rec("R1", None, ville="Lyon"), _rec("R2", None, ville="Lyon"),
               _rec("R3", "SRC_B", ville="Nice")]
    trace = fus.trace_selection(membres, "ville")
    assert {g["valeur_normalisee"]: (g["n_sources"], g["n_records"], g["source_inconnue"],
                                     g["record_ids"], g["source_ids"])
            for g in trace["bulletin"]["groupes"]} == {
        "lyon": (1, 2, True, ["R1", "R2"], []),
        "nice": (1, 1, False, ["R3"], ["SRC_B"])}
    assert fus.MAJORITE in trace["decision"]["regles_abstenues"]
    assert fus.consolide_entite(membres)["ville"] == "Lyon"


def test_le_rang_d_un_groupe_est_celui_de_sa_MEILLEURE_source():
    """Un seau porté par PLUSIEURS sources prend le rang de la mieux classée.

    Partout ailleurs dans ce fichier, chaque valeur normalisée n'est portée que par une
    source : `min` et `max` y sont indiscernables, et l'agrégation n'est donc jamais
    éprouvée. Ici les deux seaux ont deux sources chacun, et les échanger inverse la règle.
    """
    priorite = ("SRC_A", "SRC_B", "SRC_C", "SRC_D")
    membres = [_rec("R1", "SRC_A", ville="Lyon"), _rec("R2", "SRC_D", ville="Lyon"),
               _rec("R3", "SRC_B", ville="Nice"), _rec("R4", "SRC_C", ville="Nice")]
    trace = fus.trace_selection(membres, "ville", priorite_sources=priorite)
    assert {g["valeur_normalisee"]: (g["rang_source"], g["n_sources"])
            for g in trace["bulletin"]["groupes"]} == {"lyon": (0, 2), "nice": (1, 2)}
    assert trace["decision"]["regle"] == fus.SOURCE_PRIORITAIRE
    assert fus.consolide_entite(membres, priorite_sources=priorite)["ville"] == "Lyon"


def test_une_source_absente_ou_inconnue_est_classee_en_DERNIER():
    """`-1` ou `0` en feraient la source la PLUS prioritaire : un trou de schéma
    renverserait silencieusement une politique déclarée."""
    membres = [_rec("R1", None, ville="Lyon"), _rec("R2", "SRC_B", ville="Nice")]
    rangs = {g["valeur_normalisee"]: g["rang_source"]
             for g in fus.trace_selection(membres, "ville",
                                          priorite_sources=("SRC_B",))["bulletin"]["groupes"]}
    assert rangs == {"lyon": 1, "nice": 0}, "la source absente n'est pas au dernier rang"
    dore = fus.consolide_entite(membres, priorite_sources=("SRC_B",))
    assert dore["ville"] == "Nice"


def test_une_table_de_priorite_vide_n_invente_aucun_ordre():
    """Table vide : tous les rangs valent 0, la règle s'abstient.

    Inventer un ordre alphabétique sur les identifiants de source serait une décision métier
    non déclarée, sous couvert de déterminisme.
    """
    membres = [_rec("R1", "SRC_A", ville="Lyon"), _rec("R2", "SRC_B", ville="Nice")]
    decision = fus.trace_selection(membres, "ville")["decision"]
    assert fus.SOURCE_PRIORITAIRE in decision["regles_abstenues"]
    assert decision["regle"] == fus.ORDRE_CANONIQUE
    assert decision["valeur"] == "Lyon", "« lyon » < « nice » : la règle terminale a tranché"


# =================== 5. Les quatre règles sont des FILTRES PURS — DoD-4 ==============
def _groupe(valeur, n_sources=1, longueur=None, rang=0, rid="R1"):
    """Groupe de bulletin littéral, réduit aux seuls champs que les règles consomment."""
    return {"valeur_normalisee": valeur,
            "longueur_normalisee": len(valeur) if longueur is None else longueur,
            "n_sources": n_sources, "n_records": n_sources, "rang_source": rang,
            "source_ids": [], "source_inconnue": False, "record_ids": [rid],
            "formes_brutes": [{"forme": valeur, "n_records": 1, "record_id_min": rid}]}


_FILTRES = ((fus.MAJORITE, fus.regle_majorite), (fus.COMPLETUDE, fus.regle_completude),
            (fus.SOURCE_PRIORITAIRE, fus.regle_source_prioritaire),
            (fus.ORDRE_CANONIQUE, fus.regle_ordre_canonique))


def test_chaque_regle_isolee_sur_trois_groupes_litteraux():
    """Chaque règle est pinçable SEULE, sans enregistrement, sans groupe, sans partition."""
    trois = [_groupe("aa", n_sources=3, rang=2), _groupe("bbbb", n_sources=1, rang=0),
             _groupe("cc", n_sources=1, rang=1)]
    assert [g["valeur_normalisee"] for g in fus.regle_majorite(trois)] == ["aa"]
    assert [g["valeur_normalisee"] for g in fus.regle_completude(trois)] == ["bbbb"]
    assert [g["valeur_normalisee"] for g in fus.regle_source_prioritaire(trois)] == ["bbbb"]
    assert [g["valeur_normalisee"] for g in fus.regle_ordre_canonique(trois)] == ["aa"]


def test_s_abstenir_c_est_rendre_la_liste_inchangee_donc_observable():
    """L'abstention est un ÉTAT OBSERVABLE, et non un silence."""
    ex_aequo = [_groupe("aa", n_sources=2), _groupe("bb", n_sources=2)]
    assert fus.regle_majorite(ex_aequo) == ex_aequo
    assert fus.regle_completude(ex_aequo) == ex_aequo
    assert fus.regle_source_prioritaire(ex_aequo) == ex_aequo


def test_les_regles_sont_des_filtres_idempotents_et_reducteurs():
    """`1 <= len(r(x)) <= len(x)` et `r(r(x)) == r(x)`, sur tous les littéraux du fichier."""
    jeux = {
        "trois_distincts": [_groupe("aa", 3, rang=2), _groupe("bbbb", 1), _groupe("cc", 1, rang=1)],
        "ex_aequo": [_groupe("aa", 2), _groupe("bb", 2)],
        "un_seul": [_groupe("aa", 1)],
    }
    for nom_jeu, entree in sorted(jeux.items()):
        for nom_regle, filtre in _FILTRES:
            sortie = filtre(entree)
            assert 1 <= len(sortie) <= len(entree), f"{nom_jeu}/{nom_regle} : cardinalité"
            assert filtre(sortie) == sortie, f"{nom_jeu}/{nom_regle} : non idempotent"
            assert all(g in entree for g in sortie), f"{nom_jeu}/{nom_regle} : groupe inventé"
    for _, filtre in _FILTRES:
        assert filtre([]) == [], "une règle doit tolérer une liste vide"
    garde_non_vacuite(jeux=jeux)


def test_l_arbitrage_d_un_bulletin_ecrit_a_la_main():
    """Le SEUL test où l'entrée de l'arbitrage ne vient pas de `valeurs_candidates`.

    Tous les autres partent d'un bulletin produit par le module : une erreur de regroupement
    y serait invisible, puisque l'attendu en découlerait. Ici, le bulletin est un littéral et
    la valeur attendue se déduit de la cascade par lecture — les deux étages sont découplés.
    """
    bulletin = {"attribut": "ville", "n_membres": 4, "n_candidats": 4, "n_groupes": 3,
                "groupes": [_groupe("aa", n_sources=1, rang=0, rid="R3"),
                            _groupe("bbbb", n_sources=2, rang=2, rid="R1"),
                            _groupe("cc", n_sources=2, rang=1, rid="R2")]}
    decision = fus.arbitre_attribut(bulletin, fus.POLITIQUE_DEFAUT)
    # MAJORITE garde bbbb et cc (2 sources) ; COMPLETUDE garde bbbb (4 > 2) : elle tranche.
    assert (decision["regle"], decision["valeur"], decision["origine"]) == (
        fus.COMPLETUDE, "bbbb", "R1")
    assert decision["rang_regle"] == 1 and decision["regles_abstenues"] == []
    # MAJORITE a RESTREINT (3 -> 2) sans DÉCIDER : elle n'est donc ni créditée ni abstenue,
    # et son écart de tête vaut 0 — c'est précisément ce qui explique qu'elle n'ait pas
    # tranché seule. COMPLETUDE, elle, tranche avec une marge de 2 (« bbbb » 4 contre 2).
    assert decision["ecart_majorite"] == 0 and decision["ecart_completude"] == 2
    autre = fus.arbitre_attribut(bulletin, fus.POLITIQUE_COMPLETUDE_DABORD)
    assert (autre["regle"], autre["valeur"]) == (fus.COMPLETUDE, "bbbb")
    assert _reference_independante(bulletin, fus.POLITIQUE_DEFAUT) == ("bbbb", "R1")


def test_aucun_normaliseur_ne_rend_de_forme_vide_non_nulle():
    """Ce qui rend `is not None` et un test de vérité booléenne ÉQUIVALENTS aujourd'hui.

    L'éligibilité d'un candidat est écrite `forme is not None`. Elle ne se distingue d'un
    `if forme:` que si un normaliseur peut rendre une valeur falsy sans rendre `None` —
    aujourd'hui aucun ne le fait, tous finissant par `return s or None`. Le témoin
    `code_postal == "0"` ne peut donc PAS pincer cette distinction : `bool("0")` est vrai.

    C'est l'invariant lui-même qu'il faut figer, et il vit dans un module que la fusion n'a pas
    le droit de modifier : le jour où il tombe, c'est ici que la différence apparaîtra.
    """
    temoins = ("", "   ", "-", "0", "0000", ".", "--", "\t", "SARL", "S.A.R.L.",
               "Jean-Pierre", "00", "+", "()")
    n_verifs = 0
    for attribut in _ATTRIBUTS:
        for temoin in temoins:
            forme = nrm.NORMALISEURS[attribut](temoin)
            assert forme is None or bool(forme), (
                f"{attribut}({temoin!r}) = {forme!r} : forme vide NON nulle — l'eligibilite "
                f"par `is not None` cesse de coincider avec un test de verite booleenne")
            n_verifs += 1
    assert n_verifs == len(_ATTRIBUTS) * len(temoins)


def test_la_regle_terminale_rend_toujours_exactement_un_groupe():
    """C'est ce qui la rend TOTALE, donc ce qui autorise à clore la cascade avec elle."""
    for entree in ([_groupe("aa"), _groupe("bb"), _groupe("cc")],
                   [_groupe("bb"), _groupe("aa")], [_groupe("aa")]):
        assert len(fus.regle_ordre_canonique(entree)) == 1
    assert fus.regle_ordre_canonique(
        [_groupe("bb"), _groupe("aa")])[0]["valeur_normalisee"] == "aa"
    assert fus.POLITIQUE_DEFAUT[-1] == fus.REGLE_TERMINALE


def test_une_politique_invalide_est_refusee_a_l_entree():
    """Une cascade non terminale lèverait au MILIEU d'une consolidation, à moitié faite."""
    membres = [_rec("R1", "S1", nom="Dupont"), _rec("R2", "S2", nom="Martin")]
    for politique in ((), (fus.MAJORITE,), (fus.MAJORITE, fus.MAJORITE, fus.ORDRE_CANONIQUE),
                      ("INCONNUE", fus.ORDRE_CANONIQUE),
                      (fus.ORDRE_CANONIQUE, fus.MAJORITE)):
        with pytest.raises(ValueError):
            fus.consolide_entite(membres, politique=politique)
    with pytest.raises(ValueError):
        fus.consolide_entite(membres, priorite_sources=("A", "A"))
    with pytest.raises(ValueError):
        fus.consolide_entite(membres, priorite_sources=("A", 3))


def test_chaque_code_de_selection_est_atteint_au_moins_une_fois():
    """Couverture du registre FERMÉ : sans ce test, une règle morte passerait au vert."""
    scenarios = {
        fus.AUCUN_CANDIDAT: ([_rec("R1", "S1"), _rec("R2", "S2")], "ville", ()),
        fus.CANDIDAT_UNIQUE: ([_rec("R1", "S1", ville="Lyon"), _rec("R2", "S2")], "ville", ()),
        fus.MAJORITE: ([_rec("R1", "S1", ville="Lyon"), _rec("R2", "S2", ville="Lyon"),
                        _rec("R3", "S3", ville="Nice")], "ville", ()),
        fus.COMPLETUDE: ([_rec("R1", "S1", ville="Lyon"),
                          _rec("R2", "S2", ville="Lyon Cedex")], "ville", ()),
        fus.SOURCE_PRIORITAIRE: ([_rec("R1", "SRC_A", ville="Nice"),
                                  _rec("R2", "SRC_B", ville="Lyon")], "ville", ("SRC_A",)),
        fus.ORDRE_CANONIQUE: ([_rec("R1", "S1", ville="Nice"),
                               _rec("R2", "S2", ville="Lyon")], "ville", ()),
    }
    assert set(scenarios) == set(fus.CODES_SELECTION), (
        f"registre non couvert : {sorted(set(fus.CODES_SELECTION) ^ set(scenarios))}")
    for code, (membres, attribut, priorite) in sorted(scenarios.items()):
        decision = fus.trace_selection(membres, attribut,
                                       priorite_sources=priorite)["decision"]
        assert decision["regle"] == code, (
            f"scenario {code} : regle obtenue {decision['regle']}")
        if code in fus.MOTIFS:
            assert decision["rang_regle"] is None, f"{code} n'est pas un arbitrage"
        else:
            assert decision["rang_regle"] == fus.POLITIQUE_DEFAUT.index(code), code


def test_l_ecart_de_majorite_est_toujours_publie_et_explique_l_abstention():
    """« 0 » explique une abstention ; une marge non nulle documente la décision."""
    tranche = [_rec("R1", "S1", ville="Lyon"), _rec("R2", "S2", ville="Lyon"),
               _rec("R3", "S3", ville="Nice")]
    ex_aequo = [_rec("R1", "S1", ville="Lyon"), _rec("R2", "S2", ville="Nice")]
    assert fus.trace_selection(tranche, "ville")["decision"]["ecart_majorite"] == 1
    assert fus.trace_selection(ex_aequo, "ville")["decision"]["ecart_majorite"] == 0
    completude = [_rec("R1", "S1", ville="Lyon"), _rec("R2", "S2", ville="Lyon Cedex")]
    decision = fus.trace_selection(completude, "ville")["decision"]
    assert decision["regle"] == fus.COMPLETUDE and decision["ecart_completude"] > 0
    assert fus.trace_selection(tranche, "ville")["decision"]["ecart_completude"] is None


# =================== 6. Conflits, traçabilité, rejouabilité — DoD-5 ==================
_CONFLIT_TOTAL = [_rec("R1", "SRC_A", nom="Dupont", prenom="Marie", date_naissance="1981-06-18",
                       adresse="12 rue des Lilas", code_postal="75011", ville="Paris",
                       email="m.dupont@x.fr", telephone="0145678901"),
                  _rec("R2", "SRC_B", nom="Martin", prenom="Alice", date_naissance="1979-04-02",
                       adresse="34 rue des Roses", code_postal="69003", ville="Lyon",
                       email="a.martin@y.fr", telephone="0478901234")]


def test_un_desaccord_sur_les_huit_attributs_est_tranche_par_la_source_prioritaire():
    """Longueurs normalisées volontairement proches : la cascade doit tomber jusqu'à R3."""
    dore = fus.consolide_entite(_CONFLIT_TOTAL, priorite_sources=("SRC_B", "SRC_A"))
    verifie_dore(dore, _CONFLIT_TOTAL)
    tranches = [a for a in _ATTRIBUTS
                if fus.trace_selection(_CONFLIT_TOTAL, a,
                                       priorite_sources=("SRC_B", "SRC_A")
                                       )["decision"]["regle"] == fus.SOURCE_PRIORITAIRE]
    garde_non_vacuite(attributs_tranches_par_la_source=tranches)
    for attribut in tranches:
        assert dore["origines"][attribut] == "R2", attribut


def test_le_rejeu_depuis_la_seule_trace_retrouve_chaque_valeur():
    """LE test de traçabilité : un tiers qui n'a que la trace refait la décision.

    L'aller-retour JSON est obligatoire — il prouve que rien n'a transité par une identité
    d'objet Python qui ne survivrait pas à l'archivage. Deux ré-arbitrages sont exercés :
    celui du module, et une réimplémentation naïve écrite dans ce fichier, qui prouve que la
    trace suffit à qui n'a PAS le module.
    """
    cas = {"conflit_total": (_CONFLIT_TOTAL, ("SRC_B", "SRC_A")),
           "contre_exemple": (_CONTRE_EXEMPLE, ()),
           "singleton": ([_rec("R1", "S1", nom="Dupont")], ())}
    n_rejeux = 0
    for nom_cas, (membres, priorite) in sorted(cas.items()):
        dore = fus.consolide_entite(membres, priorite_sources=priorite)
        for attribut in _ATTRIBUTS:
            trace = fus.trace_selection(membres, attribut, priorite_sources=priorite)
            archive = json.loads(json.dumps(trace["bulletin"]))
            rejoue = fus.arbitre_attribut(archive, fus.POLITIQUE_DEFAUT)
            assert rejoue["valeur"] == dore[attribut], f"{nom_cas}/{attribut} : rejeu"
            assert rejoue["origine"] == dore["origines"][attribut], f"{nom_cas}/{attribut}"
            valeur, origine = _reference_independante(archive, fus.POLITIQUE_DEFAUT)
            assert (valeur, origine) == (dore[attribut], dore["origines"][attribut]), (
                f"{nom_cas}/{attribut} : la trace ne suffit pas a un tiers")
            n_rejeux += 1
    assert n_rejeux == 3 * len(_ATTRIBUTS), f"oracle maigre : {n_rejeux} rejeux"


def test_controle_negatif_retirer_un_champ_de_la_trace_casse_le_rejeu():
    """Sans ce contrôle, un champ DÉCORATIF s'installerait dans la trace sans que rien ne le
    signale — et la trace grossirait sans porter d'information.

    Chaque champ est éprouvé DANS LE SCÉNARIO OÙ IL TRANCHE, et non dans un scénario
    unique : la cascade s'arrête dès qu'un groupe survit, donc un scénario tranché par la
    complétude n'atteint jamais la règle de source et laisserait `rang_source` passer pour
    décoratif. Le test asserte donc d'abord que la règle attendue est bien celle qui décide
    — sans quoi il ne prouverait rien de ce champ-là.
    """
    scenarios = {
        "n_sources": ([_rec("R1", "SRC_A", ville="Lyon"), _rec("R2", "SRC_B", ville="Lyon"),
                       _rec("R3", "SRC_C", ville="Nice")], (), fus.MAJORITE),
        "longueur_normalisee": ([_rec("R1", "SRC_A", ville="Lyon"),
                                 _rec("R2", "SRC_B", ville="Lyon Cedex")],
                                (), fus.COMPLETUDE),
        "rang_source": ([_rec("R1", "SRC_A", ville="Nice"), _rec("R2", "SRC_B", ville="Lyon")],
                        ("SRC_B", "SRC_A"), fus.SOURCE_PRIORITAIRE),
        "valeur_normalisee": ([_rec("R1", "SRC_A", ville="Nice"),
                               _rec("R2", "SRC_B", ville="Lyon")], (), fus.ORDRE_CANONIQUE),
        "formes_brutes": ([_rec("R1", "SRC_A", ville="Lyon"),
                           _rec("R2", "SRC_B", ville="Lyon")], (), fus.CANDIDAT_UNIQUE),
    }
    assert set(scenarios) == set(_CHAMPS_PORTEURS), (
        f"la liste des champs porteurs a bouge : {sorted(set(scenarios) ^ set(_CHAMPS_PORTEURS))}")
    for champ, (membres, priorite, regle_attendue) in sorted(scenarios.items()):
        reference = fus.trace_selection(membres, "ville", priorite_sources=priorite)
        verifie_bulletin(reference["bulletin"])
        assert reference["decision"]["regle"] == regle_attendue, (
            f"{champ} : le scenario est tranche par {reference['decision']['regle']}, "
            f"il ne met donc pas ce champ sur le chemin de la decision")
        assert reference["decision"]["valeur"] is not None
        mutile = json.loads(json.dumps(reference["bulletin"]))
        for groupe in mutile["groupes"]:
            groupe.pop(champ, None)
        with pytest.raises((KeyError, TypeError)):
            fus.arbitre_attribut(mutile, fus.POLITIQUE_DEFAUT)
    # Et la provenance de l'écriture est elle aussi porteuse, pas décorative.
    membres = scenarios["formes_brutes"][0]
    mutile = json.loads(json.dumps(
        fus.trace_selection(membres, "ville")["bulletin"]))
    for groupe in mutile["groupes"]:
        for ecriture in groupe["formes_brutes"]:
            ecriture.pop("record_id_min", None)
    with pytest.raises(KeyError):
        fus.arbitre_attribut(mutile, fus.POLITIQUE_DEFAUT)


def test_la_partition_champs_porteurs_champs_de_lecture_est_exacte():
    """Le module DÉCLARE que cinq champs sont de lecture pure. Ici on le VÉRIFIE.

    Sans cet oracle, la déclaration reste de la prose : un champ de lecture pourrait devenir
    porteur (ou l'inverse) sans que rien ne bouge. Le balayage porte sur TOUS les champs
    publiés, et chacun tombe d'un côté ou de l'autre — jamais entre les deux.

    Un champ n'est « de lecture » que si AUCUN chemin ne le lit : le balayage court donc sur
    plusieurs jeux ET sur les deux politiques, de façon que chaque règle de la cascade soit
    effectivement atteinte quelque part. Un seul jeu ne suffirait pas — la cascade s'arrête
    dès qu'un groupe survit, et une règle jamais atteinte ferait passer son champ pour mort.
    """
    jeux = (
        ([_rec("R1", "SRC_A", ville="Lyon"), _rec("R2", "SRC_B", ville="Lyon"),
          _rec("R3", "SRC_C", ville="Nice")], ()),                          # MAJORITE
        ([_rec("R1", "SRC_A", ville="Lyon"),
          _rec("R2", "SRC_B", ville="Lyon Cedex")], ()),                    # COMPLETUDE
        ([_rec("R1", "SRC_A", ville="Nice"), _rec("R2", "SRC_D", ville="Nice"),
          _rec("R3", "SRC_B", ville="Lyon"), _rec("R4", "SRC_C", ville="Lyon")],
         ("SRC_B", "SRC_C", "SRC_A", "SRC_D")),                             # SOURCE_PRIORITAIRE
        ([_rec("R1", "SRC_A", ville="Nice"), _rec("R2", "SRC_B", ville="Lyon")], ()),
    )
    politiques = (fus.POLITIQUE_DEFAUT, fus.POLITIQUE_COMPLETUDE_DABORD)
    regles_atteintes, consommes = set(), set()
    for membres, priorite in jeux:
        bulletin = fus.trace_selection(membres, "ville",
                                       priorite_sources=priorite)["bulletin"]
        verifie_bulletin(bulletin)
        for politique in politiques:
            reference = fus.arbitre_attribut(json.loads(json.dumps(bulletin)), politique)
            regles_atteintes.add(reference["regle"])
            for champ in _CLES_GROUPE:
                mutile = json.loads(json.dumps(bulletin))
                for groupe in mutile["groupes"]:
                    groupe.pop(champ, None)
                try:
                    if fus.arbitre_attribut(mutile, politique) != reference:
                        consommes.add(champ)
                except (KeyError, TypeError):
                    consommes.add(champ)
    assert set(fus.REGLES) <= regles_atteintes, (
        f"regles jamais atteintes par le balayage : {sorted(set(fus.REGLES) - regles_atteintes)} "
        f"— leurs champs passeraient a tort pour morts")
    assert consommes == set(_CHAMPS_PORTEURS), (
        f"partition porteurs/lecture fausse : {sorted(consommes ^ set(_CHAMPS_PORTEURS))}")
    garde_non_vacuite(porteurs=_CHAMPS_PORTEURS, consommes=consommes)


def test_forme_retenue_est_totale_meme_sur_un_groupe_mal_forme():
    """La totalité de l'ordre ne doit reposer sur aucune garde qui vit ailleurs.

    `consolide_entite` refuse un `record_id` répété, mais `valeurs_candidates` et
    `trace_selection` l'acceptent : sur ces chemins-là, deux écritures peuvent partager leur
    plus petit `record_id`. La clé de tri se termine donc par l'écriture elle-même.
    """
    membres = [_rec("R1", "S1", ville="Marché"), _rec("R1", "S2", ville="Marche")]
    trace = fus.trace_selection(membres, "ville")
    groupe = trace["bulletin"]["groupes"][0]
    assert [f["record_id_min"] for f in groupe["formes_brutes"]] == ["R1", "R1"], (
        "le cas d'egalite de provenance n'est plus construit : oracle mort")
    assert fus.forme_retenue(groupe) == ("Marche", "R1"), "l'ordre n'est plus total"
    assert fus.forme_retenue(groupe) == fus.forme_retenue(groupe)
    with pytest.raises(ValueError, match="duplique"):
        fus.consolide_entite(membres)


def test_la_trace_ne_peut_pas_diverger_du_produit():
    """Trace et produit délèguent au MÊME arbitre : c'est une propriété, pas une convention."""
    for membres in (_CONFLIT_TOTAL, _CONTRE_EXEMPLE):
        dore = fus.consolide_entite(membres)
        for attribut in _ATTRIBUTS:
            decision = fus.trace_selection(membres, attribut)["decision"]
            assert decision["valeur"] == dore[attribut], attribut
            assert decision["origine"] == dore["origines"][attribut], attribut


def test_la_consolidation_selectionne_et_ne_synthetise_jamais():
    """Invariant de non-invention, en propriété sur tous les cas, plus l'anti-concaténation.

    Composer ENTRE attributs est le principe même du produit ; composer À L'INTÉRIEUR d'un
    attribut est interdit — une valeur synthétisée n'a aucun enregistrement d'origine, et
    `origines` cesserait de pouvoir désigner quoi que ce soit.
    """
    cas = {"conflit_total": _CONFLIT_TOTAL, "contre_exemple": _CONTRE_EXEMPLE,
           "adresses_complementaires": [_rec("R1", "S1", adresse="12 rue des Lilas"),
                                        _rec("R2", "S2", adresse="Batiment C")],
           "telephone_tronque": [_rec("R1", "S1", telephone="01 45"),
                                 _rec("R2", "S2", telephone="0145678901")]}
    for nom_cas, membres in sorted(cas.items()):
        dore = fus.consolide_entite(membres)
        verifie_dore(dore, membres)
        # Anti-synthèse : une valeur COMPOSÉE serait plus longue que toute valeur reçue.
        for attribut in _ATTRIBUTS:
            if dore[attribut] is None:
                continue
            recues = [r.get(attribut) for r in membres if r.get(attribut) is not None]
            assert len(dore[attribut]) <= max(len(v) for v in recues), (
                f"{nom_cas}/{attribut} : {dore[attribut]!r} est plus long que toute valeur "
                f"reçue — la consolidation a SYNTHÉTISÉ au lieu de sélectionner")
    # Le cas cible : deux fragments d'adresse complémentaires ne se concatènent pas.
    dore = fus.consolide_entite(cas["adresses_complementaires"])
    assert dore["adresse"] in ("12 rue des Lilas", "Batiment C")
    # Et un numéro tronqué ne se fait pas compléter par le numéro entier de l'autre source.
    tel = fus.consolide_entite(cas["telephone_tronque"])["telephone"]
    assert tel in ("01 45", "0145678901")


def test_le_dore_porte_exactement_ses_membres_par_egalite():
    """EGALITÉ, jamais inclusion : l'inclusion laisserait passer une perte de sources."""
    membres = [_rec("R1", "S1", nom="Dupont"), _rec("R2", "S2", nom="Dupont"),
               _rec("R3", "S3", nom="Dupont")]
    assert fus.consolide_entite(membres)["record_ids_sources"] == ["R1", "R2", "R3"]


# =================== 7. Déterminisme de la consolidation — DoD-2 =====================
def test_invariance_par_permutation_des_membres():
    """Le tri des seaux a lieu en UN seul endroit, et tout l'aval en dépend.

    L'invariance porte sur `trace_selection`, qui — contrairement à `consolide_entite` —
    accepte des membres NON TRIÉS. Re-trier les membres avant l'appel rendrait le test
    tautologique : il comparerait la sortie d'une entrée à la sortie de la MÊME entrée, et
    le tri qui établit l'invariance pourrait être supprimé sans qu'il rougisse.

    La comparaison porte sur la sérialisation COMPLÈTE du bulletin, pas sur la seule valeur
    retenue : c'est l'ordre des seaux et celui des écritures qui sont en jeu.
    """
    membres = [_rec("R1", "S1", ville="Nice", nom="Marché"),
               _rec("R2", "S2", ville="Lyon", nom="Marche"),
               _rec("R3", "S3", ville="Amiens", nom="Marche")]
    n = 0
    for attribut in ("ville", "nom"):
        attendu = json.dumps(fus.trace_selection(membres, attribut), sort_keys=True,
                             ensure_ascii=False)
        for permutation in itertools.permutations(membres):
            obtenu = json.dumps(fus.trace_selection(list(permutation), attribut),
                                sort_keys=True, ensure_ascii=False)
            assert obtenu == attendu, (
                f"{attribut} / ordre {[r['record_id'] for r in permutation]}")
            n += 1
    assert n == 12, f"oracle maigre : {n} permutations"
    # Et le jeu doit être discriminant : trois seaux, et deux écritures dans l'un d'eux.
    assert fus.trace_selection(membres, "ville")["bulletin"]["n_groupes"] == 3
    assert len(fus.trace_selection(membres, "nom")["bulletin"]["groupes"][0]
               ["formes_brutes"]) == 2, "aucun seau à deux écritures : l'oracle serait aveugle"


def test_appels_repetes_sur_une_entree_identique_sont_stables():
    """Propriété distincte de l'invariance : deux appels successifs coïncident."""
    for membres in (_CONFLIT_TOTAL, _CONTRE_EXEMPLE):
        assert fus.consolide_entite(membres) == fus.consolide_entite(membres)


def test_un_groupe_non_canonique_est_refuse():
    """Le déterminisme de la consolidation est CONDITIONNÉ par la canonicité de la clôture.

    Accepter un groupe désordonné rendrait silencieusement le produit dépendant de l'ordre
    d'entrée — exactement ce que la clôture a passé son temps à éliminer.
    """
    desordre = [_rec("R2", "S2", nom="Martin"), _rec("R1", "S1", nom="Dupont")]
    with pytest.raises(ValueError):
        fus.consolide_entite(desordre)
    with pytest.raises(ValueError):
        fus.consolide_entite([_rec("R1", "S1"), _rec("R1", "S2")])
    with pytest.raises(ValueError):
        fus.consolide_entite([])


_SCRIPT_ENFANT = """\
import json, sys
sys.path.insert(0, {src!r})
from engine import fusion as fus
membres = json.loads({membres!r})
sortie = json.dumps(fus.consolide_entite(membres, priorite_sources=("SRC_B", "SRC_A")),
                    sort_keys=True, ensure_ascii=False, separators=(", ", ": "))
sys.stdout.buffer.write(sortie.encode('utf-8'))
"""


def test_determinisme_inter_processus_sur_un_cas_a_egalite(tmp_path):
    """Deux PROCESSUS, deux `PYTHONHASHSEED` DIFFÉRENTS, sur un cas qui comporte une ÉGALITÉ.

    L'égalité de clé est le SEUL cas qui sépare une règle totale d'une règle partielle :
    `max(..., key=...)` rend à égalité le premier élément RENCONTRÉ, donc une sortie qui peut
    dépendre de la graine de hachage. Un cas sans ex aequo laisserait ce défaut invisible.
    """
    membres = [_rec("R1", "SRC_A", ville="Nice", nom="Dupont"),
               _rec("R2", "SRC_B", ville="Lyon", nom="Dupont")]
    script = tmp_path / "run_consolidation.py"
    script.write_text(_SCRIPT_ENFANT.format(src=_SRC, membres=json.dumps(membres)),
                      encoding="utf-8")
    graines = ("0", "12345")
    sorties = []
    for graine in graines:
        env = dict(os.environ, PYTHONHASHSEED=graine, PYTHONIOENCODING="utf-8")
        proc = subprocess.run([sys.executable, str(script)], capture_output=True, env=env)
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
        sorties.append(proc.stdout)
    assert sorties[0], "sortie enfant vide : oracle vide"
    assert sorties[0] == sorties[1], (
        f"deux processus (PYTHONHASHSEED {graines[0]} puis {graines[1]}) divergent : déterminisme")
    attendu = json.dumps(fus.consolide_entite(membres, priorite_sources=("SRC_B", "SRC_A")),
                         sort_keys=True, ensure_ascii=False, separators=(", ", ": "))
    assert attendu.encode("utf-8") == sorties[0]


def test_la_cle_de_vote_repose_sur_des_normaliseurs_idempotents():
    """Dépendance TACITE rendue explicite : le regroupement suppose `f(f(x)) == f(x)`.

    Rien dans `normalize.py` ne garantit cette propriété, et la fusion n'a pas le droit d'y
    toucher. La figer ici est le seul moyen qu'une évolution du recollement de sigles ou de
    la table d'abréviations ne déplace pas silencieusement tous les produits.
    """
    temoins = ("Jean-Pierre", "S.A.R.L. Boulangerie", "  Marché  ", "3 r. du Marché",
               "+33 1 45 67 89 01", "07/03/1970", "0", "-", "St Étienne", "A. B. Dupont")
    n_verifs = 0
    for attribut in _ATTRIBUTS:
        normaliseur = nrm.NORMALISEURS[attribut]
        for temoin in temoins:
            une_fois = normaliseur(temoin)
            assert normaliseur(une_fois) == une_fois, (
                f"{attribut}({temoin!r}) n'est pas idempotent : {une_fois!r}")
            n_verifs += 1
    assert n_verifs == len(_ATTRIBUTS) * len(temoins)


def test_temoins_de_normalisation_figes():
    """Table littérale : un changement de `normalize.py` déplacerait les regroupements, donc
    tous les produits, sans qu'aucun test de la zone moteur ne rougisse. Il rougira ici."""
    temoins = (("prenom", "Jean-Pierre", "jean pierre"),
               ("prenom", "JEAN PIERRE", "jean pierre"),
               ("ville", "Marché", "marche"),
               ("ville", "Marche", "marche"),
               ("telephone", "01 45 67 89 01", "0145678901"),
               ("telephone", "0033145678901", "0145678901"),
               ("date_naissance", "1970-3-7", "1970-03-07"),
               ("date_naissance", "07/03/1970", "1970-03-07"),
               ("code_postal", "0", "0"),
               ("ville", "   ", None),
               ("nom", "-", None),
               ("nom", "SARL Boulangerie", "boulangerie"))
    for attribut, brut, attendu in temoins:
        assert nrm.NORMALISEURS[attribut](brut) == attendu, f"{attribut}({brut!r})"
    garde_non_vacuite(temoins=temoins)


# =================== 8. Non-circularité, périmètre et data-indépendance — DoD-7/8 ====
def test_cc1_comportemental_une_colonne_surnumeraire_n_atteint_pas_le_produit():
    """La projection défensive itère le tuple FERMÉ des attributs, jamais `record.keys()`.

    C'est cette projection — et non la discipline — qui rend structurellement impossible
    qu'une étiquette de référence atteigne le produit ou sa trace.
    """
    membres = [dict(_rec("R1", "S1", nom="Dupont"), id_entite_vraie="E1",
                    ground_truth=True, zone_intention_design="piege", colonne_en_trop="X"),
               dict(_rec("R2", "S2", nom="Dupont"), id_entite_vraie="E1")]
    nus = [_rec("R1", "S1", nom="Dupont"), _rec("R2", "S2", nom="Dupont")]
    assert fus.consolide_entite(membres) == fus.consolide_entite(nus)
    serialisee = json.dumps([fus.consolide_entite(membres),
                             fus.trace_selection(membres, "nom")],
                            sort_keys=True, ensure_ascii=False)
    for jeton in ("id_entite_vraie", "ground_truth", "zone_intention_design",
                  "piege", "colonne_en_trop"):
        assert jeton not in serialisee, f"{jeton} a transpire dans le produit ou sa trace"


def test_cc1_l_arbitrage_ne_recoit_pas_les_enregistrements():
    """La signature EST la preuve de rejouabilité : rien hors de la trace ne peut peser."""
    assert list(inspect.signature(fus.arbitre_attribut).parameters) == [
        "bulletin", "politique"], "l'arbitrage s'est ouvert a autre chose que la trace"
    assert list(inspect.signature(fus.consolide_partition).parameters) == [
        "partition", "records", "politique", "priorite_sources"]


def test_le_poids_agrege_de_la_decision_n_entre_pas_dans_la_consolidation():
    """Ce serait une propriété d'une PAIRE projetée sur un enregistrement — sans réponse de
    principe — et cela rendrait les produits dépendants de seuils non calibrés.

    L'oracle porte sur l'identifiant du champ, et le message porte le motif du rejet : un
    test qui enseigne, pas seulement qui bloque.
    """
    identifiant = "poids" + "_match"
    source = _source_module("fusion.py")
    assert identifiant not in source.replace("\\\n", "").replace("\n", " "), (
        f"{identifiant} est lu par la consolidation : c'est une propriete d'une PAIRE, "
        f"pas d'un enregistrement, et les seuils qui la produisent ne sont pas calibres")
    # Contrôle POSITIF : l'oracle voit bien l'identifiant quand il est présent.
    assert identifiant in 'v = correspondance["poids' + '_match"]', "oracle mort"


def test_cc1_les_cles_lues_par_la_consolidation_forment_un_ensemble_clos():
    """Pendant AST de l'oracle de la clôture — le volet que DoD-5 exige sur les DEUX modules.

    Le grep nominatif et le test comportemental ne détectent qu'une étiquette DÉJÀ CONNUE
    par son nom. L'inventaire clos, lui, attrape celle qu'on n'a pas prévue.

    Les clés lues sur un ENREGISTREMENT sont deux ; toutes les autres sont des clés des
    structures que le module a lui-même construites. La seule lecture DYNAMIQUE est
    `record.get(attribut)`, déjà fermée au runtime par le contrôle d'appartenance à
    `ATTRIBUTS_COMPARE` — donc une colonne d'annotation ne peut pas y entrer.
    """
    entrantes = {"record_id", "source_id"}
    internes = {"attribut", "forme", "formes", "formes_brutes", "groupes",
                "longueur_normalisee", "n_candidats", "n_groupes", "n_records", "n_sources",
                "origine", "origines", "rang_source", "rangs", "record_id_min",
                "record_ids", "sources", "valeur", "valeur_normalisee"}
    arbre = ast.parse(_source_module("fusion.py"))
    lues, dynamiques = set(), []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Subscript) and isinstance(noeud.slice, ast.Constant) \
                and isinstance(noeud.slice.value, str):
            lues.add(noeud.slice.value)
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute) \
                and noeud.func.attr == "get" and noeud.args:
            if isinstance(noeud.args[0], ast.Constant):
                lues.add(noeud.args[0].value)
            else:
                dynamiques.append(noeud)
    assert lues <= entrantes | internes, (
        f"cles lues hors inventaire clos : {sorted(lues - entrantes - internes)}")
    garde_non_vacuite(cles_lues=lues)
    assert [ast.unparse(n) for n in dynamiques] == ["record.get(attribut)"], (
        "une seconde lecture dynamique est apparue : l'inventaire n'est plus clos")
    # Contrôle POSITIF : l'oracle voit une lecture d'étiquette injectée.
    fautif = ast.parse('v = pack["id_entite_vraie"]\nw = rec.get("ground_truth")\n')
    detectees = set()
    for noeud in ast.walk(fautif):
        if isinstance(noeud, ast.Subscript) and isinstance(noeud.slice, ast.Constant):
            detectees.add(noeud.slice.value)
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute) \
                and noeud.func.attr == "get":
            detectees.add(noeud.args[0].value)
    assert detectees == {"id_entite_vraie", "ground_truth"}, (
        f"l'oracle de cles lues ne detecte plus une infraction flagrante : {detectees}")


def test_un_parametrage_a_usage_unique_ne_se_perd_pas_en_silence():
    """Valider CONSOMME : un itérable à usage unique arriverait VIDE au calcul.

    Le mode de défaillance est le pire possible : aucune exception, et un produit DIFFÉRENT.
    Une table de priorité perdue rend tous les rangs égaux, la règle de source s'abstient, et
    la cascade retombe sur l'ordre canonique. Les quatre formes ci-dessous déclarent la MÊME
    table : les quatre doivent rendre le même produit.
    """
    membres = [_rec("R1", "SRC_A", prenom="Alpha"), _rec("R2", "SRC_B", prenom="Bravo")]
    assert len(nrm.NORMALISEURS["prenom"]("Alpha")) == len(nrm.NORMALISEURS["prenom"]("Bravo")), (
        "longueurs normalisees differentes : SOURCE_PRIORITAIRE ne trancherait pas")
    formes = (lambda: ("SRC_B", "SRC_A"), lambda: iter(["SRC_B", "SRC_A"]),
              lambda: reversed(["SRC_A", "SRC_B"]), lambda: (s for s in ("SRC_B", "SRC_A")))
    for forme in formes:
        assert fus.consolide_entite(membres, priorite_sources=forme())["prenom"] == "Bravo"
        assert fus.trace_selection(membres, "prenom", priorite_sources=forme()
                                   )["decision"]["regle"] == fus.SOURCE_PRIORITAIRE
        assert fus.consolide_partition([["R1", "R2"]], membres,
                                       priorite_sources=forme())[0]["prenom"] == "Bravo"
    # Même racine pour la politique : un itérateur ne doit ni la vider ni fausser le motif.
    for point in (lambda p: fus.consolide_entite(membres, politique=p)["prenom"],
                  lambda p: fus.trace_selection(membres, "prenom",
                                                politique=p)["decision"]["valeur"]):
        assert point(iter(fus.POLITIQUE_DEFAUT)) == point(fus.POLITIQUE_DEFAUT)
    bulletin = fus.valeurs_candidates(membres, "prenom")
    assert (fus.arbitre_attribut(bulletin, politique=iter(fus.POLITIQUE_DEFAUT))
            == fus.arbitre_attribut(bulletin, politique=fus.POLITIQUE_DEFAUT))


def test_le_refus_de_cascade_non_terminale_est_inatteignable_depuis_l_api():
    """La garde de dernier recours doit rester MORTE : toute politique valide est totale.

    Elle ne pouvait être atteinte que par une politique à usage unique, vidée par la
    validation — c'est-à-dire par le défaut précédent, et non par une cascade réellement
    non terminale. Ce test fige la propriété plutôt que la garde.
    """
    membres = [_rec("R1", "SRC_A", prenom="Alpha"), _rec("R2", "SRC_B", prenom="Bravo")]
    bulletin = fus.valeurs_candidates(membres, "prenom")
    for politique in (fus.POLITIQUE_DEFAUT, fus.POLITIQUE_COMPLETUDE_DABORD,
                      (fus.ORDRE_CANONIQUE,), (fus.MAJORITE, fus.ORDRE_CANONIQUE),
                      iter(fus.POLITIQUE_DEFAUT)):
        assert fus.arbitre_attribut(bulletin, politique)["valeur"] is not None
    # Et une politique non terminale est refusée à l'entrée, pas au milieu du calcul.
    with pytest.raises(ValueError, match="non terminale"):
        fus.arbitre_attribut(bulletin, (fus.MAJORITE, fus.COMPLETUDE))


def test_les_messages_de_refus_sont_reproductibles():
    """Une erreur au message variable est indiagnosticable : deux opérateurs, deux messages.

    Trier un ensemble hétérogène lève un `TypeError` dont le message nomme les opérandes
    dans l'ordre d'itération de l'ensemble — donc dans un ordre qui suit la graine de
    hachage. Le refus doit être un `ValueError` au message stable, quel que soit le type reçu.
    """
    for politique in ((1, "FOO", fus.ORDRE_CANONIQUE), (["x"], fus.ORDRE_CANONIQUE),
                      ({"a": 1}, fus.ORDRE_CANONIQUE)):
        with pytest.raises(ValueError, match="regles inconnues"):
            fus.valide_politique(politique)
    messages = set()
    for _ in range(3):
        try:
            fus.valide_politique((1, "FOO", fus.ORDRE_CANONIQUE))
        except ValueError as erreur:
            messages.add(str(erreur))
    assert len(messages) == 1, f"message de refus instable : {messages}"


def test_un_attribut_hors_du_schema_compare_est_refuse():
    """`trace_selection` sur une colonne inconnue échoue net plutôt que de rendre un vide."""
    membres = [_rec("R1", "S1", nom="Dupont")]
    with pytest.raises(ValueError):
        fus.trace_selection(membres, "colonne_inconnue")
    with pytest.raises(ValueError):
        fus.valeurs_candidates(membres, "id_entite_vraie")


def test_les_entrees_malformees_de_la_partition_sont_refusees():
    """Un membre sans enregistrement : échec net, jamais un produit à huit nuls fantôme."""
    records = [_rec("R1", "S1", nom="Dupont")]
    with pytest.raises(ValueError):
        fus.consolide_partition([["R1", "R9"]], records)
    with pytest.raises(ValueError):
        fus.consolide_partition([["R1"]], records + [_rec("R1", "S2")])
    with pytest.raises(ValueError):
        fus.consolide_partition([["R1"]], [{"source_id": "S1"}])
    with pytest.raises(ValueError):
        fus.consolide_entite([_rec("R1", "S1", nom=42)])


def _jetons_de_dependance_aux_donnees():
    """Fragments assemblés à l'exécution : écrits en clair, ils se compteraient eux-mêmes."""
    return ("synth" + "_env", "FIXTURE" + "_PACK", "V1" + "_2", "execute" + "_moteur")


def test_meta_aucun_produit_d_un_jeu_reel_n_est_fige_dans_ce_fichier():
    """DoD-8 : la data-indépendance devient un ORACLE, et cesse d'être une intention.

    Les seuils du moteur vont bouger : les groupes formés sur un jeu réel changeront, donc
    les produits correspondants aussi. Un test qui en figerait un casserait au premier
    recalibrage, sans qu'aucun défaut n'ait été introduit.
    """
    with open(os.path.abspath(__file__), encoding="utf-8") as fh:
        arbre = ast.parse(fh.read())
    for jeton in _jetons_de_dependance_aux_donnees():
        fautives = [n.value for n in ast.walk(arbre)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                    and jeton in n.value]
        assert not fautives, f"dependance a un jeu de donnees ({jeton}) : {fautives}"
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name) \
                and noeud.func.id == "open":
            cible = ast.dump(noeud.args[0]) if noeud.args else ""
            assert "__file__" in cible or "_ENGINE" in cible, (
                f"ouverture d'un fichier de donnees dans les tests : {cible}")
    assert not re.search(r"\bfrom\s+generator|\bimport\s+generator|\bimport\s+scorer",
                         open(os.path.abspath(__file__), encoding="utf-8").read())


def test_meta_les_oracles_de_ce_fichier_ne_sont_pas_vides():
    """Anti-vacuité mordante : les jeux DOIVENT contenir de quoi trancher un conflit réel."""
    garde_non_vacuite(conflit=_CONFLIT_TOTAL, contre_exemple=_CONTRE_EXEMPLE)
    assert len(_CONTRE_EXEMPLE) >= 3, "le desaccord entre les deux ordres n'existe qu'a n >= 3"
    bulletin = fus.trace_selection(_CONTRE_EXEMPLE, "nom")["bulletin"]
    assert bulletin["n_groupes"] >= 2, "aucun conflit a trancher : l'oracle serait vide"
    conflits = [a for a in _ATTRIBUTS
                if fus.trace_selection(_CONFLIT_TOTAL, a)["bulletin"]["n_groupes"] >= 2]
    assert len(conflits) == len(_ATTRIBUTS), (
        f"le conflit total n'oppose que {len(conflits)} attributs sur {len(_ATTRIBUTS)}")
