# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Générateur GEN_001 (population BULK vérité terrain, from-seed)."""
from .canonicalization import content_sha256, seal_sha256_16, verify_pack
from .generator import generate_pack, RATES_SEALED, GENERATOR_VERSION

__all__ = ["content_sha256", "seal_sha256_16", "verify_pack",
           "generate_pack", "RATES_SEALED", "GENERATOR_VERSION"]
