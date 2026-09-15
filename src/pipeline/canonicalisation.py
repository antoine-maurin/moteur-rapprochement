# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Forme canonique et `content_sha256` de la sortie BOUT-EN-BOUT (O4 / CRIT_AUTO_001).

Le projet promet `from-seed -> content_sha256` : d'une graine, une sortie identique à
l'octet. Cette promesse était éprouvée sur le seul GÉNÉRATEUR. Ici elle porte sur toute la
chaîne — enregistrements dorés, verdicts, et revue.

## La convention est celle du projet, reprise VERBATIM
`json.dumps(..., sort_keys=True, ensure_ascii=False, separators=(", ", ": "))` puis sha256
des octets UTF-8. C'est exactement `generator.canonicalization.content_sha256`, et le fait
que ce soit la même est éprouvé plutôt que supposé : deux conventions qui se ressemblent
sans être identiques produiraient deux empreintes également plausibles, et le jour où elles
divergeraient, personne ne saurait laquelle avait raison.

## Ce qui entre dans l'empreinte, et ce qui n'y entre pas
Entrent les trois choses que la chaîne PRODUIT : `golden_records`, `correspondances`
(verdicts, revue comprise) et `partition`. S'y ajoutent les grandeurs du rapport qui
décrivent la DÉCISION — répartition des verdicts, poids, seuils employés, trace de revue.

N'entrent pas : durées, horodatages, chemins, provenance git, versions d'interpréteur. Les
exclure n'est pas un aménagement de confort — c'est ce qui distingue « la chaîne produit la
même chose » de « la chaîne a tourné dans le même contexte ». Une empreinte qui bouge à
chaque commit ne prouve rien : c'est précisément le défaut que `tools/banc_ub6.py` a
présenté, et qui a coûté un test rouge sur la branche d'intégration.

L'exclusion est POSITIVE : la charge est construite en NOMMANT ce qu'on garde, jamais en
retirant ce qu'on rejette. Une charge construite par soustraction laisse entrer toute clé
future que personne n'a pensé à exclure — un défaut qui ne se voit qu'au moment où il fait
mal.
"""
from __future__ import annotations

import hashlib
import json

__all__ = [
    "CLES_PAYLOAD_E2E", "CLES_RAPPORT_E2E", "CLES_POINT_E2E", "CLES_PROVENANCE_E2E",
    "serialisation_canonique", "payload_e2e", "content_sha256_e2e",
]

#: Ce que la chaîne PRODUIT. Nommé, jamais soustrait.
CLES_PAYLOAD_E2E = ("golden_records", "correspondances", "partition", "decision")

#: Du rapport, ce qui décrit la DÉCISION — donc ce dont un changement doit déplacer
#: l'empreinte.
CLES_RAPPORT_E2E = ("repartition_verdicts", "poids", "parametres",
                    "parametres_non_calibres", "revue", "n_aretes", "n_entites",
                    "n_golden_records", "n_records", "n_paires", "etages")

#: Du point de fonctionnement : les seuils employés.
CLES_POINT_E2E = ("t_mu", "t_lambda", "nom", "derive_a_l_execution")

#: De la PROVENANCE du point : comment les seuils ont été obtenus.
#:
#: Ces clés-ci manquaient, et leur absence était un angle mort réel : changer de méthode de
#: dimensionnement, ou lever le marqueur `provisoire`, n'aurait pas déplacé
#: l'empreinte bout-en-bout, alors que ce sont des changements de DÉCISION. Deux chaînes
#: dont l'une annonce des seuils provisoires et l'autre des seuils calibrés auraient rendu
#: la même empreinte.
#:
#: Ce qui reste dehors est le CONTEXTE, non la décision : chemins, sha de fixture, origine,
#: empreintes de population. Les inclure ferait bouger l'empreinte au déplacement d'un
#: fichier — exactement le défaut que ce module existe pour éviter.
CLES_PROVENANCE_E2E = ("methode", "provisoire", "gap", "budget_vise", "frontiere",
                       "repli", "motif_repli")


def serialisation_canonique(objet) -> str:
    """La forme canonique du projet. Une seule, partagée, jamais réinventée localement."""
    return json.dumps(objet, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))


def payload_e2e(sortie: dict) -> dict:
    """La charge hachée : ce que la chaîne produit, plus ce qui décrit sa décision.

    Construite par sélection POSITIVE sur trois niveaux (sortie, rapport, point) : une clé
    neuve n'entre dans l'empreinte que si quelqu'un l'y met délibérément.
    """
    rapport = sortie.get("rapport") or {}
    point = rapport.get("point") or {}
    provenance = point.get("provenance") or {}
    decision = {cle: rapport[cle] for cle in CLES_RAPPORT_E2E if cle in rapport}
    decision["point"] = {cle: point[cle] for cle in CLES_POINT_E2E if cle in point}
    decision["point"]["provenance"] = {
        cle: provenance[cle] for cle in CLES_PROVENANCE_E2E if cle in provenance}
    charge = {cle: sortie[cle] for cle in CLES_PAYLOAD_E2E if cle in sortie}
    charge["decision"] = decision
    return charge


def content_sha256_e2e(sortie: dict) -> str:
    """`content_sha256` de la sortie bout-en-bout : sha256 des octets UTF-8 canoniques."""
    return hashlib.sha256(
        serialisation_canonique(payload_e2e(sortie)).encode("utf-8")).hexdigest()
