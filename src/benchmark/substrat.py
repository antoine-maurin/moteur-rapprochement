# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Substrat commun : la donnée que les TROIS systèmes reçoivent.

La loyauté de la comparaison commence ici, et par une propriété très simple : il n'existe qu'un seul
objet de données dans tout le banc, il est construit une seule fois, son empreinte est
publiée, et les trois adaptateurs le reçoivent tel quel. Donner à un système une donnée
mieux préparée qu'à un autre est la première façon, et la plus discrète, de fabriquer un
écart — d'où le critère gelé `L1_MEME_DONNEE`, qui compare des sha256 et non des intentions.

## La normalisation est du SUBSTRAT, pas un différenciateur
`engine.normalise_records` est appliqué **une fois**, et son résultat est remis à Splink et
aux baselines comme au moteur. C'est un arbitrage, et il est déclaré :

  - le priver à Splink mesurerait un handicap de **plomberie** déguisé en handicap
    d'algorithme — Splink documente qu'il ne nettoie pas et attend une donnée standardisée ;
  - le lui donner rend le bras honnêtement « Splink + normalisation maison », ce que
    l'artefact dit, et que la sensibilité `SENS_1` chiffre en rejouant Splink sur données
    brutes.

Aucune des deux options n'est neutre. Celle-ci est retenue parce que son biais est
mesurable et publié, là où l'autre serait invisible dans le résultat.

## Non-circularité
Ce module lit `pack["records"]`. Il ne charge la vérité terrain que pour recalculer
l'empreinte du pack, et `charge` ne la RETOURNE jamais : `tools/banc_ub6.py` la relit
séparément pour l'oracle. La frontière est portée par la signature, pas par la vigilance.
"""
from __future__ import annotations

import hashlib
import json
import os

import engine
from engine import blocking as blk

__all__ = ["CHEMIN_FIXTURE", "CONTENT_SHA256_V1_2", "Substrat", "charge", "empreinte_pack"]

#: Chemin POSIX relatif à la racine du repo (aucun chemin absolu OS-spécifique).
CHEMIN_FIXTURE = "fixtures/FIXTURE_PACK_GT_V1_2.json"
CONTENT_SHA256_V1_2 = "66f627edb37022dcecab04dae9c327b342d8dfbb785533ffe8017919000117a2"

#: Canonicalisation de l'empreinte du pack V1.2, telle que SON manifest la déclare (V1.2 a
#: retiré `zone_intention_design` : le jeu de clés fait partie de la référence).
CLES_CANONICALISEES = ("records", "ground_truth", "corruption_annotation")

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def empreinte_pack(pack: dict) -> str:
    """`content_sha256` du pack : sha256 des octets UTF-8 de la forme canonique, manifest EXCLU."""
    canon = json.dumps({k: pack[k] for k in CLES_CANONICALISEES},
                       sort_keys=True, ensure_ascii=False, separators=(', ', ': '))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class Substrat:
    """La donnée partagée, et les clés de blocking qui en dérivent.

    Immuable en pratique : les adaptateurs le lisent, aucun ne le modifie. Un test vérifie
    que l'empreinte du substrat est identique avant et après le passage de chaque système —
    un adaptateur qui muterait la donnée en place avantagerait tous ceux qui passent après lui.
    """

    def __init__(self, records, normalises, empreinte, c0, trace_blocking):
        self.records = records
        self.normalises = normalises
        self.empreinte_fixture = empreinte
        self.c0 = c0                                  # liste triée de clés (a, b)
        self.trace_blocking = trace_blocking

    @property
    def sha256(self) -> str:
        """Empreinte de la LISTE NORMALISÉE réellement remise aux systèmes.

        C'est cette valeur, et non celle de la fixture, que `L1_MEME_DONNEE` compare : deux
        systèmes peuvent recevoir la même fixture et des préparations différentes.
        """
        canon = json.dumps(self.normalises, sort_keys=True, ensure_ascii=False,
                           separators=(", ", ": "))
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()

    @staticmethod
    def cle_pref(nrecord):
        """Clé de la passe PREF, calculée par LA FONCTION DU MOTEUR.

        Elle est exposée ici pour que l'adaptateur Splink reproduise l'ensemble candidat sans
        réimplémenter la règle en SQL. Deux subtilités qu'une réimplantation raterait : un
        prénom absent n'invalide PAS la clé (personnes morales), et un nom absent écarte le
        record de la passe au lieu de le verser dans un seau de clés vides.
        """
        return blk.cle_prefixe(nrecord, blk.LONGUEUR_PREFIXE_DEFAUT)

    @staticmethod
    def cle_cp(nrecord):
        """Clé de la passe CP : le code postal normalisé, ou `None`."""
        return nrecord.get("code_postal") or None

    def resume(self) -> dict:
        """Ce que l'artefact publie du substrat — jamais la donnée elle-même."""
        return {
            "n_records": len(self.records),
            "empreinte_fixture": self.empreinte_fixture,
            "sha256_substrat_normalise": self.sha256,
            "attributs": list(engine.ATTRIBUTS_COMPARE),
            "normalisation": "engine.normalise_records, appliquee UNE FOIS",
            "n_paires_possibles": len(self.records) * (len(self.records) - 1) // 2,
            "c0": {
                "n_paires": len(self.c0),
                "passes": list(self.trace_blocking["passes"]),
                "longueur_prefixe": self.trace_blocking["longueur_prefixe"],
                "origine": "engine.genere_paires_candidates — le blocking du moteur maison",
            },
        }


def charge(chemin_fixture: str = CHEMIN_FIXTURE, passes=None) -> Substrat:
    """Ouvre la fixture en LECTURE SEULE, vérifie son empreinte, et bâtit le substrat.

    `passes` vaut par défaut `engine.PASSES_DEFAUT`, soit `("CP", "PREF")` depuis le retrait
    de `SDX_NOM` (objectif O0a). L'ensemble candidat `C0` ainsi produit est celui du bras
    APPARIÉ : c'est lui que les trois systèmes noteront, à la paire près.

    Ne retourne PAS le pack : la vérité terrain n'entre pas dans le substrat.
    """
    chemin = chemin_fixture if os.path.isabs(chemin_fixture) else os.path.join(
        _RACINE, chemin_fixture)
    with open(chemin, encoding="utf-8") as fh:
        pack = json.load(fh)
    obtenue = empreinte_pack(pack)
    if obtenue != CONTENT_SHA256_V1_2:
        raise ValueError(
            f"empreinte de pack divergente : attendu {CONTENT_SHA256_V1_2}, obtenu {obtenue}. "
            f"La fixture n'est pas celle que le mandat designe.")

    records = pack["records"]
    normalises = engine.normalise_records(records)
    resultat = blk.genere_paires_candidates(
        normalises, passes=tuple(passes or engine.PASSES_DEFAUT))
    c0 = [(p["record_id_a"], p["record_id_b"]) for p in resultat["paires"]]
    return Substrat(records, normalises, obtenue, c0, resultat["trace"])
