# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Vocabulaire de PROTOCOLE et validations de forme.

## Pourquoi ces littéraux sont RE-DÉCLARÉS et non importés
`"MATCH"`, `"NON_MATCH"`, `"ZONE_GRISE"`, les 8 attributs comparés et les 4 niveaux d'accord
existent aussi dans `src/engine/`. Les importer serait la façon la plus naturelle — et
exactement ce que la non-circularité interdit : le scoreur ne doit dépendre d'aucune ligne du
moteur, faute de quoi il ne prouve plus rien sur lui.

Ce sont donc des constantes de **protocole** : le vocabulaire de l'artefact CORRESPONDENCE,
au même titre qu'un schéma de message. La duplication est le PRIX de l'indépendance, et elle
est payante : si le moteur changeait son vocabulaire, `valide_correspondances` échouerait
bruyamment au lieu d'absorber le changement en silence. Un import rendrait l'écart invisible ;
la re-déclaration le rend détectable.

Frontière de non-circularité : aucun import de `src/engine/` ni de `src/generator/`.
Stdlib seule (C7).
"""
from __future__ import annotations

import math

__all__ = [
    "MATCH", "NON_MATCH", "ZONE_GRISE", "VERDICTS_ATTENDUS", "CONVENTIONS",
    "ATTRIBUTS_ATTENDUS", "NIVEAUX_ATTENDUS", "GRILLE_R_DECIMALES", "DECIMALES_MESURE",
    "cle_paire", "cle_de_correspondance", "valide_correspondances",
]

# --- Vocabulaire de verdict (énumération FERMÉE, protocole) --------------------------
MATCH = "MATCH"
NON_MATCH = "NON_MATCH"
ZONE_GRISE = "ZONE_GRISE"
VERDICTS_ATTENDUS = (MATCH, NON_MATCH, ZONE_GRISE)

#: Les quatre projections de la zone grise sur une décision binaire. Toutes calculées,
#: toutes publiées ; la convention de TÊTE (`stricte`) est déclarée dans `metriques.py`.
CONVENTIONS = ("stricte", "acceptation", "optimiste", "pessimiste")

ATTRIBUTS_ATTENDUS = ("nom", "prenom", "date_naissance", "adresse",
                      "code_postal", "ville", "email", "telephone")
NIVEAUX_ATTENDUS = ("ACCORD_FORT", "ACCORD_PARTIEL", "DESACCORD", "INDETERMINE_MANQUANT")

#: Le moteur arrondit `R` à 9 décimales avant de le livrer : les valeurs vivent sur une
#: grille explicite. Le scoreur les compare TELLES QUE LIVRÉES, sans ré-arrondi — ré-arrondir
#: fusionnerait ou scinderait arbitrairement les ex aequo, ce qui déplacerait le plancher de
#: Bayes et la mixité de la bande, deux quantités dont le verdict dépend.
GRILLE_R_DECIMALES = 9
#: Les mesures DÉRIVÉES sont arrondies UNE SEULE FOIS, avant sérialisation : la valeur
#: publiée est exactement celle qui a été comparée aux seuils du verdict.
DECIMALES_MESURE = 6


def cle_paire(a: str, b: str) -> tuple:
    """Clé canonique d'une paire non ordonnée : `(min, max)` lexicographique.

    Le scoreur RE-DÉRIVE cette clé des deux côtés (vérité terrain et sortie du moteur)
    plutôt que de présumer l'orientation produite par le blocking. Deux raisons : dépendre
    d'une convention interne du moteur serait un partage d'état que la non-circularité interdit ;
    et une orientation divergente fabriquerait simultanément un faux négatif et un faux positif
    fantômes, c'est-à-dire une erreur de mesure qui ressemblerait à une erreur du moteur.
    """
    if a == b:
        raise ValueError(f"auto-paire interdite : {a!r} apparie avec lui-meme")
    return (a, b) if a < b else (b, a)


def cle_de_correspondance(corr: dict) -> tuple:
    """Clé canonique d'une CORRESPONDENCE, lue sur ses deux identifiants."""
    return cle_paire(corr["record_id_a"], corr["record_id_b"])


def valide_correspondances(correspondances, n_paires_candidates_annonce=None) -> dict:
    """AUDIT D'INTÉGRITÉ de la sortie du moteur, exécuté AVANT toute métrique.

    Retourne un dict de constats. Rien n'est corrigé ni dédupliqué en silence : chaque
    anomalie est COMPTÉE et publiée, et `alerte` en fait la synthèse. Une mesure calculée
    sur une jointure douteuse n'est pas une mesure dégradée, c'est un artefact — d'où le
    préalable bloquant P0 du pré-enregistrement.

    Contrôles : cardinalité annoncée vs observée, clés dupliquées, auto-paires, orientation
    non canonique, vocabulaire de verdict hors énumération, et `poids_match` non fini. Le
    contrôle NaN n'est pas décoratif : un NaN se propage silencieusement dans tout tri et
    toute comparaison, et rendrait chaque quantile et chaque plancher faux sans rien lever.
    """
    vues = set()
    dupliquees, auto_paires, non_canoniques, verdicts_inconnus, poids_non_finis = [], [], [], [], []
    for corr in correspondances:
        a, b = corr.get("record_id_a"), corr.get("record_id_b")
        if a == b:
            auto_paires.append(a)
            continue
        if a is not None and b is not None and a > b:
            non_canoniques.append((a, b))
        cle = cle_paire(a, b)
        if cle in vues:
            dupliquees.append(cle)
        vues.add(cle)
        if corr.get("verdict") not in VERDICTS_ATTENDUS:
            verdicts_inconnus.append(corr.get("verdict"))
        poids = corr.get("poids_match")
        if not isinstance(poids, (int, float)) or isinstance(poids, bool) or not math.isfinite(poids):
            poids_non_finis.append(cle)

    ecart_cardinalite = None
    if n_paires_candidates_annonce is not None:
        ecart_cardinalite = len(list(correspondances)) - n_paires_candidates_annonce

    constats = {
        "n_correspondances": len(list(correspondances)),
        "n_cles_distinctes": len(vues),
        "cles_dupliquees": sorted(set(dupliquees)),
        "auto_paires": sorted(set(x for x in auto_paires if x is not None)),
        "orientations_non_canoniques": sorted(set(non_canoniques)),
        "verdicts_hors_enumeration": sorted(set(str(v) for v in verdicts_inconnus)),
        "poids_non_finis": sorted(set(poids_non_finis)),
        "ecart_cardinalite_vs_trace_moteur": ecart_cardinalite,
    }
    constats["alerte"] = bool(
        constats["cles_dupliquees"] or constats["auto_paires"]
        or constats["orientations_non_canoniques"] or constats["verdicts_hors_enumeration"]
        or constats["poids_non_finis"] or ecart_cardinalite not in (None, 0))
    constats["motif"] = _motif(constats) if constats["alerte"] else None
    return constats


def _motif(constats: dict) -> str:
    """Motif lisible de l'alerte, énumérant CE QUI a échoué et en quelle quantité."""
    morceaux = []
    for cle, libelle in (("cles_dupliquees", "cle(s) de paire dupliquee(s)"),
                         ("auto_paires", "auto-paire(s)"),
                         ("orientations_non_canoniques", "orientation(s) non canonique(s)"),
                         ("verdicts_hors_enumeration", "verdict(s) hors enumeration"),
                         ("poids_non_finis", "poids_match non fini(s)")):
        if constats[cle]:
            morceaux.append(f"{len(constats[cle])} {libelle}")
    ecart = constats["ecart_cardinalite_vs_trace_moteur"]
    if ecart not in (None, 0):
        morceaux.append(f"ecart de cardinalite de {ecart:+d} avec la trace du moteur")
    return " ; ".join(morceaux)
