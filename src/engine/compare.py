"""Comparateurs par champ : paire -> COMPARISON_VECTOR.

Pour chaque CANDIDATE_PAIR, **un** COMPARISON_VECTOR de **8 composantes** `accord_<attribut>`,
chacune dans l'énumération FERMÉE `NIVEAUX`. Chaîne par champ :

    valeurs normalisées -> similarité s ∈ [0,1] -> niveau via les cutoffs (c_fort, c_partiel)

| attribut         | similarité                                              |
|------------------|---------------------------------------------------------|
| nom, prenom, ville | Jaro-Winkler                                          |
| adresse          | Dice sur bigrammes (robuste au réordonnancement)        |
| date_naissance   | égalité + similarité partielle par composantes          |
| code_postal      | égalité + préfixe commun                                |
| email            | égalité + distance d'édition ≤ 1                        |
| telephone        | égalité sur la chaîne de chiffres normalisée            |

Les noyaux (Jaro, Jaro-Winkler, Levenshtein, q-grammes) sont écrits **à la main** : le
`requirements.lock` ne contient ni `rapidfuzz` ni `jellyfish`, et l'installation d'une
dépendance est impossible (offline strict au runtime, C7). Stdlib uniquement. Splink est
proscrit ici : c'est le banc d'essai de la comparaison à l'état de l'art.

Frontière de non-circularité : ce module compare des attributs ; il ne consomme aucune donnée de
vérité terrain et ne mesure aucune qualité.
"""
from __future__ import annotations

import re
from typing import Optional

from .normalize import ATTRIBUTS_COMPARE

# --- Énumération FERMÉE des niveaux d'accord (mandat §3) -----------------------------
ACCORD_FORT = "ACCORD_FORT"
ACCORD_PARTIEL = "ACCORD_PARTIEL"
DESACCORD = "DESACCORD"
INDETERMINE_MANQUANT = "INDETERMINE_MANQUANT"

NIVEAUX = (ACCORD_FORT, ACCORD_PARTIEL, DESACCORD, INDETERMINE_MANQUANT)
#: Niveaux porteurs de preuve : seuls ceux-là reçoivent un poids non nul (cf. `decide`).
NIVEAUX_INFORMATIFS = (ACCORD_FORT, ACCORD_PARTIEL, DESACCORD)

#: Les 8 composantes, dans l'ordre canonique des attributs comparés.
COMPOSANTES = tuple("accord_" + attribut for attribut in ATTRIBUTS_COMPARE)

# --- Cutoffs par défaut — NON CALIBRÉS (mandat §3) -----------------------------------
# Ordres de grandeur usuels d'un appariement Jaro-Winkler, PAS des valeurs ajustées sur ce
# jeu de données. La calibration est différée après le scoreur : aucune valeur cible de succès
# n'est postulée ici.
C_FORT_DEFAUT = 0.90
C_PARTIEL_DEFAUT = 0.70

#: Arrondi des similarités avant seuillage : rend le niveau insensible au dernier bit
#: flottant, et garantit que la valeur tracée est EXACTEMENT celle qui a été seuillée.
DECIMALES_SIMILARITE = 6

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


# ===================== Noyaux de similarité (stdlib pure) ============================
def jaro(a: str, b: str) -> float:
    """Similarité de Jaro ∈ [0,1].

    Fenêtre d'appariement `max(len_a, len_b) // 2 - 1`, bornée à 0 — c'est le point que
    les réimplémentations ratent le plus souvent, avec le comptage des transpositions
    (nombre d'appariements dans le désordre, divisé par deux).
    """
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0.0
    fenetre = max(la, lb) // 2 - 1
    if fenetre < 0:
        fenetre = 0
    apparie_a = [False] * la
    apparie_b = [False] * lb
    n_appariements = 0
    for i in range(la):
        debut = max(0, i - fenetre)
        fin = min(i + fenetre + 1, lb)
        for j in range(debut, fin):
            if apparie_b[j] or a[i] != b[j]:
                continue
            apparie_a[i] = apparie_b[j] = True
            n_appariements += 1
            break
    if n_appariements == 0:
        return 0.0
    # Transpositions : parcours parallèle des seuls caractères appariés.
    k = 0
    n_transpositions = 0
    for i in range(la):
        if not apparie_a[i]:
            continue
        while not apparie_b[k]:
            k += 1
        if a[i] != b[k]:
            n_transpositions += 1
        k += 1
    t = n_transpositions / 2.0
    m = float(n_appariements)
    return (m / la + m / lb + (m - t) / m) / 3.0


def jaro_winkler(a: str, b: str, facteur: float = 0.1, prefixe_max: int = 4,
                 seuil_bonus: float = 0.7) -> float:
    """Jaro-Winkler : Jaro majoré par la longueur du préfixe commun (cap 4 caractères).

    Le bonus n'est appliqué qu'au-dessus de `seuil_bonus` (règle classique de Winkler) :
    majorer deux chaînes déjà dissemblables parce qu'elles commencent pareil produirait de
    faux accords (« martin » / « martelli » ne doit pas être remonté artificiellement).
    """
    j = jaro(a, b)
    if j <= seuil_bonus:
        return j
    prefixe = 0
    for ca, cb in zip(a, b):
        if ca != cb or prefixe >= prefixe_max:
            break
        prefixe += 1
    return j + prefixe * facteur * (1.0 - j)


def levenshtein(a: str, b: str) -> int:
    """Distance d'édition (insertion / suppression / substitution), programmation dynamique."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    precedente = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        courante = [i]
        for j, cb in enumerate(b, start=1):
            courante.append(min(precedente[j] + 1,          # suppression
                                courante[j - 1] + 1,        # insertion
                                precedente[j - 1] + (ca != cb)))  # substitution
        precedente = courante
    return precedente[-1]


def qgrammes(s: str, q: int = 2) -> list:
    """Liste (avec répétitions) des q-grammes d'une chaîne ; la chaîne entière si trop courte."""
    if len(s) < q:
        return [s] if s else []
    return [s[i:i + q] for i in range(len(s) - q + 1)]


def dice_qgrammes(a: str, b: str, q: int = 2) -> float:
    """Coefficient de Dice sur multi-ensembles de q-grammes ∈ [0,1].

    Multi-ensemble et non ensemble : « rue rue » et « rue » ne doivent pas être déclarés
    identiques. Insensible à l'ordre des tokens, ce qui convient aux adresses.
    """
    if a == b:
        return 1.0
    ga, gb = qgrammes(a, q), qgrammes(b, q)
    if not ga or not gb:
        return 0.0
    restants = {}
    for g in gb:
        restants[g] = restants.get(g, 0) + 1
    communs = 0
    for g in ga:
        if restants.get(g, 0) > 0:
            restants[g] -= 1
            communs += 1
    return 2.0 * communs / (len(ga) + len(gb))


# ===================== Similarités par attribut ======================================
def _sim_date(a: str, b: str) -> float:
    """Égalité, sinon similarité partielle sur (année, mois, jour).

    Barème DÉCLARÉ, non calibré : 2 composantes sur 3 -> 0.75 ; 1 -> 0.40 ; 0 -> 0.0. Une
    inversion jour/mois (saisie FR vs ISO résiduelle) vaut 0.75 : c'est une erreur de
    format, pas un désaccord de fond. Si l'une des deux dates n'est pas en forme ISO
    (valeur non reconnue conservée telle quelle par la normalisation), on retombe sur
    Jaro-Winkler plutôt que de forcer un désaccord.
    """
    ma, mb = _ISO.match(a), _ISO.match(b)
    if not (ma and mb):
        return jaro_winkler(a, b)
    ya, moa, ja = ma.groups()
    yb, mob, jb = mb.groups()
    if ja == mob and moa == jb and ya == yb and ja != moa:
        return 0.75
    accords = (ya == yb) + (moa == mob) + (ja == jb)
    return {3: 1.0, 2: 0.75, 1: 0.40, 0: 0.0}[accords]


def _sim_code_postal(a: str, b: str) -> float:
    """Égalité, sinon longueur du préfixe commun rapportée à la plus longue des deux.

    « 69003 » / « 69007 » -> 0.8 (même commune, bureau distributeur différent) ;
    « 75011 » / « 13001 » -> 0.0. Monotone et sans table arbitraire.
    """
    prefixe = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        prefixe += 1
    return prefixe / float(max(len(a), len(b)))


def _sim_email(a: str, b: str) -> float:
    """Égalité (1.0), distance d'édition ≤ 1 (0.9), sinon 0.0 — barème du mandat §3.

    Un email est un identifiant : au-delà d'une coquille d'un caractère, deux adresses
    différentes désignent deux boîtes différentes. Aucune similarité graduelle n'est donc
    accordée au-delà de ce seuil.
    """
    if a == b:
        return 1.0
    return 0.9 if levenshtein(a, b) <= 1 else 0.0


def _sim_telephone(a: str, b: str) -> float:
    """Égalité stricte sur la chaîne de chiffres normalisée — barème du mandat §3."""
    return 1.0 if a == b else 0.0


SIMILARITES = {
    "nom": jaro_winkler,
    "prenom": jaro_winkler,
    "ville": jaro_winkler,
    "adresse": dice_qgrammes,
    "date_naissance": _sim_date,
    "code_postal": _sim_code_postal,
    "email": _sim_email,
    "telephone": _sim_telephone,
}


def similarite(attribut: str, valeur_a, valeur_b) -> Optional[float]:
    """Similarité d'un attribut, ou `None` si la valeur manque d'au moins un côté.

    `None` est le signal de l'indétermination : il n'y a pas de similarité « 0 » d'un champ
    absent — une absence n'est pas un désaccord.
    """
    if valeur_a is None or valeur_b is None:
        return None
    brut = SIMILARITES[attribut](valeur_a, valeur_b)
    return round(min(1.0, max(0.0, float(brut))), DECIMALES_SIMILARITE)


def niveau(sim: Optional[float], c_fort: float = C_FORT_DEFAUT,
           c_partiel: float = C_PARTIEL_DEFAUT) -> str:
    """Applique les cutoffs : `None` -> INDETERMINE_MANQUANT, sinon les 3 niveaux du mandat."""
    if sim is None:
        return INDETERMINE_MANQUANT
    if sim >= c_fort:
        return ACCORD_FORT
    if sim >= c_partiel:
        return ACCORD_PARTIEL
    return DESACCORD


def vecteur_comparaison(paire: dict, index_normalise: dict,
                        c_fort: float = C_FORT_DEFAUT,
                        c_partiel: float = C_PARTIEL_DEFAUT) -> dict:
    """COMPARISON_VECTOR d'une CANDIDATE_PAIR.

    Les 8 clés `accord_<attribut>` sont au **premier niveau** du dict : la conformité
    « exactement 8 composantes dans l'énumération fermée » se vérifie alors directement,
    sans convention de lecture intermédiaire. Les similarités brutes sont conservées à
    part, pour la traçabilité, sans se mêler aux composantes.
    """
    a = index_normalise[paire["record_id_a"]]
    b = index_normalise[paire["record_id_b"]]
    vecteur = {
        "record_id_a": paire["record_id_a"],
        "record_id_b": paire["record_id_b"],
        "bloc_origine": list(paire.get("bloc_origine", [])),
    }
    sims = {}
    for attribut in ATTRIBUTS_COMPARE:
        sim = similarite(attribut, a.get(attribut), b.get(attribut))
        sims[attribut] = sim
        vecteur["accord_" + attribut] = niveau(sim, c_fort, c_partiel)
    vecteur["similarites"] = sims
    return vecteur


def composantes(vecteur: dict) -> dict:
    """Les 8 composantes `accord_<attribut>` d'un COMPARISON_VECTOR, isolées."""
    return {cle: vecteur[cle] for cle in COMPOSANTES}


def vecteurs_comparaison(paires, index_normalise: dict,
                         c_fort: float = C_FORT_DEFAUT,
                         c_partiel: float = C_PARTIEL_DEFAUT) -> list:
    """Un COMPARISON_VECTOR par CANDIDATE_PAIR, dans l'ordre des paires (déterminisme)."""
    return [vecteur_comparaison(p, index_normalise, c_fort, c_partiel) for p in paires]
