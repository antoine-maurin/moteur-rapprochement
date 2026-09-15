# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Métriques pairwise — de la contingence à P/R/F1.

Cadre : **pairwise, micro-agrégé** (compteurs poolés). C'est la définition canonique pour une
décision PAR PAIRE, qui est exactement ce que produisent le moteur et la revue. Les métriques
cluster-wise (B-cubed, variation d'information, generalized merge distance) évaluent le
regroupement : elles sont hors périmètre, et ne sont pas approximées ici.

## La contingence à 7 entiers, dont TOUTE métrique est une fonction pure

    mv = |MATCH ∩ M|        mf = |MATCH \\ M|
    gv = |ZONE_GRISE ∩ M|   gf = |ZONE_GRISE \\ M|
    nv = |NON_MATCH ∩ M|    nf = |NON_MATCH \\ M|
    pb = |M \\ C|            (vraies paires PERDUES au blocking, jamais scorées)

Deux invariants, vérifiés sur des ENTIERS et jamais avec une tolérance flottante :
`mv + gv + nv + pb == |M|` et `mv + mf + gv + gf + nv + nf == |C|`. Faire transiter toute
métrique par ces 7 nombres a une conséquence pratique : un test peut écrire une contingence
littérale à la main et pinner chaque métrique en fractions exactes, sans aucune donnée.

## Quatre conventions de zone grise, la principale déclarée AVANT la mesure
La convention de TÊTE est `stricte` : ZONE_GRISE compte comme prédit-négatif. Justification —
`revue_zone_grise.statut == "en_attente"` : le moteur a explicitement REFUSÉ de trancher, et
compter ce refus comme un appariement le créditerait d'une décision qu'il n'a pas prise. Le
choix est posé d'avance, et non après avoir constaté laquelle des quatre flatte le résultat.

`acceptation` et `pessimiste` sont conservées toutes deux et ne se confondent pas : la
première est une POLITIQUE (tout accepter en bloc), la seconde une BORNE (le pire relecteur
concevable). Elles coïncident numériquement tant que la revue ne produit aucune décision
partielle — l'artefact l'énonce plutôt que de les fusionner.

## Le dénominateur du rappel
`rappel_bout_en_bout = TP / |M|` : le dénominateur est `|M|` ENTIER, paires perdues au
blocking comprises. Les exclure reviendrait à noter le moteur sur un examen dont il a
lui-même retiré les questions difficiles — c'est la façon canonique de faire disparaître une
perte de blocking d'un rapport de qualité : le chiffre monte, la perte reste. Le rappel
conditionnel au blocking est publié à côté, étiqueté, jamais en tête.

## Ce que ce module ne fait JAMAIS
Il LIT `verdict` ; il ne le RECALCULE jamais depuis `poids_match` et les seuils. Recalculer
introduirait une seconde décision, divergente au flottant près, et ferait perdre la propriété
qui fonde toute la mesure : le scoreur mesure la SORTIE du moteur, pas une reconstruction.

Frontière de non-circularité : aucun import de `src/engine/`. Stdlib seule (C7).
"""
from __future__ import annotations

import math
from typing import Optional

from .contrat import (CONVENTIONS, MATCH, NON_MATCH, ZONE_GRISE, cle_de_correspondance)

__all__ = [
    "CONVENTION_DE_TETE", "classe_les_paires", "contingence", "verifie_invariants",
    "precision", "rappel", "f1", "intervalle_wilson", "mesures", "mesures_toutes_conventions",
    "metriques_sous_abstention", "decomposition_du_rappel", "attribution_des_faux_negatifs",
]

#: Déclarée AVANT la mesure (cf. docstring du module).
CONVENTION_DE_TETE = "stricte"

#: Plafond d'énumération des cas exhibés. Une troncature est toujours SIGNALÉE : une liste
#: coupée en silence se lit comme une liste complète.
MAX_EXHIBEES = 50


def classe_les_paires(correspondances, vraies) -> dict:
    """Range chaque paire dans une des six cases, et repère les vraies paires non candidates.

    Retourne des listes de clés TRIÉES (déterminisme) plus l'ensemble des perdues au blocking.
    L'appartenance à la zone grise est lue sur `verdict`, JAMAIS reconstruite par comparaison
    de `poids_match` aux seuils : les deux diffèrent, et exactement là où c'est gênant (les
    paires gardées R-20 portent `R = 0.0` et tomberaient dans la bande sans être ZONE_GRISE).
    """
    cases = {(v, c): [] for v in (MATCH, ZONE_GRISE, NON_MATCH) for c in (True, False)}
    candidates = set()
    for corr in correspondances:
        cle = cle_de_correspondance(corr)
        candidates.add(cle)
        cases[(corr["verdict"], cle in vraies)].append(cle)
    perdues = sorted(set(vraies) - candidates)
    return {
        "mv": sorted(cases[(MATCH, True)]), "mf": sorted(cases[(MATCH, False)]),
        "gv": sorted(cases[(ZONE_GRISE, True)]), "gf": sorted(cases[(ZONE_GRISE, False)]),
        "nv": sorted(cases[(NON_MATCH, True)]), "nf": sorted(cases[(NON_MATCH, False)]),
        "perdues_blocking": perdues,
        "n_candidates": len(candidates),
        "vraies_candidates": sorted(set(vraies) & candidates),
    }


def contingence(classement: dict, n_vraies_total: int) -> dict:
    """Les 7 entiers, plus les cardinaux de référence."""
    cont = {cle: len(classement[cle]) for cle in ("mv", "mf", "gv", "gf", "nv", "nf")}
    cont["pb"] = len(classement["perdues_blocking"])
    cont["n_vraies"] = n_vraies_total
    cont["n_candidates"] = classement["n_candidates"]
    cont["n_vraies_candidates"] = len(classement["vraies_candidates"])
    return cont


def verifie_invariants(cont: dict) -> None:
    """Vérifie les deux identités de partition. Lève — une contingence fausse fausse tout."""
    somme_vraies = cont["mv"] + cont["gv"] + cont["nv"] + cont["pb"]
    if somme_vraies != cont["n_vraies"]:
        raise AssertionError(
            f"invariant rompu : mv+gv+nv+pb = {somme_vraies} != |M| = {cont['n_vraies']}")
    somme_candidates = sum(cont[k] for k in ("mv", "mf", "gv", "gf", "nv", "nf"))
    if somme_candidates != cont["n_candidates"]:
        raise AssertionError(
            f"invariant rompu : somme des six cases = {somme_candidates} "
            f"!= |C| = {cont['n_candidates']}")
    for cle in ("mv", "mf", "gv", "gf", "nv", "nf", "pb"):
        if cont[cle] < 0:
            raise AssertionError(f"effectif negatif : {cle} = {cont[cle]}")


def _tp_fp_fn(cont: dict, convention: str) -> tuple:
    """Projection de la zone grise sur une décision binaire, selon la convention.

    `optimiste` et `pessimiste` sont des CONFIGURATIONS ATTEIGNABLES (une résolution que
    quelqu'un pourrait réellement produire), et non une enveloppe de bornes indépendantes :
    prendre le meilleur numérateur ET le meilleur dénominateur sur des résolutions
    DIFFÉRENTES donnerait un F1 supérieur à tout F1 atteignable — une borne qui n'est vraie
    de personne.
    """
    mv, mf, gv, gf, nv, pb = (cont["mv"], cont["mf"], cont["gv"],
                              cont["gf"], cont["nv"], cont["pb"])
    if convention == "stricte":
        return mv, mf, gv + nv + pb
    if convention == "acceptation":
        return mv + gv, mf + gf, nv + pb
    if convention == "optimiste":
        return mv + gv, mf, nv + pb
    if convention == "pessimiste":
        return mv, mf + gf, gv + nv + pb
    raise ValueError(f"convention inconnue : {convention!r}")


def precision(tp: int, fp: int) -> dict:
    """`TP / (TP + FP)`, ou `None` motivé si aucun positif n'est prédit.

    Jamais `0.0` : un zéro se propage silencieusement dans les moyennes et les comparaisons
    de seuils, alors que `None` force le consommateur à traiter le cas. Un moteur qui
    n'apparie rien est un résultat, pas un crash — et « 0/0 » n'est pas « 0 ».

    La précision est INSENSIBLE au choix de l'univers : aucun faux positif ne peut vivre hors
    de l'ensemble candidat. C'est le rappel, et lui seul, que ce choix déplace.
    """
    if tp + fp == 0:
        return {"valeur": None, "motif": "aucun positif predit : 0/0, et non 0.0",
                "denominateur": 0}
    return {"valeur": tp / (tp + fp), "motif": None, "denominateur": tp + fp}


def rappel(tp: int, denominateur: int, libelle: str) -> dict:
    """`TP / denominateur`, ou `None` motivé si le dénominateur est nul."""
    if denominateur == 0:
        return {"valeur": None, "motif": f"denominateur nul ({libelle})", "denominateur": 0}
    return {"valeur": tp / denominateur, "motif": None, "denominateur": denominateur,
            "libelle_denominateur": libelle}


def f1(p: dict, r: dict) -> dict:
    """Moyenne harmonique, ou `None` motivé si l'une des deux est indéfinie ou si `P+R == 0`."""
    if p["valeur"] is None or r["valeur"] is None:
        return {"valeur": None, "motif": "precision ou rappel indefini"}
    if p["valeur"] + r["valeur"] == 0:
        return {"valeur": None, "motif": "precision + rappel = 0 : harmonique indefinie"}
    return {"valeur": 2 * p["valeur"] * r["valeur"] / (p["valeur"] + r["valeur"]), "motif": None}


def intervalle_wilson(succes: int, total: int, z: float = 1.96) -> Optional[list]:
    """Intervalle de Wilson à 95 % — l'incertitude d'échantillonnage d'une proportion.

    Retenu plutôt que l'intervalle de Wald : ce dernier dégénère aux proportions extrêmes
    (il produit des bornes hors de [0,1], et un intervalle de largeur nulle à 0 ou 1), or
    c'est précisément là que vivent les rappels mesurés ici. Publier « 0,970 » sans son
    intervalle laisserait croire à une précision de mesure qui n'existe pas : à ce
    dénominateur, la demi-largeur vaut environ 2 points.
    """
    if total <= 0:
        return None
    p = succes / total
    d = 1.0 + z * z / total
    centre = (p + z * z / (2 * total)) / d
    demi = (z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))) / d
    return [max(0.0, centre - demi), min(1.0, centre + demi)]


def mesures(cont: dict, convention: str) -> dict:
    """Toutes les métriques d'une convention, avec leurs dénominateurs explicites."""
    tp, fp, fn = _tp_fp_fn(cont, convention)
    p = precision(tp, fp)
    r_bout = rappel(tp, cont["n_vraies"], "|M| (toutes les vraies paires, perdues comprises)")
    r_post = rappel(tp, cont["n_vraies_candidates"],
                    "|M inter C| (vraies paires survivant au blocking)")
    return {
        "convention": convention,
        "tp": tp, "fp": fp, "fn": fn,
        "fn_blocking": cont["pb"],
        "fn_scoring": fn - cont["pb"],
        "tn_candidats": cont["nf"],
        "note_tn": ("effectif descriptif : ce n'est PAS le TN de l'univers. La difference est "
                    "exactement le nombre de paires que le blocking n'a jamais proposees."),
        "precision": p["valeur"], "motif_precision": p["motif"],
        "rappel_bout_en_bout": r_bout["valeur"], "motif_rappel": r_bout["motif"],
        "rappel_post_blocking": r_post["valeur"],
        "f1_bout_en_bout": f1(p, r_bout)["valeur"],
        "motif_f1": f1(p, r_bout)["motif"],
        "f1_post_blocking": f1(p, r_post)["valeur"],
        "denominateurs_explicites": {
            "precision": p["denominateur"],
            "rappel_bout_en_bout": r_bout["denominateur"],
            "rappel_post_blocking": r_post["denominateur"],
        },
        "ic_wilson_95": {
            "precision": intervalle_wilson(tp, tp + fp),
            "rappel_bout_en_bout": intervalle_wilson(tp, cont["n_vraies"]),
            "rappel_post_blocking": intervalle_wilson(tp, cont["n_vraies_candidates"]),
        },
        "etiquette_rappel_post_blocking": (
            "perimetre : decision seule ; ne decrit PAS la chaine ; NON comparable entre "
            "systemes de blocking differents"),
    }


def mesures_toutes_conventions(cont: dict) -> dict:
    """Les quatre projections, calculées et publiées ensemble — aucune n'est choisie après coup."""
    return {c: mesures(cont, c) for c in CONVENTIONS}


def metriques_sous_abstention(cont: dict) -> dict:
    """P/R/F1 sur les seules paires DÉCIDÉES, obligatoirement flanqués de la COUVERTURE.

    Lecture de Chow (1970) : un classifieur muni d'une option de rejet obtient mécaniquement
    de meilleures métriques sur ce qu'il accepte de décider. Sans la couverture affichée, ce
    chiffre est trompeur ; il n'est donc jamais publié seul. Les paires grises sortent du
    numérateur ET du dénominateur — y compris du dénominateur du rappel, dont on retire les
    vraies paires grises.
    """
    tp, fp = cont["mv"], cont["mf"]
    n_decidees = cont["n_candidates"] - cont["gv"] - cont["gf"]
    denom_rappel = cont["n_vraies"] - cont["gv"]
    p = precision(tp, fp)
    r = rappel(tp, denom_rappel, "|M| prive des vraies paires en zone grise")
    return {
        "couverture": (n_decidees / cont["n_candidates"]) if cont["n_candidates"] else None,
        "n_paires_decidees": n_decidees,
        "n_paires_abstenues": cont["gv"] + cont["gf"],
        "precision": p["valeur"], "rappel": r["valeur"], "f1": f1(p, r)["valeur"],
        "avertissement": (
            "metriques calculees sur les seules paires DECIDEES : elles sont mecaniquement "
            "meilleures (Chow 1970) et ne se lisent qu'avec la couverture affichee a cote."),
    }


def decomposition_du_rappel(cont: dict, convention: str = CONVENTION_DE_TETE) -> dict:
    """Factorisation `rappel_bout_en_bout = rappel_blocking x rappel_post_blocking`.

    Publiée comme une LECTURE — elle dit OÙ la perte se produit — et non comme une preuve :
    l'identité est algébriquement triviale par construction, et l'asserter ne démontrerait
    rien. Ce qui est réellement contrôlé ailleurs, c'est que `pb` est calculé depuis `M \\ C`
    indépendamment de la classification des correspondances (cf. `classe_les_paires`).
    """
    m = mesures(cont, convention)
    pc = (cont["n_vraies_candidates"] / cont["n_vraies"]) if cont["n_vraies"] else None
    return {
        "rappel_blocking": pc,
        "rappel_post_blocking": m["rappel_post_blocking"],
        "rappel_bout_en_bout": m["rappel_bout_en_bout"],
        "convention": convention,
        "lecture": ("le rappel bout en bout est le produit du rappel de blocking (ce que la "
                    "chaine peut au mieux atteindre) et du rappel post-blocking (ce que la "
                    "decision en fait)"),
    }


def attribution_des_faux_negatifs(classement: dict, correspondances, categories: dict,
                                  vraies_par_entite: Optional[dict] = None,
                                  max_exhibees: int = MAX_EXHIBEES) -> dict:
    """Ventile les faux négatifs (convention de tête) par CAUSE, somme contrôlée.

    Un rappel sans attribution est un chiffre ; avec attribution, c'est un diagnostic. Les
    quatre causes sont exclusives et exhaustives : perte au blocking, garde R-20 (aucun champ
    informatif), zone grise, ou rejet par seuil.

    Les cas sont EXHIBÉS dans un ordre TOTAL — `(-poids_match, a, b)`, les quasi-succès
    d'abord — de sorte que la liste ne puisse pas être cueillie à la main.
    """
    par_cle = {cle_de_correspondance(c): c for c in correspondances}
    causes = {"perdue_blocking": [], "garde_r20": [], "zone_grise": [], "non_match_par_seuil": []}
    for cle in classement["perdues_blocking"]:
        causes["perdue_blocking"].append(cle)
    for cle in classement["gv"]:
        causes["zone_grise"].append(cle)
    for cle in classement["nv"]:
        corr = par_cle[cle]
        if corr.get("garde_r20_appliquee") or corr.get("n_composantes_informatives") == 0:
            causes["garde_r20"].append(cle)
        else:
            causes["non_match_par_seuil"].append(cle)

    total = sum(len(v) for v in causes.values())
    attendu = len(classement["perdues_blocking"]) + len(classement["gv"]) + len(classement["nv"])
    if total != attendu:
        raise AssertionError(f"attribution incomplete : {total} causes pour {attendu} FN")

    exhibees = []
    scores = []
    for cause, cles in causes.items():
        for cle in cles:
            corr = par_cle.get(cle)
            poids = corr["poids_match"] if corr else None
            scores.append((-(poids if poids is not None else -math.inf), cle[0], cle[1],
                           cause, corr))
    for _, a, b, cause, corr in sorted(scores)[:max_exhibees]:
        entree = {"record_id_a": a, "record_id_b": b, "cause": cause,
                  "categories_a": categories.get(a, []), "categories_b": categories.get(b, [])}
        if corr is not None:
            entree.update({
                "poids_match": corr["poids_match"], "verdict": corr["verdict"],
                "composantes": corr.get("composantes"),
                "poids_par_champ": corr.get("poids_par_champ"),
                "n_composantes_informatives": corr.get("n_composantes_informatives"),
            })
        if vraies_par_entite is not None:
            entree["id_entite_vraie"] = vraies_par_entite.get(a)
        exhibees.append(entree)

    return {
        "causes": {k: len(v) for k, v in causes.items()},
        "somme_controlee": total,
        "n_faux_negatifs": attendu,
        "fn_exhibees": exhibees,
        "enumeration_tronquee": len(scores) > max_exhibees,
        "n_exhibees": len(exhibees),
        "ordre": "(-poids_match, record_id_a, record_id_b) : ordre TOTAL, quasi-succes d'abord",
    }


def profil_des_faux_positifs(classement: dict, correspondances, categories: dict,
                             max_exhibees: int = MAX_EXHIBEES) -> dict:
    """Faux positifs de la convention de tête, exhibés dans le même ordre total."""
    par_cle = {cle_de_correspondance(c): c for c in correspondances}
    scores = sorted((-par_cle[cle]["poids_match"], cle[0], cle[1]) for cle in classement["mf"])
    exhibees = []
    for _, a, b in scores[:max_exhibees]:
        corr = par_cle[(a, b)]
        exhibees.append({
            "record_id_a": a, "record_id_b": b, "poids_match": corr["poids_match"],
            "composantes": corr.get("composantes"),
            "n_composantes_informatives": corr.get("n_composantes_informatives"),
            "categories_a": categories.get(a, []), "categories_b": categories.get(b, []),
        })
    return {"n": len(classement["mf"]), "liste_bornee": exhibees,
            "enumeration_tronquee": len(scores) > max_exhibees,
            "ordre": "(-poids_match, record_id_a, record_id_b)"}
