# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Assemblage de l'artefact de mesure.

Construit `artifacts/discrimination_v1_2.json` à partir de la sortie du moteur et de la
vérité terrain. `construis_rapport` est **PURE** : aucune E/S, aucune horloge. Seule
`ecris_artefact` écrit.

## Pas d'horodatage
Une date casserait la reproductibilité octet à octet : deux exécutions du même code sur la
même fixture doivent produire le même fichier. La provenance est portée par les SHA de commit
et le `content_sha256` de la fixture, pas par l'horloge — même discipline que
`artifacts/thresholds_sized.json`.

## Un seul arrondi
Les valeurs de `R` ne sont jamais ré-arrondies (elles vivent sur la grille du moteur). Toutes
les mesures DÉRIVÉES sont arrondies **une seule fois**, juste avant sérialisation, de sorte
que la valeur publiée soit exactement celle qui a été comparée aux seuils du verdict.

## Règle de forme
Aucune clé ne peut manquer selon la branche empruntée — même discipline que
`threshold_sizing._socle_sortie` : un consommateur ne devrait pas avoir à tester l'existence
de chaque clé avant de la lire, et la première branche oubliée casserait chez lui, pas ici.

Frontière de non-circularité : aucun import de `src/engine/`. Stdlib seule (C7).
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Optional

from . import couverture as cvt
from . import criteres as crt
from . import distribution as dist
from . import metriques as met
from . import split as spl
from . import verite as vrt
from . import zone_grise as zgr
from .contrat import (DECIMALES_MESURE, MATCH, cle_de_correspondance, valide_correspondances)

__all__ = [
    "CHEMIN_ARTEFACT", "SOUS_ARBRES_EMPREINTE", "VERSION_SCHEMA",
    "construis_rapport", "arrondis_mesures", "serialisation_canonique",
    "empreinte_des_mesures", "ecris_artefact",
]

CHEMIN_ARTEFACT = os.path.join("artifacts", "discrimination_v1_2.json")
VERSION_SCHEMA = "scorer/1.0"
#: Sous-arbres couverts par `empreinte_des_mesures`. Le verdict et la provenance en sont
#: EXCLUS : l'empreinte ne doit pas se couvrir elle-même, et elle doit rester stable quand
#: seule la formulation du rapport change.
SOUS_ARBRES_EMPREINTE = ("verite_terrain", "couverture_blocking", "distribution_r",
                         "regimes", "split")

#: Attributs dont un DÉSACCORD est une cause matérielle forte de non-appariement.
ATTRIBUTS_IDENTIFIANTS = ("email", "telephone", "date_naissance")


def _fn_explique(entree: dict) -> bool:
    """Un faux négatif porte-t-il une CAUSE MATÉRIELLE identifiable ?

    Six causes, testées dans l'ordre : perte au blocking, garde R-20, au moins deux
    désaccords, au moins trois champs manquants, un désaccord sur un attribut identifiant, ou
    une corruption annotée sur l'un des deux enregistrements. Un FN inexpliqué n'accuse pas le
    moteur : il fait d'abord soupçonner un défaut de MESURE (dérivation des vraies paires, clé
    de paire, jointure), ce que le critère A3 dit explicitement.
    """
    if entree.get("cause") == "perdue_blocking":
        return True
    if entree.get("cause") == "garde_r20":
        return True
    composantes = entree.get("composantes") or {}
    niveaux = list(composantes.values())
    if niveaux.count("DESACCORD") >= 2:
        return True
    if niveaux.count("INDETERMINE_MANQUANT") >= 3:
        return True
    for attribut in ATTRIBUTS_IDENTIFIANTS:
        if composantes.get("accord_" + attribut) == "DESACCORD":
            return True
    if entree.get("categories_a") or entree.get("categories_b"):
        return True
    return False


def _diagnostic_des_fn(attribution: dict, r_vraies) -> dict:
    """Part de FN expliqués, et part de FN « faciles » (au-dessus de la médiane des vraies).

    L'anti-vacuité de la difficulté est le pendant de l'attribution : si des paires FACILES
    sont manquées, la cause n'est pas la dureté de la donnée mais une anomalie de décision, et
    le critère A4 le signale.
    """
    exhibees = attribution["fn_exhibees"]
    if not exhibees:
        return {"part_fn_expliques": None, "part_fn_au_dessus_de_la_mediane_des_vraies": None,
                "n_fn_examines": 0,
                "motif": "aucun faux negatif exhibe : rien a diagnostiquer"}
    expliques = sum(1 for e in exhibees if _fn_explique(e))
    mediane = None
    if r_vraies:
        mediane = dist.quantile(sorted(float(v) for v in r_vraies), 0.5)
    faciles = 0
    avec_r = [e for e in exhibees if e.get("poids_match") is not None]
    if mediane is not None and avec_r:
        faciles = sum(1 for e in avec_r if e["poids_match"] > mediane)
    return {
        "part_fn_expliques": expliques / len(exhibees),
        "n_fn_expliques": expliques,
        "n_fn_examines": len(exhibees),
        "mediane_r_des_vraies": mediane,
        "part_fn_au_dessus_de_la_mediane_des_vraies": (faciles / len(avec_r)) if avec_r else None,
        "n_fn_au_dessus_de_la_mediane": faciles,
        "note_perimetre": (
            "diagnostic calcule sur les FN EXHIBES (au plus " + str(met.MAX_EXHIBEES) +
            ", ordonnes par -poids_match) et non sur la totalite : l'echantillon est celui des "
            "quasi-succes, donc le plus severe pour le moteur. Le perimetre est declare "
            "plutot que tu, et 'enumeration_tronquee' dit s'il y en avait davantage."),
        "causes_materielles": (
            "perdue au blocking | garde R-20 | >= 2 DESACCORD | >= 3 INDETERMINE_MANQUANT | "
            ">= 1 DESACCORD sur email/telephone/date_naissance | >= 1 categorie de corruption"),
    }


def _profil_des_vraies_paires(vraies, categories: dict, par_cle: dict) -> dict:
    """Anti-dégénérescence : ces vraies paires sont-elles réellement non triviales ?

    Un rappel parfait obtenu sur des doublons quasi exacts ne mesure rien. Deux constats
    indépendants : la part de vraies paires portant au moins une corruption annotée, et
    l'existence d'au moins une vraie paire dont au moins deux composantes ne sont pas en
    ACCORD_FORT.
    """
    n_corrompues = 0
    n_non_triviales = 0
    for cle in vraies:
        a, b = cle
        if categories.get(a) or categories.get(b):
            n_corrompues += 1
        corr = par_cle.get(cle)
        if corr:
            niveaux = list((corr.get("composantes") or {}).values())
            if sum(1 for n in niveaux if n != "ACCORD_FORT") >= 2:
                n_non_triviales += 1
    total = len(vraies)
    return {
        "n_vraies_paires": total,
        "n_vraies_paires_corrompues": n_corrompues,
        "part_vraies_paires_corrompues": (n_corrompues / total) if total else None,
        "n_vraies_paires_non_triviales": n_non_triviales,
        "au_moins_une_vraie_paire_non_triviale": n_non_triviales > 0,
        "note": ("garde anti-degenerescence : un rappel eleve obtenu sur des doublons quasi "
                 "exacts, ou en declarant tout MATCH, ne mesure pas la discrimination"),
    }


def _regime(correspondances, vraies, n_vraies_total: int, seuils: dict,
            categories: dict) -> dict:
    """Toutes les mesures d'un régime de seuils. Forme IDENTIQUE d'un régime à l'autre."""
    classement = met.classe_les_paires(correspondances, vraies)
    cont = met.contingence(classement, n_vraies_total)
    met.verifie_invariants(cont)
    partition_ent = {}
    attribution = met.attribution_des_faux_negatifs(classement, correspondances, categories,
                                                    partition_ent)
    r_vraies = [c["poids_match"] for c in correspondances
                if cle_de_correspondance(c) in vraies]
    n_match = sum(1 for c in correspondances if c["verdict"] == MATCH)
    return {
        "seuils": seuils,
        "contingence": {k: cont[k] for k in ("mv", "mf", "gv", "gf", "nv", "nf", "pb")},
        "invariants_verifies": True,
        "cardinaux": {"n_vraies": cont["n_vraies"], "n_candidates": cont["n_candidates"],
                      "n_vraies_candidates": cont["n_vraies_candidates"],
                      "n_match": n_match,
                      "taux_match": (n_match / cont["n_candidates"]) if cont["n_candidates"] else None},
        "mesures_par_convention": met.mesures_toutes_conventions(cont),
        "convention_de_tete": met.CONVENTION_DE_TETE,
        "abstention": met.metriques_sous_abstention(cont),
        "decomposition_du_rappel": met.decomposition_du_rappel(cont),
        "zone_grise": zgr.analyse_zone_grise(correspondances, vraies, cont,
                                             seuils["t_mu"], seuils["t_lambda"],
                                             seuils.get("budget_vise")),
        "placement_des_seuils": None,     # renseigné par `construis_rapport` (besoin de ks_x)
        "attribution_des_fn": attribution,
        "diagnostic_des_fn": _diagnostic_des_fn(attribution, r_vraies),
        "faux_positifs": met.profil_des_faux_positifs(classement, correspondances, categories),
        "reference_triviale": {
            "precision_du_tout_match": cvt.pairs_quality(cont["n_vraies_candidates"],
                                                         cont["n_candidates"]),
            "note": ("precision qu'obtiendrait un classifieur declarant MATCH tout candidat : "
                     "le plancher contre lequel lire la precision du moteur"),
        },
        "_classement": classement,
        "_contingence_complete": cont,
    }


def _mesures_pour_criteres(regime: dict, separation: dict, decomposition: dict,
                           profil_vraies: dict, integrite: dict,
                           diagnostic_supervise: Optional[dict],
                           f1_eval_non_supervise: Optional[float]) -> dict:
    """Aplatit ce dont les critères gelés ont besoin. Aucune décision n'est prise ici."""
    tete = regime["mesures_par_convention"][met.CONVENTION_DE_TETE]
    zg = regime["zone_grise"]
    cont = regime["_contingence_complete"]
    bornes = zg["bornes_du_doute"]
    return {
        "alerte_plomberie": integrite["alerte"],
        "motif_plomberie": integrite.get("motif"),
        "n_vraies_paires": cont["n_vraies"],
        "n_vraies_paires_candidates": cont["n_vraies_candidates"],
        "n_paires_candidates": cont["n_candidates"],
        "rappel_bout_en_bout": tete["rappel_bout_en_bout"],
        "ic_wilson_rappel": tete["ic_wilson_95"]["rappel_bout_en_bout"],
        "tp": tete["tp"],
        "precision": tete["precision"],
        "f1_bout_en_bout": tete["f1_bout_en_bout"],
        "taux_match": regime["cardinaux"]["taux_match"],
        "rappel_blocking": decomposition["rappel_blocking"],
        "n_perdues_blocking": cont["pb"],
        "n_manquees_decision": cont["gv"] + cont["nv"],
        "part_fn_expliques": regime["diagnostic_des_fn"]["part_fn_expliques"],
        "part_fn_au_dessus_de_la_mediane_des_vraies":
            regime["diagnostic_des_fn"]["part_fn_au_dessus_de_la_mediane_des_vraies"],
        "part_vraies_paires_corrompues": profil_vraies["part_vraies_paires_corrompues"],
        "au_moins_une_vraie_paire_non_triviale":
            profil_vraies["au_moins_une_vraie_paire_non_triviale"],
        "n_gris": zg["composition"]["n_gris"],
        "part_gris": zg["composition"]["part_gris"],
        "n_vraies_gris": zg["composition"]["n_vraies_gris"],
        "n_fausses_gris": zg["composition"]["n_fausses_gris"],
        "part_minoritaire": zg["composition"]["part_minoritaire"],
        "rappel_en_jeu": zg["composition"]["rappel_en_jeu"],
        "part_paires_mixtes": zg["irreductibilite"]["part_paires_mixtes"],
        "plancher_bayes_bande": zg["irreductibilite"]["plancher_bayes_bande"],
        "auc_dans_la_zone_grise": zg["irreductibilite"]["auc_dans_la_zone_grise"],
        "motif_auc_zone_grise": zg["irreductibilite"]["motif_auc_zone_grise"],
        "largeur_intervalle_f1": bornes["largeur_intervalle_f1"],
        # Publie pour la table de proximite : ce que le critere gele B4 DECRIT dans son
        # enonce (le gain d'une revue parfaite), a cote de ce qu'il LIT (l'amplitude).
        "gain_d_une_revue_parfaite_f1": bornes["gain_d_une_revue_parfaite_f1"],
        "gain_d_une_revue_parfaite_rappel": bornes["gain_d_une_revue_parfaite_rappel"],
        "rappel_optimiste": bornes["optimiste"]["rappel"],
        "rappel_pessimiste": bornes["pessimiste"]["rappel"],
        "auc": separation["auc"],
        "ovl": separation["ovl"],
        "ap": separation["ap"],
        "marge_de_separation": separation["marge_de_separation"],
        "plage_commune": separation["plage_commune"],
        "plancher_bayes_r": separation["plancher_bayes_r"],
        "f1_evaluation_non_supervise": f1_eval_non_supervise,
        "f1_evaluation_oracle": (diagnostic_supervise or {}).get("f1_evaluation_a_t_optimal"),
        "motif_regret": (diagnostic_supervise or {}).get("motif"),
    }


#: Marge de PROXIMITÉ : en deçà, un critère est déclaré « au ras de sa borne ». C'est une
#: convention de RAPPORT, et non un critère : elle ne déplace aucune borne et ne change aucune
#: issue. Elle applique la discipline pré-enregistrée — « si une valeur tombe juste à la
#: frontière d'une bande, l'artefact publie la valeur, la bande, et SIGNALE la proximité ».
MARGE_PROXIMITE_RELATIVE = 0.10
MARGE_PROXIMITE_ENTIERE = 2


def _proximite_aux_frontieres(mesures_plates: dict) -> dict:
    """Signale les critères dont la valeur observée frôle son seuil pré-enregistré.

    Un verdict qui tient à un cheveu et un verdict franc se lisent de la même façon dans une
    liste d'issues : cette table est ce qui les distingue. Elle ne modifie rien — elle rend
    visible la fragilité, qui est une propriété de la MESURE et doit être publiée avec elle.
    """
    # Poids d'UNE unité de comptage sur chaque grandeur dérivée d'un effectif entier : c'est
    # la vraie résolution de la mesure. Une part calculée sur 271 vraies paires ne peut pas
    # s'écarter de sa borne de moins de 1/271 sans que ce soit un pas entier — juger sa
    # proximité au seul écart relatif déclarerait « confortable » un écart d'une demi-paire.
    n_vraies = mesures_plates.get("n_vraies_paires") or 0
    n_gris = ((mesures_plates.get("n_vraies_gris") or 0)
              + (mesures_plates.get("n_fausses_gris") or 0))
    unite_vraies = (1.0 / n_vraies) if n_vraies else None
    unite_bande = (1.0 / n_gris) if n_gris else None

    controles = [
        ("A1_RAPPEL", "rappel_bout_en_bout", mesures_plates.get("rappel_bout_en_bout"),
         crt.SEUIL_RAPPEL_EXERCE, "relatif", unite_vraies),
        ("B2_MIXITE", "part_minoritaire", mesures_plates.get("part_minoritaire"),
         crt.MIN_PART_MINORITAIRE, "relatif", unite_bande),
        ("B2_MIXITE", "effectif_minoritaire",
         (None if mesures_plates.get("n_vraies_gris") is None
          else min(mesures_plates["n_vraies_gris"], mesures_plates.get("n_fausses_gris", 0))),
         crt.MIN_EFFECTIF_MINORITAIRE, "entier", None),
        ("B3_IRREDUCTIBILITE", "plancher_bayes_bande", mesures_plates.get("plancher_bayes_bande"),
         crt.MIN_PLANCHER_BAYES_BANDE, "entier", None),
        ("B4_ENJEU", "rappel_en_jeu", mesures_plates.get("rappel_en_jeu"),
         crt.MIN_RAPPEL_EN_JEU, "relatif", unite_vraies),
        ("B4_ENJEU", "largeur_intervalle_f1", mesures_plates.get("largeur_intervalle_f1"),
         crt.MIN_LARGEUR_F1, "relatif", None),
        ("B4_ENJEU", "gain_d_une_revue_parfaite_f1",
         mesures_plates.get("gain_d_une_revue_parfaite_f1"),
         crt.MIN_LARGEUR_F1, "relatif", None),
        ("C1_SEPARATION", "paires_equivalentes_mal_classees",
         (None if mesures_plates.get("auc") is None
          else (1.0 - mesures_plates["auc"]) * (mesures_plates.get("n_vraies_paires") or 0)),
         crt.MAX_EQUIV_MAL_CLASSEES_SEPAREES, "relatif", None),
        ("E1_REGRET", "regret",
         (None if (mesures_plates.get("f1_evaluation_oracle") is None
                   or mesures_plates.get("f1_evaluation_non_supervise") is None)
          else mesures_plates["f1_evaluation_oracle"]
               - mesures_plates["f1_evaluation_non_supervise"]),
         crt.REGRET_MAX, "relatif", None),
    ]
    au_ras, table = [], []
    for code, nom, valeur, seuil, mode, unite in controles:
        if valeur is None or seuil in (None, 0):
            continue
        ecart = valeur - seuil
        if mode == "entier":
            proche = abs(ecart) <= MARGE_PROXIMITE_ENTIERE
            motif = f"a {abs(ecart):.6g} unite(s) de la borne"
        else:
            par_relatif = abs(ecart) <= MARGE_PROXIMITE_RELATIVE * abs(seuil)
            # Second critere, ABSOLU : une grandeur derivee d'un comptage est « au ras » des
            # qu'un seul element la ferait basculer, meme si l'ecart relatif parait large.
            par_unite = unite is not None and abs(ecart) <= unite
            proche = par_relatif or par_unite
            motif = " et ".join(
                [m for m, actif in ((f"ecart <= {MARGE_PROXIMITE_RELATIVE:.0%} du seuil",
                                     par_relatif),
                                    ("moins d'une unite de comptage separe la valeur de la "
                                     "borne", par_unite)) if actif]) or "ecart confortable"
        sens = "borne haute" if seuil > valeur else "borne basse"
        entree = {"code": code, "grandeur": nom, "valeur": valeur, "seuil": seuil,
                  "ecart": ecart, "sens_de_la_borne": sens,
                  "poids_d_une_unite_de_comptage": unite,
                  "au_ras_de_la_borne": proche, "motif": motif}
        table.append(entree)
        if proche:
            au_ras.append(f"{code}.{nom} = {valeur:.6g}, {sens} a {seuil:.6g} ({motif})")
    return {
        "marge_relative": MARGE_PROXIMITE_RELATIVE,
        "marge_entiere": MARGE_PROXIMITE_ENTIERE,
        "table": table,
        "grandeurs_au_ras_de_leur_borne": au_ras,
        "n_au_ras": len(au_ras),
        "note": (
            "convention de RAPPORT, pas un critere : aucune borne n'est deplacee, aucune issue "
            "n'est changee. Elle applique la discipline pre-enregistree — une valeur qui frole "
            "sa borne est publiee AVEC sa proximite, pour qu'un verdict tenant a un cheveu ne "
            "se lise pas comme un verdict franc."),
    }


def _sensibilite_du_verdict_de_bande(mesures_plates: dict) -> dict:
    """De combien de vraies paires le verdict « le doute est exercé » tient-il ?

    On perturbe le nombre de VRAIES paires de la bande à taille de bande CONSTANTE (une paire
    de la bande devient vraie, ou cesse de l'être) et on ré-applique les critères GELÉS, sans
    en modifier un seul. Le plancher de Bayes de la bande est borné par `min(plancher, gv')` :
    il vaut `Σ_valeurs min(n_vraies, n_fausses)`, donc il ne peut jamais dépasser le nombre de
    vraies paires de la bande — la borne est exacte, pas une approximation commode.

    Publier ce nombre est ce qui sépare « le doute est exercé » de « le doute est exercé, et il
    suffirait d'UNE vraie paire de moins pour que ce ne soit plus le cas ».
    """
    gv = mesures_plates.get("n_vraies_gris")
    gf = mesures_plates.get("n_fausses_gris")
    if gv is None or gf is None:
        return {"evaluable": False, "motif": "composition de la bande indisponible"}
    n_gris = gv + gf
    n_vraies = mesures_plates.get("n_vraies_paires") or 0
    plancher = mesures_plates.get("plancher_bayes_bande")
    axes = ("B1_VOLUME", "B2_MIXITE", "B3_IRREDUCTIBILITE", "B4_ENJEU")

    def doute_exerce(delta: int) -> bool:
        gv2, gf2 = gv + delta, gf - delta
        if gv2 < 0 or gf2 < 0 or n_gris == 0:
            return False
        perturbe = dict(mesures_plates)
        perturbe["n_vraies_gris"] = gv2
        perturbe["n_fausses_gris"] = gf2
        # Fonction PARTAGEE avec `composition` : recopier la formule laisserait les deux
        # definitions diverger sans qu'aucun oracle ne le voie.
        perturbe["part_minoritaire"] = zgr.part_minoritaire(gv2, gf2)
        perturbe["rappel_en_jeu"] = (gv2 / n_vraies) if n_vraies else None
        if plancher is not None:
            perturbe["plancher_bayes_bande"] = min(plancher, gv2)
        issues = {c["code"]: c["issue"] for c in crt.evalue_criteres(perturbe)}
        return all(issues.get(a) == "SATISFAIT" for a in axes)

    actuel = doute_exerce(0)
    bascule = None
    for pas in range(1, n_gris + 1):
        for delta in (-pas, pas):
            if doute_exerce(delta) != actuel:
                bascule = delta
                break
        if bascule is not None:
            break
    return {
        "evaluable": True,
        "doute_exerce_observe": actuel,
        "n_vraies_paires_dans_la_bande": gv,
        "delta_minimal_qui_bascule_le_verdict": bascule,
        "lecture": (
            "nombre de vraies paires qu'il faudrait ajouter (+) ou retirer (-) de la bande, a "
            "taille de bande constante, pour que la conjonction Z1..Z4 change d'issue. Un "
            "|delta| de 1 signifie que le verdict de bande tient a UNE seule paire."
            if bascule is not None else
            "aucune perturbation de la composition de la bande ne change l'issue"),
        "methode": ("criteres GELES re-appliques tels quels sur une composition perturbee ; "
                    "plancher de Bayes borne par min(plancher, gv') — borne exacte, puisque "
                    "le plancher est une somme de min(n_vraies, n_fausses) par valeur de R"),
    }


def construis_rapport(pack: dict, regimes: dict, provenance: dict) -> dict:
    """Construit l'artefact complet. Fonction PURE : aucune E/S, aucune horloge.

    `regimes` : `{nom: {"correspondances": [...], "seuils": {...}, "rapport_moteur": {...}}}`,
    au moins `"seuils_placeholder"` et `"seuils_dimensionnes"`. Les deux régimes sont publiés
    côte à côte et aucun n'est désigné comme « le bon » : le sélectionner serait déjà une
    calibration.
    """
    ground_truth = pack["ground_truth"]
    records = pack["records"]
    manifest = pack.get("manifest") or {}
    categories = vrt.categories_par_record(pack.get("corruption_annotation") or [])
    stats_verite = vrt.statistiques_verite(ground_truth)
    vraies = vrt.paires_vraies(ground_truth)
    partition = vrt.partition_entites(ground_truth)
    groupes = vrt.entites(ground_truth)
    tailles = {ent: len(rids) for ent, rids in groupes.items()}
    couverture_ids = vrt.controle_couverture_identifiants(records, ground_truth)

    # --- Régime de référence pour tout ce qui NE dépend PAS des seuils --------------
    nom_ref = "seuils_dimensionnes"
    corr_ref = regimes[nom_ref]["correspondances"]
    trace_blocking = (regimes[nom_ref].get("rapport_moteur") or {}).get("blocking") or {}
    integrite = valide_correspondances(corr_ref, trace_blocking.get("n_paires"))
    if not couverture_ids["bijection"]:
        integrite = dict(integrite)
        integrite["alerte"] = True
        integrite["motif"] = ((integrite.get("motif") or "")
                              + " ; defaut de bijection records/ground_truth").strip(" ;")
    integrite["couverture_identifiants"] = couverture_ids

    par_cle_ref = {cle_de_correspondance(c): c for c in corr_ref}
    profil_vraies = _profil_des_vraies_paires(vraies, categories, par_cle_ref)

    blocking = cvt.analyse_blocking(
        corr_ref, vraies, stats_verite["n_records"], partition, categories, tailles,
        trace_blocking,
        (manifest.get("difficulty_estimate_default_mu") or {}).get("true_pairs_lost_to_blocking"))

    # --- Distribution de R : publiée UNE SEULE FOIS, hors des régimes ---------------
    # R ne dépend pas des seuils ; le republier par régime laisserait croire le contraire.
    r_vraies, r_fausses = [], []
    r_vraies_hg, r_fausses_hg = [], []
    for corr in corr_ref:
        cle = cle_de_correspondance(corr)
        r = corr["poids_match"]
        garde = bool(corr.get("garde_r20_appliquee"))
        if cle in vraies:
            r_vraies.append(r)
            if not garde:
                r_vraies_hg.append(r)
        else:
            r_fausses.append(r)
            if not garde:
                r_fausses_hg.append(r)

    n_vraies_total = stats_verite["n_vraies_paires"]
    sep_principal = dist.separation(r_vraies, r_fausses, n_vraies_total)
    sep_hors_garde = dist.separation(r_vraies_hg, r_fausses_hg, n_vraies_total)
    plancher = dist.plancher_bayes_sur_r(r_vraies, r_fausses)
    sep_principal["plancher_bayes_r"] = plancher["plancher_bayes"]
    sep_hors_garde["plancher_bayes_r"] = dist.plancher_bayes_sur_r(
        r_vraies_hg, r_fausses_hg)["plancher_bayes"]

    sensible_perimetre = None
    if sep_principal["auc"] is not None and sep_hors_garde["auc"] is not None:
        sensible_perimetre = (abs(sep_principal["auc"] - sep_hors_garde["auc"]) > 0.02
                              or abs((sep_principal["ovl"] or 0) - (sep_hors_garde["ovl"] or 0)) > 0.02)

    distribution_r = {
        "note_perimetre": (
            "R n'existe que sur les paires candidates : " + str(len(vraies) - len(r_vraies)) +
            " vraie(s) paire(s) perdue(s) au blocking n'en ont pas. La distribution ne couvre "
            "donc PAS toutes les vraies paires."),
        "par_perimetre": {
            "principal": {
                "definition": "toutes les paires candidates (ce que la decision voit reellement)",
                "vraies": dist.statistiques(r_vraies),
                "fausses": dist.statistiques(r_fausses),
                "total": dist.statistiques(r_vraies + r_fausses),
                "separation": sep_principal,
                "planchers": {
                    "plancher_bayes_r": plancher["plancher_bayes"],
                    "n_valeurs_mixtes": plancher["n_valeurs_mixtes"],
                    "part_paires_mixtes": plancher["part_paires_mixtes"],
                    "plancher_seuil_unique": dist.meilleur_seuil_unique(
                        r_vraies, r_fausses, n_vraies_total),
                    "oracle_f1": dist.seuil_oracle_f1(r_vraies, r_fausses, n_vraies_total),
                },
                "histogramme": {
                    "vraies": dist.histogramme(r_vraies),
                    "fausses": dist.histogramme(r_fausses),
                },
            },
            "hors_garde_r20": {
                "definition": "paires ayant au moins une composante informative",
                "exclus": {
                    "n": len(r_vraies) + len(r_fausses) - len(r_vraies_hg) - len(r_fausses_hg),
                    "vraies": len(r_vraies) - len(r_vraies_hg),
                    "fausses": len(r_fausses) - len(r_fausses_hg),
                },
                "vraies": dist.statistiques(r_vraies_hg),
                "fausses": dist.statistiques(r_fausses_hg),
                "separation": sep_hors_garde,
            },
        },
        "sensible_au_perimetre": sensible_perimetre,
        "note_deux_perimetres": (
            "les paires gardees R-20 portent R = 0.0 comme VALEUR PAR DEFAUT et non comme "
            "score : les inclure plante un pic artificiel exactement a la frontiere. Les DEUX "
            "perimetres sont donc calcules et publies, declares avant mesure, et aucun n'est "
            "choisi apres coup. Les metriques P/R/F1 portent TOUJOURS sur toutes les paires "
            "candidates, gardees comprises."),
    }

    # --- Split (post-hoc sur les artefacts) et diagnostic supervisé -----------------
    affectation = spl.partitionne_entites(groupes)
    trace = spl.trace_split(groupes, affectation, vraies, corr_ref)
    f1_eval_ns = spl.f1_par_pli(corr_ref, vraies, affectation, spl.EVALUATION)
    diagnostic = spl.diagnostic_seuil_optimal_non_reinjectable(
        corr_ref, vraies, affectation, f1_eval_ns, n_vraies_total)
    trace.pop("_repartition", None)

    # --- Les deux régimes -----------------------------------------------------------
    sorties_regimes = {}
    for nom, donnees in sorted(regimes.items()):
        reg = _regime(donnees["correspondances"], vraies, n_vraies_total,
                      donnees["seuils"], categories)
        r_v = [c["poids_match"] for c in donnees["correspondances"]
               if cle_de_correspondance(c) in vraies]
        r_f = [c["poids_match"] for c in donnees["correspondances"]
               if cle_de_correspondance(c) not in vraies]
        reg["placement_des_seuils"] = dist.placement_des_seuils(
            r_v, r_f, donnees["seuils"]["t_mu"], donnees["seuils"]["t_lambda"],
            sep_principal.get("ks_x_non_actionnable"))
        reg.pop("_classement", None)
        sorties_regimes[nom] = reg

    reg_ref = sorties_regimes[nom_ref]
    mesures_plates = _mesures_pour_criteres(
        reg_ref, sep_principal, reg_ref["decomposition_du_rappel"], profil_vraies,
        integrite, diagnostic, f1_eval_ns)
    verdict = crt.lis_verdict(mesures_plates)
    verdict["proximite_aux_frontieres"] = _proximite_aux_frontieres(mesures_plates)
    verdict["sensibilite_du_verdict_de_bande"] = _sensibilite_du_verdict_de_bande(mesures_plates)
    for reg in sorties_regimes.values():
        reg.pop("_contingence_complete", None)

    rapport = {
        "_lisez_moi": _LISEZ_MOI,
        "version_schema": VERSION_SCHEMA,
        "mandat": "DISP-UB5-01",
        "unite": "U-B5",
        "objectif": "O2",
        "statut": verdict["statut"],
        "provenance": dict(provenance, verite_terrain_recomptee={
            "n_vraies_paires": n_vraies_total,
            "controle_manifest": vrt.controle_manifest(stats_verite, manifest),
        }),
        "preenregistrement": {
            "sha256_criteres": crt.sha256_criteres(),
            "commit_de_gel": provenance.get("commit_de_gel_des_criteres"),
            "ordre": "pose avant toute mesure ; committe SEUL et AVANT le code de mesure",
            "criteres_declares": sorted(crt.CRITERES),
            "justifications": crt.JUSTIFICATIONS,
            "socle_de_resolution": crt.SOCLE_DE_RESOLUTION,
        },
        "conventions": _CONVENTIONS,
        "alerte_plomberie": integrite["alerte"],
        "controles_prealables": integrite,
        "verite_terrain": stats_verite,
        "profil_des_vraies_paires": profil_vraies,
        "couverture_blocking": blocking,
        "distribution_r": distribution_r,
        "regimes": sorties_regimes,
        "split": trace,
        "diagnostic_supervise_non_reinjectable": diagnostic,
        "verdict": verdict,
        "limites": _LIMITES,
    }
    rapport = arrondis_mesures(rapport)
    rapport["empreinte_des_mesures"] = empreinte_des_mesures(rapport)
    return rapport


def arrondis_mesures(objet, decimales: int = DECIMALES_MESURE):
    """Arrondit récursivement les flottants — UNE SEULE FOIS, avant sérialisation.

    Les entiers et les booléens sont laissés intacts. Les valeurs de `R` publiées dans les
    listes de cas conservent la grille du moteur (9 décimales) : arrondir à 6 les fusionnerait
    avec leurs voisines et déplacerait les ex aequo, donc le plancher de Bayes.
    """
    if isinstance(objet, bool) or objet is None or isinstance(objet, int):
        return objet
    if isinstance(objet, float):
        return round(objet, decimales)
    if isinstance(objet, dict):
        return {k: (v if k in _CLES_NON_ARRONDIES else arrondis_mesures(v, decimales))
                for k, v in objet.items()}
    if isinstance(objet, (list, tuple)):
        return [arrondis_mesures(v, decimales) for v in objet]
    return objet


#: Clés dont la valeur vit sur la grille de `R` et ne doit PAS être ré-arrondie.
_CLES_NON_ARRONDIES = frozenset({
    "poids_match", "t_mu", "t_lambda", "seuil", "x_non_actionnable",
    "ks_x_non_actionnable", "t_optimal_calibration", "poids_par_champ",
})


def serialisation_canonique(objet) -> str:
    """Forme canonique et stable : clés triées, espacement figé, accents conservés."""
    return json.dumps(objet, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))


def empreinte_des_mesures(rapport: dict) -> str:
    """sha256 de la sérialisation canonique des sous-arbres DÉCLARÉS.

    Non circulaire : l'empreinte ne couvre ni le verdict, ni la provenance, ni elle-même. Un
    test la pinne, si bien que la dérive d'une mesure quelconque fait rougir un test unique et
    nommé, au lieu de se diluer dans une comparaison de fichier entier.
    """
    sous_arbre = {cle: rapport[cle] for cle in SOUS_ARBRES_EMPREINTE if cle in rapport}
    return hashlib.sha256(serialisation_canonique(sous_arbre).encode("utf-8")).hexdigest()


def ecris_artefact(rapport: dict, chemin: str = CHEMIN_ARTEFACT) -> str:
    """Écrit l'artefact en JSON canonique, régénérable à l'identique (aucun horodatage)."""
    dossier = os.path.dirname(chemin)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rapport, fh, sort_keys=True, ensure_ascii=False, indent=2)
        fh.write("\n")
    return chemin


_LISEZ_MOI = (
    "VERIFICATION, JAMAIS TUNING. Cet artefact MESURE si la fixture V1.2 exerce la decision "
    "3 zones du moteur. La donnee n'est JAMAIS ajustee sur ce resultat : aucun chiffre ici ne "
    "constitue une demande de modification de la fixture, et aucune recommandation de ce type "
    "n'y figure. Si le moteur se revele excellent sur cette donnee realiste, C'EST UN RESULTAT "
    "VRAI A PUBLIER, PAS UN DEFAUT A CORRIGER — la branche qui produit cet enonce a ete ecrite "
    "AVANT la mesure. La convention de tete est 'stricte' (ZONE_GRISE compte comme "
    "predit-negatif) : le moteur a explicitement refuse de trancher, et compter ce refus comme "
    "un appariement le crediterait d'une decision qu'il n'a pas prise. Les chiffres etiquetes "
    "ORACLE sont choisis EN LISANT la verite terrain : ce sont des bornes diagnostiques, JAMAIS "
    "des performances du moteur. Tout chiffre est indissociable de son regime de projection "
    "(convention) et de son univers (denominateur) : les deux sont publies a cote de lui."
)

_CONVENTIONS = {
    "definition_des_vraies_paires": (
        "CLOTURE d'equivalence induite par ground_truth.id_entite_vraie, diagonale exclue "
        "(|M| = somme des C(n_e, 2)). PAS la foret de provenance record_id_origine, qui donne "
        "somme des (n_e - 1) et sous-estimerait le denominateur du rappel."),
    "univers": (
        "C(N,2) paires possibles. Le blocking ne filtre PAS par source_id : les paires "
        "INTRA-source sont incluses, donc le regime mesure est la DEDUPLICATION toutes sources "
        "confondues, et non la liaison inter-sources pure. Declare, car les deux ne sont pas "
        "comparables."),
    "conventions_de_zone_grise": (
        "stricte (TETE, ZONE_GRISE = predit-negatif) | acceptation (POLITIQUE : tout accepter) "
        "| optimiste (bande resolue parfaitement) | pessimiste (bande resolue a l'envers). "
        "acceptation et pessimiste coincident numeriquement tant que la revue ne produit aucune "
        "decision partielle, mais ne se confondent pas : l'une est une politique, l'autre une "
        "borne. Bloc separe 'abstention' : paires grises retirees des deux cotes, toujours "
        "flanque de la couverture."),
    "denominateur_du_rappel": (
        "|M| ENTIER, vraies paires perdues au blocking comprises. Les exclure reviendrait a "
        "noter le moteur sur un examen dont il a lui-meme retire les questions difficiles."),
    "methode_de_quantile": "interpolation lineaire entre rangs : position = q x (n - 1)",
    "grille_histogramme": "pas 1.0 bit, bornes [-128, 128], DECLAREE a priori (jamais derivee des donnees)",
    "ex_aequo": "AUC en rangs moyens, calcul exact en Fraction, arrondi final unique",
    "grille_de_r": "R livre a 9 decimales par le moteur ; JAMAIS re-arrondi par le scoreur",
    "arrondi_des_mesures": "mesures derivees arrondies UNE SEULE FOIS a 6 decimales avant serialisation",
    "metriques_non_publiees": (
        "exactitude, specificite, taux de faux positifs, AUC-ROC lue comme mesure "
        "operationnelle. Motif : sous une prevalence de ~0,19 %, l'exactitude vaut ~99,8 % pour "
        "un systeme qui ne predit RIEN, et tout ratio ayant TN au denominateur est ecrase "
        "(Davis & Goadrich 2006). Seul tn_candidats est publie, a titre descriptif."),
    "cadre": "pairwise, micro-agrege. Le cluster-wise (B-cubed, VI, GMD) evalue U-B4 : hors perimetre.",
}

_LIMITES = [
    "DEFAUT DU CRITERE GELE C1, CONSERVE ET PUBLIE (regle de non-revision). C1 lit "
    "`(1 - auc) x |M|` avec |M| = 271, alors que l'AUC divise par le nombre de vraies paires "
    "REELLEMENT SCOREES (|M inter C| = 262 : les paires perdues au blocking n'ont pas de R et "
    "n'entrent dans aucune comparaison). Descendre une vraie paire sous toutes les fausses "
    "coute donc 1/262 d'AUC, et non 1/271 : la conversion que le pre-enregistrement declare "
    "« EXACTE » surestime de 3,4 %. Le critere n'est PAS reecrit apres coup — c'est la regle "
    "que le pre-enregistrement s'impose a lui-meme — et la conversion coherente est publiee a "
    "cote, sous `paires_scorees_equivalentes_mal_classees`. VERIFIE : l'ecart ne change pas la "
    "bande atteinte par C1, les deux valeurs tombant entre les memes bornes (0,5 et 3,0).",
    "DEFAUT DU CRITERE GELE B4, CONSERVE ET PUBLIE (regle de non-revision). B4 compare "
    "`largeur_intervalle_f1` (= F1 optimiste - F1 pessimiste, soit l'AMPLITUDE entre le "
    "meilleur et le PIRE relecteur concevable) au seuil MIN_LARGEUR_F1 = 0,01, alors que son "
    "enonce pre-ecrit decrit un GAIN (« une resolution parfaite de la bande porterait le F1 de "
    "+Y points »), c'est-a-dire F1 optimiste - F1 de la convention de tete. Les deux different "
    "d'un facteur ~27 sur ce jeu. Le critere n'est pas reecrit ; le gain est publie a cote sous "
    "`gain_d_une_revue_parfaite_f1`, et la table de proximite le confronte AUSSI au seuil, de "
    "sorte qu'un lecteur voie ce que B4 aurait donne s'il avait ete pose sur la grandeur que "
    "son enonce nomme.",
    "OPTIMISME IN-SAMPLE, assume et declare : l'EM des m/u et le dimensionnement de la bande "
    "sont non supervises (aucune fuite d'ETIQUETTES possible) mais ajustes sur la population "
    "meme ou ils sont mesures. Regime transductif SANS etiquette. Aucun split ne le corrige, "
    "deliberement : en exploitation le moteur ajuste aussi son EM sur la population qu'il "
    "traite, et splitter mesurerait un moteur qui n'est pas celui qu'on livre. Corollaire : ces "
    "chiffres ne predisent pas la performance sur une population NOUVELLE.",
    "TAUTOLOGIE RESIDUELLE DE LA BANDE : sa taille est dimensionnee sur la population ou elle "
    "est mesuree. L'avertissement ecrit avant le chiffre neutralise la LECTURE, pas le FAIT.",
    "UNE SEULE FIXTURE, UNE SEULE GRAINE EM, UNE SEULE CONFIGURATION DE BLOCKING : aucune "
    "variance inter-fixtures, inter-graines ou inter-configurations n'est estimee. Les "
    "intervalles de Wilson decrivent l'incertitude d'ECHANTILLONNAGE des proportions sur ce "
    "jeu, pas la variabilite qu'induirait un autre tirage.",
    "LE PLAFOND DE BLOCKING N'EST PAS LE PLAFOND DE LA CHAINE : une vraie paire perdue peut "
    "etre recuperee par transitivite en U-B4. Le rappel publie est donc PESSIMISTE du point de "
    "vue du systeme complet, et l'ecart n'est pas mesure ici.",
    "METRIQUES CLUSTER-WISE ABSENTES (B-cubed, variation d'information, generalized merge "
    "distance) : elles relevent de U-B4. Le F1 pairwise pondere un cluster de taille n par "
    "n(n-1)/2 ; il n'est comparable d'un jeu a l'autre qu'accompagne de la distribution des "
    "tailles de cluster, publiee pour cette raison.",
    "DEBIT REEL DE LA REVUE U-B3 NON MESURE : le budget de 300 derive d'un modele de capacite "
    "provisoire. largeur_intervalle_f1 mesure ce qu'une revue PARFAITE apporterait au maximum ; "
    "elle ne dit rien de ce qu'une revue REELLE apportera.",
    "TRANSFERABILITE DE LA PRECISION : elle depend de la prevalence de l'ensemble candidat. Le "
    "meme moteur sur un blocking plus large la verrait chuter sans avoir change. Elle est donc "
    "publiee avec |C|, pairs_quality et la prevalence, mais aucune correction ne la rend "
    "transportable.",
    "INDEPENDANCE CONDITIONNELLE ASSUMEE PAR LE MOTEUR : le modele Fellegi-Sunter suppose les 8 "
    "attributs conditionnellement independants, hypothese certainement violee (code postal et "
    "ville, nom et prefixe de blocking). Le scoreur MESURE la sortie ; il ne teste pas "
    "l'hypothese et ne peut pas dire quelle part du recouvrement residuel lui est imputable.",
    "ARBITRAIRE ASSUME DE PLUSIEURS SEUILS DE LECTURE : ils sont argumentes mais restent des "
    "conventions. Leur vertu n'est pas d'etre justes, c'est d'etre FIXES, publies et "
    "verifiablement anterieurs aux chiffres (commit dedie + sha256).",
    "LE PRE-ENREGISTREMENT PROTEGE DU CHOIX DE CRITERE, PAS DU CHOIX DE MESURE : le catalogue "
    "de mesures publiees a lui-meme ete choisi avant la mesure, mais sans controle externe. Un "
    "tiers avec un autre catalogue obtiendrait des chiffres differents sur les memes donnees ; "
    "c'est le bloc 'conventions' qui limite ce risque.",
    "DIAGNOSTIC DES FAUX NEGATIFS calcule sur l'echantillon EXHIBE (au plus 50, ordonne par "
    "-poids_match), et non sur la totalite. Le perimetre est declare a cote du chiffre.",
    "PUISSANCE DU SPLIT : un cote portant moins de 60 vraies paires donne une demi-largeur de "
    "Wilson superieure a ~5 points pres de 0,95 ; la mesure supervisee est alors etiquetee "
    "INDICATIVE — etiquetee, pas supprimee. L'exclusion des paires a cheval rend de plus la "
    "precision intra-pli OPTIMISTE.",
    "NON-COMPARABILITE AVEC LES CHIFFRES V1.1 : population differente, donc aucun chiffre de "
    "cet artefact ne se compare a une mesure anterieure sur une autre fixture.",
]
