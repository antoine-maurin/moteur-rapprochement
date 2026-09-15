# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Produit l'artefact `artifacts/thresholds_sized.json` (O2).

    .venv\\Scripts\\python tools/dimensionne_seuils.py

Pourquoi ce script vit HORS de `src/engine/` : le dimensionnement doit s'appliquer à
n'importe quelle population — en exploitation, ce sont les données réelles. Faire dépendre
`src/engine/threshold_sizing.py` du générateur coupleraient deux unités que la doctrine
sépare, et briserait la liste blanche d'imports du moteur (bibliothèque standard
seulement, C7). Le générateur ne sert ici qu'à fournir une **population de démonstration**
représentative ; il reste du côté de l'outillage.

Non-circularité : seuls les `records` du pack sont consommés. La vérité terrain du générateur n'est
ni lue ni transmise ; le dimensionnement ne voit que des valeurs de `R`.
"""
from __future__ import annotations

import json
import os
import sys

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RACINE, "src"))

import engine                                            # noqa: E402
from engine import threshold_sizing as ts                # noqa: E402
from generator import generate_pack                      # noqa: E402

#: Population de démonstration : la population BULK du générateur, à graine scellée.
GRAINE_POPULATION = "SP_CYCLE_001::GEN-01::seed-0001"
N_ENTITES = 400

CHEMIN_ARTEFACT = os.path.join(_RACINE, "artifacts", "thresholds_sized.json")

#: Passes de blocking sous lesquelles cet artefact a été PUBLIÉ.
#: Épinglées ICI, et non héritées de `blocking.PASSES_DEFAUT`, depuis que le banc de
#: comparaison a retiré `SDX_NOM` du défaut (objectif O0a). Ce retrait est qualifié
#: d'« exécution ADDITIONNELLE », avec « l'antériorité des paramètres préservée » : un
#: artefact déjà publié ne doit donc pas se mettre à décrire un autre moteur parce qu'un
#: défaut a bougé ailleurs. Épingler rend la configuration de publication EXPLICITE au lieu
#: de la laisser dépendre d'une constante mutable — la reproductibilité de l'artefact cesse
#: d'être accidentelle. Ce n'est pas un retour en arrière sur O0a : c'est ce qui permet à O0a
#: d'être additif plutôt que rétroactif.
PASSES_PUBLIEES = ("CP", "SDX_NOM", "PREF")


def construis_rapport(graine: str = GRAINE_POPULATION, n_entites: int = N_ENTITES,
                      budget_revue: int = ts.BUDGET_REVUE_DEFAUT) -> dict:
    """Exécute le moteur sur la population de démonstration et dimensionne les seuils."""
    pack = generate_pack(graine, n_entities=n_entites)
    records = pack["records"]                       # Non-circularité : les records, rien d'autre

    avant = engine.execute_moteur(records,
                                  engine.ParametresMoteur(passes_blocking=PASSES_PUBLIEES))
    dimensionnement = ts.dimensionne_depuis_correspondances(
        avant["correspondances"], budget_revue=budget_revue)

    parametres = engine.ParametresMoteur(t_mu=dimensionnement["t_mu"],
                                         t_lambda=dimensionnement["t_lambda"],
                                         passes_blocking=PASSES_PUBLIEES)
    apres = engine.execute_moteur(records, parametres)

    return {
        "_lisez_moi": (
            "Seuils Tmu/Tlambda dimensionnes sur la distribution de R. "
            "PROVISOIRES : ils placent une "
            "zone grise non vide pour alimenter la revue de zone grise ; ils ne pretendent PAS etre "
            "optimaux. La calibration fine des taux d'erreur releve du scoreur, sur un jeu de "
            "calibration DISTINCT du jeu d'evaluation. Aucune verite terrain n'entre dans "
            "ce calcul."),
        "statut": "PROVISOIRE",
        "gap": "calibration différée",
        "population_demonstration": {
            "source": "generateur GEN_001, population BULK",
            "graine": graine,
            "n_entites": n_entites,
            "n_records": len(records),
            "n_paires_candidates": avant["rapport"]["n_paires"],
        },
        "budget_revue": {
            "valeur": dimensionnement["budget_vise"],
            "derivation": "debit_par_minute x duree_minutes",
            "debit_par_minute": ts.DEBIT_REVUE_PAR_MINUTE_PROVISOIRE,
            "duree_minutes": ts.DUREE_REVUE_MINUTES_PROVISOIRE,
            "statut": ("PROVISOIRE : le debit reel de la revue de zone grise n'est pas "
                       "mesurable tant qu'elle n'est pas construite. Seul ce couple de "
                       "constantes changera quand elle le sera."),
        },
        "seuils_dimensionnes": {
            "t_lambda": dimensionnement["t_lambda"],
            "t_mu": dimensionnement["t_mu"],
            "frontiere": dimensionnement["frontiere"],
            "methode": dimensionnement["methode"],
        },
        "seuils_placeholder_precedents": {
            "t_lambda": engine.ParametresMoteur().t_lambda,
            "t_mu": engine.ParametresMoteur().t_mu,
        },
        "effet": {
            "repartition_avant": avant["rapport"]["repartition_verdicts"],
            "repartition_apres": apres["rapport"]["repartition_verdicts"],
            "zone_grise_avant": avant["rapport"]["repartition_verdicts"]["ZONE_GRISE"],
            "zone_grise_apres": apres["rapport"]["repartition_verdicts"]["ZONE_GRISE"],
            "ecart_au_budget": dimensionnement["ecart_au_budget"],
            "budget_sature": dimensionnement["budget_sature"],
        },
        "statistiques_r": dimensionnement["statistiques_r"],
        "parametres_provisoires": dimensionnement["parametres_provisoires"],
    }


def ecris_artefact(rapport: dict, chemin: str = CHEMIN_ARTEFACT) -> str:
    """Écrit l'artefact en JSON canonique (clés triées) : régénérable à l'identique."""
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rapport, fh, sort_keys=True, ensure_ascii=False, indent=2)
        fh.write("\n")
    return chemin


def main() -> int:
    rapport = construis_rapport()
    chemin = ecris_artefact(rapport)
    seuils = rapport["seuils_dimensionnes"]
    effet = rapport["effet"]
    sys.stdout.buffer.write(
        (f"artefact ecrit : {os.path.relpath(chemin, _RACINE)}\n"
         f"  T_lambda = {seuils['t_lambda']}\n"
         f"  T_mu     = {seuils['t_mu']}\n"
         f"  zone grise : {effet['zone_grise_avant']} -> {effet['zone_grise_apres']} "
         f"paires (budget {rapport['budget_revue']['valeur']}, "
         f"ecart {effet['ecart_au_budget']:+d})\n"
         f"  statut : PROVISOIRE (calibration différée)\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
