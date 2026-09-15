"""Orchestration du bloc B2 : records -> CORRESPONDENCE.

    normalisation  ->  blocking  ->  comparateurs  ->  décision

Périmètre STRICT du bloc B2. Sont hors de cette unité et volontairement absents :
la revue du doute en zone grise, le clustering et la fusion en
enregistrements dorés.

Frontière de non-circularité — trois garanties, dont deux structurelles :
  1. aucune dépendance vers `src/scorer` (et réciproquement) ;
  2. la normalisation **projette** les enregistrements sur les 8 attributs comparés et les
     2 identifiants techniques : toute autre colonne présente en entrée est écartée avant
     que quoi que ce soit ne la voie — le moteur est donc incapable de lire une annotation
     de vérité terrain, même si on la lui passait ;
  3. le moteur DÉCIDE ; il ne mesure pas sa propre qualité (c'est le scoreur, séparé).

Déterminisme : aucune source d'aléa non scellée, aucun parcours d'ensemble non trié,
aucun recours à `hash()`. Deux exécutions dans deux processus distincts produisent la même
sortie canonique — c'est vérifié par la suite de tests.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Optional

from . import blocking as blk
from . import compare as cmp
from . import decide as dec
from . import normalize as nrm

__all__ = ["ParametresMoteur", "execute_moteur", "sortie_canonique"]


@dataclass(frozen=True)
class ParametresMoteur:
    """Paramétrage du bloc B2. Gelé : un jeu de paramètres est une donnée, pas un état.

    Les champs listés dans `PARAMETRES_NON_CALIBRES` sont des **placeholders déclarés** :
    ils ne sont issus d'aucun ajustement sur données et la calibration est
    différée après la mesure de qualité. Aucune valeur cible de qualité n'est postulée ici.
    """
    c_fort: float = cmp.C_FORT_DEFAUT
    c_partiel: float = cmp.C_PARTIEL_DEFAUT
    t_mu: float = dec.T_MU_DEFAUT
    t_lambda: float = dec.T_LAMBDA_DEFAUT
    graine_em: str = dec.GRAINE_EM_SCELLEE
    passes_blocking: tuple = blk.PASSES_DEFAUT
    longueur_prefixe: int = blk.LONGUEUR_PREFIXE_DEFAUT
    taille_bloc_max: Optional[int] = None
    max_iter_em: int = dec.MAX_ITER_DEFAUT
    tolerance_em: float = dec.TOLERANCE_DEFAUT

    #: Ce qui, dans ce paramétrage, n'est PAS calibré (mandat §0 constraints).
    PARAMETRES_NON_CALIBRES = ("c_fort", "c_partiel", "t_mu", "t_lambda",
                               "passes_blocking", "longueur_prefixe")

    def __post_init__(self):
        if not 0.0 <= self.c_partiel <= self.c_fort <= 1.0:
            raise ValueError(
                f"cutoffs incoherents : attendu 0 <= c_partiel <= c_fort <= 1, "
                f"recu c_partiel={self.c_partiel}, c_fort={self.c_fort}")
        if self.t_lambda > self.t_mu:
            raise ValueError(
                f"seuils incoherents : T_LAMBDA={self.t_lambda} au-dessus de T_MU={self.t_mu}")


def execute_moteur(records, parametres: Optional[ParametresMoteur] = None) -> dict:
    """Exécute le bloc B2 sur une collection d'enregistrements source.

    Retourne `{"correspondances": [...], "rapport": {...}}` où :
      - `correspondances` porte **exactement une** CORRESPONDENCE par CANDIDATE_PAIR,
        dans l'ordre déterministe des paires ;
      - `rapport` porte tout ce qui n'appartient pas à une paire en particulier : trace de
        blocking, trace d'estimation (convergence, itérations, repli éventuel et son
        motif), table des poids, paramètres employés et ceux qui sont non calibrés.

    La séparation est volontaire : une CORRESPONDENCE reste une décision sur une paire,
    non un fourre-tout de diagnostic.
    """
    parametres = parametres or ParametresMoteur()

    normalises = nrm.normalise_records(records)
    index = {}
    for nrec in normalises:
        rid = nrec.get("record_id")
        if rid is None:
            raise ValueError("enregistrement sans record_id : identification impossible")
        if rid in index:
            raise ValueError(f"record_id duplique : {rid!r}")
        index[rid] = nrec

    bloc = blk.genere_paires_candidates(
        normalises,
        passes=parametres.passes_blocking,
        longueur_prefixe=parametres.longueur_prefixe,
        taille_bloc_max=parametres.taille_bloc_max)

    vecteurs = cmp.vecteurs_comparaison(
        bloc["paires"], index,
        c_fort=parametres.c_fort, c_partiel=parametres.c_partiel)

    estimation = dec.estime_m_u(
        vecteurs,
        graine=parametres.graine_em,
        max_iter=parametres.max_iter_em,
        tolerance=parametres.tolerance_em)

    poids = dec.table_de_poids(estimation["m"], estimation["u"])

    liste = dec.correspondances(vecteurs, poids,
                                t_mu=parametres.t_mu, t_lambda=parametres.t_lambda)

    repartition = {v: 0 for v in dec.VERDICTS}
    for corr in liste:
        repartition[corr["verdict"]] += 1

    trace_estimation = {cle: valeur for cle, valeur in estimation.items()
                        if cle not in ("m", "u")}
    trace_estimation["m"] = estimation["m"]
    trace_estimation["u"] = estimation["u"]

    rapport = {
        "n_records": len(normalises),
        "n_paires": len(liste),
        "blocking": bloc["trace"],
        "estimation": trace_estimation,
        "poids": poids,
        "repartition_verdicts": repartition,
        "parametres": _parametres_serialisables(parametres),
        "parametres_non_calibres": list(ParametresMoteur.PARAMETRES_NON_CALIBRES),
        # Ce que `execute_moteur` ne fait PAS. Champs MACHINE, lus en aval : ils doivent
        # rester VRAIS après chaque unité livrée, sans quoi la sortie du moteur
        # contredirait les artefacts publiés à côté d'elle.
        #
        # La partition est celle-ci : `instruit_en_aval` liste
        # ce qui est CONSTRUIT et consomme cette sortie sans la modifier ;
        # `hors_perimetre_u_b2` liste ce qui n'appartient pas à ce paquet, définitivement.
        # Clustering et fusion étaient rangés dans le second bien que construits depuis leur merge —
        # ils passent donc dans le premier, à côté de la revue. Ce qui reste dehors l'est par
        # construction, non par calendrier : la mesure de qualité doit rester indépendante
        # du moteur (non-circularité de la preuve), et la comparaison à l'état de l'art
        # dépend de ce paquet sans que l'inverse soit jamais vrai.
        "hors_perimetre_u_b2": [
            "mesure de qualite P/R/F : hors de ce paquet par construction, "
            "c'est la condition de non-circularite de la preuve",
            "comparaison a l'etat de l'art : depend de ce paquet, "
            "jamais l'inverse",
        ],
        "instruit_en_aval": [
            "revue zone grise : passe posterieure, "
            "consomme cette sortie sans la modifier",
            "clustering et fusion : passes posterieures, "
            "consomment cette sortie sans la modifier",
        ],
    }
    return {"correspondances": liste, "rapport": rapport}


def _parametres_serialisables(parametres: ParametresMoteur) -> dict:
    """Vue JSON des paramètres (les tuples deviennent des listes)."""
    brut = asdict(parametres)
    brut["passes_blocking"] = list(parametres.passes_blocking)
    return brut


def sortie_canonique(resultat: dict) -> str:
    """Sérialisation canonique et stable d'un résultat de moteur.

    `sort_keys` neutralise l'ordre d'insertion des dicts, `separators` fige l'espacement,
    `ensure_ascii=False` conserve les accents tels quels. C'est la forme comparée par le
    test de déterminisme inter-processus.

    Volontairement **indépendante** de la canonicalisation du générateur : le moteur ne
    doit dépendre ni du générateur ni d'un format de pack particulier — il tourne sur
    n'importe quelle collection d'enregistrements, y compris celle d'un banc d'essai.
    """
    return json.dumps(resultat, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))
