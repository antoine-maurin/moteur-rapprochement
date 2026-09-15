"""Fellegi-Sunter + décision 3 zones.

Chaîne : COMPARISON_VECTOR -> estimation (m, u) par EM -> poids w = log2(m/u) ->
agrégat R = Σ w -> verdict dans {MATCH, NON_MATCH, ZONE_GRISE} -> CORRESPONDENCE.

## Le modèle
Modèle à classes latentes à 2 composantes sur les niveaux d'accord :
`m[j][l] = P(niveau l sur le champ j | la paire est un lien)` et `u[j][l]` la même chose
sous l'hypothèse contraire, avec un poids de mélange `p = P(lien)`. Indépendance
conditionnelle **assumée en V1** (mandat §4) : c'est ce qui rend l'agrégat additif.

## L'indétermination
`INDETERMINE_MANQUANT` ne reçoit pas de probabilité : le champ est simplement **retiré du
produit de vraisemblance** de la paire. C'est l'hypothèse « manquant au hasard », et c'est
exactement ce qui donne `w = 0` — une absence n'apporte aucune preuve, ni pour ni contre.
Les deux formulations coïncident ; « poids nul » est la lecture, « facteur retiré » est le
mécanisme.

## Non-circularité
L'EM est **non supervisé** : il n'utilise que les vecteurs de comparaison. Aucune donnée de
vérité terrain n'entre ici — c'est la condition pour que la mesure de qualité
(indépendante) reste une preuve et non un raisonnement circulaire.

## Paramètres NON CALIBRÉS
Les seuils `T_MU` / `T_LAMBDA` et les tables a priori de repli sont des **placeholders
déclarés**, pas des valeurs ajustées : la calibration est différée après la mesure de qualité.
"""
from __future__ import annotations

import hashlib
import math
import random
from typing import Optional

from .compare import (ACCORD_FORT, ACCORD_PARTIEL, DESACCORD, INDETERMINE_MANQUANT,
                      NIVEAUX_INFORMATIFS)
from .normalize import ATTRIBUTS_COMPARE

# --- Verdicts (énumération fermée, mandat §4) ----------------------------------------
MATCH = "MATCH"
NON_MATCH = "NON_MATCH"
ZONE_GRISE = "ZONE_GRISE"
VERDICTS = (MATCH, NON_MATCH, ZONE_GRISE)

# --- Graine scellée de l'EM ----------------------------------------------------------
#: Scellée : elle fait partie de la définition du moteur, pas de son paramétrage d'appel.
GRAINE_EM_SCELLEE = "U-B2::E-DEC::EM::seed-0001"

# --- Hyperparamètres de l'estimation -------------------------------------------------
MAX_ITER_DEFAUT = 200
TOLERANCE_DEFAUT = 1e-9
#: Lissage de Dirichlet (pseudo-comptes ajoutés à chaque niveau avant normalisation).
#: 0,5 est l'a priori de Jeffreys pour une multinomiale. Il évite les probabilités nulles,
#: donc les poids infinis, et il s'efface à mesure que les données s'accumulent.
#: Borne exacte qui en découle, pour un champ de masse effective `N` sur 3 niveaux :
#: la probabilité lissée vit dans `[a/(N+3a), (N+a)/(N+3a)]`, donc
#: `|w| = |log2(m/u)| <= log2((N + a) / a)`. La borne CROÎT avec la taille du jeu — c'est
#: attendu (plus de données autorisent des rapports plus extrêmes), et c'est énoncé ici
#: plutôt que remplacé par une constante commode qui serait fausse.
PSEUDO_COMPTE_DIRICHLET = 0.5
#: Marge de sécurité gardant le poids de mélange `p` hors des bornes 0 et 1 (log défini).
MARGE_P = 1e-9
#: En deçà, un mélange à 2 classes sur 3 niveaux x 8 champs n'est pas identifiable :
#: on n'estime pas, on se replie (et on le trace).
MIN_PAIRES_EM = 4
#: Amplitude du bruit déterministe d'initialisation (tiré de la graine scellée). Il rompt
#: la symétrie exacte de l'initialisation sans déplacer le point de départ.
AMPLITUDE_JITTER = 0.05
P_INITIAL = 0.10

# --- Tables a priori de REPLI — provenance déclarée ----------------------------------
#: Ordres de grandeur conventionnels du modèle de Fellegi-Sunter : un champ discriminant
#: s'accorde fortement chez les liens et rarement chez les non-liens. Ces valeurs ne sont
#: PAS mesurées sur les données, ne sont PAS calibrées, et ne servent QUE de repli — un
#: repli qui est systématiquement TRACÉ dans la sortie, jamais appliqué en silence.
PRIORS_M = {ACCORD_FORT: 0.85, ACCORD_PARTIEL: 0.10, DESACCORD: 0.05}
PRIORS_U = {ACCORD_FORT: 0.05, ACCORD_PARTIEL: 0.15, DESACCORD: 0.80}
PROVENANCE_PRIORS = (
    "a priori conventionnels du modele de Fellegi-Sunter (forme attendue d'un champ "
    "discriminant), NON mesures et NON calibres sur ce jeu de donnees ; usage strictement "
    "limite au repli, toujours signale par repli=True et motif_repli"
)

# --- Seuils de décision — NON CALIBRÉS (mandat §4) -----------------------------------
#: R est un rapport de vraisemblance exprimé en BITS. Les placeholders sont posés
#: symétriquement à +/- 8 bits, soit une cote de 256 contre 1 dans chaque sens : c'est un
#: choix a priori d'ordre de grandeur, DÉLIBÉRÉMENT indépendant des données, et non le
#: résultat d'un ajustement. Toute valeur cible de qualité est hors sujet ici.
T_MU_DEFAUT = 8.0
T_LAMBDA_DEFAUT = -8.0

#: Arrondi de l'agrégat avant seuillage et avant sérialisation : la valeur tracée est
#: exactement celle qui a été comparée aux seuils.
DECIMALES_POIDS = 9

PARAMETRES_NON_CALIBRES = ("T_MU", "T_LAMBDA", "PRIORS_M", "PRIORS_U")


def graine_entiere(graine: str) -> int:
    """Entier déterministe dérivé d'une graine textuelle.

    Via SHA-256, et **jamais** via `hash()` : le `hash()` des chaînes est salé par
    processus, ce qui casserait la reproductibilité inter-processus exigée par le déterminisme.
    """
    return int(hashlib.sha256(graine.encode("utf-8")).hexdigest(), 16) % (2 ** 32)


def _normalise_distribution(valeurs: dict) -> dict:
    """Ramène un dict de masses positives à une distribution (somme = 1)."""
    total = sum(valeurs[l] for l in NIVEAUX_INFORMATIFS)
    return {l: valeurs[l] / total for l in NIVEAUX_INFORMATIFS}


def _tables_a_priori() -> tuple:
    """Tables (m, u) a priori, un jeu par attribut comparé."""
    m = {j: dict(PRIORS_M) for j in ATTRIBUTS_COMPARE}
    u = {j: dict(PRIORS_U) for j in ATTRIBUTS_COMPARE}
    return m, u


def _initialise(graine: str) -> tuple:
    """Initialisation des tables (m, u) à partir des a priori + bruit de graine scellée."""
    alea = random.Random(graine_entiere(graine))
    m, u = {}, {}
    for j in ATTRIBUTS_COMPARE:                       # ordre canonique => tirages stables
        brut_m, brut_u = {}, {}
        for niveau in NIVEAUX_INFORMATIFS:
            secousse = 1.0 + alea.uniform(-AMPLITUDE_JITTER, AMPLITUDE_JITTER)
            brut_m[niveau] = PRIORS_M[niveau] * secousse
            secousse = 1.0 + alea.uniform(-AMPLITUDE_JITTER, AMPLITUDE_JITTER)
            brut_u[niveau] = PRIORS_U[niveau] * secousse
        m[j] = _normalise_distribution(brut_m)
        u[j] = _normalise_distribution(brut_u)
    return m, u


def _sigmoide(x: float) -> float:
    """Sigmoïde numériquement stable (pas d'`exp` d'un grand positif)."""
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _niveaux_de(vecteur: dict) -> dict:
    """Extrait `{attribut: niveau}` d'un COMPARISON_VECTOR."""
    return {j: vecteur["accord_" + j] for j in ATTRIBUTS_COMPARE}


def estime_m_u(vecteurs, graine: str = GRAINE_EM_SCELLEE,
               max_iter: int = MAX_ITER_DEFAUT,
               tolerance: float = TOLERANCE_DEFAUT,
               pseudo_compte: float = PSEUDO_COMPTE_DIRICHLET,
               min_paires: int = MIN_PAIRES_EM) -> dict:
    """Estime `m` et `u` par espérance-maximisation, sans aucune étiquette.

    Retourne un dict portant `m`, `u`, `p`, et la TRACE complète de l'estimation :
    `convergence`, `iterations`, `repli`, `motif_repli`, `champs_repli`, `graine`,
    `provenance_priors`. Le repli n'est jamais muet : quand il s'applique, `repli` vaut
    `True` et `motif_repli` dit pourquoi.

    Repli intégral (tables a priori) si : trop peu de paires pour identifier le mélange,
    ou non-convergence en `max_iter` itérations, ou dégénérescence du mélange (`p`
    collé à 0 ou 1). Repli **par champ** si un attribut n'est observé dans aucune paire :
    ses tables restent celles des a priori et il est listé dans `champs_repli`.
    """
    observations = [_niveaux_de(v) for v in vecteurs]
    n = len(observations)

    def replie(motif: str, iterations_effectuees: int = 0) -> dict:
        """Repli TRACÉ sur les tables a priori. `iterations_effectuees` dit le travail
        réellement fourni avant l'abandon : rapporter 0 après 200 itérations serait une
        trace fausse, et une trace fausse vaut un repli silencieux."""
        m, u = _tables_a_priori()
        return {"m": m, "u": u, "p": P_INITIAL, "convergence": False,
                "iterations": iterations_effectuees,
                "repli": True, "motif_repli": motif,
                "champs_repli": sorted(ATTRIBUTS_COMPARE),
                "echange_de_classes": False,
                "graine": graine, "n_paires": n, "provenance_priors": PROVENANCE_PRIORS}

    if n < min_paires:
        return replie(f"paires insuffisantes pour identifier le melange ({n} < {min_paires})")

    m, u = _initialise(graine)
    p = P_INITIAL
    convergence = False
    iterations = 0

    for iterations in range(1, max_iter + 1):
        # --- E : responsabilité de la classe « lien » pour chaque paire ---------------
        gammas = []
        for obs in observations:
            delta = math.log(p) - math.log(1.0 - p)
            for j in ATTRIBUTS_COMPARE:              # ordre fixe => somme reproductible
                niveau = obs[j]
                if niveau == INDETERMINE_MANQUANT:
                    continue                          # facteur retiré (= poids nul)
                delta += math.log(m[j][niveau]) - math.log(u[j][niveau])
            gammas.append(_sigmoide(delta))

        # --- M : ré-estimation lissée ------------------------------------------------
        nouveau_p = min(1.0 - MARGE_P, max(MARGE_P, sum(gammas) / n))
        nouveau_m, nouveau_u = {}, {}
        champs_repli = []
        for j in ATTRIBUTS_COMPARE:
            masse_m = {l: pseudo_compte for l in NIVEAUX_INFORMATIFS}
            masse_u = {l: pseudo_compte for l in NIVEAUX_INFORMATIFS}
            observe = False
            for obs, gamma in zip(observations, gammas):
                niveau = obs[j]
                if niveau == INDETERMINE_MANQUANT:
                    continue
                observe = True
                masse_m[niveau] += gamma
                masse_u[niveau] += 1.0 - gamma
            if observe:
                nouveau_m[j] = _normalise_distribution(masse_m)
                nouveau_u[j] = _normalise_distribution(masse_u)
            else:
                # Jamais observé : rien à estimer. On pose les a priori, et on le dit.
                nouveau_m[j] = dict(PRIORS_M)
                nouveau_u[j] = dict(PRIORS_U)
                champs_repli.append(j)

        ecart = abs(nouveau_p - p)
        for j in ATTRIBUTS_COMPARE:
            for l in NIVEAUX_INFORMATIFS:
                ecart = max(ecart, abs(nouveau_m[j][l] - m[j][l]),
                            abs(nouveau_u[j][l] - u[j][l]))
        m, u, p = nouveau_m, nouveau_u, nouveau_p
        if ecart < tolerance:
            convergence = True
            break

    if not convergence:
        return replie(f"non-convergence en {max_iter} iterations", iterations)

    m, u, p, echange = oriente_classes(m, u, p)

    degenere = p <= 2 * MARGE_P or p >= 1.0 - 2 * MARGE_P
    if degenere:
        return replie(f"melange degenere (p={p!r}) : les deux classes ne se separent pas",
                      iterations)

    return {"m": m, "u": u, "p": p, "convergence": True, "iterations": iterations,
            "repli": False, "motif_repli": None, "champs_repli": sorted(champs_repli),
            "echange_de_classes": echange, "graine": graine, "n_paires": n,
            "provenance_priors": PROVENANCE_PRIORS}


def oriente_classes(m: dict, u: dict, p: float) -> tuple:
    """Lève l'ambiguïté d'étiquetage des deux classes latentes. Retourne `(m, u, p, echange)`.

    L'EM ne sait pas laquelle de ses deux classes est « lien » : permuter `(m, u)` et
    remplacer `p` par `1 - p` donne exactement la MÊME vraisemblance. Sans règle, le sens
    des poids dépendrait de l'initialisation, et le moteur pourrait décider à l'envers.

    Règle déterministe : la classe « lien » est celle dont la masse d'accord fort est la
    plus grande, sommée sur les attributs. À égalité exacte, aucun échange — l'ordre
    d'initialisation tranche, ce qui garde la fonction reproductible.

    Extraite pour être éprouvable directement : sur des données réelles l'échange ne se
    produit pratiquement jamais, si bien qu'un test de bout en bout laisserait cette
    branche muette.
    """
    masse_forte_m = sum(m[j][ACCORD_FORT] for j in ATTRIBUTS_COMPARE)
    masse_forte_u = sum(u[j][ACCORD_FORT] for j in ATTRIBUTS_COMPARE)
    if masse_forte_u > masse_forte_m:
        return u, m, 1.0 - p, True
    return m, u, p, False


def table_de_poids(m: dict, u: dict) -> dict:
    """Poids `w[j][l] = log2(m/u)` pour les niveaux informatifs, `0.0` pour l'indétermination.

    Le zéro sur `INDETERMINE_MANQUANT` n'est pas une convention d'affichage : c'est la
    valeur qui rend l'absence d'observation neutre dans l'agrégat.
    """
    poids = {}
    for j in ATTRIBUTS_COMPARE:
        poids[j] = {l: math.log2(m[j][l] / u[j][l]) for l in NIVEAUX_INFORMATIFS}
        poids[j][INDETERMINE_MANQUANT] = 0.0
    return poids


def poids_par_champ(vecteur: dict, poids: dict) -> dict:
    """Contribution de chaque attribut à l'agrégat, dans l'ordre canonique."""
    return {j: poids[j][vecteur["accord_" + j]] for j in ATTRIBUTS_COMPARE}


def agregat(vecteur: dict, poids: dict) -> float:
    """`R = Σ_j w[j][niveau_j]`, sommé dans l'ordre canonique des attributs.

    L'ordre de sommation est fixé parce que l'addition flottante n'est pas associative :
    sommer dans un autre ordre pourrait changer le dernier bit, donc l'empreinte de sortie.
    """
    total = 0.0
    for j in ATTRIBUTS_COMPARE:
        total += poids[j][vecteur["accord_" + j]]
    return round(total, DECIMALES_POIDS)


def composantes_informatives(vecteur: dict) -> list:
    """Attributs porteurs de preuve pour cette paire (tout sauf l'indétermination)."""
    return [j for j in ATTRIBUTS_COMPARE if vecteur["accord_" + j] != INDETERMINE_MANQUANT]


def verdict_3_zones(r: float, t_mu: float = T_MU_DEFAUT,
                    t_lambda: float = T_LAMBDA_DEFAUT) -> str:
    """`R > Tμ` -> MATCH ; `R < Tλ` -> NON_MATCH ; entre les deux (bornes incluses) -> ZONE_GRISE."""
    if t_lambda > t_mu:
        raise ValueError(f"seuils incoherents : T_LAMBDA={t_lambda} au-dessus de T_MU={t_mu}")
    if r > t_mu:
        return MATCH
    if r < t_lambda:
        return NON_MATCH
    return ZONE_GRISE


def correspondance(vecteur: dict, poids: dict, t_mu: float = T_MU_DEFAUT,
                   t_lambda: float = T_LAMBDA_DEFAUT) -> dict:
    """CORRESPONDENCE d'un COMPARISON_VECTOR : exactement une, pour exactement une paire.

    Invariants portés ici même (mandat §4) :
      - `verdict` appartient à `VERDICTS` ;
      - `revue_zone_grise` est renseigné **si et seulement si** le verdict est ZONE_GRISE ;
        il reste au statut `en_attente` : l'instruction du doute est la revue de zone grise ;
      - **garde R-20** : une paire dont AUCUN champ n'est informatif ne peut pas être
        déclarée MATCH. Le déclencheur est « zéro composante informative », et non
        « R == 0 » : deux poids opposés peuvent s'annuler par accident alors que la paire
        porte, elle, de la preuve. Sans preuve, l'absence de lien est ce qui est retenu
        (NON_MATCH) plutôt qu'un doute soumis à revue : il n'y a rien à instruire.
    """
    r = agregat(vecteur, poids)
    informatives = composantes_informatives(vecteur)
    garde = not informatives
    verdict = NON_MATCH if garde else verdict_3_zones(r, t_mu, t_lambda)
    return {
        "record_id_a": vecteur["record_id_a"],
        "record_id_b": vecteur["record_id_b"],
        "poids_match": r,
        "verdict": verdict,
        "revue_zone_grise": ({"statut": "en_attente", "decision": None,
                              "unite_responsable": "revue_zone_grise"}
                             if verdict == ZONE_GRISE else None),
        "bloc_origine": list(vecteur.get("bloc_origine", [])),
        "composantes": {"accord_" + j: vecteur["accord_" + j] for j in ATTRIBUTS_COMPARE},
        "poids_par_champ": poids_par_champ(vecteur, poids),
        "n_composantes_informatives": len(informatives),
        "garde_r20_appliquee": garde,
    }


def correspondances(vecteurs, poids: dict, t_mu: float = T_MU_DEFAUT,
                    t_lambda: float = T_LAMBDA_DEFAUT) -> list:
    """Une CORRESPONDENCE par COMPARISON_VECTOR, dans l'ordre reçu (cardinalité 1-1)."""
    return [correspondance(v, poids, t_mu, t_lambda) for v in vecteurs]
