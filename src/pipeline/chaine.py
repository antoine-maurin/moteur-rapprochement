# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Orchestration E2E — la chaîne complète, d'un pack d'enregistrements aux enregistrements dorés.

    normalisation -> blocking -> comparaison -> décision
                                                   |
                                    revue du doute en zone grise (substitut 1b)
                                                   |
                                    clôture transitive -> fusion -> DORÉS

## Ce module ORCHESTRE, il ne décide de rien
Aucune règle de décision, aucun seuil, aucune métrique n'est définie ici. Chaque étage est
appelé, dans l'ordre, avec ce que l'étage précédent a produit. C'est la propriété qui rend
la chaîne lisible : si un verdict surprend, il n'y a qu'un seul endroit où le chercher, et
ce n'est pas ici.

## La jonction revue -> clôture, qui est l'endroit fragile
La revue rend des CORRESPONDENCE **enrichies** ; `ensemble_de_match` en extrait les paires
retenues comme liens (MATCH du moteur ∪ MATCH_APRÈS_REVUE). C'est cette liste, et non la
liste brute, qui alimente la clôture transitive.

Le passage par `ensemble_de_match` est une redondance ASSUMÉE avec `clustering.est_liante`,
qui sait désormais reconnaître le même jeton. Elle est gardée parce que les deux chemins ont
divergé une fois — `est_liante` comparait la décision de revue au jeton `MATCH` du moteur,
que la revue n'émet jamais, si bien que toute promotion était silencieusement perdue. Une
garde de conservation (§`aretes_de_l_ensemble_de_match`) compare les deux lectures et lève
si elles cessent de coïncider, plutôt que de laisser la prochaine divergence se traduire par
des entités trop petites que rien ne signale.

## Non-circularité — structurelle, pas déclarative
Ce module ne lit JAMAIS la vérité terrain. Il reçoit des `records` déjà projetés par
l'appelant et ne connaît d'un enregistrement que ce que `normalise_records` en garde. Les
jetons `ground_truth`, `id_entite_vraie`, `zone_intention_design` n'apparaissent nulle part
dans ce paquet, et un test l'éprouve par analyse du code source. La mesure de ce que la
chaîne produit est le travail du SCOREUR, séparément et après coup : le pipeline n'importe
pas `scorer`, et ne le peut pas sans faire rougir l'oracle d'import.

## Déterminisme
Aucun parcours d'ensemble non trié, aucun `hash()`, aucune horloge. La sortie complète est
canonicalisable et son empreinte est stable d'un processus à l'autre — c'est ce que
`canonicalisation` fournit et ce que la suite éprouve sur deux `PYTHONHASHSEED` distincts.
"""
from __future__ import annotations

from typing import Optional

import engine
from engine import clustering as clu
from engine import llm_client as clt
from engine import llm_review as rev

from .point import PointDeFonctionnement, verifie_provenance

__all__ = [
    "ETAGES", "execute_chaine", "aretes_de_l_ensemble_de_match",
    "client_substitut_1b", "ConservationRompue",
]

#: Les étages, nommés et publiés : la sortie dit ce qu'elle a traversé.
ETAGES = ("normalisation", "blocking", "comparaison", "decision",
          "revue_zone_grise", "cloture_transitive", "fusion")


class ConservationRompue(RuntimeError):
    """Les deux lectures de « ce qui est un lien » ont cessé de coïncider."""


def client_substitut_1b(transcription: dict):
    """Le substitut `1b`, DÉCLARÉ pour ce qu'il est : un rejeu déterministe.

    Ce n'est pas un modèle de langue, et rien dans ce dépôt n'en exécute un : le runtime est
    hors ligne strict et aucun poids de modèle n'est déclaré. Le substitut rejoue une table
    de réponses enregistrée ; il rend la chaîne déterministe là où un adjudicateur
    externe ne le serait pas.

    Ce qu'il éprouve est le MÉCANISME de la revue, pas la justesse d'une adjudication.
    """
    return clt.ClientRejeu(transcription)


def aretes_de_l_ensemble_de_match(correspondances) -> list:
    """Arêtes liantes, lues DEUX FOIS et comparées.

    `ensemble_de_match` et `est_liante` répondent à la même question par deux
    chemins. Les faire coïncider explicitement coûte un parcours et ferme la seule
    défaillance de cette jonction qui soit **silencieuse** : une divergence de jeton ne
    produit pas d'erreur, elle produit des entités trop petites, qui n'ont l'air anormales
    nulle part.
    """
    retenues = rev.ensemble_de_match(correspondances)
    par_revue = sorted({clu.cle_paire(c["record_id_a"], c["record_id_b"])
                        for c in retenues})
    par_clustering = clu.aretes_liantes(correspondances)
    if par_revue != par_clustering:
        seulement_revue = sorted(set(par_revue) - set(par_clustering))
        seulement_clustering = sorted(set(par_clustering) - set(par_revue))
        raise ConservationRompue(
            "les deux lectures du lien divergent — "
            f"{len(seulement_revue)} paire(s) vues par la revue seule "
            f"{seulement_revue[:3]}, {len(seulement_clustering)} par la cloture seule "
            f"{seulement_clustering[:3]}. Un jeton de decision a derive.")
    return par_clustering


def execute_chaine(records, point: PointDeFonctionnement, client,
                   budget_revue: Optional[int] = None,
                   politique=engine.POLITIQUE_DEFAUT,
                   priorite_sources=(), strict: bool = True) -> dict:
    """D'un pack d'enregistrements aux enregistrements dorés, au point demandé.

    `client` est OBLIGATOIRE et sans valeur par défaut : un défaut silencieux
    (`ClientIndisponible`) ferait passer une chaîne dont l'étage de revue n'instruit rien
    pour une chaîne complète. L'appelant dit quel adjudicateur il emploie, ou il n'exécute
    pas la chaîne.

    Rend `{"golden_records", "correspondances", "partition", "rapport"}`. Le rapport porte
    ce qui n'appartient à aucune entité en particulier : les traces de chaque étage, le
    point employé et sa vérification de provenance.
    """
    parametres = point.parametres_moteur()
    sortie = engine.execute_moteur(records, parametres)
    correspondances = sortie["correspondances"]
    rapport_moteur = sortie["rapport"]

    # La provenance est vérifiée MAINTENANT : la table de poids n'existe qu'après le moteur.
    provenance = verifie_provenance(point, records, rapport_moteur["poids"])

    index = {nrec["record_id"]: nrec for nrec in engine.normalise_records(records)}
    revue = rev.revue_des_correspondances(
        correspondances, index, client, budget=budget_revue, strict=strict)

    # La garde de conservation tourne AVANT la clôture, et sur la même liste qu'elle : elle
    # doit lever si les deux lectures du lien divergent, pas constater après coup une
    # partition déjà calculée de travers.
    aretes = aretes_de_l_ensemble_de_match(revue["correspondances"])
    univers = engine.univers_depuis_records(records)
    partition = engine.cloture_transitive(revue["correspondances"], univers)
    dores = engine.consolide_partition(partition, records, politique=politique,
                                       priorite_sources=priorite_sources)

    return {
        "golden_records": dores,
        "correspondances": revue["correspondances"],
        "partition": partition,
        "rapport": {
            "etages": list(ETAGES),
            "n_records": rapport_moteur["n_records"],
            "n_paires": rapport_moteur["n_paires"],
            "blocking": rapport_moteur["blocking"],
            "estimation": rapport_moteur["estimation"],
            "poids": rapport_moteur["poids"],
            "repartition_verdicts": rapport_moteur["repartition_verdicts"],
            "parametres": rapport_moteur["parametres"],
            "parametres_non_calibres": rapport_moteur["parametres_non_calibres"],
            "revue": revue["trace"],
            "n_aretes": len(aretes),
            "n_entites": len(partition),
            "n_golden_records": len(dores),
            "point": point.en_dict(),
            "provenance_du_point": provenance,
        },
    }
