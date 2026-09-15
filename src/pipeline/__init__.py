# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""`pipeline` — orchestration bout-en-bout.

    records  ->  [moteur]  ->  [revue]  ->  [clôture + fusion]  ->  dorés

Ce paquet ne contient AUCUNE décision, AUCUN seuil et AUCUNE métrique : il chaîne. C'est
pourquoi il vit hors de `src/engine/` — la zone moteur porte un inventaire clos et une liste
blanche d'imports qui exclut `os` et `json`, alors qu'un orchestrateur doit pouvoir charger
un point de fonctionnement publié. Séparer les deux garde la liste blanche du moteur
intacte au lieu de l'élargir pour loger un module qui ne décide de rien.

## Frontière de non-circularité, dans les deux sens
Ce paquet n'importe PAS `scorer` et ne lit JAMAIS la vérité terrain : ni `ground_truth`, ni
`id_entite_vraie`, ni `zone_intention_design` n'apparaissent dans son code, et un test
l'éprouve par analyse du source. Mesurer ce que la chaîne produit est le travail du scoreur,
séparément et APRÈS COUP — c'est la condition de non-circularité de la preuve, et elle
survit à l'assemblage complet.
"""
from .point import (PointDeFonctionnement, SeuilsPerimes, CHEMIN_DIMS_V2,
                    DECIMALES_EMPREINTE_POIDS, empreinte_population,
                    empreinte_table_de_poids, point_depuis_artefact,
                    point_depuis_records, point_depuis_correspondances,
                    verifie_provenance)
from .chaine import (ETAGES, execute_chaine, aretes_de_l_ensemble_de_match,
                     client_substitut_1b, ConservationRompue)
from .canonicalisation import (CLES_PAYLOAD_E2E, CLES_RAPPORT_E2E, CLES_POINT_E2E,
                               CLES_PROVENANCE_E2E, serialisation_canonique,
                               payload_e2e, content_sha256_e2e)

__all__ = [
    # point de fonctionnement et provenance
    "PointDeFonctionnement", "SeuilsPerimes", "CHEMIN_DIMS_V2",
    "DECIMALES_EMPREINTE_POIDS", "empreinte_population", "empreinte_table_de_poids",
    "point_depuis_artefact", "point_depuis_records", "point_depuis_correspondances",
    "verifie_provenance",
    # la chaîne
    "ETAGES", "execute_chaine", "aretes_de_l_ensemble_de_match",
    "client_substitut_1b", "ConservationRompue",
    # canonicalisation bout-en-bout
    "CLES_PAYLOAD_E2E", "CLES_RAPPORT_E2E", "CLES_POINT_E2E", "CLES_PROVENANCE_E2E",
    "serialisation_canonique", "payload_e2e", "content_sha256_e2e",
]
