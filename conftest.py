# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Configuration pytest du chantier de build.

Src-layout sans installation : ajoute `dev/src/` au sys.path pour que les paquets
(`generator`, puis `engine`, `scorer`, …) soient importables par les tests.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def pytest_configure(config):
    """Déclare les marqueurs employés, pour qu'un marqueur mal orthographié se voie.

    `slow` : test qui rejoue une chaîne complète (le banc dure ~130 s). Il tourne dans
    la suite entière ; `-m "not slow"` permet de l'écarter pendant une itération courte.
    """
    config.addinivalue_line("markers", "slow: rejoue une chaine complete (plusieurs minutes)")
