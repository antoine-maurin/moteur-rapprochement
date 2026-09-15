# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""`scorer` — le scoreur INDÉPENDANT.

Ce paquet mesure la qualité d'un appariement contre la vérité terrain. Il est le SEUL
composant autorisé à lire `ground_truth` — le moteur, lui, en est structurellement incapable,
sa normalisation projetant les enregistrements sur les 8 attributs comparés.

## Frontière de non-circularité — la raison d'être de ce paquet
`src/scorer/` et `src/engine/` sont **disjoints** : aucun import, dans aucun sens. Ce n'est
pas une convention de rangement, c'est la condition de validité de la preuve — on ne peut pas
démontrer la qualité d'un moteur avec un scoreur qui en dépend. Le prix en est assumé : le
vocabulaire de verdict est re-déclaré (`contrat.py`) et la méthode de quantile réimplémentée
(`distribution.py`) plutôt qu'importés. Le seul point de rencontre des deux zones est
`tools/mesure_discrimination.py`, hors de `src/`, où elles se croisent **par données**.

## Régime de mesure, déclaré
Pairwise, micro-agrégé. Convention de tête : `stricte` (ZONE_GRISE compte comme
prédit-négatif). Dénominateur du rappel : `|M|` entier, vraies paires perdues au blocking
comprises. Les métriques cluster-wise relèvent du clustering et ne sont pas approximées ici.

## Anti-circularité
Les critères de lecture du verdict sont **pré-enregistrés** dans `criteres.py`, gelé et
committé AVANT tout code de mesure : git atteste l'antériorité, et l'issue « le moteur est
excellent » a déjà son énoncé, si bien qu'elle ne peut pas être requalifiée après coup en
défaut à corriger. La donnée n'est jamais ajustée sur le résultat.

Déterminisme : aucun `hash()` de chaîne (salé par processus), aucun parcours d'ensemble
non trié, aucun aléa non scellé. Offline strict (C7) : bibliothèque standard seulement.
"""
from __future__ import annotations

from .contrat import (CONVENTIONS, MATCH, NON_MATCH, ZONE_GRISE, VERDICTS_ATTENDUS,
                      cle_paire, cle_de_correspondance, valide_correspondances)
from .couverture import (analyse_blocking, pairs_quality, rappel_blocking,
                         taux_de_reduction, n_paires_possibles)
from .criteres import CRITERES, ENONCES, evalue_criteres, lis_verdict, sha256_criteres
from .distribution import (auc_mann_whitney, average_precision, kolmogorov_smirnov,
                           marge_de_separation, plancher_bayes_sur_r, quantile,
                           recouvrement, separation, seuil_oracle_f1, statistiques)
from .metriques import (CONVENTION_DE_TETE, classe_les_paires, contingence,
                        decomposition_du_rappel, f1, intervalle_wilson, mesures,
                        mesures_toutes_conventions, precision, rappel, verifie_invariants)
from .rapport import (CHEMIN_ARTEFACT, construis_rapport, ecris_artefact,
                      empreinte_des_mesures, serialisation_canonique)
from .split import (GRAINE_SPLIT_SCELLEE, diagnostic_seuil_optimal_non_reinjectable,
                    partitionne_entites, pli_de_entite, repartit_paires, trace_split)
from .verite import (charge_pack, empreinte_pack, entites, paires_vraies, partition_entites,
                     statistiques_verite)
from .zone_grise import analyse_zone_grise, bornes_du_doute, composition, irreductibilite

__all__ = [
    # contrat
    "MATCH", "NON_MATCH", "ZONE_GRISE", "VERDICTS_ATTENDUS", "CONVENTIONS",
    "cle_paire", "cle_de_correspondance", "valide_correspondances",
    # vérité terrain
    "charge_pack", "empreinte_pack", "partition_entites", "entites", "paires_vraies",
    "statistiques_verite",
    # couverture / blocking
    "n_paires_possibles", "taux_de_reduction", "pairs_quality", "rappel_blocking",
    "analyse_blocking",
    # métriques
    "CONVENTION_DE_TETE", "classe_les_paires", "contingence", "verifie_invariants",
    "precision", "rappel", "f1", "intervalle_wilson", "mesures",
    "mesures_toutes_conventions", "decomposition_du_rappel",
    # distribution
    "quantile", "statistiques", "auc_mann_whitney", "average_precision",
    "kolmogorov_smirnov", "recouvrement", "marge_de_separation", "plancher_bayes_sur_r",
    "seuil_oracle_f1", "separation",
    # zone grise
    "composition", "irreductibilite", "bornes_du_doute", "analyse_zone_grise",
    # split
    "GRAINE_SPLIT_SCELLEE", "pli_de_entite", "partitionne_entites", "repartit_paires",
    "trace_split", "diagnostic_seuil_optimal_non_reinjectable",
    # critères pré-enregistrés
    "CRITERES", "ENONCES", "sha256_criteres", "evalue_criteres", "lis_verdict",
    # rapport
    "CHEMIN_ARTEFACT", "construis_rapport", "serialisation_canonique",
    "empreinte_des_mesures", "ecris_artefact",
]
