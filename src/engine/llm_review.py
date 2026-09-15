"""Revue hors ligne du doute en zone grise.

    correspondances (dont ZONE_GRISE)  ->  adjudication paire a paire  ->  correspondances
                                                                          ENRICHIES

## Une passe AVAL, jamais un branchement dans le moteur
La revue prend la liste de CORRESPONDENCE produite par le bloc B2 et en rend une
**nouvelle**. Elle ne modifie pas `execute_moteur`, qui continue de poser le marqueur
`en_attente` sur chaque paire indéterminée. Ce n'est pas un choix de style : la sortie du
moteur est épinglée par la suite du moteur, et l'entrée reçue ici n'est jamais mutée — deux
exécutions de la revue sur la même liste rendent le même résultat, et la liste d'origine
reste comparable à l'octet près.

## Périmètre STRICT
Seules les paires `verdict == ZONE_GRISE` sont instruites. Une paire déjà tranchée n'est ni
relue, ni re-soumise, ni modifiée : la revue **enrichit** le doute, elle ne rejuge pas ce
qui a été décidé.

## Prudence
`NON_TRANCHE` laisse la paire indéterminée. Une paire n'est **jamais** promue sans preuve :
l'ambiguïté d'une réponse, un raté de rejeu, un adjudicateur injoignable ou un budget épuisé
mènent tous à « on ne sait pas », **jamais** à « c'est un lien ».

## Budget et repli tracé
Le budget compte les **paires tentées**, pas les questions distinctes — deux paires posant
la même question consomment deux unités. L'alternative (compter les questions) ferait
dépendre l'ensemble effectivement instruit du nombre de doublons rencontrés avant
l'épuisement, donc d'un ordre que la déclaration ne décrit pas. Le coût déclaré par un
client est publié **à côté**, et n'entre jamais dans la coupe : sans cela, changer de client
changerait l'ensemble revu, donc la contribution mesurée.

L'ordre d'instruction est l'ordre canonique des identifiants de paire. Il est
délibérément **indépendant de l'agrégat de vraisemblance** : ordonner par l'agrégat ferait
d'une coupe budgétaire un « k premiers par agrégat », si bien que l'ensemble promu serait
par construction un sous-ensemble d'un simple seuillage — et la revue ne pourrait plus
apporter autre chose que ce que le moteur savait déjà.

## Frontière de non-circularité
Ce module ne lit d'une correspondance que son identité et son verdict, et des
enregistrements que les 8 attributs comparés — lesquels sont, sur une entrée normalisée,
les seuls présents. Il ne mesure aucune qualité : la mesure de ce que la revue apporte est
un travail d'outillage, séparé par construction, et elle vit hors du moteur.
"""
from __future__ import annotations

from typing import Optional

from . import llm_client as clt
from .decide import MATCH, ZONE_GRISE

__all__ = [
    "STATUTS", "EN_ATTENTE", "REVUE", "NON_REVUE", "MOTIFS_NON_REVUE",
    "revue_des_correspondances", "ensemble_de_match", "UNITE_BUDGET",
]

# --- Statuts d'instruction (énumération FERMÉE) --------------------------------------
#: Posé par le moteur : la paire est indéterminée et n'a pas encore été soumise.
EN_ATTENTE = "en_attente"
#: Soumise, et une décision a été rendue (y compris `NON_TRANCHE`).
REVUE = "revue"
#: Non soumise, ou soumise sans réponse exploitable. Le motif dit toujours laquelle.
NON_REVUE = "non_revue"
STATUTS = (EN_ATTENTE, REVUE, NON_REVUE)

#: Motifs de non-revue, jeu de clés FIXE : le compte est initialisé à zéro pour chacun,
#: de sorte qu'un motif jamais rencontré vaille `0` et non une clé absente. Un lecteur
#: aval n'a donc pas à distinguer « aucun » de « pas de champ ».
MOTIFS_NON_REVUE = ("budget_epuise", "adjudicateur_indisponible", "reponse_absente")

#: Ce que le budget décompte. Publié, pour que la coupe soit lisible sans lire le code.
UNITE_BUDGET = "paires_tentees"


def _copie(correspondance: dict) -> dict:
    """Copie d'une CORRESPONDENCE, détachée de l'originale sur toute sa profondeur utile.

    Écrite à la main plutôt qu'avec `copy.deepcopy` : `copy` n'est pas dans la liste
    blanche d'imports du moteur. Une CORRESPONDENCE n'imbrique qu'un niveau de dicts et de
    listes, donc ce détachement est complet — et l'invariant « l'entrée n'est pas mutée »
    est éprouvé par la suite de tests plutôt que supposé ici.
    """
    sortie = {}
    for cle, valeur in correspondance.items():
        if isinstance(valeur, dict):
            sortie[cle] = dict(valeur)
        elif isinstance(valeur, list):
            sortie[cle] = list(valeur)
        else:
            sortie[cle] = valeur
    return sortie


def _marqueur(statut: str, decision, justification: str = "",
              motif: Optional[str] = None, cle: Optional[str] = None) -> dict:
    """Marqueur de revue écrit dans une correspondance de zone grise.

    Conserve `unite_responsable`, comme le marqueur `en_attente` que pose le moteur : la
    forme reste reconnaissable d'un bout à l'autre de la chaîne.
    """
    return {"statut": statut, "decision": decision, "justification": justification,
            "motif": motif, "cle_revue": cle, "unite_responsable": "revue_zone_grise"}


def revue_des_correspondances(correspondances, index_normalise: dict, client,
                              budget: Optional[int] = None,
                              strict: bool = True) -> dict:
    """Instruit les paires en ZONE_GRISE et rend `{"correspondances", "trace"}`.

    `client` est soit un `ClientRejeu` (déterministe, alimenté par une transcription déjà
    chargée), soit tout objet exposant `repond(invite)`. Le rejeu est interrogé **par clé**,
    ce qui court-circuite le rendu textuel sans changer la question posée.

    `strict` gouverne le raté de rejeu : à `True` (défaut), une réponse absente est un
    défaut **tracé** qui laisse la paire indéterminée. Le drapeau est publié dans la trace,
    faute de quoi une revue partielle serait indiscernable d'une revue complète.

    La trace porte l'identité de conservation `n_revues + n_non_revues + n_en_attente ==
    n_zone_grise` : sur un run complet, `n_en_attente` vaut zéro, et un écart signale un
    défaut d'orchestration au lieu de se fondre dans un décompte fourre-tout.
    """
    rendues, motifs = [], {motif: 0 for motif in MOTIFS_NON_REVUE}
    decisions = {decision: 0 for decision in clt.DECISIONS}
    n_grises = n_revues = n_non_revues = n_en_attente = n_tentees = 0

    # Ordre canonique, indépendant de l'agrégat : voir le docstring du module.
    grises = sorted((c["record_id_a"], c["record_id_b"]) for c in correspondances
                    if c["verdict"] == ZONE_GRISE)
    a_instruire = set(grises if budget is None else grises[:max(0, int(budget))])

    for correspondance in correspondances:
        copie = _copie(correspondance)
        if copie["verdict"] != ZONE_GRISE:
            rendues.append(copie)                      # jamais touchée
            continue
        n_grises += 1
        identite = (copie["record_id_a"], copie["record_id_b"])
        if identite not in a_instruire:
            motifs["budget_epuise"] += 1
            n_non_revues += 1
            copie["revue_zone_grise"] = _marqueur(
                NON_REVUE, None, motif="budget_epuise")
            rendues.append(copie)
            continue

        n_tentees += 1
        charge = clt.charge_de_revue(index_normalise[identite[0]],
                                     index_normalise[identite[1]])
        cle = clt.cle_de_charge(charge)
        try:
            if hasattr(client, "repond_a_cle"):
                texte = client.repond_a_cle(cle)
            else:
                texte = client.repond(clt.invite_de_charge(charge))
        except clt.AdjudicationIndisponible:
            motifs["adjudicateur_indisponible"] += 1
            n_non_revues += 1
            copie["revue_zone_grise"] = _marqueur(
                NON_REVUE, None, motif="adjudicateur_indisponible", cle=cle)
            rendues.append(copie)
            continue
        except clt.ReponseAbsente:
            if not strict:
                raise
            motifs["reponse_absente"] += 1
            n_non_revues += 1
            copie["revue_zone_grise"] = _marqueur(
                NON_REVUE, None, motif="reponse_absente", cle=cle)
            rendues.append(copie)
            continue

        decision, justification = clt.analyse_reponse(texte)
        decisions[decision] += 1
        n_revues += 1
        copie["revue_zone_grise"] = _marqueur(REVUE, decision, justification, cle=cle)
        rendues.append(copie)

    trace = {
        "n_correspondances": len(rendues),
        "n_zone_grise": n_grises,
        "n_tentees": n_tentees,
        "n_revues": n_revues,
        "n_non_revues": n_non_revues,
        "n_en_attente": n_en_attente,
        "decisions": decisions,
        "motifs_non_revue": motifs,
        "budget": budget,
        "unite_budget": UNITE_BUDGET,
        "mode_strict": strict,
        "client": client.description() if hasattr(client, "description") else {},
        "ordre_instruction": "identifiants de paire (independant de l'agregat)",
        "perimetre": "paires ZONE_GRISE seules ; MATCH et NON_MATCH jamais touches",
    }
    if trace["n_revues"] + trace["n_non_revues"] + trace["n_en_attente"] != n_grises:
        raise AssertionError(
            f"identite de conservation rompue : {trace['n_revues']} revues + "
            f"{trace['n_non_revues']} non revues + {trace['n_en_attente']} en attente "
            f"!= {n_grises} paires en zone grise")
    return {"correspondances": rendues, "trace": trace}


def ensemble_de_match(correspondances) -> list:
    """Paires retenues comme liens APRÈS revue : MATCH du moteur ∪ MATCH_APRES_REVUE.

    C'est l'entrée de l'unité aval. La comparaison se fait par **égalité** sur le jeton de
    décision, jamais par test de sous-chaîne : le jeton de rejet contient le jeton de
    promotion, si bien qu'un `in` retournerait le sens d'un refus.
    """
    retenues = []
    for correspondance in correspondances:
        if correspondance["verdict"] != ZONE_GRISE:
            # Le jeton est IMPORTÉ de la décision, jamais retapé : un littéral se
            # désolidariserait en silence si l'énumération des verdicts changeait, et les
            # matchs du moteur seraient perdus sans qu'aucune exception ne le signale.
            if correspondance["verdict"] == MATCH:
                retenues.append(correspondance)
            continue
        marqueur = correspondance["revue_zone_grise"] or {}
        if marqueur.get("decision") == clt.MATCH_APRES_REVUE:
            retenues.append(correspondance)
    return retenues
