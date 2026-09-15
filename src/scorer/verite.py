# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Vérité terrain — le SEUL module autorisé à lire `ground_truth`.

Le moteur ne lit jamais la vérité terrain ; il en est même structurellement incapable, sa
normalisation projetant les enregistrements sur les 8 attributs comparés. Le scoreur, lui, la
lit — c'est ce qui lui permet de RECOMPTER. Concentrer cette lecture dans un module unique
rend la frontière vérifiable par un test : `ground_truth` doit apparaître ICI et nulle part
ailleurs dans `src/scorer/`.

## Les vraies paires sont une CLÔTURE, pas une forêt
`ground_truth` associe chaque `record_id` à un `id_entite_vraie` : c'est une relation
d'ÉQUIVALENCE. L'ensemble `M` des vraies paires est donc la clôture privée de la diagonale,
`|M| = Σ_e C(n_e, 2)` — et **non** le nombre d'arêtes d'une forêt de provenance.

L'erreur est facile et coûteuse. `corruption_annotation[].record_id_origine` décrit « qui a
été copié de qui » : une forêt orientée de `Σ_e (n_e − 1)` arêtes. Sur ce pack, 537 − 320 =
**217** arêtes contre **271** vraies paires. S'en servir sous-estimerait le dénominateur du
rappel d'environ 20 % et transformerait les paires « frère-frère » (deux copies d'un même
original) en faux positifs. La signature de `paires_vraies()` ferme la porte : elle ne reçoit
QUE `ground_truth`. `corruption_annotation` sert au DIAGNOSTIC, jamais à dériver `M`.

Les deux comptes sont publiés côte à côte, précisément pour rendre l'erreur visible plutôt
que possible : leur écart (271 − 217 = 54) est la preuve arithmétique, par convexité de
`k ↦ C(k,2)`, qu'il existe des entités de taille ≥ 3 — donc que la transitivité est ACTIVE
sur ce jeu, et qu'un split par paire fuirait.

## Interdiction symétrique
Aucune fonction d'ici n'applique de clôture transitive aux PRÉDICTIONS. Propager les MATCH
(a-b et b-c donc a-c) emprunterait le travail de clustering et gonflerait le
rappel quadratiquement. La fonction n'existe pas ; elle ne peut donc pas être appelée par
mégarde.

Frontière de non-circularité : aucun import de `src/engine/` ni de `src/generator/`.
Stdlib seule (C7).
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

from .contrat import cle_paire

__all__ = [
    "CLES_CANONICALISEES", "charge_pack", "empreinte_pack", "partition_entites", "entites",
    "paires_vraies", "statistiques_verite", "controle_manifest",
    "controle_couverture_identifiants", "categories_par_record",
]

#: Canonicalisation de l'empreinte du pack V1.2, telle que SON manifest la déclare.
#: V1.1 hachait quatre blocs ; V1.2 a retiré `zone_intention_design`, et le jeu de clés fait
#: donc partie de la référence — appliquer les 4 clés à V1.2 lèverait un KeyError, appliquer
#: les 3 clés à V1.1 donnerait un hash différent du hash publié.
CLES_CANONICALISEES = ("records", "ground_truth", "corruption_annotation")


def charge_pack(chemin: str, sha256_attendu: Optional[str] = None) -> dict:
    """Charge un pack de fixture en LECTURE SEULE, en vérifiant son empreinte si elle est fournie.

    La fixture est CONSOMMÉE, jamais éditée : ce module n'ouvre jamais un fichier en écriture.
    Un écart d'empreinte lève — mesurer sur une donnée qui n'est pas celle qu'on annonce
    invaliderait tout ce qui suit, silencieusement.
    """
    with open(chemin, encoding="utf-8") as fh:
        pack = json.load(fh)
    if sha256_attendu is not None:
        obtenu = empreinte_pack(pack)
        if obtenu != sha256_attendu:
            raise ValueError(
                f"empreinte de pack divergente : attendu {sha256_attendu}, obtenu {obtenu}. "
                f"La fixture n'est pas celle que le mandat designe.")
    return pack


def empreinte_pack(pack: dict) -> str:
    """`content_sha256` du pack : sha256 des octets UTF-8 de la forme canonique, manifest EXCLU."""
    canon = json.dumps({k: pack[k] for k in CLES_CANONICALISEES},
                       sort_keys=True, ensure_ascii=False, separators=(', ', ': '))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def partition_entites(ground_truth) -> dict:
    """`{record_id: id_entite_vraie}`. Lève si un `record_id` est affecté deux fois.

    Un « dernier gagne » silencieux modifierait la partition, donc la cardinalité de
    référence `|M|`, donc le dénominateur du rappel — sans laisser la moindre trace. Une
    vérité terrain ambiguë est une raison d'arrêter, pas de choisir.
    """
    partition = {}
    for entree in ground_truth:
        rid = entree["record_id"]
        ent = entree["id_entite_vraie"]
        if rid in partition and partition[rid] != ent:
            raise ValueError(
                f"record_id {rid!r} affecte a deux entites : {partition[rid]!r} et {ent!r}")
        if rid in partition:
            raise ValueError(f"record_id {rid!r} duplique dans ground_truth")
        partition[rid] = ent
    return partition


def entites(ground_truth) -> dict:
    """`{id_entite_vraie: [record_id, ...]}`, chaque liste TRIÉE (déterminisme)."""
    groupes = {}
    for rid, ent in partition_entites(ground_truth).items():
        groupes.setdefault(ent, []).append(rid)
    return {ent: sorted(rids) for ent, rids in sorted(groupes.items())}


def paires_vraies(ground_truth) -> frozenset:
    """L'ensemble `M` des vraies paires : CLÔTURE d'équivalence, diagonale exclue.

    Ne reçoit QUE `ground_truth` — la signature interdit de dériver les paires de la
    provenance (`record_id_origine`), qui donnerait une forêt et non une clôture.
    """
    sortie = set()
    for rids in entites(ground_truth).values():
        for i in range(len(rids)):
            for j in range(i + 1, len(rids)):
                sortie.add(cle_paire(rids[i], rids[j]))
    return frozenset(sortie)


def statistiques_verite(ground_truth) -> dict:
    """Description de la vérité terrain, avec le compte-forêt publié POUR MÉMOIRE.

    Le compte-forêt `Σ_e (n_e − 1)` n'est pas une alternative proposée : c'est le piège
    nommé, chiffré et exposé à côté du bon compte, pour qu'un lecteur voie l'écart au lieu de
    le reproduire.
    """
    groupes = entites(ground_truth)
    tailles = {}
    for rids in groupes.values():
        tailles[len(rids)] = tailles.get(len(rids), 0) + 1
    n_records = sum(len(r) for r in groupes.values())
    n_vraies = sum(len(r) * (len(r) - 1) // 2 for r in groupes.values())
    n_foret = sum(len(r) - 1 for r in groupes.values())
    n_possibles = n_records * (n_records - 1) // 2
    return {
        "n_records": n_records,
        "n_entites": len(groupes),
        "n_entites_singleton": tailles.get(1, 0),
        "distribution_tailles_entites": {str(k): v for k, v in sorted(tailles.items())},
        "taille_entite_max": max(tailles) if tailles else 0,
        "n_vraies_paires": n_vraies,
        "n_paires_foret_pour_memoire": n_foret,
        "ecart_cloture_foret": n_vraies - n_foret,
        "note_cloture_vs_foret": (
            "n_vraies_paires est la CLOTURE d'equivalence (somme des C(n,2)). Le compte-foret "
            "(somme des n-1, = nombre d'aretes de provenance) est publie POUR MEMOIRE : c'est "
            "l'erreur classique, et l'ecart prouve par convexite qu'il existe des entites de "
            "taille >= 3, donc que la transitivite est active sur ce jeu."),
        "n_paires_possibles": n_possibles,
        "prevalence_absolue": (n_vraies / n_possibles) if n_possibles else None,
    }


def controle_manifest(stats: dict, manifest: Optional[dict]) -> dict:
    """Confronte le nombre de vraies paires RECOMPTÉ à celui que le manifest ANNONCE.

    Le manifest est une PRÉTENTION, la dérivation est la mesure. Tout écart est publié tel
    quel : adopter après coup la définition qui reproduirait le chiffre annoncé serait
    exactement la fuite par « définition choisie après coup » que le pré-enregistrement
    interdit.
    """
    annonce = None
    if manifest:
        annonce = (manifest.get("difficulty_estimate_default_mu") or {}).get("n_true_pairs_total")
    recompte = stats["n_vraies_paires"]
    return {
        "n_vraies_paires_annonce": annonce,
        "n_vraies_paires_recompte": recompte,
        "ecart": None if annonce is None else recompte - annonce,
        "coincide": None if annonce is None else recompte == annonce,
        "definition_retenue": "cloture d'equivalence sur id_entite_vraie (pre-enregistree)",
    }


def controle_couverture_identifiants(records, ground_truth) -> dict:
    """Contrôle la bijection `records` ↔ `ground_truth`, sans jamais lever.

    Arbitrage déclaré : un `record_id` dupliqué DANS la vérité lève (cf. `partition_entites`)
    parce qu'il rend la partition ambiguë ; un défaut de couverture, lui, ne lève pas — il est
    compté, publié, et les paires qu'il touche sont exclues des DEUX côtés. Un enregistrement
    non étiqueté n'est pas un non-lien : c'est une absence d'information, et le compter comme
    négatif fabriquerait de la précision à partir de rien.
    """
    ids_records = [r.get("record_id") for r in records]
    ens_records = set(ids_records)
    ens_verite = set(partition_entites(ground_truth))
    dupliques = sorted({r for r in ids_records if ids_records.count(r) > 1})
    sans_verite = sorted(ens_records - ens_verite)
    sans_record = sorted(ens_verite - ens_records)
    return {
        "n_records": len(ids_records),
        "n_records_distincts": len(ens_records),
        "record_id_dupliques": dupliques,
        "records_sans_verite": sans_verite,
        "verite_sans_record": sans_record,
        "bijection": not (dupliques or sans_verite or sans_record),
        "identifiants_exclus": sorted(set(sans_verite) | set(sans_record)),
    }


def categories_par_record(corruption_annotation) -> dict:
    """`{record_id: [categorie, ...]}` — usage DIAGNOSTIC exclusivement.

    Sert à TYPER les faux négatifs et les paires perdues au blocking (« cette paire est-elle
    manquée parce qu'elle est lourdement corrompue ? »). Ne sert JAMAIS à dériver les vraies
    paires : `record_id_origine` est délibérément ignoré ici, pour que ce dict ne puisse pas
    servir de porte dérobée vers la forêt de provenance.
    """
    return {e["record_id"]: sorted(e.get("categories_appliquees") or [])
            for e in corruption_annotation}
