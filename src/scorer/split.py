# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Split calibration / évaluation — au niveau ENTITÉ.

## La règle, et rien de plus
Dès qu'une valeur PUBLIÉE dépend d'un paramètre choisi EN REGARDANT LA VÉRITÉ TERRAIN, ce
paramètre est choisi sur la calibration et la valeur est rapportée sur l'évaluation. Rien
d'autre ne déclenche l'obligation — et l'artefact MOTIVE l'absence de split là où il n'est
pas requis, plutôt que d'appliquer un rituel qui donnerait une fausse impression de rigueur.

**Hors obligation, et pourquoi :** l'estimation EM des `m`/`u` est non supervisée par
construction (le moteur ne voit que des vecteurs de comparaison, et sa normalisation le rend
structurellement incapable de lire une annotation) ; le dimensionnement DIMS de Tμ/Tλ ne lit
que `poids_match` et un budget ; le blocking et les cutoffs sont des placeholders déclarés
a priori et GELÉS en git avant la mesure ; PC, RR, PQ, AUC, AP, KS, OVL et les planchers sont
des fonctionnelles SANS paramètre ajusté, qui ne peuvent pas sur-ajuster sur une population
entière. **Sur le chemin principal, le split n'est donc pas requis**, et les métriques de tête
portent sur les 537 enregistrements et les 271 vraies paires.

**Honnêteté requise :** ce n'est pas « aucun optimisme », c'est « aucune fuite d'étiquettes ».
Il subsiste un optimisme IN-SAMPLE (les `m`/`u` collent à cette population, la bande est calée
sur la population où sa taille est mesurée). Ce régime est transductif mais SANS étiquette, et
il n'est pas traité par un split — délibérément : en exploitation, le moteur ajuste aussi son
EM sur la population qu'il traite, et splitter mesurerait un moteur qui n'est pas celui qu'on
livre. C'est déclaré dans `limites`, pas dissimulé.

## Pourquoi l'ENTITÉ, par élimination
- Par PAIRE : fuite double. Deux paires partageant un enregistrement partagent ses attributs
  et ses corruptions ; pire, la transitivité est active (il existe des entités de taille ≥ 3),
  si bien que (a,b) et (a,c) en calibration avec (b,c) en évaluation revient à évaluer sur une
  paire presque entièrement déterminée par la calibration.
- Par RECORD : coupe les clusters, DÉTRUIT des vraies paires par construction, et frappe
  préférentiellement les grandes entités — le dénominateur du rappel de chaque pli devient une
  propriété du tirage, pas de la donnée. Un split qui détruit la quantité mesurée est pire
  qu'aucun split.
- Par ENTITÉ : le cluster est l'unité d'indépendance naturelle du record linkage. Aucune vraie
  paire à cheval, aucune détruite, le dénominateur se partitionne exactement.

## Anti-seed-shopping
Le sel est SCELLÉ. Tirer plusieurs splits jusqu'à en trouver un « propre » est une fuite
déguisée en rigueur. Il existe UN split ; si le sel changeait un jour, le changement ET les
deux résultats seraient publiés côte à côte.

Frontière de non-circularité : aucun import de `src/engine/`. Stdlib seule (C7).
"""
from __future__ import annotations

import hashlib
from typing import Optional

from .contrat import cle_de_correspondance
from .distribution import seuil_oracle_f1
from .metriques import CONVENTION_DE_TETE, contingence, classe_les_paires, mesures

__all__ = [
    "GRAINE_SPLIT_SCELLEE", "PROPORTION_CALIBRATION", "CALIBRATION", "EVALUATION",
    "graine_entiere", "pli_de_entite", "partitionne_entites", "repartit_paires",
    "trace_split", "diagnostic_seuil_optimal_non_reinjectable",
]

GRAINE_SPLIT_SCELLEE = "U-B5::SCORER::SPLIT::sel-0001"
PROPORTION_CALIBRATION = 0.5
CALIBRATION = "calibration"
EVALUATION = "evaluation"
#: Granularité du tirage. 10000 (et non 100) pour que la proportion reste finement
#: paramétrable sans changer la méthode.
GRANULARITE = 10000
#: En deçà, la demi-largeur de Wilson sur un rappel de pli dépasse ~5 points près de 0,95 :
#: toute mesure supervisée issue de ce pli est étiquetée INDICATIVE — étiquetée, pas supprimée.
MIN_VRAIES_PAR_PLI = 60


def graine_entiere(graine: str) -> int:
    """Entier déterministe dérivé d'une graine textuelle, via SHA-256.

    Et **jamais** via `hash()` : le `hash()` des chaînes est salé par processus, ce qui
    donnerait un split différent d'une exécution à l'autre. C'est la même faute que celle déjà
    évitée dans le moteur, et un test la pinne en lançant deux sous-processus sous des
    `PYTHONHASHSEED` différents.
    """
    return int(hashlib.sha256(graine.encode("utf-8")).hexdigest(), 16)


def pli_de_entite(id_entite: str, graine: str = GRAINE_SPLIT_SCELLEE,
                  proportion: float = PROPORTION_CALIBRATION) -> str:
    """Pli d'une entité — fonction PURE de son identifiant.

    Pure au sens fort : l'affectation d'une entité ne dépend d'aucune autre. Elle est donc
    stable à l'ajout ou au retrait d'entités, ce qu'aucun schéma par index, par rang ou par
    mélange global n'offre — et un test le pinne (split sur E, puis sur E ∪ {nouvelle}, les
    affectations existantes doivent être inchangées).
    """
    tirage = graine_entiere(f"{graine}::{id_entite}") % GRANULARITE
    return CALIBRATION if tirage < proportion * GRANULARITE else EVALUATION


def partitionne_entites(entites: dict, graine: str = GRAINE_SPLIT_SCELLEE,
                        proportion: float = PROPORTION_CALIBRATION) -> dict:
    """`{id_entite: pli}` et `{record_id: pli}`, tous deux déterministes."""
    par_entite = {ent: pli_de_entite(ent, graine, proportion) for ent in sorted(entites)}
    par_record = {}
    for ent, rids in entites.items():
        for rid in rids:
            par_record[rid] = par_entite[ent]
    return {"par_entite": par_entite, "par_record": par_record}


def repartit_paires(paires, pli_par_record: dict) -> dict:
    """Range chaque paire dans son pli ; ÉCARTE et COMPTE les paires à cheval.

    Propriété DÉMONTRABLE, pinnée par un test : toute paire à cheval est FAUSSE, puisque ses
    deux enregistrements appartiennent à des entités distinctes — donc l'exclusion ne détruit
    aucune vraie paire. Elle retire en revanche des NÉGATIFS, ce qui rend la précision
    intra-pli OPTIMISTE et déplace la prévalence de chaque pli : l'effet est déclaré, et les
    chiffres de pli ne sont comparables qu'entre eux.
    """
    plis = {CALIBRATION: [], EVALUATION: []}
    a_cheval = []
    for cle in paires:
        a, b = cle
        pa, pb = pli_par_record.get(a), pli_par_record.get(b)
        if pa is None or pb is None:
            continue
        if pa == pb:
            plis[pa].append(cle)
        else:
            a_cheval.append(cle)
    return {CALIBRATION: sorted(plis[CALIBRATION]), EVALUATION: sorted(plis[EVALUATION]),
            "a_cheval": sorted(a_cheval)}


def trace_split(entites: dict, affectation: dict, vraies, correspondances) -> dict:
    """Ce que le split a RÉELLEMENT produit — proportions atteintes, jamais forcées.

    Forcer un 50/50 exact exigerait un tri global, donc une dépendance de chaque affectation à
    la population entière : la stabilité à l'ajout d'une entité serait perdue. Les proportions
    atteintes sont donc publiées telles quelles.
    """
    par_entite = affectation["par_entite"]
    par_record = affectation["par_record"]
    cles_corr = [cle_de_correspondance(c) for c in correspondances]
    rep_vraies = repartit_paires(sorted(vraies), par_record)
    rep_cand = repartit_paires(cles_corr, par_record)

    detail = {}
    for pli in (CALIBRATION, EVALUATION):
        n_ent = sum(1 for p in par_entite.values() if p == pli)
        n_rec = sum(1 for p in par_record.values() if p == pli)
        n_v, n_c = len(rep_vraies[pli]), len(rep_cand[pli])
        detail[pli] = {
            "n_entites": n_ent, "n_records": n_rec,
            "n_vraies_paires": n_v, "n_paires_candidates": n_c,
            "prevalence_parmi_les_candidats": (n_v / n_c) if n_c else None,
            "puissance_suffisante": n_v >= MIN_VRAIES_PAR_PLI,
            "etiquette": ("mesure exploitable" if n_v >= MIN_VRAIES_PAR_PLI
                          else "INDICATIVE, puissance insuffisante"),
        }
    return {
        "niveau": "entite",
        "methode": ("pli(e) = calibration si sha256(sel::id_entite) mod 10000 < 10000 x "
                    "proportion, sinon evaluation — fonction PURE de l'identifiant"),
        "sel_scelle": GRAINE_SPLIT_SCELLEE,
        "proportion_visee": PROPORTION_CALIBRATION,
        "plis": detail,
        "n_paires_a_cheval_ecartees": len(rep_cand["a_cheval"]),
        "n_vraies_paires_a_cheval": len(rep_vraies["a_cheval"]),
        "effet_declare_exclusion": (
            "toute paire a cheval est FAUSSE (deux entites distinctes) : l'exclusion ne detruit "
            "aucune vraie paire, mais elle retire des NEGATIFS. La precision intra-pli est donc "
            "OPTIMISTE et la prevalence de chaque pli differe de celle du jeu entier : les "
            "chiffres de pli ne sont comparables QU'ENTRE EUX, jamais aux metriques de tete."),
        "anti_seed_shopping": (
            "le sel est SCELLE. Il existe UN split ; si le sel changeait, le changement ET les "
            "deux resultats seraient publies cote a cote."),
        "usage": ("obligatoire pour toute valeur dependant d'un parametre choisi en regardant "
                  "la verite terrain — ici le seul seuil oracle. Le chemin principal n'en "
                  "depend pas."),
        "_repartition": {"vraies": rep_vraies, "candidates": rep_cand},
    }


def diagnostic_seuil_optimal_non_reinjectable(correspondances, vraies, affectation: dict,
                                              f1_evaluation_non_supervise: Optional[float],
                                              n_vraies_total: Optional[int] = None) -> dict:
    """Calibre un seuil unique T* sur CALIBRATION, le rapporte sur ÉVALUATION.

    C'est le SEUL chiffre supervisé de l'artefact, et son nom porte l'interdit :
    `non_reinjectable`. Aucune fonction publique de `src/scorer/` ne retourne un objet ayant la
    FORME d'un paramètre du moteur — à cette exception nommée près, de sorte que toute ligne de
    code qui tenterait de la passer au moteur soit visible par un simple `grep`. Un test le
    pinne.

    L'`ecart_calibration_evaluation` est publié MÊME — et surtout — s'il est nul : c'est la
    mesure du sur-ajustement du seuil à son propre jeu.
    """
    par_record = affectation["par_record"]
    par_cle = {cle_de_correspondance(c): c for c in correspondances}
    rep = repartit_paires(sorted(par_cle), par_record)

    def scores(pli):
        v, f = [], []
        for cle in rep[pli]:
            r = par_cle[cle]["poids_match"]
            (v if cle in vraies else f).append(r)
        return v, f

    v_cal, f_cal = scores(CALIBRATION)
    v_eva, f_eva = scores(EVALUATION)
    # Le dénominateur du rappel de chaque pli est le nombre de VRAIES paires de ce pli, y
    # compris celles perdues au blocking : sinon le seuil serait calibré sur un examen dont
    # les questions difficiles ont été retirées.
    vraies_cal = [c for c in vraies if par_record.get(c[0]) == CALIBRATION
                  and par_record.get(c[1]) == CALIBRATION]
    vraies_eva = [c for c in vraies if par_record.get(c[0]) == EVALUATION
                  and par_record.get(c[1]) == EVALUATION]

    if not v_cal or not f_cal or not v_eva or not f_eva:
        return {"t_optimal_calibration": None,
                "motif": "un des deux plis ne contient pas les deux classes",
                "avertissement": "diagnostic NON REINJECTABLE dans le moteur"}

    oracle_cal = seuil_oracle_f1(v_cal, f_cal, len(vraies_cal))
    t_star = oracle_cal["seuil"]

    def f1_a(seuil, v, f, n_total):
        tp = sum(1 for x in v if x > seuil)
        fp = sum(1 for x in f if x > seuil)
        if tp + fp == 0 or not n_total:
            return None
        p, r = tp / (tp + fp), tp / n_total
        return None if p + r == 0 else 2 * p * r / (p + r)

    f1_eval_a_t = f1_a(t_star, v_eva, f_eva, len(vraies_eva))
    f1_cal_a_t = oracle_cal["f1_max"]
    regret = None
    if f1_eval_a_t is not None and f1_evaluation_non_supervise is not None:
        regret = f1_eval_a_t - f1_evaluation_non_supervise
    return {
        "t_optimal_calibration": t_star,
        "f1_calibration_a_t_optimal": f1_cal_a_t,
        "f1_evaluation_a_t_optimal": f1_eval_a_t,
        "f1_evaluation_seuils_non_supervises": f1_evaluation_non_supervise,
        "regret": regret,
        "ecart_calibration_evaluation": (
            None if (f1_cal_a_t is None or f1_eval_a_t is None) else f1_cal_a_t - f1_eval_a_t),
        "n_vraies_calibration": len(vraies_cal), "n_vraies_evaluation": len(vraies_eva),
        "avertissement": (
            "SEUL chiffre supervise de l'artefact. T* est choisi EN LISANT la verite terrain "
            "sur un jeu de calibration DISJOINT, et rapporte sur l'evaluation. Il n'est JAMAIS "
            "passe au moteur : le nom 'non_reinjectable' rend toute tentative visible par grep."),
    }


def f1_par_pli(correspondances, vraies, affectation: dict, pli: str,
               convention: str = CONVENTION_DE_TETE) -> Optional[float]:
    """F1 des seuils NON SUPERVISÉS (ceux du moteur) restreint à un pli.

    Sert de terme de comparaison au seuil oracle : les deux sont mesurés sur le MÊME pli
    d'évaluation, faute de quoi le regret comparerait deux populations différentes.
    """
    par_record = affectation["par_record"]
    corrs = [c for c in correspondances
             if par_record.get(c["record_id_a"]) == pli
             and par_record.get(c["record_id_b"]) == pli]
    vraies_pli = frozenset(c for c in vraies
                           if par_record.get(c[0]) == pli and par_record.get(c[1]) == pli)
    if not corrs or not vraies_pli:
        return None
    classement = classe_les_paires(corrs, vraies_pli)
    cont = contingence(classement, len(vraies_pli))
    return mesures(cont, convention)["f1_bout_en_bout"]
