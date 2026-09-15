# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Distribution de `R` et séparation des classes.

Ce module répond à la question qui fait le verdict : **la distribution de `R` des VRAIES
paires se distingue-t-elle de celle des FAUSSES ?** Il ne lit que des valeurs de `R` et une
appartenance de classe ; il ignore tout du moteur qui les a produites.

## Six mesures, six questions distinctes
- `auc`  — *R ordonne-t-il correctement ?* Sans seuil, donc insensible au placement de
  Tμ/Tλ : c'est ce qui sépare « le score est-il informatif » de « les seuils sont-ils bien
  posés », deux questions que P/R/F1 confondent.
- `ap`   — la même chose SOUS la prévalence réelle : contrairement à l'AUC, l'average
  precision dépend du déséquilibre, et c'est elle qui parle du régime opérationnel.
- `ks`   — de combien les deux fonctions de répartition s'écartent, et OÙ.
- `ovl`  — quelle MASSE est commune aux deux distributions. Recalculable à la main sur un
  mini-jeu, ce qu'une AUC n'offre pas.
- `marge_de_separation` — *un seuil unique sépare-t-il parfaitement ?* Question binaire que
  les autres ne tranchent pas directement.
- `planchers` — le nombre d'erreurs qu'AUCUNE règle lisant `R` ne peut éviter.

## Les ex aequo ne sont pas un détail
Des paires au profil d'accord identique reçoivent un poids identique : les ex aequo sont
abondants. L'AUC est donc calculée avec des **rangs moyens**, en arithmétique entière sur
des rangs doublés puis en `Fraction`, avec un arrondi final unique. Leur donner crédit plein
gonflerait mécaniquement la séparation. Et c'est le même fait qui rend le **plancher de
Bayes** décisif : deux paires de classes opposées portant la MÊME valeur de `R` sont
indiscernables par toute règle lisant `R`, fût-elle fournie par un oracle.

## Grille d'histogramme DÉCLARÉE A PRIORI
Bornes et pas sont fixés d'avance, indépendamment des données. Une grille dérivée des min/max
observés rendrait deux exécutions incomparables et l'histogramme impinnable ; pire, choisir
la largeur après avoir vu la forme fait apparaître ou disparaître un creux au choix — fuite
modeste, mais réelle. Freedman-Diaconis et Sturges sont écartés pour la même raison : largeur
différente par classe et par jeu, donc histogrammes non superposables.

Frontière de non-circularité : aucun import de `src/engine/`. `quantile` est RÉIMPLÉMENTÉ ici
(la méthode du moteur est recopiée en toutes lettres ci-dessous) — quinze lignes dupliquées achètent
l'indépendance structurelle. Stdlib seule (C7).
"""
from __future__ import annotations

import math
from fractions import Fraction
from typing import Optional, Sequence

__all__ = [
    "PAS_HISTOGRAMME", "PAS_HISTOGRAMME_FIN", "BORNES_HISTOGRAMME",
    "quantile", "statistiques", "histogramme", "auc_mann_whitney", "average_precision",
    "kolmogorov_smirnov", "recouvrement", "marge_de_separation", "plancher_bayes_sur_r",
    "meilleur_seuil_unique", "seuil_oracle_f1", "placement_des_seuils", "separation",
]

#: 1 bit = un facteur 2 sur le rapport de vraisemblance : l'unité naturelle de
#: Fellegi-Sunter, et celle dans laquelle les placeholders ±8 étaient exprimés.
PAS_HISTOGRAMME = 1.0
#: Pas fin, pour le contrôle de sensibilité au binning : un recouvrement qui dépend du seau
#: n'est pas une propriété de la donnée.
PAS_HISTOGRAMME_FIN = 0.5
BORNES_HISTOGRAMME = (-128.0, 128.0)
TOLERANCE_BINNING = 0.05


def quantile(valeurs_triees: Sequence[float], q: float) -> float:
    """Quantile par interpolation linéaire entre rangs : `position = q x (n - 1)`.

    Méthode DÉCLARÉE et réimplémentée plutôt qu'importée du moteur (frontière de non-circularité).
    C'est exactement la méthode de `engine.threshold_sizing._quantile` ; un test croise les deux
    implémentations sur un vecteur littéral écrit à la main, **sans importer le moteur** —
    contrôle d'accord, et non couplage.
    """
    if not valeurs_triees:
        raise ValueError("quantile d'une population vide")
    if len(valeurs_triees) == 1:
        return float(valeurs_triees[0])
    position = q * (len(valeurs_triees) - 1)
    bas = int(math.floor(position))
    haut = min(bas + 1, len(valeurs_triees) - 1)
    poids = position - bas
    return float(valeurs_triees[bas] * (1.0 - poids) + valeurs_triees[haut] * poids)


def statistiques(valeurs: Sequence[float]) -> dict:
    """Descriptifs d'une population de `R`.

    `q01` et `q99` sont demandés explicitement : c'est la QUEUE BASSE des vraies et la QUEUE
    HAUTE des fausses qui se rencontrent, pas les médianes. Publier médiane et quartiles seuls
    masquerait exactement la zone d'intérêt. L'écart-type est publié avec sa mise en garde —
    il décrit mal une distribution bimodale, et n'est ici qu'un garde-fou grossier.
    """
    triees = sorted(float(v) for v in valeurs)
    if not triees:
        return {"n": 0, "note": "population vide"}
    n = len(triees)
    moyenne = sum(triees) / n
    variance = sum((v - moyenne) ** 2 for v in triees) / n
    return {
        "n": n, "min": triees[0], "max": triees[-1],
        "q01": quantile(triees, 0.01), "q05": quantile(triees, 0.05),
        "q10": quantile(triees, 0.10), "q25": quantile(triees, 0.25),
        "mediane": quantile(triees, 0.50), "q75": quantile(triees, 0.75),
        "q90": quantile(triees, 0.90), "q95": quantile(triees, 0.95),
        "q99": quantile(triees, 0.99),
        "moyenne": moyenne, "ecart_type": math.sqrt(variance),
        "n_valeurs_distinctes": len(set(triees)),
        "note_ecart_type": ("decrit mal une distribution bimodale : garde-fou grossier, pas "
                            "une mesure de separation"),
    }


def histogramme(valeurs: Sequence[float], pas: float = PAS_HISTOGRAMME,
                bornes: tuple = BORNES_HISTOGRAMME) -> dict:
    """Histogramme SPARSE sur la grille déclarée. `n_hors_support` doit valoir 0.

    S'il ne vaut pas 0, c'est SIGNALÉ — jamais étendu en silence : une grille qui s'adapte
    aux données cesse d'être une grille déclarée.
    """
    seaux, hors = {}, 0
    for v in valeurs:
        if not (bornes[0] <= v < bornes[1]):
            hors += 1
            continue
        indice = math.floor((v - bornes[0]) / pas)
        borne_basse = bornes[0] + indice * pas
        cle = "%.6g" % borne_basse
        seaux[cle] = seaux.get(cle, 0) + 1
    return {"pas": pas, "bornes_declarees": list(bornes),
            "seaux": dict(sorted(seaux.items(), key=lambda kv: float(kv[0]))),
            "n_hors_support": hors}


def auc_mann_whitney(vraies: Sequence[float], fausses: Sequence[float]) -> dict:
    """AUC exacte par sommes de rangs, ex aequo traités en RANGS MOYENS.

    `auc = P(R_v > R_f) + ½ P(R_v = R_f)`. Calculée en arithmétique entière sur des rangs
    DOUBLÉS (ce qui rend les demi-rangs exacts), agrégée en `Fraction`, arrondie une seule
    fois : deux exécutions donnent le même dernier bit.

    Mise en garde publiée avec le chiffre : l'AUC est invariante à la prévalence. C'est une
    bonne mesure de SÉPARATION, comparable d'un jeu à l'autre, et une mauvaise mesure de
    qualité OPÉRATIONNELLE sous un déséquilibre de 1 pour 500.
    """
    n_v, n_f = len(vraies), len(fausses)
    if n_v == 0 or n_f == 0:
        return {"valeur": None, "motif": "une des deux classes est vide", "n_vraies": n_v,
                "n_fausses": n_f}
    pool = sorted([(float(v), 1) for v in vraies] + [(float(v), 0) for v in fausses])
    somme_rangs_doubles = 0
    i = 0
    while i < len(pool):
        j = i
        while j < len(pool) and pool[j][0] == pool[i][0]:
            j += 1
        # Positions 1-based i+1..j ; rang moyen doublé = (i+1) + j.
        rang_double = (i + 1) + j
        somme_rangs_doubles += rang_double * sum(1 for k in range(i, j) if pool[k][1] == 1)
        i = j
    somme_rangs = Fraction(somme_rangs_doubles, 2)
    auc = (somme_rangs - Fraction(n_v * (n_v + 1), 2)) / Fraction(n_v * n_f)
    return {"valeur": float(auc), "motif": None, "n_vraies": n_v, "n_fausses": n_f,
            "avertissement": ("invariante a la prevalence : mesure de SEPARATION comparable "
                              "entre jeux, PAS une mesure de qualite operationnelle")}


def _balayage(vraies: Sequence[float], fausses: Sequence[float], n_vraies_total: int):
    """Balaye tous les seuils candidats (points milieux), en rendant (t, tp, fp, fn).

    Convention : est prédit positif ce qui vérifie `R > t`. Les seuils candidats sont les
    points milieux entre valeurs distinctes consécutives, plus un seuil sous le minimum et un
    au-dessus du maximum — grille DÉCLARÉE, de sorte qu'aucune valeur observée ne tombe
    exactement sur un seuil et que l'inégalité stricte n'ait pas d'effet de bord.

    `n_vraies_total` est le dénominateur BOUT EN BOUT : les vraies paires perdues au blocking
    n'ont pas de `R`, mais elles comptent en faux négatifs — sinon le balayage optimiserait
    un rappel dont les questions difficiles ont été retirées.
    """
    valeurs = sorted(set([float(v) for v in vraies] + [float(v) for v in fausses]))
    if not valeurs:
        return
    candidats = [valeurs[0] - 1.0]
    for a, b in zip(valeurs, valeurs[1:]):
        candidats.append((a + b) / 2.0)
    candidats.append(valeurs[-1] + 1.0)

    v_triees = sorted(float(v) for v in vraies)
    f_triees = sorted(float(v) for v in fausses)
    perdues = n_vraies_total - len(v_triees)
    for t in candidats:
        tp = len(v_triees) - _n_inferieurs_ou_egaux(v_triees, t)
        fp = len(f_triees) - _n_inferieurs_ou_egaux(f_triees, t)
        fn = n_vraies_total - tp
        yield t, tp, fp, fn, perdues


def _n_inferieurs_ou_egaux(triees: Sequence[float], t: float) -> int:
    """Nombre d'éléments `<= t` par recherche dichotomique (borne droite)."""
    bas, haut = 0, len(triees)
    while bas < haut:
        milieu = (bas + haut) // 2
        if triees[milieu] <= t:
            bas = milieu + 1
        else:
            haut = milieu
    return bas


def average_precision(vraies: Sequence[float], fausses: Sequence[float],
                      n_vraies_total: Optional[int] = None) -> dict:
    """Average precision = `Σ_k (rappel_k - rappel_{k-1}) x precision_k`.

    Pas d'interpolation, pas de règle des 11 points : la somme est prise sur le balayage des
    seuils distincts, dans l'ordre décroissant du score. `ap_reference` est la précision d'un
    classement aléatoire (c'est-à-dire `pairs_quality`), et `lift` le rapport des deux.
    """
    n_v, n_f = len(vraies), len(fausses)
    if n_v == 0 or n_f == 0:
        return {"valeur": None, "motif": "une des deux classes est vide"}
    total = n_vraies_total if n_vraies_total is not None else n_v
    points = sorted(_balayage(vraies, fausses, total), key=lambda x: -x[0])
    ap = 0.0
    rappel_precedent = 0.0
    for _, tp, fp, _, _ in points:
        if tp + fp == 0:
            continue
        p = tp / (tp + fp)
        r = tp / total
        ap += (r - rappel_precedent) * p
        rappel_precedent = r
    reference = n_v / (n_v + n_f)
    return {"valeur": ap, "motif": None, "ap_reference": reference,
            "lift": (ap / reference) if reference else None,
            "denominateur_rappel": total,
            "note": ("depend de la prevalence, contrairement a l'AUC : c'est elle qui parle "
                     "du regime operationnel reel")}


def kolmogorov_smirnov(vraies: Sequence[float], fausses: Sequence[float]) -> dict:
    """`D = sup_x |F_vraies(x) - F_fausses(x)|`, et la position `x*` du sup.

    **Aucune p-valeur** : on mesure une population ENTIÈRE, pas un échantillon. Il n'y a pas
    d'hypothèse à tester, seulement une taille d'effet à rapporter ; sur ~20 000 négatifs,
    toute p-valeur asymptotique serait nulle et vide de contenu.

    `x*` est étiqueté **non actionnable** : c'est un seuil DÉRIVÉ DE LA VÉRITÉ TERRAIN, et
    l'employer comme Tμ serait la fuite archétypale. Il est publié parce qu'il dit OÙ se joue
    la séparation, et neutralisé par son nom même.
    """
    n_v, n_f = len(vraies), len(fausses)
    if n_v == 0 or n_f == 0:
        return {"d": None, "motif": "une des deux classes est vide"}
    v_triees = sorted(float(v) for v in vraies)
    f_triees = sorted(float(v) for v in fausses)
    d_max, x_star = -1.0, None
    for x in sorted(set(v_triees) | set(f_triees)):
        fv = _n_inferieurs_ou_egaux(v_triees, x) / n_v
        ff = _n_inferieurs_ou_egaux(f_triees, x) / n_f
        ecart = abs(fv - ff)
        if ecart > d_max:                     # `>` strict : à égalité, le plus petit x gagne
            d_max, x_star = ecart, x
    return {"d": d_max, "x_non_actionnable": x_star,
            "separabilite_par_seuil_unique": (1.0 + d_max) / 2.0,
            "motif": None,
            "etiquette_x": ("SEUIL DERIVE DE LA VERITE TERRAIN : descriptif uniquement, "
                            "JAMAIS reinjecte comme T_mu")}


def recouvrement(vraies: Sequence[float], fausses: Sequence[float],
                 pas: float = PAS_HISTOGRAMME) -> dict:
    """`ovl = Σ_seaux min(p_vraies, p_fausses)` sur la grille déclarée ; `tvd = 1 - ovl`.

    0 = supports disjoints, 1 = distributions identiques. Retenu comme chiffre de tête du
    recouvrement parce qu'il est recalculable à la main sur un mini-jeu — propriété qu'une AUC
    n'a pas, et qui rend l'oracle du test véritablement indépendant du code testé.
    """
    n_v, n_f = len(vraies), len(fausses)
    if n_v == 0 or n_f == 0:
        return {"ovl": None, "tvd": None, "motif": "une des deux classes est vide"}
    h_v, h_f = histogramme(vraies, pas), histogramme(fausses, pas)
    hv, hf = h_v["seaux"], h_f["seaux"]
    ovl = 0.0
    for cle in sorted(set(hv) | set(hf)):
        ovl += min(hv.get(cle, 0) / n_v, hf.get(cle, 0) / n_f)
    # Une valeur hors de la grille déclarée est ABSENTE des deux histogrammes : la masse
    # correspondante disparaît du recouvrement, qui paraît alors plus faible qu'il ne l'est —
    # une distribution pourrait sembler parfaitement séparée en n'étant que hors-grille. La
    # discipline de `histogramme` (signaler, jamais étendre) serait perdue si on ne la
    # remontait pas ici : l'OVL est donc rendu NON ÉVALUABLE plutôt qu'optimiste.
    hors = h_v["n_hors_support"] + h_f["n_hors_support"]
    if hors:
        return {"ovl": None, "tvd": None, "pas": pas, "grille_saturee": True,
                "n_hors_support": hors,
                "motif": (f"{hors} valeur(s) hors de la grille declaree {BORNES_HISTOGRAMME} : "
                          f"leur masse manquerait au recouvrement, qui paraitrait plus faible "
                          f"qu'il n'est")}
    return {"ovl": ovl, "tvd": 1.0 - ovl, "pas": pas, "grille_saturee": False,
            "n_hors_support": 0, "motif": None}


def marge_de_separation(vraies: Sequence[float], fausses: Sequence[float]) -> dict:
    """`min(R_vraies) - max(R_fausses)`, SIGNÉE. Positive => un seuil unique sépare parfaitement.

    Si elle est négative, sa valeur absolue mesure l'ampleur de l'entrelacement. `plage_commune`
    est publiée à côté : grossière et sensible à une seule valeur extrême, déclarée comme telle,
    mais elle tranche une question binaire que les autres mesures n'abordent pas de front.
    """
    if not vraies or not fausses:
        return {"marge": None, "motif": "une des deux classes est vide"}
    min_v, max_v = min(vraies), max(vraies)
    min_f, max_f = min(fausses), max(fausses)
    bas, haut = max(min_v, min_f), min(max_v, max_f)
    disjoints = min_v > max_f
    part_v = sum(1 for v in vraies if bas <= v <= haut) / len(vraies)
    part_f = sum(1 for v in fausses if bas <= v <= haut) / len(fausses)
    return {
        "marge": min_v - max_f,
        "supports_disjoints": disjoints,
        "plage_commune": [bas, haut] if bas <= haut else None,
        "part_vraies_dans_la_plage_commune": part_v,
        "part_fausses_dans_la_plage_commune": part_f,
        "motif": None,
    }


def plancher_bayes_sur_r(vraies: Sequence[float], fausses: Sequence[float]) -> dict:
    """`Σ_valeurs min(n_vraies, n_fausses)` : erreurs qu'AUCUNE règle lisant `R` n'évite.

    Y compris une règle non monotone, y compris fournie par un oracle : deux paires de classes
    opposées portant la même valeur de `R` sont indiscernables pour qui ne lit que `R`. C'est
    le plancher DUR, et c'est la quantité qui répond littéralement à « le score seul
    tranche-t-il ? ».
    """
    compte_v, compte_f = {}, {}
    for v in vraies:
        compte_v[float(v)] = compte_v.get(float(v), 0) + 1
    for v in fausses:
        compte_f[float(v)] = compte_f.get(float(v), 0) + 1
    plancher = 0
    valeurs_mixtes = []
    paires_mixtes = 0
    for valeur in sorted(set(compte_v) | set(compte_f)):
        nv, nf = compte_v.get(valeur, 0), compte_f.get(valeur, 0)
        plancher += min(nv, nf)
        if nv and nf:
            valeurs_mixtes.append(valeur)
            paires_mixtes += nv + nf
    total = len(vraies) + len(fausses)
    return {
        "plancher_bayes": plancher,
        "n_valeurs_mixtes": len(valeurs_mixtes),
        "n_paires_sur_valeur_mixte": paires_mixtes,
        "part_paires_mixtes": (paires_mixtes / total) if total else None,
        "n_valeurs_distinctes": len(set(compte_v) | set(compte_f)),
        "lecture": ("nombre minimal d'erreurs de TOUTE regle ne lisant que R, y compris non "
                    "monotone et fournie par un oracle"),
    }


def meilleur_seuil_unique(vraies: Sequence[float], fausses: Sequence[float],
                          n_vraies_total: Optional[int] = None) -> dict:
    """`min_t (FN(t) + FP(t))` : plancher des règles MONOTONES, et le seuil qui l'atteint.

    Il est supérieur ou égal au plancher de Bayes ; l'écart mesure la non-monotonie de la
    relation entre `R` et la classe. Départage à égalité vers le plus petit seuil (ordre
    total, reproductible).
    """
    total = n_vraies_total if n_vraies_total is not None else len(vraies)
    meilleur = None
    for t, tp, fp, fn, _ in _balayage(vraies, fausses, total):
        erreurs = fn + fp
        if meilleur is None or erreurs < meilleur[0]:
            meilleur = (erreurs, t, tp, fp, fn)
    if meilleur is None:
        return {"erreurs": None, "motif": "population vide"}
    erreurs, t, tp, fp, fn = meilleur
    return {"erreurs": erreurs, "seuil": t, "tp": tp, "fp": fp, "fn": fn,
            "note": "plancher des regles MONOTONES ; >= plancher de Bayes"}


def seuil_oracle_f1(vraies: Sequence[float], fausses: Sequence[float],
                    n_vraies_total: Optional[int] = None) -> dict:
    """Seuil unique maximisant le F1, CHOISI EN LISANT LA VÉRITÉ TERRAIN.

    C'est le seul chiffre de ce module issu d'un choix supervisé, et il est étiqueté comme
    tel sans ambiguïté : borne supérieure DIAGNOSTIQUE, non transférable, à ne jamais
    reporter comme une performance du moteur. Il est de surcroît réévalué hors échantillon
    via le split (`split.py`), parce qu'un seuil choisi sur les données qui l'ont produit est
    optimiste par construction.
    """
    total = n_vraies_total if n_vraies_total is not None else len(vraies)
    meilleur = None
    for t, tp, fp, fn, _ in _balayage(vraies, fausses, total):
        if tp + fp == 0 or total == 0:
            continue
        p, r = tp / (tp + fp), tp / total
        if p + r == 0:
            continue
        valeur = 2 * p * r / (p + r)
        if meilleur is None or valeur > meilleur[0] + 1e-15:
            meilleur = (valeur, t, p, r, tp, fp, fn)
    if meilleur is None:
        return {"f1_max": None, "motif": "aucun seuil evaluable"}
    valeur, t, p, r, tp, fp, fn = meilleur
    return {
        "f1_max": valeur, "seuil": t, "precision": p, "rappel": r,
        "tp": tp, "fp": fp, "fn": fn,
        "statut": ("ORACLE — choisi EN LISANT la verite terrain ; borne superieure "
                   "diagnostique, non transferable ; NE PAS reporter comme performance "
                   "du moteur"),
    }


def placement_des_seuils(vraies: Sequence[float], fausses: Sequence[float],
                         t_mu: float, t_lambda: float, ks_x: Optional[float]) -> dict:
    """Où tombent les seuils RÉELS dans chacune des deux distributions.

    C'est le chiffre qui dit si la bande capture du vrai doute ou du vide déjà tranché.
    Descriptif, publié, JAMAIS réinjecté dans le moteur.
    """
    def centile(valeurs, seuil):
        if not valeurs:
            return None
        return sum(1 for v in valeurs if v <= seuil) / len(valeurs)

    return {
        "t_mu": t_mu, "t_lambda": t_lambda,
        "centile_t_mu_dans_vraies": centile(vraies, t_mu),
        "centile_t_mu_dans_fausses": centile(fausses, t_mu),
        "centile_t_lambda_dans_vraies": centile(vraies, t_lambda),
        "centile_t_lambda_dans_fausses": centile(fausses, t_lambda),
        "n_vraies_au_dessus_de_t_mu": sum(1 for v in vraies if v > t_mu),
        "n_fausses_au_dessus_de_t_mu": sum(1 for v in fausses if v > t_mu),
        "n_vraies_sous_t_lambda": sum(1 for v in vraies if v < t_lambda),
        "n_fausses_sous_t_lambda": sum(1 for v in fausses if v < t_lambda),
        "n_paires_entre_les_deux": (sum(1 for v in vraies if t_lambda <= v <= t_mu)
                                    + sum(1 for v in fausses if t_lambda <= v <= t_mu)),
        "ecart_t_mu_ks": None if ks_x is None else t_mu - ks_x,
        "note": "descriptif : ces centiles ne sont JAMAIS reinjectes comme parametres",
    }


def separation(vraies: Sequence[float], fausses: Sequence[float],
               n_vraies_total: Optional[int] = None) -> dict:
    """Agrège les six mesures de séparation, plus le contrôle de sensibilité au binning."""
    total = n_vraies_total if n_vraies_total is not None else len(vraies)
    auc = auc_mann_whitney(vraies, fausses)
    ap = average_precision(vraies, fausses, total)
    ks = kolmogorov_smirnov(vraies, fausses)
    ovl_std = recouvrement(vraies, fausses, PAS_HISTOGRAMME)
    ovl_fin = recouvrement(vraies, fausses, PAS_HISTOGRAMME_FIN)
    marge = marge_de_separation(vraies, fausses)
    sensible = None
    if ovl_std["ovl"] is not None and ovl_fin["ovl"] is not None:
        sensible = abs(ovl_std["ovl"] - ovl_fin["ovl"]) > TOLERANCE_BINNING
    # --- Conversion de l'AUC en « paires équivalentes mal classées » : DEUX périmètres.
    # L'AUC divise par `n_v x n_f` où `n_v` est le nombre de vraies paires RÉELLEMENT SCORÉES
    # (les perdues au blocking n'ont pas de R et n'entrent dans aucune comparaison). Descendre
    # une vraie paire sous toutes les fausses coûte donc exactement `1 / n_v`, et non `1/|M|`.
    # Le critère gelé C1 emploie `|M|` : ce défaut est CONSERVÉ tel quel (règle de
    # non-révision du pré-enregistrement) et la conversion cohérente est publiée À CÔTÉ, pour
    # que le lecteur dispose des deux. L'écart ne change pas la bande atteinte par C1.
    n_scorees = len(vraies)
    equiv_m = (1.0 - auc["valeur"]) * total if (auc["valeur"] is not None and total) else None
    equiv_scorees = ((1.0 - auc["valeur"]) * n_scorees
                     if (auc["valeur"] is not None and n_scorees) else None)
    ap_ref_scorees = ap.get("ap_reference")
    ap_ref_coherente = (None if (ap_ref_scorees is None or not total)
                        else ap_ref_scorees * n_scorees / total)
    return {
        "auc": auc["valeur"],
        "avertissement_auc": auc.get("avertissement"),
        "paires_vraies_equivalentes_mal_classees": equiv_m,
        "paires_scorees_equivalentes_mal_classees": equiv_scorees,
        "denominateur_de_l_auc": n_scorees,
        "lecture_equiv": (
            "nombre de vraies paires ENTIEREMENT mal classees qui produirait la meme AUC. "
            "Le denominateur COHERENT est celui de l'AUC elle-meme, |M inter C| = "
            + str(n_scorees) + " (paires reellement scorees) : c'est "
            "`paires_scorees_equivalentes_mal_classees`. `paires_vraies_equivalentes_mal_"
            "classees` emploie |M| = " + str(total) + ", perimetre du critere gele C1, "
            "conserve tel quel et surestimant la conversion de " + ("%.1f %%" % (
                100.0 * (total / n_scorees - 1.0)) if n_scorees else "n/d") + "."),
        "ap": ap["valeur"], "ap_reference": ap_ref_scorees,
        "ap_reference_coherente_avec_le_rappel": ap_ref_coherente,
        "lift": ap.get("lift"),
        "note_ap_reference": (
            "ap_reference = n_v/(n_v+n_f) est la precision d'un tirage aleatoire sur les "
            "paires SCOREES, alors que l'AP est calculee avec un rappel de denominateur |M|. "
            "La reference ramenee au meme perimetre est publiee a cote."),
        "ks_d": ks.get("d"), "ks_x_non_actionnable": ks.get("x_non_actionnable"),
        "separabilite_par_seuil_unique": ks.get("separabilite_par_seuil_unique"),
        "ovl": ovl_std["ovl"], "tvd": ovl_std["tvd"],
        "ovl_pas_fin": ovl_fin["ovl"], "ovl_sensible_au_binning": sensible,
        "tolerance_binning": TOLERANCE_BINNING,
        "marge_de_separation": marge.get("marge"),
        "supports_disjoints": marge.get("supports_disjoints"),
        "plage_commune": marge.get("plage_commune"),
        "part_vraies_dans_la_plage_commune": marge.get("part_vraies_dans_la_plage_commune"),
        "part_fausses_dans_la_plage_commune": marge.get("part_fausses_dans_la_plage_commune"),
        "ecart_medianes": (
            None if not vraies or not fausses
            else quantile(sorted(float(v) for v in vraies), 0.5)
                 - quantile(sorted(float(v) for v in fausses), 0.5)),
        "desequilibre": {
            "n_vraies": len(vraies), "n_fausses": len(fausses),
            "ratio": (len(fausses) / len(vraies)) if vraies else None,
            "taux_de_positifs": (len(vraies) / (len(vraies) + len(fausses)))
                                if (vraies or fausses) else None,
        },
    }
