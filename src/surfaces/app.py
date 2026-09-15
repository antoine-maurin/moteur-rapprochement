# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Le serveur des trois surfaces. Starlette + Jinja2, hors ligne.

    .venv\\Scripts\\python -m surfaces.app          # http://127.0.0.1:7860

## Pourquoi Starlette et pas autre chose
Le produit doit tourner **hors ligne** : aucune dépendance ne peut être installée après coup,
et le `.venv` du projet n'a pas de `pip`. Des serveurs web disponibles dans l'environnement
verrouillé — `starlette`, `uvicorn`, `jinja2`, `streamlit` — seuls les trois premiers laissent
reproduire la maquette au pixel près. Streamlit imposerait sa propre chrome, qu'il faudrait
ensuite combattre ; ce n'est pas un choix esthétique mais un choix de fidélité.

## Aucune ressource distante
Ni CDN, ni carte, ni télémétrie, ni police servie par un tiers. Une page qui irait chercher
une fonte chez un tiers ferait mentir « il tourne chez vous, hors ligne » au premier
chargement — et c'est l'argument central de la Vitrine.

Les fontes de la maquette (*Space Grotesk*, *Inter*, *JetBrains Mono*) sont **auto-hébergées** :
les fichiers `.woff2` vivent dans `statique/fontes/`, servis par ce serveur comme le reste du
statique, et déclarés en `@font-face` avec des chemins locaux. Le seul accès réseau a lieu au
moment de les récupérer (`deploiement/recupere_fontes.py`), une fois, hors exécution du
produit. Chaque famille garde une pile système en repli. `tests/test_surfaces.py` vérifie
qu'aucune surface n'émet la moindre requête sortante au rendu.

## Ce que ce module ne fait pas
Il ne lit aucun artefact lui-même et ne met aucune valeur en forme : il assemble `vue` et les
gabarits. Le modèle d'affichage est construit UNE fois au démarrage et partagé par les deux
surfaces qui l'affichent — c'est ce qui rend `G4` structurel plutôt que testé après coup.
"""
from __future__ import annotations

import json
import os
import sys

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

_ICI = os.path.dirname(os.path.abspath(__file__))
if _ICI not in sys.path:                                  # exécution par `python -m surfaces.app`
    sys.path.insert(0, os.path.dirname(_ICI))

from surfaces import bac_a_sable, format as fmt, vue      # noqa: E402

__all__ = ["cree_application", "rend", "GABARITS", "RACINE_REPO"]

#: Les gabarits, et la surface que chacun sert. C'est sur cette table que le scan de vocabulaire
#: s'appuie pour savoir quelle page doit être exempte de jargon.
GABARITS = {
    "vitrine": "vitrine.html",
    "salle_des_machines": "salle_des_machines.html",
    "bac_a_sable": "bac_a_sable.html",
    "dossier_technique": "dossier_technique.html",
}

#: Les surfaces de VENTE, celles que le scan de vocabulaire doit tenir propres. Le dossier
#: technique n'en fait pas partie : il NOMME les systèmes, et c'est sa fonction.
SURFACES_DE_VENTE = ("vitrine", "salle_des_machines", "bac_a_sable")

#: Racine du repo, déduite de l'emplacement du module — jamais un chemin absolu écrit en dur.
RACINE_REPO = os.path.dirname(os.path.dirname(_ICI))

_GABARITS = os.path.join(_ICI, "gabarits")
_STATIQUE = os.path.join(_ICI, "statique")

#: Port par défaut de Hugging Face Spaces.
PORT_DEFAUT = 7860


def _gabarits() -> Jinja2Templates:
    """Les gabarits, avec les filtres de mise en forme française."""
    gabarits = Jinja2Templates(directory=_GABARITS)
    gabarits.env.filters["nombre"] = fmt.nombre
    gabarits.env.filters["signe"] = fmt.signe
    gabarits.env.filters["pourcent"] = fmt.pourcent
    gabarits.env.filters["entier"] = fmt.entier
    gabarits.env.filters["booleen"] = fmt.booleen
    gabarits.env.filters["libelle"] = fmt.libelle
    gabarits.env.filters["liste_libelles"] = fmt.liste_libelles
    gabarits.env.filters["liste_libelles_avec_articles"] = fmt.liste_libelles_avec_articles
    gabarits.env.filters["accorde"] = fmt.accorde
    # `trim_blocks` garde le HTML rendu lisible : un gabarit illisible est un gabarit qu'on
    # ne relit pas, et c'est ce HTML-là que le scan de vocabulaire inspecte.
    gabarits.env.trim_blocks = True
    gabarits.env.lstrip_blocks = True
    return gabarits


def rend(gabarit: str, modele: dict, **extra) -> str:
    """Rend un gabarit en HTML, sans serveur ni requête.

    C'est ce que les oracles inspectent : le scan de vocabulaire porte sur ce que le lecteur VOIT,
    pas sur la source du gabarit. Un jargon introduit par une valeur d'artefact plutôt que par le
    texte du gabarit passerait une revue de source et pas celle-ci.
    """
    contexte = {"v": modele, "request": None}
    contexte.update(extra)
    return _gabarits().get_template(gabarit).render(**contexte)


def cree_application(racine: str = RACINE_REPO) -> Starlette:
    """L'application, modèle d'affichage construit une seule fois.

    Le point de fonctionnement est chargé ici, depuis l'artefact, et passé au bac à sable :
    aucun seuil n'est écrit dans ce fichier, et il n'existe aucun chemin par lequel il
    pourrait l'être.
    """
    from pipeline import point as pt                      # import tardif : seul le bac en a besoin

    gabarits = _gabarits()
    modele = vue.construit(racine=racine)
    point = pt.point_depuis_artefact(pt.CHEMIN_DIMS_V2, racine=racine)

    async def vitrine(request):
        return gabarits.TemplateResponse(request, "vitrine.html", {"v": modele})

    async def salle_des_machines(request):
        return gabarits.TemplateResponse(request, "salle_des_machines.html", {"v": modele})

    async def dossier(request):
        return gabarits.TemplateResponse(request, "dossier_technique.html", {"v": modele})

    async def bac(request):
        return gabarits.TemplateResponse(request, "bac_a_sable.html", {
            "v": modele,
            "extrait_json": json.dumps(
                modele["demonstration"]["extrait"]["records"], ensure_ascii=False),
            "champs": list(bac_a_sable.CHAMPS_RECORD),
            # Le plafond de longueur part au navigateur plutôt que d'y être recopié : les deux
            # copies pouvaient diverger, et c'est le champ de saisie qui aurait tronqué en
            # silence, rendant inatteignable le message d'erreur du serveur.
            "longueur_max_valeur": bac_a_sable.LONGUEUR_MAX_VALEUR,
        })

    async def api_scenario(request):
        """Le détail d'un scénario, servi à la demande.

        L'artefact pèse plus d'un demi-mégaoctet : l'inliner dans la page ferait payer à
        chaque visiteur les trois scénarios pour n'en regarder qu'un, et le budget de la
        Vitrine se compte jusqu'au premier écran lisible.
        """
        cle = request.path_params["cle"]
        for scenario in modele["scenarios"]:
            if scenario["cle"] == cle:
                return JSONResponse(scenario)
        return JSONResponse({"erreur": f"scénario inconnu : {cle}"}, status_code=404)

    async def api_rapprocher(request):
        """Exécute le moteur sur l'entrée reçue. Le seul point de l'application qui calcule."""
        try:
            charge_utile = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse({"erreur": "Corps de requête illisible."}, status_code=400)
        # Un corps JSON valide mais qui n'est pas un objet (`[]`, `"x"`, `3`) n'a pas de
        # `.get` : sans cette garde, la première entrée hostile venue rend une 500 et une
        # trace de pile, là où le module entier a pour doctrine de refuser proprement.
        if not isinstance(charge_utile, dict):
            return JSONResponse(
                {"erreur": "Le corps doit être un objet de la forme {records: [...]}.",
                 "type": "entree"}, status_code=400)
        try:
            records = bac_a_sable.normalise_entree(charge_utile.get("records"))
            resultat = bac_a_sable.execute(records, point)
        except bac_a_sable.BudgetDepasse as erreur:
            return JSONResponse({"erreur": str(erreur), "type": "budget"}, status_code=413)
        except (bac_a_sable.EntreeInvalide, ValueError) as erreur:
            return JSONResponse({"erreur": str(erreur), "type": "entree"}, status_code=400)
        return JSONResponse(resultat)

    return Starlette(routes=[
        Route("/", vitrine),
        Route("/salle-des-machines", salle_des_machines),
        Route("/bac-a-sable", bac),
        Route("/dossier-technique", dossier),
        Route("/api/scenario/{cle}", api_scenario),
        Route("/api/rapprocher", api_rapprocher, methods=["POST"]),
        Mount("/statique", StaticFiles(directory=_STATIQUE), name="statique"),
    ])


application = None


def main() -> int:
    import uvicorn
    port = int(os.environ.get("PORT", PORT_DEFAUT))
    uvicorn.run(cree_application(), host="0.0.0.0", port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
