# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Zone grise — taille, composition, et IRRÉDUCTIBILITÉ au score seul.

## La taille n'est pas une preuve
Sous des seuils dimensionnés par budget, la TAILLE de la bande est un **paramètre**, pas une
mesure : `threshold_sizing` la choisit précisément pour approcher le budget de revue.
`n_gris ≈ 300` est donc tautologique et ne prouve rien — ni sur la donnée, ni sur le moteur.
L'avertissement est écrit dans l'artefact AVANT le chiffre, pour qu'on ne puisse pas le lire
comme un résultat.

## La question qui compte
« Existe-t-il un doute que le score seul ne tranche pas ? » se mesure par
l'IRRÉDUCTIBILITÉ : deux paires de classes opposées portant la MÊME valeur de `R` sont
indiscernables par TOUTE règle lisant `R`. Si au contraire chaque valeur de `R` dans la bande
est pure, alors un meilleur SEUIL — et non un humain, et non un modèle de langue — résout la
bande : le doute est un artefact de PLACEMENT, et il faut le dire ainsi.

## La source de vérité de l'appartenance
L'appartenance à la zone grise se lit sur `verdict == "ZONE_GRISE"`, **jamais** sur
`t_lambda <= poids_match <= t_mu`. Les deux diffèrent, et exactement là où c'est gênant : la
garde R-20 force NON_MATCH pour une paire sans aucun champ informatif, dont l'agrégat vaut
`0.0` — soit précisément la frontière autour de laquelle la bande est emboîtée. Reconstruire
les verdicts par comparaison de seuils verserait toutes ces paires dans la zone grise et
fausserait sa composition. Le contrôle de réconciliation ci-dessous est le SEUL endroit du
scoreur où `R` est comparé aux seuils, et c'est un contrôle, pas une mesure.

## Les bornes du doute sont des configurations ATTEIGNABLES
`optimiste` et `pessimiste` décrivent deux résolutions qu'un relecteur pourrait réellement
produire. Prendre le meilleur numérateur et le meilleur dénominateur sur des résolutions
DIFFÉRENTES donnerait un F1 supérieur à tout F1 atteignable — une borne qui n'est vraie de
personne. Les bornes sont calculées par SUBSTITUTION sur la sortie existante, jamais par
ré-exécution du moteur avec d'autres seuils : re-seuiller pour voir « ce que ça donnerait »
est exactement la fuite par relecture du résultat.

Frontière de non-circularité : aucun import de `src/engine/`. Stdlib seule (C7).
"""
from __future__ import annotations

import math
from typing import Optional

from . import distribution as dist
from .contrat import ZONE_GRISE, cle_de_correspondance
from .metriques import _tp_fp_fn, f1, precision, rappel

__all__ = ["MIN_VRAIES_ZG_EVALUABLE", "part_minoritaire", "composition", "irreductibilite",
           "reconciliation_de_bande", "bornes_du_doute", "analyse_zone_grise"]


def part_minoritaire(n_vraies_gris: int, n_fausses_gris: int):
    """Part de la classe la MOINS représentée dans la bande.

    Extraite en fonction nommée parce qu'elle est load-bearing : c'est elle que lit le
    critère gelé Z2, donc l'un des quatre conjoints de l'axe « le doute est exercé ».
    L'analyse de sensibilité du rapport en a besoin sur des effectifs PERTURBÉS ; lui faire
    recopier la formule laisserait deux définitions diverger sans qu'aucun oracle ne le voie.
    """
    total = n_vraies_gris + n_fausses_gris
    return (min(n_vraies_gris, n_fausses_gris) / total) if total else None

#: Sous ce seuil, l'AUC interne à la bande n'est pas rendue : l'erreur d'échantillonnage
#: domine, et publier un nombre ferait passer du bruit pour une mesure.
MIN_VRAIES_ZG_EVALUABLE = 5


def _paires_grises(correspondances, vraies):
    """Les paires en ZONE_GRISE, séparées par classe. Lues sur le VERDICT (cf. docstring)."""
    gv, gf = [], []
    for corr in correspondances:
        if corr["verdict"] != ZONE_GRISE:
            continue
        cle = cle_de_correspondance(corr)
        (gv if cle in vraies else gf).append(corr)
    return gv, gf


def composition(correspondances, vraies, n_vraies_total: int,
                n_candidates: Optional[int] = None) -> dict:
    """Effectifs, pureté, entropie, et ce que la bande met en jeu.

    `entropie_bits` vaut 0 sur une bande pure et 1 sur une bande maximalement mixte : c'est
    une lecture de la mixité qui ne dépend pas de laquelle des deux classes est minoritaire.
    """
    gv, gf = _paires_grises(correspondances, vraies)
    n_gris = len(gv) + len(gf)
    total = n_candidates if n_candidates is not None else len(list(correspondances))
    p = (len(gv) / n_gris) if n_gris else None
    entropie = None
    if p is not None and 0.0 < p < 1.0:
        entropie = -p * math.log2(p) - (1 - p) * math.log2(1 - p)
    elif p is not None:
        entropie = 0.0
    return {
        "n_gris": n_gris,
        "part_gris": (n_gris / total) if total else None,
        "n_vraies_gris": len(gv), "n_fausses_gris": len(gf),
        "purete": p,
        "motif_purete": None if n_gris else "bande vide : purete indefinie",
        "part_minoritaire": part_minoritaire(len(gv), len(gf)),
        "entropie_bits": entropie,
        "rappel_en_jeu": (len(gv) / n_vraies_total) if n_vraies_total else None,
        "note_avertissement_taille": (
            "Sous des seuils dimensionnes par budget, la TAILLE de la zone grise est un "
            "PARAMETRE, pas une mesure : n_gris proche du budget ne prouve rien sur la donnee "
            "ni sur le moteur. La taille n'est JAMAIS lue comme une preuve de doute."),
    }


def irreductibilite(correspondances, vraies) -> dict:
    """Le doute de la bande est-il irréductible à toute règle lisant `R` ?

    Trois quantités : le nombre de VALEURS de `R` où les deux classes coexistent, la part des
    paires de la bande assises sur une telle valeur, et le plancher de Bayes restreint à la
    bande. Si la part est faible et le plancher proche de zéro, la bande est résoluble par un
    meilleur seuil, non par une instruction du doute.
    """
    gv, gf = _paires_grises(correspondances, vraies)
    r_v = [c["poids_match"] for c in gv]
    r_f = [c["poids_match"] for c in gf]
    plancher = dist.plancher_bayes_sur_r(r_v, r_f)
    auc = dist.auc_mann_whitney(r_v, r_f)
    evaluable = len(gv) >= MIN_VRAIES_ZG_EVALUABLE and len(gf) > 0
    return {
        "valeurs_r_mixtes": plancher["n_valeurs_mixtes"],
        "part_paires_mixtes": plancher["part_paires_mixtes"],
        "plancher_bayes_bande": plancher["plancher_bayes"],
        "n_valeurs_distinctes_dans_la_bande": plancher["n_valeurs_distinctes"],
        "auc_dans_la_zone_grise": auc["valeur"] if evaluable else None,
        "motif_auc_zone_grise": None if evaluable else (
            f"moins de {MIN_VRAIES_ZG_EVALUABLE} vraies paires dans la bande "
            f"({len(gv)}), ou aucune fausse ({len(gf)})"),
        "distribution_r_interne_par_classe": {
            "vraies": dist.statistiques(r_v), "fausses": dist.statistiques(r_f),
        },
        "lecture": (
            "deux paires de classes opposees portant la MEME valeur de R sont indiscernables "
            "par TOUTE regle lisant R. Si la part de paires mixtes est faible et le plancher "
            "proche de 0, le doute est un artefact de PLACEMENT des seuils, non un doute reel."),
    }


def profil_des_composantes(correspondances, vraies) -> dict:
    """Le doute vient-il d'un CONFLIT de preuves ou d'une ABSENCE de preuves ?

    Deux doutes de nature différente, que le seul `R` confond : une paire dont tous les champs
    manquent et une paire dont les champs se contredisent peuvent recevoir le même agrégat.
    Le profil des composantes les distingue — information dont une revue a besoin, et que la
    taille de la bande ne porte pas.
    """
    gv, gf = _paires_grises(correspondances, vraies)
    dedans = gv + gf
    dehors = [c for c in correspondances if c["verdict"] != ZONE_GRISE]

    def resume(corrs):
        if not corrs:
            return {"n": 0}
        informatives = sorted(c.get("n_composantes_informatives", 0) for c in corrs)
        n_manquants = 0
        n_composantes = 0
        profils = {}
        for c in corrs:
            comps = c.get("composantes") or {}
            for niveau in comps.values():
                n_composantes += 1
                if niveau == "INDETERMINE_MANQUANT":
                    n_manquants += 1
            profil = ",".join(sorted("%s=%s" % (k.replace("accord_", ""), v)
                                     for k, v in comps.items()))
            profils[profil] = profils.get(profil, 0) + 1
        frequents = sorted(profils.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        return {
            "n": len(corrs),
            "n_composantes_informatives_median": informatives[len(informatives) // 2],
            "taux_indetermine_manquant": (n_manquants / n_composantes) if n_composantes else None,
            "profils_d_accord_les_plus_frequents": [{"profil": p, "n": n} for p, n in frequents],
        }

    return {"dans_la_bande": resume(dedans), "hors_bande": resume(dehors),
            "lecture": ("un taux eleve d'INDETERMINE_MANQUANT dans la bande signale un doute "
                        "par ABSENCE de preuve ; un taux faible, un doute par CONFLIT")}


def reconciliation_de_bande(correspondances, t_mu: float, t_lambda: float) -> dict:
    """Contrôle — SEUL endroit du scoreur où `R` est comparé aux seuils.

    Identité attendue :
      `|{ Tλ ≤ R ≤ Tμ }| == |ZONE_GRISE| + |{ garde R-20 ∧ Tλ ≤ R ≤ Tμ }|`
    Une violation signale une incohérence entre le dimensionnement et la décision, et lève une
    alerte de plomberie. `budget_consomme_par_garde_r20` chiffre ce que la bande happe sans
    que cela n'atteigne jamais une revue : du budget dimensionné, mais pas du doute.
    """
    dans_bande = 0
    gardees_dans_bande = 0
    n_zone_grise = 0
    n_gardees = 0
    for corr in correspondances:
        r = corr["poids_match"]
        gardee = bool(corr.get("garde_r20_appliquee"))
        if gardee:
            n_gardees += 1
        if corr["verdict"] == ZONE_GRISE:
            n_zone_grise += 1
        if t_lambda <= r <= t_mu:
            dans_bande += 1
            if gardee:
                gardees_dans_bande += 1
    attendu = n_zone_grise + gardees_dans_bande
    return {
        "n_dans_la_bande_par_seuils": dans_bande,
        "n_zone_grise_par_verdict": n_zone_grise,
        "n_paires_garde_r20": n_gardees,
        "n_gardees_dans_la_bande": gardees_dans_bande,
        "budget_consomme_par_garde_r20": gardees_dans_bande,
        "ecart_bande_vs_verdict": dans_bande - attendu,
        "coherent": dans_bande == attendu,
        "note": ("du budget de revue dimensionne, les paires gardees R-20 tombant dans la "
                 "bande sont consommees sans jamais atteindre U-B3 : elles n'ont rien a "
                 "instruire, faute de la moindre composante informative"),
    }


def bornes_du_doute(cont: dict) -> dict:
    """Encadrement des métriques par les deux résolutions extrêmes ATTEIGNABLES de la bande.

    `largeur_intervalle_f1` est la valeur maximale d'une revue PARFAITE : le plafond de ce que
    la revue de zone grise peut apporter sur ce jeu, mesuré avant qu'elle n'ait rien produit. C'est
    aussi, symétriquement, ce qu'un relecteur parfaitement mauvais pourrait détruire.
    """
    sortie = {}
    for nom in ("pessimiste", "optimiste"):
        tp, fp, fn = _tp_fp_fn(cont, nom)
        p = precision(tp, fp)
        r = rappel(tp, cont["n_vraies"], "|M|")
        sortie[nom] = {"precision": p["valeur"], "rappel": r["valeur"],
                       "f1": f1(p, r)["valeur"], "tp": tp, "fp": fp, "fn": fn}
    largeur_f1 = None
    if sortie["optimiste"]["f1"] is not None and sortie["pessimiste"]["f1"] is not None:
        largeur_f1 = sortie["optimiste"]["f1"] - sortie["pessimiste"]["f1"]
    largeur_r = None
    if sortie["optimiste"]["rappel"] is not None and sortie["pessimiste"]["rappel"] is not None:
        largeur_r = sortie["optimiste"]["rappel"] - sortie["pessimiste"]["rappel"]
    largeur_p = None
    if sortie["optimiste"]["precision"] is not None and sortie["pessimiste"]["precision"] is not None:
        largeur_p = sortie["optimiste"]["precision"] - sortie["pessimiste"]["precision"]
    # --- Ce qu'une revue parfaite APPORTE, distinct de l'amplitude entre les deux extrêmes.
    # Les deux se confondent aisément et diffèrent ici d'un facteur ~27 : l'amplitude compare
    # le meilleur relecteur au PIRE, tandis que le gain compare le meilleur relecteur à
    # L'ABSENCE de revue (la convention de tête, où la bande reste non tranchée). C'est le
    # gain, et non l'amplitude, qui répond à « la revue a-t-elle matière à instruire ».
    tp_t, fp_t, _ = _tp_fp_fn(cont, "stricte")
    p_t = precision(tp_t, fp_t)
    r_t = rappel(tp_t, cont["n_vraies"], "|M|")
    f1_tete = f1(p_t, r_t)["valeur"]
    gain_f1 = (None if (f1_tete is None or sortie["optimiste"]["f1"] is None)
               else sortie["optimiste"]["f1"] - f1_tete)
    gain_rappel = (None if (r_t["valeur"] is None or sortie["optimiste"]["rappel"] is None)
                   else sortie["optimiste"]["rappel"] - r_t["valeur"])
    sortie.update({
        "f1_convention_de_tete": f1_tete,
        "gain_d_une_revue_parfaite_f1": gain_f1,
        "gain_d_une_revue_parfaite_rappel": gain_rappel,
        "note_gain_vs_amplitude": (
            "DEUX grandeurs distinctes, a ne pas confondre. `gain_d_une_revue_parfaite_f1` = "
            "F1(optimiste) - F1(convention de tete) : ce qu'une revue PARFAITE ajoute a "
            "l'absence de revue. `largeur_intervalle_f1` = F1(optimiste) - F1(pessimiste) : "
            "l'AMPLITUDE entre le meilleur et le pire relecteur concevable. La seconde est "
            "necessairement plus grande, et c'est elle que lit le critere gele B4 — voir la "
            "reserve inscrite dans `limites` : le critere compare une amplitude a un seuil que "
            "son enonce decrit comme un gain. Le critere n'est PAS reecrit ; l'ecart est "
            "publie, et le gain l'est a cote pour que le lecteur tranche lui-meme."),
        "largeur_intervalle_f1": largeur_f1,
        "largeur_intervalle_rappel": largeur_r,
        "largeur_intervalle_precision": largeur_p,
        "lecture": (
            "bornes construites comme deux resolutions ATTEIGNABLES de la bande (toutes les "
            "vraies grises resolues en MATCH et les fausses rejetees, ou l'inverse), et non "
            "comme une enveloppe de bornes independantes : un tel maximum ne serait vrai de "
            "personne. largeur_intervalle_f1 est le PLAFOND de ce qu'une revue parfaite "
            "apporterait sur ce jeu."),
        "part_de_la_precision_en_jeu": (
            cont["gf"] / (cont["mv"] + cont["mf"] + cont["gf"])
            if (cont["mv"] + cont["mf"] + cont["gf"]) else None),
    })
    return sortie


def analyse_zone_grise(correspondances, vraies, cont: dict, t_mu: float, t_lambda: float,
                       budget_vise: Optional[int] = None) -> dict:
    """Analyse complète de la bande, pour un régime de seuils donné."""
    comp = composition(correspondances, vraies, cont["n_vraies"], cont["n_candidates"])
    comp["budget_vise"] = budget_vise
    return {
        "composition": comp,
        "irreductibilite": irreductibilite(correspondances, vraies),
        "profil_des_composantes": profil_des_composantes(correspondances, vraies),
        "reconciliation_de_bande": reconciliation_de_bande(correspondances, t_mu, t_lambda),
        "bornes_du_doute": bornes_du_doute(cont),
    }
