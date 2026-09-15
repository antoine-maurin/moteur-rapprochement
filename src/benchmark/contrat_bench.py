# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Contrat de sortie commun aux trois systèmes comparés.

Un système du banc est une paire `(adaptateur, configuration gelée)`. Tout adaptateur —
moteur maison, Splink, baselines — expose la **même** signature et rend la **même** forme :

    execute(substrat, ...) -> {"systeme": str, "scores": [SCORE, ...], "diagnostic": {...}}
    SCORE = {"record_id_a", "record_id_b", "poids_match": float, "verdict_natif": str}

C'est ce contrat, et lui seul, qui permet à `tools/banc_ub6.py` de noter les trois systèmes
par **un unique chemin d'appel**, sans une seule branche `if systeme == ...` : la loyauté L3
n'est pas une promesse de relecture, c'est une propriété du code.

## Pourquoi une règle de complétion écrite d'avance
Un système peut ne pas émettre de score pour une paire candidate (Splink filtre, une baseline
peut refuser de se prononcer). Sans règle gelée, un système pourrait « ne pas répondre » sur
ses cas difficiles et voir sa précision monter mécaniquement — la paire disparaîtrait du
dénominateur au lieu de compter comme une erreur. `complete_sur_C0` la réintroduit en
`NON_MATCH`, à un score strictement inférieur à tout ce que ce système a émis, et **publie le
nombre de complétions** : une complétion massive est alors visible, pas silencieuse.

## Frontière de non-circularité
Ce module importe `engine` — jamais `scorer`. Les constantes de verdict sont reprises du
moteur plutôt que re-déclarées : le banc n'a pas à inventer un troisième vocabulaire, et
l'adhérence est vérifiable. Aucune métrique de qualité n'est calculée ici.
"""
from __future__ import annotations

import engine

__all__ = [
    "ATTRIBUTS", "MATCH", "NON_MATCH", "ZONE_GRISE", "VERDICTS", "DECIMALES_LIVRAISON",
    "cle", "cles", "valide_scores", "complete_sur_C0", "en_correspondances",
    "projette_3_zones", "ErreurContratBanc",
]

#: Les 8 attributs comparés — exactement ceux du moteur, ni un de plus ni un de moins (L6).
ATTRIBUTS = engine.ATTRIBUTS_COMPARE

MATCH = engine.MATCH
NON_MATCH = engine.NON_MATCH
ZONE_GRISE = engine.ZONE_GRISE
VERDICTS = (MATCH, NON_MATCH, ZONE_GRISE)

#: Grille de livraison des scores, alignée sur l'arrondi de `decide.agregat`. Deux systèmes
#: dont les scores sont livrés à des granularités différentes ne sont pas comparables au bit
#: près, et la dérive flottante multi-thread se rattrape ici plutôt qu'ailleurs.
DECIMALES_LIVRAISON = 9


class ErreurContratBanc(RuntimeError):
    """Toute anomalie de contrat fait ÉCHOUER BRUYAMMENT.

    Le banc ne publie jamais un chiffre douteux : un adaptateur qui viole le contrat produit
    un artefact, pas une mesure dégradée.
    """


def cle(record_id_a, record_id_b) -> tuple:
    """Clé canonique d'une paire non ordonnée : `(min, max)` en comparaison de chaînes."""
    a, b = str(record_id_a), str(record_id_b)
    return (a, b) if a <= b else (b, a)


def cles(scores) -> set:
    """Ensemble des clés canoniques d'une liste de SCORE."""
    return {cle(s["record_id_a"], s["record_id_b"]) for s in scores}


def valide_scores(scores, nom_systeme: str) -> dict:
    """Audit de FORME de la sortie d'un adaptateur, avant que l'oracle ne la voie.

    Distinct de `scorer.valide_correspondances`, et volontairement : celui-ci s'exécute côté
    banc, sans jamais importer le scoreur, et attrape les fautes d'ADAPTATION (doublon,
    auto-paire, orientation, score non fini) avant qu'elles ne se présentent à la mesure sous
    l'apparence d'un défaut du système.
    """
    vues, doublons, auto, non_finis, verdicts_inconnus = set(), [], [], [], []
    for s in scores:
        a, b = s.get("record_id_a"), s.get("record_id_b")
        if a == b:
            auto.append(a)
            continue
        k = cle(a, b)
        if k in vues:
            doublons.append(k)
        vues.add(k)
        p = s.get("poids_match")
        if not isinstance(p, (int, float)) or isinstance(p, bool) or p != p or p in (
                float("inf"), float("-inf")):
            non_finis.append(k)
        if s.get("verdict_natif") not in (MATCH, NON_MATCH):
            verdicts_inconnus.append(s.get("verdict_natif"))
    constats = {
        "systeme": nom_systeme, "n_scores": len(scores), "n_cles_distinctes": len(vues),
        "doublons": sorted(doublons), "auto_paires": sorted(auto),
        "poids_non_finis": sorted(non_finis),
        "verdicts_natifs_inconnus": sorted(set(verdicts_inconnus)),
    }
    constats["alerte"] = bool(doublons or auto or non_finis or verdicts_inconnus)
    if constats["alerte"]:
        raise ErreurContratBanc(f"contrat de banc viole par {nom_systeme} : {constats}")
    return constats


def complete_sur_C0(scores, c0) -> dict:
    """Complète la sortie d'un système pour qu'elle couvre EXACTEMENT l'ensemble candidat.

    Règle GELÉE (`criteres_ub6.REGLE_DE_COMPLETION`) : une paire de `c0` non émise reçoit
    `NON_MATCH` et un `poids_match` valant le score fini MINIMAL émis par CE système, moins
    1,0 — donc strictement en dessous de tout ce qu'il a produit, sans jamais emprunter
    l'échelle d'un autre système. Le nombre de complétions est retourné et publié.

    Lève si un système a émis des paires HORS de `c0` : dans le bras apparié, cela signifie
    que son blocking n'a pas été correctement contraint, et masquer l'écart reviendrait à
    comparer deux univers en prétendant qu'ils sont un.
    """
    attendues = {cle(a, b) for (a, b) in c0}
    presentes = cles(scores)
    hors_perimetre = sorted(presentes - attendues)
    if hors_perimetre:
        raise ErreurContratBanc(
            f"{len(hors_perimetre)} paire(s) hors de l'ensemble candidat impose, "
            f"p. ex. {hors_perimetre[:5]}")

    manquantes = sorted(attendues - presentes)
    finis = [s["poids_match"] for s in scores]
    plancher = (min(finis) - 1.0) if finis else -1.0
    complements = [{"record_id_a": a, "record_id_b": b, "poids_match": plancher,
                    "verdict_natif": NON_MATCH, "complete": True}
                   for (a, b) in manquantes]
    complets = sorted(list(scores) + complements,
                      key=lambda s: cle(s["record_id_a"], s["record_id_b"]))
    return {
        "scores": complets,
        "n_completions": len(complements),
        "plancher_de_completion": plancher,
        "regle": ("paire de C0 non emise -> NON_MATCH, poids = min(scores emis) - 1,0 ; "
                  "le nombre de completions est publie par systeme"),
    }


def projette_3_zones(r: float, t_mu: float, t_lambda: float) -> str:
    """Projection en 3 zones — DÉLÉGUÉE au moteur, jamais réimplémentée.

    Réimplémenter la comparaison de bornes ici ferait diverger le banc du moteur exactement
    là où c'est indétectable : sur l'inclusion des bornes (`r > t_mu`, et non `>=`). Un
    système tiers projeté par une règle légèrement différente de celle du moteur serait
    désavantagé sans que rien ne le signale.
    """
    return engine.verdict_3_zones(r, t_mu, t_lambda)


def en_correspondances(scores, verdicts) -> list:
    """Assemble les CORRESPONDENCE au contrat que l'oracle attend.

    `verdicts` est un dict `{cle: verdict}` produit par `points.py`. La séparation est
    délibérée : l'adaptateur produit des SCORES, le point de fonctionnement produit des
    VERDICTS, et ce module ne fait que les agrafer. Aucun des trois ne peut donc, à lui
    seul, décider à la fois du score et du seuil.
    """
    sortie = []
    for s in scores:
        k = cle(s["record_id_a"], s["record_id_b"])
        verdict = verdicts.get(k)
        if verdict not in VERDICTS:
            raise ErreurContratBanc(f"verdict absent ou hors enumeration pour {k} : {verdict!r}")
        sortie.append({
            "record_id_a": k[0], "record_id_b": k[1],
            "poids_match": s["poids_match"], "verdict": verdict,
        })
    sortie.sort(key=lambda c: (c["record_id_a"], c["record_id_b"]))
    return sortie
