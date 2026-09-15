# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Rappel de blocking — le plafond, et sa portée exacte.

    `rappel_blocking` (pair completeness, Christen 2012 §4.7) = |M ∩ C| / |M|

## Ce qu'il plafonne
`rappel_bout_en_bout = rappel_blocking × rappel_post_blocking`, et le second facteur est ≤ 1 :
donc `rappel_bout_en_bout ≤ rappel_blocking`, **quels que soient** Tμ, Tλ, la table de poids,
l'estimation EM, et quelle que soit la revue de zone grise. Une paire jamais proposée ne
peut être ni appariée, ni renvoyée en revue. C'est un plafond DUR, ANTÉRIEUR au scoring :
`(1 − PC) × |M|` est le nombre de vraies paires que le moteur ne peut pas trouver,
indépendamment de sa qualité de décision.

## Portée — la précision qui évite une sur-affirmation
Ce plafond porte sur la DÉCISION PAR PAIRE (moteur + revue). Il ne porte pas nécessairement sur
le rappel d'un regroupement transitif ultérieur : si (a,b) est perdue mais que (a,c) et (c,b)
sont appariées, un clustering replacera a et b dans la même composante. Le scoreur de
paires ne mesure pas cette récupération, et ne prétend pas le contraire.

## Trois mesures, jamais une seule
`PC` seul est trivialement maximisable en ne bloquant pas du tout. Le contrat complet d'un
blocking est le triplet `(PC, RR, PQ)` : complétude, réduction de l'espace, densité de vraies
paires parmi les candidats. Publier l'un sans les autres serait partial.

## Avertissement de fuite, pré-enregistré
La ventilation des pertes est une information de VÉRITÉ TERRAIN sur les faiblesses du
blocking. Régler les passes ou la longueur de préfixe après l'avoir lue transformerait un
blocking non calibré en un blocking calibré sur l'évaluation. Les paramètres de blocking sont
GELÉS avant la mesure, et le SHA du commit de `src/engine/` est inscrit dans l'artefact :
toute modification postérieure exige une nouvelle exécution publiée comme artefact
ADDITIONNEL, jamais en remplacement.

Frontière de non-circularité : aucun import de `src/engine/`. Stdlib seule (C7).
"""
from __future__ import annotations

from typing import Optional

from .contrat import cle_de_correspondance

__all__ = [
    "MAX_PAIRES_ENUMEREES", "n_paires_possibles", "taux_de_reduction", "pairs_quality",
    "rappel_blocking", "contribution_par_passe", "ventile_pertes", "analyse_blocking",
]

#: Plafond d'énumération des paires perdues. Toute saturation est SIGNALÉE.
MAX_PAIRES_ENUMEREES = 500


def n_paires_possibles(n_records: int) -> int:
    """`C(N, 2)` — la taille de l'univers quadratique, avant tout blocking."""
    return n_records * (n_records - 1) // 2


def taux_de_reduction(n_candidates: int, n_records: int) -> Optional[float]:
    """`RR = 1 - |C| / C(N,2)` : la part de l'espace quadratique évitée."""
    total = n_paires_possibles(n_records)
    return None if total == 0 else 1.0 - (n_candidates / total)


def pairs_quality(n_vraies_candidates: int, n_candidates: int) -> Optional[float]:
    """`PQ = |M ∩ C| / |C|` : densité de vraies paires parmi les candidats.

    C'est aussi la PRÉCISION du classifieur trivial « tout candidat est un MATCH » : le
    plancher contre lequel la précision du moteur doit être lue.
    """
    return None if n_candidates == 0 else n_vraies_candidates / n_candidates


def rappel_blocking(candidates, vraies) -> dict:
    """`PC = |M ∩ C| / |M|`, avec la liste des perdues."""
    ens_candidates = set(candidates)
    survivantes = sorted(set(vraies) & ens_candidates)
    perdues = sorted(set(vraies) - ens_candidates)
    n_vraies = len(vraies)
    return {
        "pair_completeness": (len(survivantes) / n_vraies) if n_vraies else None,
        "n_vraies": n_vraies,
        "n_vraies_survivantes": len(survivantes),
        "n_vraies_perdues": len(perdues),
        "perdues": perdues,
        "plafond_de_rappel": (len(survivantes) / n_vraies) if n_vraies else None,
        "portee_du_plafond": (
            "decision par paire (U-B2/U-B3) ; une partie des paires perdues peut etre "
            "recuperee par transitivite en U-B4, ce que cette mesure ne couvre pas"),
    }


def contribution_par_passe(correspondances, vraies) -> dict:
    """Ventile la complétude par passe de blocking, SANS réexécuter le moteur.

    `bloc_origine` porte les étiquettes `"<passe>:<clé>"` de toutes les passes ayant produit
    la paire : la ventilation se lit donc par filtrage de la sortie existante. Ré-exécuter le
    blocking pour l'obtenir changerait l'estimation EM et ferait mesurer un autre moteur.

    La marginale — `PC(union) − PC(union privée de p)` — est la bonne lecture : une passe dont
    la marginale est nulle est intégralement redondante sur ce jeu, quelle que soit sa
    complétude isolée.
    """
    par_passe = {}
    vraies_par_passe = {}
    for corr in correspondances:
        cle = cle_de_correspondance(corr)
        est_vraie = cle in vraies
        passes = {etq.split(":", 1)[0] for etq in (corr.get("bloc_origine") or [])}
        for passe in passes:
            par_passe.setdefault(passe, set()).add(cle)
            if est_vraie:
                vraies_par_passe.setdefault(passe, set()).add(cle)
    n_vraies = len(vraies)
    toutes = set()
    for cles in vraies_par_passe.values():
        toutes |= cles

    sortie = {}
    for passe in sorted(par_passe):
        seules = vraies_par_passe.get(passe, set())
        sans_elle = set()
        for autre, cles in vraies_par_passe.items():
            if autre != passe:
                sans_elle |= cles
        sortie[passe] = {
            "pc_seule": (len(seules) / n_vraies) if n_vraies else None,
            "pc_marginale": ((len(toutes) - len(sans_elle)) / n_vraies) if n_vraies else None,
            "n_paires_apportees": len(par_passe[passe]),
            "n_vraies_apportees": len(seules),
        }
    # Fragilité : vraies paires qui ne tiennent qu'à UNE passe. Si celle-ci disparaissait,
    # elles seraient perdues — c'est une mesure de robustesse du blocking, pas une consigne.
    compte = {}
    for passe, cles in vraies_par_passe.items():
        for cle in cles:
            compte[cle] = compte.get(cle, 0) + 1
    sortie_globale = {
        "par_passe": sortie,
        "n_vraies_trouvees_par_une_seule_passe": sum(1 for n in compte.values() if n == 1),
        "note_marginale": ("une passe de marginale nulle est integralement redondante SUR CE "
                           "JEU ; ce constat est descriptif et n'emporte aucune consigne"),
    }
    return sortie_globale


def ventile_pertes(perdues, partition: dict, categories: dict,
                   tailles_entites: Optional[dict] = None,
                   max_enumerees: int = MAX_PAIRES_ENUMEREES) -> dict:
    """Type les vraies paires perdues au blocking : par catégorie de corruption, par entité.

    L'énumération est bornée et sa troncature SIGNALÉE — une liste coupée en silence se lit
    comme une liste complète.
    """
    par_categorie, par_taille = {}, {}
    listees = []
    for cle in sorted(perdues)[:max_enumerees]:
        a, b = cle
        cats = sorted(set(categories.get(a, [])) | set(categories.get(b, [])))
        listees.append({
            "record_id_a": a, "record_id_b": b,
            "id_entite_vraie": partition.get(a),
            "categories_a": categories.get(a, []), "categories_b": categories.get(b, []),
        })
    for cle in sorted(perdues):
        a, b = cle
        for cat in sorted(set(categories.get(a, [])) | set(categories.get(b, []))):
            par_categorie[cat] = par_categorie.get(cat, 0) + 1
        if tailles_entites:
            taille = tailles_entites.get(partition.get(a))
            if taille is not None:
                par_taille[str(taille)] = par_taille.get(str(taille), 0) + 1
    return {
        "n_perdues": len(perdues),
        "paires_perdues": listees,
        "enumeration_tronquee": len(perdues) > max_enumerees,
        "ventilation_par_categorie_de_corruption": dict(sorted(par_categorie.items())),
        "ventilation_par_taille_entite": dict(sorted(par_taille.items())),
        "note_ventilation": ("une paire portant plusieurs categories est comptee dans chacune : "
                             "les effectifs ne s'additionnent PAS au nombre de paires"),
    }


def analyse_blocking(correspondances, vraies, n_records: int, partition: dict,
                     categories: dict, tailles_entites: Optional[dict] = None,
                     trace_moteur: Optional[dict] = None,
                     n_perdues_annonce_synth: Optional[int] = None) -> dict:
    """Le contrat complet du blocking : `(PC, RR, PQ)`, pertes typées, ventilation par passe."""
    candidates = {cle_de_correspondance(c) for c in correspondances}
    pc = rappel_blocking(candidates, vraies)
    pertes = ventile_pertes(pc["perdues"], partition, categories, tailles_entites)
    sortie = {
        "n_paires_possibles": n_paires_possibles(n_records),
        "n_paires_candidates": len(candidates),
        "taux_de_reduction": taux_de_reduction(len(candidates), n_records),
        "pairs_quality": pairs_quality(pc["n_vraies_survivantes"], len(candidates)),
        "note_pairs_quality": ("c'est aussi la PRECISION du classifieur trivial 'tout candidat "
                               "est un MATCH' : le plancher contre lequel lire la precision"),
        "rappel_blocking": pc["pair_completeness"],
        "plafond_de_rappel": pc["plafond_de_rappel"],
        "portee_du_plafond": pc["portee_du_plafond"],
        "n_vraies_perdues": pc["n_vraies_perdues"],
        "n_vraies_survivantes": pc["n_vraies_survivantes"],
        "pertes": pertes,
        "par_passe": contribution_par_passe(correspondances, vraies),
        "avertissement_non_reinjectable": (
            "la ventilation des pertes est une information de VERITE TERRAIN sur les "
            "faiblesses du blocking. Regler les passes ou la longueur de prefixe apres l'avoir "
            "lue transformerait un blocking non calibre en blocking calibre sur l'evaluation. "
            "Les parametres sont GELES avant la mesure (SHA de commit inscrit dans l'artefact)."),
    }
    if trace_moteur:
        sortie["coherence_avec_trace_moteur"] = {
            "n_paires_trace": trace_moteur.get("n_paires"),
            "n_paires_observees": len(candidates),
            "ecart": (len(candidates) - trace_moteur["n_paires"]
                      if trace_moteur.get("n_paires") is not None else None),
            "blocs_ecartes": trace_moteur.get("blocs_ecartes"),
            "record_id_dupliques": trace_moteur.get("record_id_dupliques"),
            "passes": trace_moteur.get("passes"),
            "longueur_prefixe": trace_moteur.get("longueur_prefixe"),
            "taille_bloc_max": trace_moteur.get("taille_bloc_max"),
        }
    if n_perdues_annonce_synth is not None:
        sortie["n_perdues_annonce_manifest_synth"] = n_perdues_annonce_synth
        sortie["note_comparabilite"] = (
            "les 7 vraies paires que le manifest declare perdues le sont au blocking DE "
            "SYNTH, qui n'est PAS celui du moteur (CP / SDX_NOM / PREF, prefixe 4). L'ecart "
            "entre les deux nombres est un ECART DE CONFIGURATION, jamais une erreur, et il "
            "ne declenche aucune modification.")
    return sortie
