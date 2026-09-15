# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""`surfaces` — les trois surfaces de démonstration.

    artefacts JSON  ->  lecture  ->  vue  ->  gabarits  ->  Vitrine | Salle des machines
                                     moteur -> bac_a_sable -----------^

Couche **terminale et en lecture seule**. Elle n'ajoute aucune décision, ne mesure rien, et
ne modifie aucun artefact : elle rend visible ce que d'autres unités ont produit.

## La frontière, et de quel côté chacun se tient
`lecture` et `vue` n'importent **ni** `engine` **ni** `scorer` : une surface d'affichage n'a
besoin que de JSON. `bac_a_sable` importe `engine` — c'est sa raison d'être, il exécute
réellement le moteur sur l'entrée de l'utilisateur — mais il n'importe jamais `scorer` et ne
recompte aucune métrique : ce qu'il produit est une DÉCISION, pas une note.

Personne ici n'importe `scorer`. C'est ce qui permet d'afficher « le moteur ne note pas sa
propre copie » sans que la surface ait à se croire elle-même : elle n'a structurellement pas
accès à ce qu'il faudrait pour recompter. `tests/test_surfaces.py` l'éprouve par analyse du
code source, contrôle positif à l'appui.
"""
from .lecture import ArtefactManquant, Artefacts, LectureImpossible, cellule, charge, valeur
from .vue import construit

__all__ = [
    "ArtefactManquant", "Artefacts", "LectureImpossible",
    "cellule", "charge", "valeur", "construit",
]
