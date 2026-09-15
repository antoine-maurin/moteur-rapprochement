# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""`benchmark` — le banc de comparaison.

Ce paquet compare le moteur maison à **Splink v4.0.16** et à des baselines, sur la donnée
`FX_001 V1.2`, dans des conditions déclarées. Il ne fabrique aucune métrique : il produit des
CORRESPONDENCE au contrat commun, que le scoreur indépendant note ensuite.

## Topologie — non-circularité tenue par CONSTRUCTION, pas par discipline
`src/benchmark/` importe `engine` ; il n'importe **JAMAIS** `scorer`. Le seul point où le
moteur et le scoreur se rencontrent est `tools/banc_ub6.py`, **hors de `src/`** — exactement
le précédent posé par `tools/mesure_discrimination.py`. La raison est la même : on ne
peut pas démontrer la qualité d'un moteur avec un scoreur qui en dépend, ni noter trois
systèmes avec un oracle qui connaît l'un d'eux.

Corollaire pratique : aucun module d'ici ne lit `ground_truth`. Les adaptateurs reçoivent des
enregistrements et rendent des scores ; la vérité terrain n'entre jamais dans une
configuration de système. C'est ce qui rend la comparaison non supervisée des deux côtés.

## Splink est une dépendance de BANC, jamais du produit
`splink`, `duckdb` et `pandas` ne sont importés que par `adaptateur_splink.py`. Le produit
(`src/engine/`, `src/scorer/`) reste bibliothèque standard seule et hors réseau (C7) : un test
structurel le vérifie dans les deux sens.

## Ordre de lecture
`criteres_ub6.py` est **gelé et committé SEUL, avant tout code de mesure** : il dit, en
aveugle, comment lire une comparaison qui n'existe pas encore. Tout le reste vient après.
"""
