# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Canonicalisation des empreintes du pack vérité terrain (GEN_001).

Discipline scellée par FIXTURE_PACK_GT_V1_1 (manifest.fingerprint_canonicalization) :
- content_sha256 : SHA-256 des octets UTF-8 de json.dumps({records, ground_truth,
  corruption_annotation, zone_intention_design}, sort_keys=True, ensure_ascii=False,
  separators=(', ', ': ')). Le bloc manifest est EXCLU du hachage.
- seal_sha256_16 : 16 premiers hex de SHA-256 de
  "{seed}||{generator_version}||{dumps(rates_sealed)}||{content_sha256}".

Vérifié bit-à-bit contre FX_001 (content_sha256 0c8a90994c8bd7c6…, seal 9ee258eba7ee1e38).
Déterminisme : même graine + même config => mêmes empreintes.
"""
from __future__ import annotations
import hashlib
import json

PAYLOAD_KEYS = ("records", "ground_truth", "corruption_annotation", "zone_intention_design")


def content_sha256(pack: dict) -> str:
    """SHA-256 hex du payload canonicalisé (manifest exclu)."""
    payload = {k: pack[k] for k in PAYLOAD_KEYS}
    canon = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def seal_sha256_16(seed: str, generator_version: str, rates_sealed: dict, content_hash: str) -> str:
    """16 premiers hex du sceau de configuration."""
    rates_canon = json.dumps(rates_sealed, sort_keys=True, separators=(", ", ": "))
    seal_input = f"{seed}||{generator_version}||{rates_canon}||{content_hash}"
    return hashlib.sha256(seal_input.encode("utf-8")).hexdigest()[:16]


def verify_pack(pack: dict) -> dict:
    """Recompte les empreintes d'un pack et les confronte à son manifest.

    Retourne {content_ok, seal_ok, content_sha256, seal_sha256_16}.
    Sert de garde de non-régression : un pack scellé doit rester reproductible.
    """
    m = pack["manifest"]
    ch = content_sha256(pack)
    sl = seal_sha256_16(m["seed"], m["generator_version"], m["rates_sealed"], ch)
    return {
        "content_ok": ch == m["content_sha256"],
        "seal_ok": sl == m["seal_sha256_16"],
        "content_sha256": ch,
        "seal_sha256_16": sl,
    }
