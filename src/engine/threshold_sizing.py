"""Dimensionnement budget-driven des seuils de décision.

Sous les seuils placeholder ±8 bits, la distribution de `R` est franchement **bimodale**
— les liens évidents très haut, les non-liens évidents très bas — et l'entre-deux est
presque vide : 2 paires sur 21 781. La revue du doute en zone grise n'aurait
donc rien à instruire.

Ce module place `Tμ` / `Tλ` sur la **distribution de `R` seule**, de sorte que la zone
grise capture les paires **les moins confiantes** en un volume égal à un **budget de
revue**. Il ne mesure rien, ne décide rien, et ne modifie pas le moteur : il propose deux
nombres que l'appelant passe à `ParametresMoteur`.

## Frontière de décision
Le point de référence est `R = 0`, c'est-à-dire un rapport de vraisemblance de 1 : c'est le
point où la **preuve** penche exactement autant d'un côté que de l'autre. Il est
**intrinsèque à Fellegi-Sunter** et ne s'estime pas sur les données — donc il ne dérive ni
avec l'échantillon ni avec une recalibration ultérieure des poids, qui laisse
`log2(m/u) = 0` à sa place. La frontière reste néanmoins un **paramètre** : un appelant
qui aurait une raison d'en viser une autre peut la fournir.

> Précision, car les deux notions se confondent aisément : `R = 0` est le point
> **évidentiel** neutre, et non le point où la probabilité a posteriori d'un lien vaut
> 50 %. Ce dernier se situe à `R = -log2(cote a priori)`, soit environ `+6,6` bits pour le
> poids de mélange qu'estime l'EM sur la population de démonstration. Placer la frontière
> là a été mesuré : la borne basse est **inchangée au bit près**, et les paires
> supplémentaires happées sont des liens déjà correctement tranchés — le budget de revue y
> perdrait sans que la revue y gagne. S'ajoute que faire entrer le poids de mélange estimé
> dans la frontière relèverait de la calibration, que le mandat diffère explicitement au
> scoreur. Le point évidentiel est donc retenu, et ce choix est publié dans l'artefact.

> Une frontière *estimée* (le creux entre les deux modes) a été essayée puis **écartée** :
> sur cette distribution, la vallée se situe au-delà du 98ᵉ centile, si bien que toute
> fenêtre de recherche raisonnable la manque et renvoie un creux interne au mode des
> non-liens. Un estimateur qui se trompe silencieusement vaut moins que pas d'estimateur.

## Ce qui est mesuré, et ce qui ne l'est pas
**Aucune vérité terrain n'entre ici.** Le dimensionnement ne lit que des valeurs de
`R`, produites par le moteur à partir des seuls attributs comparés. C'est précisément ce
qui le distingue d'une calibration : il choisit un **volume de revue**, pas un taux
d'erreur. La calibration fine des taux relève du scoreur, avec un jeu de calibration
distinct du jeu d'évaluation.

## Statut des valeurs produites — PROVISOIRE
Les seuils dimensionnés **débloquent** la revue ; ils ne prétendent pas être optimaux. Aucune
valeur cible de qualité n'est postulée. Le budget lui-même est provisoire : le débit réel
de la revue n'est pas connu tant qu'elle n'est pas construite.
"""
from __future__ import annotations

import math
from typing import Sequence

from .decide import T_LAMBDA_DEFAUT, T_MU_DEFAUT, DECIMALES_POIDS

__all__ = [
    "FRONTIERE_NEUTRE", "BUDGET_REVUE_DEFAUT", "budget_depuis_debit",
    "statistiques_r", "dimensionne_seuils", "dimensionne_depuis_correspondances",
]

# --- Budget de revue — DIMENSIONNÉ, et PROVISOIRE (précision ARCHI (i)) ---------------
#: Débit de la revue, en paires par minute. **Placeholder** : la revue n'est pas
#: construite, son débit réel (revue hors ligne, CPU, sans réseau) n'est donc pas mesuré.
DEBIT_REVUE_PAR_MINUTE_PROVISOIRE = 60.0
#: Durée de revue allouée, en minutes (budget de traitement évoqué par l'arbitrage).
DUREE_REVUE_MINUTES_PROVISOIRE = 5.0


def budget_depuis_debit(debit_par_minute: float, duree_minutes: float) -> int:
    """Budget de revue = débit x durée, arrondi à l'entier inférieur, au moins 1.

    Le budget est ainsi **dérivé** d'un modèle de capacité explicite plutôt que posé au
    doigt mouillé (précision ARCHI (i)). Ses deux entrées restent provisoires : quand le
    débit réel de la revue sera mesuré, seul ce couple de constantes changera.
    """
    if debit_par_minute <= 0 or duree_minutes <= 0:
        raise ValueError(
            f"debit et duree doivent etre strictement positifs : "
            f"debit={debit_par_minute}, duree={duree_minutes}")
    return max(1, int(debit_par_minute * duree_minutes))


#: 60 paires/min x 5 min = 300 paires. PROVISOIRE.
BUDGET_REVUE_DEFAUT = budget_depuis_debit(DEBIT_REVUE_PAR_MINUTE_PROVISOIRE,
                                          DUREE_REVUE_MINUTES_PROVISOIRE)

#: `R = 0` <=> rapport de vraisemblance 1 : la preuve est exactement équilibrée.
FRONTIERE_NEUTRE = 0.0

#: Pas de la grille sur laquelle vivent les valeurs de `R` : `decide.agregat` les arrondit
#: à `DECIMALES_POIDS` décimales, donc deux valeurs DISTINCTES sont séparées d'au moins ce
#: quantum. Tout écartement d'une bande dégénérée doit rester STRICTEMENT en deçà, faute
#: de quoi il atteindrait la valeur voisine et ferait entrer dans la bande une paire qui
#: n'y avait pas été retenue.
PAS_GRILLE_R = 10.0 ** (-DECIMALES_POIDS)

PARAMETRES_PROVISOIRES = ("t_mu", "t_lambda", "budget_revue",
                          "debit_revue_par_minute", "duree_revue_minutes")


def _quantile(valeurs_triees: Sequence[float], q: float) -> float:
    """Quantile par interpolation linéaire entre rangs (méthode déclarée, déterministe)."""
    if not valeurs_triees:
        raise ValueError("quantile d'une population vide")
    if len(valeurs_triees) == 1:
        return float(valeurs_triees[0])
    position = q * (len(valeurs_triees) - 1)
    bas = int(math.floor(position))
    haut = min(bas + 1, len(valeurs_triees) - 1)
    poids = position - bas
    return float(valeurs_triees[bas] * (1.0 - poids) + valeurs_triees[haut] * poids)


def _socle_sortie(frontiere: float, budget_revue: int, stats: dict) -> dict:
    """Clés communes à TOUS les chemins de sortie de `dimensionne_seuils`.

    Le contrat de sortie ne doit pas changer de forme selon la branche empruntée : un
    appelant devrait sinon tester l'existence de chaque clé avant de la lire, et la
    première branche oubliée casserait chez lui, pas ici.
    """
    return {
        "frontiere": frontiere,
        "budget_vise": budget_revue,
        "statistiques_r": stats,
        "provisoire": True,
        "gap": "calibration différée",
        "parametres_provisoires": list(PARAMETRES_PROVISOIRES),
    }


def statistiques_r(valeurs_r: Sequence[float]) -> dict:
    """Description de la distribution de `R` (aucune vérité terrain n'y entre)."""
    triees = sorted(float(r) for r in valeurs_r)
    if not triees:
        return {"n": 0}
    return {
        "n": len(triees),
        "min": triees[0],
        "max": triees[-1],
        "q05": _quantile(triees, 0.05),
        "q25": _quantile(triees, 0.25),
        "mediane": _quantile(triees, 0.50),
        "q75": _quantile(triees, 0.75),
        "q95": _quantile(triees, 0.95),
        "moyenne": sum(triees) / len(triees),
        "n_valeurs_distinctes": len(set(triees)),
    }


def dimensionne_seuils(valeurs_r: Sequence[float],
                       budget_revue: int = BUDGET_REVUE_DEFAUT,
                       frontiere: float = FRONTIERE_NEUTRE) -> dict:
    """Place `Tλ < Tμ` pour que la bande `[Tλ, Tμ]` capture ~ `budget_revue` paires.

    **Méthode.** Les valeurs distinctes de `R` sont ordonnées par distance croissante à la
    frontière. Les inclure une à une engendre une suite de bandes **emboîtées**, dont on
    retient celle dont l'effectif est le plus proche du budget ; à égalité d'écart, la
    plus petite l'emporte, de sorte que le budget n'est jamais dépassé sans nécessité.

    Pourquoi pas simplement « les k plus proches » : `R` comporte beaucoup d'ex aequo
    (des paires au profil d'accord identique reçoivent le même poids), si bien que couper
    à un rang précis produit une bande qui déborde le budget sans qu'on l'ait choisi.
    Choisir parmi les bandes réellement atteignables donne le meilleur ajustement possible
    à la granularité des données, et le dit.

    **Invariant du mandat (§5.3).** La bande retenue est un intervalle : toute paire en
    zone grise est donc plus proche de la frontière que toute paire hors zone grise située
    du même côté. Ce n'est pas un échantillon, c'est la bande médiane.

    Retourne un dict portant `t_mu`, `t_lambda`, la frontière employée, le budget visé et
    atteint, l'écart, les statistiques de `R` et le drapeau `provisoire`.
    """
    if budget_revue < 1:
        raise ValueError(f"budget_revue doit valoir au moins 1 : {budget_revue}")
    valeurs = [float(r) for r in valeurs_r]
    stats = statistiques_r(valeurs)

    if not valeurs:
        return {
            **_socle_sortie(frontiere, budget_revue, stats),
            "t_mu": T_MU_DEFAUT, "t_lambda": T_LAMBDA_DEFAUT,
            "budget_atteint": 0, "ecart_au_budget": -budget_revue,
            "taille_zone_grise": 0, "n_paires": 0, "budget_sature": False,
            "repli": True,
            "motif_repli": "population vide : rien a dimensionner, seuils par defaut conserves",
            "methode": "repli sur les placeholders +/-8 bits",
        }

    occurrences = {}
    for r in valeurs:
        occurrences[r] = occurrences.get(r, 0) + 1
    # Ordre : distance à la frontière, puis valeur — départage total et reproductible.
    ordre = sorted(occurrences, key=lambda r: (abs(r - frontiere), r))

    cumul = 0
    basse = haute = None
    meilleur = None
    for valeur in ordre:
        cumul += occurrences[valeur]
        basse = valeur if basse is None else min(basse, valeur)
        haute = valeur if haute is None else max(haute, valeur)
        ecart = abs(cumul - budget_revue)
        if meilleur is None or ecart < meilleur[0]:
            meilleur = (ecart, cumul, basse, haute)

    _, retenu, t_lambda, t_mu = meilleur

    # Recomptage indépendant, sur la bande TELLE QUE SÉLECTIONNÉE : c'est l'invariant
    # d'intervalle du mandat (§5.3). Le vérifier plutôt que le supposer, car ce nombre est
    # celui qui sera promis à la revue de zone grise comme volume de revue.
    dans_la_bande = sum(1 for r in valeurs if t_lambda <= r <= t_mu)
    if dans_la_bande != retenu:
        raise AssertionError(
            f"incoherence de dimensionnement : bande [{t_lambda}, {t_mu}] contient "
            f"{dans_la_bande} paires, accumulation annoncait {retenu}")

    if t_lambda == t_mu:
        # Bande réduite à une valeur unique : `Tλ < Tμ` est requis pour que la partition en
        # trois zones garde un sens. On s'écarte au flottant IMMÉDIATEMENT voisin, et non
        # d'un pas fixe : un pas de `PAS_GRILLE_R` atteindrait exactement la valeur arrondie
        # suivante et happerait une paire non retenue. Un flottant voisin, lui, ne peut
        # contenir aucune valeur de la grille, qui est huit ordres de grandeur plus lâche.
        t_lambda = math.nextafter(t_lambda, -math.inf)
        t_mu = math.nextafter(t_mu, math.inf)
        apres_ecartement = sum(1 for r in valeurs if t_lambda <= r <= t_mu)
        if apres_ecartement != dans_la_bande:
            raise AssertionError(
                f"l'ecartement de la bande degeneree a happe "
                f"{apres_ecartement - dans_la_bande} paire(s) : bande [{t_lambda}, {t_mu}]")

    return {
        **_socle_sortie(frontiere, budget_revue, stats),
        "t_mu": t_mu,
        "t_lambda": t_lambda,
        "budget_atteint": dans_la_bande,
        "ecart_au_budget": dans_la_bande - budget_revue,
        "taille_zone_grise": dans_la_bande,
        "n_paires": len(valeurs),
        "budget_sature": dans_la_bande == len(valeurs),
        "repli": False,
        "motif_repli": None,
        "methode": ("bande emboitee la plus proche du budget, ordonnee par distance a la "
                    "frontiere ; a egalite d'ecart, la plus petite bande"),
    }


def dimensionne_depuis_correspondances(correspondances,
                                       budget_revue: int = BUDGET_REVUE_DEFAUT,
                                       frontiere: float = FRONTIERE_NEUTRE) -> dict:
    """Dimensionne à partir d'une liste de CORRESPONDENCE (lit `poids_match`, rien d'autre).

    La projection sur le seul `poids_match` est délibérée : elle rend structurellement
    impossible qu'une autre information de la correspondance entre dans le calcul.
    """
    return dimensionne_seuils([c["poids_match"] for c in correspondances],
                              budget_revue=budget_revue, frontiere=frontiere)
