# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Accès aux artefacts mesurés. **Lit, ne calcule jamais**.

Ce module est la seule porte par laquelle un chiffre entre dans les surfaces. Tout ce qui
s'affiche passe par ici, et rien de ce qui passe par ici n'est calculé : `lecture` ouvre des
JSON produits ailleurs — par le moteur pour les décisions, par un **scoreur indépendant** pour
les métriques — et les rend tels quels.

## Trois façons de se tromper en lisant ces artefacts, et trois gardes
1. **L'index positionnel.** `banc_ub6.json` porte 32 cellules où chaque système revient
   quatre fois (2 bras × 2 points). `cellules[1]` désigne aujourd'hui le moteur au point
   retenu ; il désignerait autre chose demain. On adresse donc une cellule par son IDENTITÉ
   — `(systeme, point, bras)` — et `cellule()` refuse une sélection qui ne rend pas
   exactement un résultat.
2. **La clé absente qui vaut `None`.** `metriques["rappel"]` n'existe pas : la clé est
   `rappel_bout_en_bout`. Un `dict.get` aurait rendu `None`, et `None` se serait affiché
   comme un tiret plausible. `valeur()` lève plutôt que de rendre un trou.
3. **La convention cueillie.** Chaque cellule publie QUATRE conventions de zone grise dans
   `toutes_conventions` ; sur le moteur, le F1 va de 0,60 (pessimiste) à 0,93 (optimiste).
   Une seule est publiable — `stricte`, celle de `metriques` et du critère gelé
   `L9_CONVENTION_UNIQUE`. Ce module n'expose JAMAIS `toutes_conventions` : le cueillage le
   plus facile de tout l'artefact est rendu impossible plutôt que déconseillé.

## Non-circularité
Aucun import de `scorer`, aucun import de `engine`. Les surfaces d'affichage n'ont pas besoin
du moteur : elles lisent ce qu'il a décidé. Seul `bac_a_sable` importe `engine`, et c'est sa
raison d'être. Un test vérifie cette frontière par analyse du code source.
"""
from __future__ import annotations

import json
import os

__all__ = [
    "RACINE_ARTEFACTS", "ARTEFACTS", "ArtefactManquant", "LectureImpossible",
    "Artefacts", "charge", "valeur", "cellule",
]

#: Chemin POSIX relatif à la racine du repo (aucun chemin absolu OS-spécifique — le paquet
#: déployé tourne sous Linux).
RACINE_ARTEFACTS = "artifacts"

#: Les artefacts que les surfaces lisent, et rien d'autre. Une surface qui aurait besoin d'un
#: sixième fichier le déclare ici : la liste EST l'inventaire des sources d'affichage.
ARTEFACTS = {
    "banc": "banc_ub6.json",                    # comparaison, scoreur indépendant
    "dims": "dimensions.json",                     # point de fonctionnement
    "contribution": "contribution_llm.json",    # revue de la zone grise
    "demonstration": "ui_demonstration.json",   # sorties moteur figées (tools/produit_artefacts_ui.py)
    "scenarios": "ui_scenarios.json",           # scénarios de démonstration (tools/produit_scenarios.py)
}


class ArtefactManquant(FileNotFoundError):
    """Un artefact attendu est absent. La surface refuse de rendre une page trouée."""


class LectureImpossible(KeyError):
    """Un chemin demandé n'existe pas dans l'artefact, ou ne désigne pas une valeur unique.

    Volontairement bruyant : une valeur d'affichage introuvable est un défaut de câblage, pas
    une donnée manquante. La rendre `None` la ferait afficher comme un tiret crédible.
    """


class Artefacts:
    """Les artefacts chargés, adressables par nom. Immuable en usage : personne n'écrit ici."""

    def __init__(self, contenus: dict, racine: str):
        self._contenus = contenus
        self.racine = racine

    def __getitem__(self, nom: str) -> dict:
        if nom not in self._contenus:
            raise LectureImpossible(
                f"artefact inconnu : {nom!r}. Connus : {sorted(self._contenus)}")
        return self._contenus[nom]

    def __contains__(self, nom: str) -> bool:
        return nom in self._contenus

    def noms(self) -> list:
        return sorted(self._contenus)


def charge(racine: str = ".") -> Artefacts:
    """Ouvre les artefacts déclarés dans `ARTEFACTS`, en lecture seule.

    Lève `ArtefactManquant` dès qu'il en manque un : une surface à moitié câblée afficherait
    des trous là où le mandat exige des chiffres tracés.
    """
    contenus = {}
    for nom, fichier in ARTEFACTS.items():
        chemin = os.path.join(racine, RACINE_ARTEFACTS, fichier)
        if not os.path.exists(chemin):
            raise ArtefactManquant(
                f"artefact absent : {RACINE_ARTEFACTS}/{fichier}. "
                f"S'il s'agit de {ARTEFACTS['demonstration']}, le produire avec "
                f"`python tools/produit_artefacts_ui.py`.")
        with open(chemin, encoding="utf-8") as fh:
            contenus[nom] = json.load(fh)
    return Artefacts(contenus, racine)


def valeur(noeud, chemin: str):
    """Résout un chemin pointé (`cibles.o4.ecart`) et lève si quoi que ce soit manque.

    Les index de liste sont acceptés (`limites.0`), mais ce n'est PAS la façon d'adresser une
    cellule de banc : voir `cellule()`.
    """
    courant = noeud
    parcouru = []
    for segment in chemin.split("."):
        parcouru.append(segment)
        if isinstance(courant, list):
            if not segment.lstrip("-").isdigit():
                raise LectureImpossible(
                    f"chemin {chemin!r} : {'.'.join(parcouru)} indexe une liste avec "
                    f"{segment!r}, qui n'est pas un entier")
            indice = int(segment)
            if not -len(courant) <= indice < len(courant):
                raise LectureImpossible(
                    f"chemin {chemin!r} : index {indice} hors de la liste "
                    f"({len(courant)} elements) a {'.'.join(parcouru)}")
            courant = courant[indice]
            continue
        if not isinstance(courant, dict) or segment not in courant:
            disponibles = sorted(courant)[:12] if isinstance(courant, dict) else type(courant).__name__
            raise LectureImpossible(
                f"chemin {chemin!r} : {'.'.join(parcouru)} introuvable. Disponible : {disponibles}")
        courant = courant[segment]
    return courant


def cellule(banc: dict, systeme: str, point: str, bras: str = "A_univers_appari") -> dict:
    """LA cellule `(systeme, point, bras)` du banc, ou une erreur. Jamais un index positionnel.

    Cherche dans `cellules` puis dans `sensibilites` — une sensibilité est une cellule comme
    une autre, mesurée dans les mêmes conditions, et la cellule Splink de référence de l'écart
    O4 en est une. Les traiter à part obligerait l'appelant à savoir où vit ce qu'il demande.
    """
    trouvees = [c for c in (banc.get("cellules", []) + banc.get("sensibilites", []))
                if c.get("systeme") == systeme and c.get("point") == point
                and (bras is None or c.get("bras") == bras)]
    if len(trouvees) != 1:
        raise LectureImpossible(
            f"selection non unique : systeme={systeme!r} point={point!r} bras={bras!r} "
            f"rend {len(trouvees)} cellule(s). Une cellule s'adresse par son identite, et "
            f"cette identite doit etre unique.")
    return trouvees[0]
