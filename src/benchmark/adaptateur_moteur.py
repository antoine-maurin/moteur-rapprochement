# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Adaptateur du MOTEUR MAISON vers le contrat commun du banc.

Le moteur est le SUJET de la comparaison, pas son arbitre : il passe par le même contrat que
Splink et les baselines, et il est noté par le même oracle, au même endroit, sous la même
convention. Cet adaptateur ne fait donc rien de plus que traduire — il n'ajoute aucun seuil,
aucun filtre, aucune correction.

## Le moteur émet TROIS verdicts, les autres deux
`verdict_natif` ne peut valoir que MATCH ou NON_MATCH dans le contrat de banc : c'est le
point 1, « ce que le système déclare sans regarder la donnée », et pour le moteur ce sont ses
placeholders ±8 bits. Sa ZONE_GRISE au point 1 est donc reportée en NON_MATCH — **et c'est
délibérément le traitement le plus défavorable au moteur** : sous la convention stricte du
scoreur, une abstention compte comme prédit-négatif et pénalise son rappel, là où un système
binaire ne paie aucune abstention. L'asymétrie est déclarée (`A3`), et son sens est publié :
elle joue contre le moteur maison.

Le verdict à trois zones du moteur reste intégralement disponible dans `verdict_moteur_3z`,
publié en diagnostic, pour que la lecture puisse être refaite par un tiers.

## Non-circularité
Ce module importe `engine` et jamais `scorer`. Aucune vérité terrain n'entre dans le
paramétrage : les seuils du point 2 viennent de `points.py`, qui ne lit qu'une distribution
de scores.
"""
from __future__ import annotations

import engine

from . import contrat_bench as cb

__all__ = ["NOM", "MODE_POINT_2", "execute"]

NOM = "moteur_maison"
#: Le moteur a un score signé et une frontière évidentielle : DIMS lui est applicable.
MODE_POINT_2 = "dims"


def execute(substrat, passes=None, t_mu=None, t_lambda=None) -> dict:
    """Exécute le moteur sur le substrat et rend le contrat commun.

    `passes` vaut par défaut `engine.PASSES_DEFAUT` — soit le blocking POST-retrait de
    `SDX_NOM` (O0a). Le bras B (chaîne complète) l'appelle avec ce même défaut : c'est
    précisément ce que le produit livre.
    """
    params = engine.ParametresMoteur(
        passes_blocking=tuple(passes or engine.PASSES_DEFAUT),
        **({"t_mu": t_mu} if t_mu is not None else {}),
        **({"t_lambda": t_lambda} if t_lambda is not None else {}))
    sortie = engine.execute_moteur(substrat.records, params)
    corrs = sortie["correspondances"]

    scores = []
    for c in corrs:
        a, b = cb.cle(c["record_id_a"], c["record_id_b"])
        verdict_3z = c["verdict"]
        scores.append({
            "record_id_a": a, "record_id_b": b,
            "poids_match": round(float(c["poids_match"]), cb.DECIMALES_LIVRAISON),
            # Point 1 : la ZONE_GRISE est reportee en NON_MATCH — le traitement le plus
            # defavorable au moteur, et il est declare comme tel.
            "verdict_natif": cb.MATCH if verdict_3z == cb.MATCH else cb.NON_MATCH,
            "verdict_moteur_3z": verdict_3z,
            "garde_r20_appliquee": c.get("garde_r20_appliquee"),
            "n_composantes_informatives": c.get("n_composantes_informatives"),
        })
    scores.sort(key=lambda s: (s["record_id_a"], s["record_id_b"]))

    rapport = sortie["rapport"]
    estimation = rapport.get("estimation") or {}
    repartition = rapport.get("repartition_verdicts") or {}
    diagnostic = {
        "systeme": NOM,
        "n_paires": len(scores),
        "parametres": {
            "passes_blocking": list(params.passes_blocking),
            "longueur_prefixe": params.longueur_prefixe,
            "t_mu": params.t_mu, "t_lambda": params.t_lambda,
            "graine_em": params.graine_em,
            "non_calibres": list(engine.ParametresMoteur.PARAMETRES_NON_CALIBRES),
        },
        "repartition_verdicts_3_zones": dict(repartition),
        "n_zone_grise_point_1": repartition.get(cb.ZONE_GRISE, 0),
        "note_zone_grise_point_1": (
            "les paires ZONE_GRISE du moteur sont reportees en NON_MATCH au point 1 : sous la "
            "convention stricte, une abstention compte comme predit-negatif. C'est le "
            "traitement le PLUS DEFAVORABLE au moteur, et il est retenu deliberement."),
        "estimation_em": {
            "convergence": estimation.get("convergence"),
            "iterations": estimation.get("iterations"),
            "repli": estimation.get("repli"),
            "graine": estimation.get("graine"),
            "note": ("EM NON SUPERVISE : aucune etiquette n'y entre, exactement comme celui "
                     "de Splink"),
        },
        "passes_retirees_du_defaut": {
            nom: dict(detail) for nom, detail in engine.PASSES_RETIREES_DU_DEFAUT.items()},
    }
    return {"systeme": NOM, "scores": scores, "diagnostic": diagnostic}
