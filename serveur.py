# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Point d'entrée des surfaces.

    .venv\\Scripts\\python serveur.py          # http://127.0.0.1:7860

Le paquet vit dans `src/`, qui n'est pas installé : ce lanceur l'ajoute au chemin d'import,
puis rend la main. C'est aussi la commande que l'image de déploiement exécute — un seul point
d'entrée, donc un seul comportement à éprouver.

`PORT` est lu de l'environnement, `7860` par défaut : c'est le port qu'attend Hugging Face
Spaces. Aucun chemin absolu n'est écrit ici, le paquet déployé tournant sous Linux.
"""
from __future__ import annotations

import os
import sys

_RACINE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_RACINE, "src"))

from surfaces.app import PORT_DEFAUT, cree_application    # noqa: E402


def main() -> int:
    import uvicorn
    uvicorn.run(cree_application(racine=_RACINE), host="0.0.0.0",
                port=int(os.environ.get("PORT", PORT_DEFAUT)), log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
