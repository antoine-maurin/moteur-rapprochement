# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""La règle UNIQUE de l'empreinte de contenu des artefacts d'interface.

## Pourquoi une règle partagée

`empreinte_contenu` est publié dans chaque artefact comme sa garantie d'intégrité : un
lecteur doit pouvoir recalculer ce nombre à partir du fichier qu'il tient et retrouver celui
qui y est écrit. Deux choses ont manqué, et la revue adversariale a trouvé les deux :

1. **La règle n'était pas la même des deux côtés.** `ui_scenarios.json` excluait le commit et
   la durée de build ; `ui_demonstration.json` hachait tout, commit compris. La même promesse
   couvrait donc deux comportements différents : le premier reproductible, le second changeant
   à chaque commit sans qu'aucun contenu affiché ne change.
2. **Aucun oracle ne la vérifiait.** Le champ était produit, publié, présenté comme garantie —
   et personne ne recalculait jamais rien. Une garantie que rien ne vérifie n'est pas une
   garantie faible : c'est une affirmation.

Ce module porte la règle, une fois. Les deux producteurs l'appellent, l'oracle l'appelle, et
un lecteur qui veut vérifier lui-même lit vingt lignes plutôt que deux implémentations.

## Ce que l'empreinte couvre, et ce qu'elle ne couvre pas

Elle couvre **la matière mesurée** : records, décisions, comptes, points de fonctionnement,
énoncés. Elle exclut ce qui décrit la PRODUCTION de l'artefact et non son contenu — la durée
d'horloge du build, le SHA du commit qui l'a produit, et la version de l'interpréteur qui l'a
calculé. Deux exécutions du même code sur la même fixture doivent donner la même empreinte ;
sinon personne ne peut la reproduire, et une empreinte irreproductible ne prouve rien.

**Troisième reprise de la même faute, trouvée par la mesure.** Le point 1 ci-dessus retirait le
commit du sceau ; `version_python` y était resté, un champ plus loin. L'effet était le même, en
pire : l'artefact scellait la version de l'interpréteur qui l'avait produit, si bien que son
sceau n'était recalculable que sur cette version-là. Or, rejouée sous d'autres piles, TOUTE la
matière des deux artefacts sortait octet pour octet identique ; seule cette auto-description
divergeait. Ce n'était donc pas une limite de la reproductibilité, mais un sceau qui attestait
son environnement au lieu d'attester sa matière.

Les trois piles sur lesquelles l'empreinte a été vérifiée identique, après correction :

    Python 3.12.14 · numpy 2.5.2  · scipy 1.18.1 · unicodedata 15.0   (environnement de build)
    Python 3.12.7  · numpy 1.26.4 · scipy 1.13.1 · unicodedata 15.0
    Python 3.14.3  · sans numpy   · sans scipy   · unicodedata 16.0

Deux versions mineures de Python et deux versions des tables Unicode donnent le même sceau : la
matière mesurée ne dépend d'aucune des deux. `tools/banc_ub6.py` appliquait déjà la bonne règle
en excluant tout son bloc `provenance` (`CLES_VOLATILES`) ; les deux artefacts d'interface s'y
alignent ici. La promesse en sort plus forte, pas plus prudente : l'empreinte cesse d'être
« reproductible sur la machine de build » pour devenir reproductible tout court.

Attention à la formulation : il serait faux d'écrire que ces champs « ne sont pas affichés ».
Le commit l'est — la Salle des machines le publie dans son panneau de reproductibilité,
étiqueté comme le commit qui a produit l'artefact, ce qui est précisément son rôle. Ce que
l'exclusion dit, c'est qu'il identifie la production et non la mesure. Les champs exclus
restent PUBLIÉS et lisibles ; ils ne sont simplement pas scellés.
"""
from __future__ import annotations

import hashlib
import json

__all__ = ["CHAMPS_EXCLUS", "NOTE", "canonique", "empreinte", "verifie"]

#: Les chemins exclus du hachage, en clair. `("scenarios", "*", "duree_calcul_build_s")`
#: signifie : le champ `duree_calcul_build_s` de chaque élément de la liste `scenarios`.
CHAMPS_EXCLUS = (
    ("provenance", "commit"),
    ("provenance", "version_python"),
    ("scenarios", "*", "duree_calcul_build_s"),
    ("empreinte_contenu",),
    ("_note_empreinte",),
)

NOTE = ("empreinte de la matière mesurée. La durée de build, le commit de production et la "
        "version de l'interpréteur sont exclus du sceau — ils identifient l'exécution qui a "
        "produit ce fichier, pas ce qui y est mesuré — mais restent publiés ici, et le commit "
        "comme la version sont affichés par la surface. L'empreinte ne dépend donc d'aucun "
        "environnement : elle se recalcule à l'identique sur n'importe quelle installation. "
        "Recalculable par tools/empreinte_artefact.py.")


def canonique(objet) -> str:
    """Forme canonique du projet : triée, non échappée, séparateurs fixés."""
    return json.dumps(objet, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))


def _retire(contenu: dict, chemin: tuple) -> None:
    """Retire un chemin du contenu, en traversant les listes marquées `*`. Silencieux si absent."""
    if not chemin:
        return
    tete, reste = chemin[0], chemin[1:]
    if tete == "*":
        if isinstance(contenu, list):
            for element in contenu:
                _retire(element, reste)
        return
    if not isinstance(contenu, dict) or tete not in contenu:
        return
    if not reste:
        contenu.pop(tete, None)
        return
    _retire(contenu[tete], reste)


def empreinte(contenu: dict) -> str:
    """L'empreinte de contenu d'un artefact, champs volatils exclus.

    Le contenu passé n'est pas modifié : on travaille sur une copie obtenue par aller-retour
    JSON, ce qui garantit au passage que seule la matière SÉRIALISABLE entre dans le calcul —
    un objet Python qui se serait glissé dans l'artefact ferait lever ici, et non silence.
    """
    copie = json.loads(canonique(contenu))
    for chemin in CHAMPS_EXCLUS:
        _retire(copie, chemin)
    return hashlib.sha256(canonique(copie).encode("utf-8")).hexdigest()


def verifie(contenu: dict) -> bool:
    """L'empreinte publiée dans l'artefact correspond-elle à son contenu ?"""
    publiee = contenu.get("empreinte_contenu")
    return bool(publiee) and publiee == empreinte(contenu)
