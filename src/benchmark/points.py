# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Points de fonctionnement — les DEUX règles, identiques pour les trois systèmes (§4).

Le mandat exige que Splink soit traité « au moins aussi généreusement » que le moteur. La
façon la plus vérifiable d'y parvenir n'est pas de promettre de l'équité, c'est de n'écrire
qu'**une seule fonction par règle**, appliquée en boucle, sans une branche conditionnée au
nom du système. Le mode d'un système est une **donnée de sa configuration gelée**, jamais un
`if` dans ce fichier : un test le vérifie par analyse du code source.

## Point 1 — `a_priori_declare`
Ce que le système déclare sans regarder la donnée. Moteur : placeholders ±8 bits (déclarés
non calibrés dans le code du moteur). Splink : `match_probability >= 0,5`, c'est-à-dire la
règle de Bayes à coûts égaux, défaut documenté de la bibliothèque. Baseline : sa règle native.

## Point 2 — `budget_de_revue_egal`
Le dispositif de placement de seuil du moteur (`engine.threshold_sizing`, budget 300,
frontière évidentielle 0,0) est **offert à tout système à score signé**, sur sa propre
distribution. C'est le point qui empêche le second régime du moteur d'être un avantage
maison : Splink reçoit littéralement la même fonction, le même budget et la même frontière.

Une baseline à score entier non signé n'a pas de frontière neutre où placer une bande : DIMS
lui est **inapplicable**, et lui en appliquer une malgré tout produirait une bande arbitraire.
Son point 2 est donc `volume_egalise` — elle déclare MATCH ses `K` meilleures paires, `K`
étant le nombre de MATCH du moteur au point 2. Cette différence est **imprimée dans la
cellule**, jamais reléguée en note de bas de page.

## Ce qui est interdit, et pré-enregistré comme tel
Transposer les seuils ±8 du moteur sur la distribution de Splink. Mesuré en reconnaissance :
cela verse 55 % des paires en ZONE_GRISE, que la convention stricte compte ensuite comme
prédit-négatif — un seuil pensé pour une autre échelle anéantirait son rappel. Le banc lève
plutôt que de produire ce chiffre.
"""
from __future__ import annotations

import engine

from . import contrat_bench as cb

__all__ = [
    "POINT_1", "POINT_2", "MODE_DIMS", "MODE_VOLUME_EGALISE", "BUDGET_REVUE", "FRONTIERE",
    "applique_point_1", "applique_point_2", "ErreurPoint",
]

POINT_1 = "point_1_a_priori_declare"
POINT_2 = "point_2_budget_de_revue_egal"

MODE_DIMS = "dims"
MODE_VOLUME_EGALISE = "volume_egalise"

#: Repris tel quel de `engine.BUDGET_REVUE_DEFAUT` (60 paires/min x 5 min) — non re-dérivé.
BUDGET_REVUE = engine.BUDGET_REVUE_DEFAUT
FRONTIERE = engine.FRONTIERE_NEUTRE


class ErreurPoint(RuntimeError):
    """Un point de fonctionnement mal appliqué produirait un chiffre faux d'apparence normale."""


def applique_point_1(scores) -> dict:
    """Le verdict que le système déclare lui-même. Aucune transformation, aucun seuil ajouté.

    Un système binaire n'a pas de zone grise : ses verdicts sont MATCH/NON_MATCH, et sous la
    convention stricte il ne paie donc aucune abstention. C'est l'asymétrie `A3`, déclarée,
    et la sensibilité d'arbitrage forcé la chiffre en retirant au moteur son droit de se taire.
    """
    verdicts = {}
    for s in scores:
        v = s.get("verdict_natif")
        if v not in (cb.MATCH, cb.NON_MATCH):
            raise ErreurPoint(f"verdict natif hors enumeration : {v!r}")
        verdicts[cb.cle(s["record_id_a"], s["record_id_b"])] = v
    return {
        "point": POINT_1,
        "verdicts": verdicts,
        "parametres": {"regle": "verdict declare par le systeme, sans seuil ajoute"},
    }


def _dims(scores, budget_revue: int, frontiere: float) -> dict:
    """Bande DIMS sur la distribution de score du système — la MÊME fonction pour tous."""
    valeurs = [s["poids_match"] for s in scores]
    dim = engine.dimensionne_seuils(valeurs, budget_revue=budget_revue, frontiere=frontiere)
    verdicts = {cb.cle(s["record_id_a"], s["record_id_b"]):
                cb.projette_3_zones(s["poids_match"], dim["t_mu"], dim["t_lambda"])
                for s in scores}
    return {
        "verdicts": verdicts,
        "parametres": {
            "mode": MODE_DIMS,
            "t_mu": dim["t_mu"], "t_lambda": dim["t_lambda"],
            "frontiere": dim["frontiere"],
            "budget_vise": dim["budget_vise"], "budget_atteint": dim["budget_atteint"],
            "ecart_au_budget": dim["ecart_au_budget"],
            "methode": dim["methode"], "repli": dim["repli"],
            "note": ("meme fonction, meme budget et meme frontiere que pour le moteur maison : "
                     "le dispositif de placement de seuil n'est pas un avantage maison"),
        },
    }


def _volume_egalise(scores, k_cible: int) -> dict:
    """Les `k_cible` meilleures paires déclarées MATCH, départage des ex aequo GELÉ.

    Ordre : score décroissant, puis clé croissante — ordre TOTAL, donc reproductible. Un
    paquet d'ex aequo à cheval sur `k_cible` est inclus **en entier** si cela rapproche de la
    cible, exclu sinon : couper au milieu d'un paquet reviendrait à départager par
    l'identifiant, c'est-à-dire au hasard. Le `n_MATCH` réellement émis est publié, car il
    peut différer de `k_cible`.
    """
    if k_cible < 0:
        raise ErreurPoint(f"volume cible negatif : {k_cible}")
    ordonnes = sorted(scores, key=lambda s: (-s["poids_match"],
                                             cb.cle(s["record_id_a"], s["record_id_b"])))
    paquets, courant, valeur = [], [], None
    for s in ordonnes:
        if valeur is None or s["poids_match"] == valeur:
            courant.append(s)
            valeur = s["poids_match"]
        else:
            paquets.append(courant)
            courant, valeur = [s], s["poids_match"]
    if courant:
        paquets.append(courant)

    retenus, cumul = [], 0
    for paquet in paquets:
        if cumul >= k_cible:
            break
        avec = cumul + len(paquet)
        # Inclure le paquet entier seulement s'il rapproche de la cible ; à égalité d'écart,
        # on ne l'inclut pas (le budget n'est jamais dépassé sans nécessité).
        if abs(avec - k_cible) < abs(cumul - k_cible):
            retenus.extend(paquet)
            cumul = avec
        else:
            break

    gagnantes = {cb.cle(s["record_id_a"], s["record_id_b"]) for s in retenus}
    verdicts = {cb.cle(s["record_id_a"], s["record_id_b"]):
                (cb.MATCH if cb.cle(s["record_id_a"], s["record_id_b"]) in gagnantes
                 else cb.NON_MATCH)
                for s in scores}
    return {
        "verdicts": verdicts,
        "parametres": {
            "mode": MODE_VOLUME_EGALISE,
            "k_cible": k_cible, "n_match_emis": len(gagnantes),
            "couverture": 1.0, "n_zone_grise": 0,
            "departage": "score decroissant puis cle croissante ; paquet d'ex aequo entier ou exclu",
            "note": ("DIMS est INAPPLICABLE a un score entier non signe : aucune frontiere "
                     "neutre ou placer une bande. Ce point egalise donc le VOLUME de MATCH, "
                     "et cette difference est imprimee dans la cellule."),
        },
    }


def applique_point_2(scores, mode: str, budget_revue: int = BUDGET_REVUE,
                     frontiere: float = FRONTIERE, k_cible=None) -> dict:
    """Point 2, dispatché sur le MODE — une donnée de configuration, jamais un nom de système.

    C'est ce qui rend `L3_MEME_ORACLE` et `L5_SYMETRIE_DE_REGLAGE` vérifiables par lecture du
    code plutôt que par confiance : il n'existe ici aucune branche qui puisse traiter le
    moteur autrement que Splink.
    """
    if mode == MODE_DIMS:
        sortie = _dims(scores, budget_revue, frontiere)
    elif mode == MODE_VOLUME_EGALISE:
        if k_cible is None:
            raise ErreurPoint("mode volume_egalise sans volume cible")
        sortie = _volume_egalise(scores, k_cible)
    else:
        raise ErreurPoint(f"mode de point 2 inconnu : {mode!r}")
    sortie["point"] = POINT_2
    return sortie
