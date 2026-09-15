# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Baselines — les règles « d'une heure » que le moteur doit battre.

Le mandat exige « au moins : match exact déterministe, et une règle simple type Jaccard/seuil ».
Le piège de cet exercice est connu et il est grave : une baseline faible rend la cible
triviale, et l'écart publié ne démontre alors rien. Ces baselines sont donc écrites pour être
**fortes** — ce qu'un ingénieur compétent produirait réellement en une heure s'il n'avait ni
moteur ni Splink.

## B4 est l'ABLATION de Fellegi-Sunter, et c'est elle qui donne son sens au banc
B4 reçoit exactement la même information que le moteur : les mêmes 8 champs, les mêmes
valeurs normalisées, la même tolérance à la coquille. Elle en diffère par une seule chose —
elle **compte** les concordances au lieu d'**agréger des log-vraisemblances estimées par EM**.
L'écart entre B4 et le moteur mesure donc précisément ce que la pondération apprise achète.
Sans elle, le banc opposerait « moteur contre jouet » ; avec elle, il oppose « pondération
probabiliste contre comptage k-sur-n », qui est la question intéressante.

## B0 borne, il ne concourt pas
« Tout candidat est un MATCH » est un ÉTALON : son rappel EST le plafond de rappel de tout
système consommant le même ensemble candidat, et sa précision EST la prévalence — le plancher
contre lequel toute précision se lit. Exiger de le battre de 30 points de rappel serait
mathématiquement impossible ; il est publié, jamais opposé (`BASELINES["B0"]["concourt"]`).

## Les seuils sont défendus A PRIORI, jamais ajustés
`0,50` pour Jaccard : le point où les jetons partagés égalent exactement les jetons non
partagés, seul point remarquable de l'échelle. `0,85` pour la similarité de champ : tolérer
environ une édition dans un patronyme français de longueur typique. `3` pour le vote : nom +
prénom valent 2 concordances, c'est-à-dire l'HOMONYMIE ; 3 est le plus petit entier qu'une
homonymie ne peut pas produire. Aucune de ces valeurs n'a été choisie en regardant un résultat.

## Non-circularité
Bibliothèque standard seule. Aucun import de `scorer`, aucune vérité terrain, aucune métrique.
"""
from __future__ import annotations

import difflib

from . import contrat_bench as cb

__all__ = ["BASELINES", "BASELINE_DE_TETE", "VARIANTES_B4_PUBLIEES", "execute", "familles_non_degenerees"]

CHAMPS = cb.ATTRIBUTS
CHAMPS_TEXTE = ("nom", "prenom", "adresse", "ville")
TRIPLET_IDENTITE = ("nom", "prenom", "date_naissance")
CLES_FORTES = ("email", "telephone")

SEUIL_JACCARD = 0.5
SEUIL_SIMILARITE_CHAMP = 0.85
CONCORDANCES_EXIGEES = 3


def _egal(a, b) -> bool:
    """Un absent n'égale jamais rien — pas même un autre absent.

    Sans cette règle, deux enregistrements dépourvus d'email « concorderaient » sur l'email,
    et la baseline apparierait les incomplets entre eux. C'est la convention du moteur
    (manquant n'est pas désaccord), reprise ici pour que la comparaison porte sur la règle de
    décision et non sur un traitement divergent des valeurs absentes.
    """
    return a is not None and b is not None and a == b


def b0_tout_candidat(ra, rb) -> float:
    """ÉTALON : toute paire candidate est un MATCH. Score constant."""
    return 1.0


def b1_exact_triplet(ra, rb) -> float:
    """Match exact déterministe sur les champs d'IDENTITÉ CIVILE.

    La lecture maximaliste — conjonction des 8 champs — est REFUSÉE comme homme de paille :
    elle exigerait que deux enregistrements du même individu s'accordent aussi sur l'adresse
    (les déménagements sont annoncés par la fixture) et sur l'email (35 % d'absence mesurée).
    Le choix des trois champs se lit sur le SCHÉMA seul : identité vs volatil vs optionnel.
    """
    return 1.0 if all(_egal(ra.get(c), rb.get(c)) for c in TRIPLET_IDENTITE) else 0.0


def b2_cle_forte(ra, rb) -> float:
    """Disjonction d'identifiants forts : email OU téléphone OU triplet d'identité.

    Ne pas écrire cette disjonction serait la façon classique et discrète d'affaiblir le
    « match exact » : c'est trois lignes que personne n'oublie en pratique.
    """
    if any(_egal(ra.get(c), rb.get(c)) for c in CLES_FORTES):
        return 1.0
    return b1_exact_triplet(ra, rb)


def jetons(nrec) -> frozenset:
    """Sac de jetons : champs rédactionnels éclatés sur l'espace, champs structurés atomiques.

    Aucune étiquette de champ n'est portée : l'insensibilité au champ d'origine est la
    faiblesse ASSUMÉE de la méthode Jaccard, pas un handicap fabriqué pour la faire perdre.
    """
    sortie = []
    for champ in CHAMPS:
        valeur = nrec.get(champ)
        if not valeur:
            continue
        if champ in CHAMPS_TEXTE:
            sortie.extend(t for t in valeur.split(" ") if t)
        else:
            sortie.append(valeur)
    return frozenset(sortie)


def b3_jaccard(ra, rb) -> float:
    """Jaccard des sacs de jetons. La baseline explicitement nommée par le mandat.

    Seule baseline à score CONTINU, donc la seule dont la distribution se prête à une lecture
    fine du compromis précision/rappel.
    """
    sa, sb = jetons(ra), jetons(rb)
    union = len(sa | sb)
    return (len(sa & sb) / union) if union else 0.0


def similarite_texte(a, b) -> float:
    """Similarité de deux champs texte. `autojunk=False` : sinon le ratio dépend de la longueur.

    Le filtre heuristique de `difflib` traite les caractères très fréquents comme du bruit dès
    que la chaîne dépasse 200 caractères ; sur des adresses longues, il rendrait le seuil de
    0,85 non comparable d'un champ à l'autre.
    """
    if a is None or b is None:
        return 0.0
    return 1.0 if a == b else difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def b4_concordance(ra, rb) -> float:
    """Vote k-sur-n : le nombre de champs concordants parmi les 8. L'ABLATION du moteur.

    Un champ absent d'au moins un côté n'est ni concordance ni discordance : il n'est pas
    compté — même convention que le moteur, pour que l'écart mesure la pondération et non le
    traitement des manquants.
    """
    n = 0
    for champ in CHAMPS:
        va, vb = ra.get(champ), rb.get(champ)
        if va is None or vb is None:
            continue
        if champ in CHAMPS_TEXTE:
            n += 1 if similarite_texte(va, vb) >= SEUIL_SIMILARITE_CHAMP else 0
        else:
            n += 1 if va == vb else 0
    return float(n)


def b5_cle_forte_ou_concordance(ra, rb) -> float:
    """BASELINE DE TÊTE : clé forte exacte OU au moins 3 champs concordants.

    B2 et B4 ne s'emboîtent pas : chacune attrape des paires que l'autre manque. Un ingénieur
    qui a écrit les deux les réunit par un OU sans y penser. Les publier séparément, chacune
    sous-maximale, serait l'homme de paille le plus subtil du dispositif.

    Le score EST la fonctionnelle de décision (`max` des deux voies), de sorte qu'un balayage
    de seuil sur ce score reproduit exactement le verdict — sans quoi le point 2 « volume
    égalisé » classerait selon un ordre étranger à la règle.
    """
    n = b4_concordance(ra, rb)
    forte = any(_egal(ra.get(c), rb.get(c)) for c in CLES_FORTES)
    return max(n, float(CONCORDANCES_EXIGEES) if forte else 0.0)


#: Inventaire FERMÉ. `concourt` dit si la baseline entre dans l'arithmétique des cibles.
BASELINES = {
    "B0_tout_candidat": {"fn": b0_tout_candidat, "seuil": 1.0, "concourt": False,
                         "role": "etalon : plafond de rappel et plancher de precision"},
    "B1_exact_triplet": {"fn": b1_exact_triplet, "seuil": 1.0, "concourt": True,
                         "role": "match exact deterministe (exige par le mandat)"},
    "B2_cle_forte": {"fn": b2_cle_forte, "seuil": 1.0, "concourt": True,
                     "role": "disjonction d'identifiants forts"},
    # Le nom est celui de l'INVENTAIRE GELÉ (`criteres_ub6.BASELINES`) : c'est l'implémentation
    # qui se conforme au pré-enregistrement, jamais l'inverse.
    "B3_jaccard_jetons": {"fn": b3_jaccard, "seuil": SEUIL_JACCARD, "concourt": True,
                   "role": "regle simple a seuil (exigee par le mandat) ; score continu"},
    "B4_concordance_3_sur_8": {"fn": b4_concordance, "seuil": float(CONCORDANCES_EXIGEES),
                               "concourt": True,
                               "role": "ablation de Fellegi-Sunter : comptage non pondere"},
    "B5_cle_forte_ou_concordance": {"fn": b5_cle_forte_ou_concordance,
                                    "seuil": float(CONCORDANCES_EXIGEES), "concourt": True,
                                    "role": "baseline de TETE : la meilleure regle d'une heure"},
}
BASELINE_DE_TETE = "B5_cle_forte_ou_concordance"

#: `k = 2..8` de B4, TOUTES publiées. Ne publier que le meilleur `k` donnerait à la baseline
#: un avantage d'oracle que le moteur n'a pas — l'inverse du biais que l'on redoute, mais un
#: biais tout de même.
VARIANTES_B4_PUBLIEES = tuple(range(2, 9))

#: Une baseline à score entier non signé n'a pas de frontière neutre : DIMS lui est
#: inapplicable (cf. `points.py`).
MODE_POINT_2 = "volume_egalise"


def familles_non_degenerees() -> tuple:
    """Les baselines qui CONCOURENT — B0 en est exclu par construction, pas après coup."""
    return tuple(nom for nom, d in BASELINES.items() if d["concourt"])


def execute(substrat, nom_baseline: str = BASELINE_DE_TETE, paires=None, seuil=None) -> dict:
    """Évalue une baseline sur un ensemble de paires et rend le contrat commun.

    `paires` vaut par défaut l'ensemble candidat `C0` du substrat (bras apparié). Le bras B
    lui passe l'espace complet : une baseline n'a pas de blocking, et lui en prêter un serait
    lui prêter une compétence qu'elle n'a pas.
    """
    if nom_baseline not in BASELINES:
        raise KeyError(f"baseline inconnue : {nom_baseline!r}")
    definition = BASELINES[nom_baseline]
    fn = definition["fn"]
    seuil_effectif = definition["seuil"] if seuil is None else seuil
    index = {r["record_id"]: r for r in substrat.normalises}
    paires = substrat.c0 if paires is None else paires

    scores = []
    for (ida, idb) in paires:
        a, b = cb.cle(ida, idb)
        score = float(fn(index[a], index[b]))
        scores.append({
            "record_id_a": a, "record_id_b": b,
            "poids_match": round(score, cb.DECIMALES_LIVRAISON),
            "verdict_natif": cb.MATCH if score >= seuil_effectif else cb.NON_MATCH,
        })
    scores.sort(key=lambda s: (s["record_id_a"], s["record_id_b"]))

    n_match = sum(1 for s in scores if s["verdict_natif"] == cb.MATCH)
    diagnostic = {
        "systeme": nom_baseline,
        "role": definition["role"],
        "concourt_aux_cibles": definition["concourt"],
        "seuil_declare": seuil_effectif,
        "n_paires": len(scores),
        "n_match_declares": n_match,
        "n_valeurs_de_score_distinctes": len({s["poids_match"] for s in scores}),
        "parametres_declares": {
            "champs": list(CHAMPS), "champs_texte": list(CHAMPS_TEXTE),
            "triplet_identite": list(TRIPLET_IDENTITE), "cles_fortes": list(CLES_FORTES),
            "seuil_jaccard": SEUIL_JACCARD,
            "seuil_similarite_champ": SEUIL_SIMILARITE_CHAMP,
            "concordances_exigees": CONCORDANCES_EXIGEES,
        },
        "substrat": ("recoit la normalisation FR du moteur — concession DECLAREE qui rend les "
                     "baselines plus fortes, donc la cible O-P1 plus dure (asymetrie A9)"),
    }
    return {"systeme": nom_baseline, "scores": scores, "diagnostic": diagnostic}
