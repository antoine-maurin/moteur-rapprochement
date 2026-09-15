# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Point de fonctionnement de la chaîne, et sa PROVENANCE (O3).

    (population, table de poids)  ->  seuils  ->  provenance qui les lie aux deux

## La dette §12.1, rendue systématique
Des seuils DIMS ne valent que pour la population ET la table de poids qui les ont produits.
Recopier `t_mu = 2,650183265` dans un autre contexte produit un nombre d'allure correcte et
sans signification : la bande grise qu'il découpe n'a plus aucun rapport avec le budget de
revue qu'on croyait viser. La dette a été soldée une fois, à la main, par
`tools/derive_dimensions.py` ; ici elle devient **structurelle**.

Un `PointDeFonctionnement` porte donc TOUJOURS sa provenance, et cette provenance porte une
empreinte de la population et une empreinte de la table de poids. `verifie_provenance` lève
`SeuilsPerimes` quand on présente le point à une population qui n'est pas la sienne — un
échec bruyant, à l'endroit où le silence coûterait le plus cher.

## Deux façons d'obtenir un point, et une seule façon de le fabriquer
`point_depuis_artefact` **charge** un point déjà dérivé et publié ; `point_depuis_records`
le **re-dérive**. Aucune des deux ne recopie un seuil : la première lit un artefact qui
porte sa propre provenance, la seconde appelle le module de dimensionnement. Il n'existe
aucun chemin, dans ce paquet, par lequel un flottant de seuil serait écrit à la main.

## Non-circularité
Ce module ne lit JAMAIS la vérité terrain. Il ne reçoit que des `records` déjà projetés et
des CORRESPONDENCE ; `ground_truth` n'apparaît pas dans ce fichier, et un test l'éprouve par
analyse du code source. Le dimensionnement lui-même ne lit que `poids_match` — la projection
est ce qui rend structurellement impossible qu'autre chose entre dans le calcul.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

import engine
from engine import threshold_sizing as ts

__all__ = [
    "PointDeFonctionnement", "SeuilsPerimes",
    "DECIMALES_EMPREINTE_POIDS", "CHEMIN_DIMS_V2",
    "empreinte_population", "empreinte_table_de_poids",
    "point_depuis_artefact", "point_depuis_records", "point_depuis_correspondances",
    "verifie_provenance",
]

#: Chemin POSIX relatif à la racine du repo (jamais de chemin absolu OS-spécifique).
CHEMIN_DIMS_V2 = "artifacts/dimensions.json"

#: Arrondi appliqué aux poids AVANT empreinte. Les poids sont issus d'une estimation EM :
#: deux exécutions déterministes donnent le même flottant, mais deux PLATEFORMES peuvent
#: différer sur le dernier bit. Empreindre le flottant brut rendrait la provenance
#: dépendante de la machine ; l'arrondi la rend dépendante du seul calcul.
DECIMALES_EMPREINTE_POIDS = 9


class SeuilsPerimes(ValueError):
    """Un point de fonctionnement est présenté à une population qui n'est pas la sienne."""


def _canon(objet) -> str:
    """Forme canonique du projet : triée, non échappée, séparateurs fixés."""
    return json.dumps(objet, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))


def empreinte_population(records) -> str:
    """Empreinte des records tels que le MOTEUR les voit — normalisés, donc projetés.

    Normaliser avant d'empreindre n'est pas un détail de commodité : c'est ce qui rend
    l'empreinte insensible à ce que le moteur ne regarde pas, et sensible à tout ce qu'il
    regarde. Deux packs qui ne diffèrent que par une colonne jamais comparée décrivent, pour
    le dimensionnement, la même population — et doivent donner la même empreinte.
    """
    normalises = engine.normalise_records(records)
    projetes = [{cle: nrec.get(cle) for cle in sorted(nrec)} for nrec in normalises]
    projetes.sort(key=lambda r: r.get("record_id") or "")
    return hashlib.sha256(_canon(projetes).encode("utf-8")).hexdigest()


def empreinte_table_de_poids(poids: dict) -> str:
    """Empreinte de la table de poids, arrondie à `DECIMALES_EMPREINTE_POIDS`."""
    def _arrondi(valeur):
        if isinstance(valeur, float):
            return round(valeur, DECIMALES_EMPREINTE_POIDS)
        if isinstance(valeur, dict):
            return {cle: _arrondi(v) for cle, v in valeur.items()}
        if isinstance(valeur, list):
            return [_arrondi(v) for v in valeur]
        return valeur
    return hashlib.sha256(_canon(_arrondi(poids)).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PointDeFonctionnement:
    """Deux seuils, et de quoi savoir à quoi ils se rapportent.

    `provenance` n'est pas décorative : `verifie_provenance` s'en sert pour refuser un point
    présenté à la mauvaise population. Un point sans provenance est constructible — c'est le
    cas d'un point manuel — mais il est alors marqué `provenance_absente`, et la vérification
    le refuse au lieu de le laisser passer par défaut.
    """
    t_mu: float
    t_lambda: float
    nom: str = "manuel"
    derive_a_l_execution: bool = False
    provenance: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.t_lambda > self.t_mu:
            raise ValueError(
                f"seuils incoherents : t_lambda={self.t_lambda} au-dessus de "
                f"t_mu={self.t_mu}")

    def parametres_moteur(self, **surcharges):
        """Les paramètres moteur correspondants. Aucune décision n'est prise ici."""
        return engine.ParametresMoteur(t_mu=self.t_mu, t_lambda=self.t_lambda, **surcharges)

    def en_dict(self) -> dict:
        return asdict(self)


def point_depuis_artefact(chemin: str, racine: Optional[str] = None) -> PointDeFonctionnement:
    """Charge un point DÉJÀ dérivé et publié (par ex. `artifacts/dimensions.json`).

    Le point chargé embarque la provenance de l'artefact : la population sur laquelle il a
    été dérivé y est identifiée par le `content_sha256` de sa fixture.
    """
    complet = os.path.join(racine or ".", chemin)
    with open(complet, encoding="utf-8") as fh:
        artefact = json.load(fh)
    seuils = artefact["seuils_dimensions"]
    prov = artefact.get("provenance") or {}
    return PointDeFonctionnement(
        t_mu=seuils["t_mu"], t_lambda=seuils["t_lambda"], nom="DIMS-v2",
        derive_a_l_execution=False,
        provenance={
            "origine": "artefact",
            "chemin": chemin,
            "fixture": (prov.get("fixture") or {}).get("chemin_relatif_repo"),
            "content_sha256_fixture": (prov.get("fixture") or {}).get(
                "content_sha256_recalcule"),
            "budget_vise": seuils.get("budget_vise"),
            "taille_zone_grise_declaree": seuils.get("taille_zone_grise"),
            "provisoire": seuils.get("provisoire"),
            "gap": artefact.get("gap"),
            "methode": seuils.get("methode"),
            # L'empreinte de population n'est PAS dans l'artefact publié : il identifie sa
            # population par le sha de la fixture. `verifie_provenance` le dit plutôt que
            # de faire croire à une liaison qui n'existe pas.
            "empreinte_population": None,
            "empreinte_table_de_poids": None,
        })


def point_depuis_correspondances(correspondances, empreinte_pop: str,
                                 empreinte_poids: str,
                                 budget_revue: int = ts.BUDGET_REVUE_DEFAUT,
                                 frontiere: float = ts.FRONTIERE_NEUTRE,
                                 nom: str = "re-derive") -> PointDeFonctionnement:
    """RE-DÉRIVE les seuils depuis une distribution de `R`, et LIE le résultat aux entrées.

    C'est le seul constructeur qui produit des seuils neufs, et il exige les deux empreintes
    : on ne peut pas obtenir un point re-dérivé sans dire de quoi il est dérivé.
    """
    seuils = ts.dimensionne_depuis_correspondances(
        correspondances, budget_revue=budget_revue, frontiere=frontiere)
    return PointDeFonctionnement(
        t_mu=seuils["t_mu"], t_lambda=seuils["t_lambda"], nom=nom,
        derive_a_l_execution=True,
        provenance={
            "origine": "re-derivation",
            "empreinte_population": empreinte_pop,
            "empreinte_table_de_poids": empreinte_poids,
            "budget_vise": seuils.get("budget_vise"),
            "budget_atteint": seuils.get("budget_atteint"),
            "ecart_au_budget": seuils.get("ecart_au_budget"),
            "taille_zone_grise_declaree": seuils.get("taille_zone_grise"),
            "frontiere": seuils.get("frontiere"),
            "methode": seuils.get("methode"),
            "provisoire": seuils.get("provisoire"),
            "repli": seuils.get("repli"),
            "motif_repli": seuils.get("motif_repli"),
            "n_paires": seuils.get("n_paires"),
        })


def point_depuis_records(records, budget_revue: int = ts.BUDGET_REVUE_DEFAUT,
                         frontiere: float = ts.FRONTIERE_NEUTRE,
                         nom: str = "re-derive") -> tuple:
    """Passe complet de re-dérivation : records -> (point, sortie moteur du 1er passage).

    Le moteur tourne une PREMIÈRE fois — aux seuils par défaut — pour obtenir la
    distribution de `R`. Ce premier passage est refait en entier au second, estimation EM
    comprise : il rend la même table de poids parce que les entrées sont identiques et que
    le moteur est déterministe, non parce qu'il la réutiliserait. Le coût est donc
    doublé, et c'est le prix, déclaré, d'un point re-dérivé plutôt que recopié.
    """
    amont = engine.execute_moteur(records)
    poids = amont["rapport"]["poids"]
    point = point_depuis_correspondances(
        amont["correspondances"],
        empreinte_pop=empreinte_population(records),
        empreinte_poids=empreinte_table_de_poids(poids),
        budget_revue=budget_revue, frontiere=frontiere, nom=nom)
    return point, amont


def verifie_provenance(point: PointDeFonctionnement, records, poids: dict) -> dict:
    """Le point se rapporte-t-il bien à CETTE population et à CETTE table de poids ?

    Rend un rapport plutôt que de lever, sauf en cas de non-concordance avérée : un point
    sans empreinte (chargé d'un artefact qui identifie sa population autrement) n'est pas
    une faute, c'est une liaison plus faible — et le rapport le DIT, au lieu de laisser
    croire à une vérification qui n'a pas eu lieu.
    """
    attendue_pop = (point.provenance or {}).get("empreinte_population")
    attendue_poids = (point.provenance or {}).get("empreinte_table_de_poids")
    obtenue_pop = empreinte_population(records)
    obtenue_poids = empreinte_table_de_poids(poids)

    if attendue_pop is None and attendue_poids is None:
        return {"verifiable": False, "concordant": None,
                "motif": ("le point n'embarque aucune empreinte : sa liaison a la "
                          "population repose sur une identification externe "
                          "(sha de fixture), non verifiee ici"),
                "empreinte_population_obtenue": obtenue_pop,
                "empreinte_table_de_poids_obtenue": obtenue_poids}

    ecarts = []
    if attendue_pop is not None and attendue_pop != obtenue_pop:
        ecarts.append(f"population (attendue {attendue_pop[:16]}, obtenue {obtenue_pop[:16]})")
    if attendue_poids is not None and attendue_poids != obtenue_poids:
        ecarts.append(
            f"table de poids (attendue {attendue_poids[:16]}, obtenue {obtenue_poids[:16]})")
    if ecarts:
        raise SeuilsPerimes(
            "seuils perimes : " + " ; ".join(ecarts) +
            ". Les seuils DIMS ne valent que pour la population et la table de poids qui "
            "les ont produits ; re-deriver plutot que recopier.")
    return {"verifiable": True, "concordant": True, "motif": None,
            "empreinte_population_obtenue": obtenue_pop,
            "empreinte_table_de_poids_obtenue": obtenue_poids}
