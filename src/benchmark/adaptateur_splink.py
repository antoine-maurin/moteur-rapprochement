# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Adaptateur SPLINK 4.0.16 — le SEUL fichier du dépôt qui importe `splink` (mandat §4).

Splink est une dépendance de **banc**, jamais du produit : `src/engine/` et `src/scorer/`
restent bibliothèque standard seule et hors réseau (C7), et un test structurel le vérifie
dans les deux sens.

## Alignement d'échelle — la condition sans laquelle le point 2 serait truqué
Le `match_weight` de Splink vaut `log2(λ/(1−λ)) + Σⱼ log2(bfⱼ)` ; le `R` du moteur est la
seule somme `Σⱼ log2(mⱼ/uⱼ)`, sans terme a priori. Le score livré ici est donc
`match_weight − log2(λ/(1−λ))` : les deux grandeurs redeviennent la **même quantité
physique**, et la frontière `0` reprend la même signification des deux côtés. Sans ce
retranchement, appliquer la bande DIMS (frontière évidentielle 0,0) à Splink placerait sa
zone grise ailleurs que celle du moteur tout en prétendant appliquer la même règle. Un
contrôle vérifie l'identité ligne à ligne plutôt que de la supposer.

`match_weight` et `match_probability` bruts restent publiés en champs annexes : le retrait du
prior est une transformation **monotone**, elle ne change aucun classement, et un lecteur doit
pouvoir refaire le calcul.

## Ce que le seuil natif est, et ce qu'il n'est pas
Splink ne rend pas de verdict : il rend un score. `match_probability >= 0,5` — équivalent à
`match_weight >= 0` — est la règle de Bayes à coûts égaux, défaut documenté de la
bibliothèque. C'est le point 1, choisi **sans avoir vu la moindre métrique de qualité**.

**Interdit et pré-enregistré** : transposer les seuils ±8 bits du moteur sur la distribution
de Splink. Mesuré en reconnaissance, cela verse 55 % des paires en ZONE_GRISE, que la
convention stricte compte ensuite comme prédit-négatif — un seuil pensé pour une autre
échelle anéantirait son rappel, et l'écart mesurerait ma transposition, pas Splink.

## Déterminisme, et les deux pièges qui le cassent en silence
  - `seed=0` **désactive** l'échantillonnage répétable : le dialecte duckdb teste `if seed:`.
    La graine est donc strictement positive.
  - dès que `max_pairs >= C(n,2)`, l'échantillonnage de `u` devient **exhaustif** et il n'y a
    plus d'aléa du tout — propriété plus forte qu'une graine, et vérifiée en reconnaissance
    (graines différentes, tables `u` identiques).
  - `threads = 1` et livraison arrondie à 9 décimales absorbent la dérive flottante.

## Hors réseau
Aucune extension duckdb téléchargeable n'est autorisée, et `splink.datasets` — le seul point
d'entrée réseau de la bibliothèque — n'est jamais touché.

## Non-circularité
N'importe pas `scorer`. Ne lit ni `ground_truth` ni `corruption_annotation`. Ne calcule
aucune métrique de qualité : il rend des scores, que l'oracle notera ailleurs.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import multiprocessing
import time

import duckdb
import splink.comparison_level_library as cll
import splink.comparison_library as cl
from splink import DuckDBAPI, Linker, SettingsCreator, block_on

from . import contrat_bench as cb

__all__ = ["NOM", "MODE_POINT_2", "execute", "sha256_configuration", "EchecBanc"]

NOM = "splink_4_0_16"
#: Splink a un score signé et une frontière évidentielle : DIMS lui est applicable.
MODE_POINT_2 = "dims"

# ------------------------------------------------------------------ constantes SCELLÉES
GRAINE_U = 20260905          # strictement positive : cf. piège `seed=0` ci-dessus
MAX_PAIRS_U = 1e7            # >= C(537,2) = 143 916 -> échantillonnage exhaustif
EM_CONVERGENCE = 1e-4
MAX_ITERATIONS = 60          # le défaut 25 a été frôlé (24 itérations) en reconnaissance
RECALL_DECLARE = 0.7         # valeur des tutoriels Splink, déclarée A PRIORI
SEUIL_NATIF = 0.5            # match_probability >= 0,5 <=> match_weight >= 0
NOM_TABLE = "records_v12"
COLONNES = ("record_id", "source_id") + tuple(cb.ATTRIBUTS) + ("cle_cp", "cle_pref")

REGLE_EM_UNION = "l.cle_cp = r.cle_cp OR l.cle_pref = r.cle_pref"
REGLES_DETERMINISTES = [
    "l.nom = r.nom AND l.prenom = r.prenom AND l.date_naissance = r.date_naissance",
    "l.email = r.email",
    "l.telephone = r.telephone",
]


class EchecBanc(RuntimeError):
    """Toute anomalie fait ÉCHOUER BRUYAMMENT : le banc ne publie jamais un chiffre douteux."""


def regles_blocking_naturel():
    """Bras B — Splink choisit SES règles, comme le ferait un praticien sur de la donnée FR.

    Sept règles : les six canoniques pour de la donnée personne, plus une règle de préfixe de
    patronyme sans laquelle le rappel s'effondre sur les variantes phonétiques. Ce choix est
    une décision de LOYAUTÉ, déclarée : le priver de cette règle rendrait le bras B
    artificiellement défavorable à Splink.
    """
    return [block_on("nom", "prenom"), block_on("date_naissance"), block_on("email"),
            block_on("telephone"), block_on("code_postal"), block_on("adresse"),
            block_on("cle_pref")]


def comparaison_code_postal_fr():
    """`cl.PostcodeComparison` est câblé sur le format BRITANNIQUE et dégénère sur 5 chiffres.

    On garde sa STRUCTURE (exact -> voisinage -> reste) recâblée sur la hiérarchie française.
    Le niveau « même département » est écarté du modèle de tête : la colinéarité avec `ville`
    est parfaite sur cette fixture, et le compter reviendrait à compter deux fois la même
    preuve dans un modèle qui postule l'indépendance conditionnelle — ce qui gonflerait
    artificiellement les poids de Splink. La variante AVEC département est publiée en
    sensibilité déclarée (`SENS_3`), pour que le choix soit contestable.
    """
    return cl.CustomComparison(
        output_column_name="code_postal",
        comparison_description="CP FR 5 chiffres : exact / meme prefixe de 4",
        comparison_levels=[
            cll.NullLevel("code_postal"),
            cll.ExactMatchLevel("code_postal"),
            # Splink 4 suffixe les colonnes : `l.`/`r.` serait invalide ici.
            cll.CustomLevel(sql_condition="substr(code_postal_l, 1, 4) = "
                                          "substr(code_postal_r, 1, 4)",
                            label_for_charts="meme prefixe de 4 chiffres"),
            cll.ElseLevel(),
        ])


def comparaisons(avec_departement: bool = False):
    """Une ComparisonCreator par attribut comparé du moteur : 8, ni plus ni moins (L6).

    **Règle de rétention, gelée avant toute mesure de qualité** : on prend le CONSTRUCTEUR
    PAR DÉFAUT de la bibliothèque partout où ses niveaux sont entraînables, et on ne retire un
    niveau que s'il est mesuré à occupation ZÉRO — un niveau jamais observé n'est pas un
    paramètre, Splink le remplit d'une valeur par défaut muette. Cette règle existe pour que
    « Splink sous-configuré » soit un constat vérifiable et non une accusation invérifiable.
    """
    cp = (cl.PostcodeComparison("code_postal") if avec_departement
          else comparaison_code_postal_fr())
    return [
        # Variantes phonétiques, fautes, transpositions ; ajustement de fréquence de terme
        # actif (un « Martin » partagé pèse moins qu'un patronyme rare). Seuils = défaut.
        cl.NameComparison("nom", jaro_winkler_thresholds=[0.92, 0.88, 0.70]),
        cl.NameComparison("prenom", jaro_winkler_thresholds=[0.92, 0.88, 0.70]),
        # Dates déjà ramenées à la forme ISO unique par la normalisation du moteur.
        cl.DateOfBirthComparison(
            "date_naissance", input_is_string=True, datetime_format="%Y-%m-%d",
            datetime_thresholds=[1, 1, 10], datetime_metrics=["month", "year", "year"],
            invalid_dates_as_null=True),
        # Distance d'édition AVEC transposition. Jaro-Winkler surpondère le préfixe, donc le
        # NUMÉRO de voie ; et le `jaccard` de duckdb travaille sur l'ENSEMBLE des caractères.
        cl.DamerauLevenshteinAtThresholds("adresse", [1, 2]),
        cp,
        cl.ExactMatch("ville"),
        cl.EmailComparison("email"),
        cl.ExactMatch("telephone"),
    ]


def construit_settings(regles_blocking, avec_departement: bool = False):
    return SettingsCreator(
        link_type="dedupe_only",
        unique_id_column_name="record_id",
        comparisons=comparaisons(avec_departement),
        blocking_rules_to_generate_predictions=regles_blocking,
        retain_matching_columns=False,
        retain_intermediate_calculation_columns=False,
        em_convergence=EM_CONVERGENCE,
        max_iterations=MAX_ITERATIONS,
    )


def lignes(substrat):
    """Records NORMALISÉS par le moteur + les 2 clés de blocking, en VARCHAR, TRIÉS.

    `cle_pref` est calculée par LA FONCTION DU MOTEUR et non réimplémentée en SQL : un
    décalage d'un caractère passerait inaperçu et ferait diverger l'ensemble candidat, ce que
    le bras apparié ne tolère pas.
    """
    ids = [r["record_id"] for r in substrat.normalises]
    if len(set(ids)) != len(ids):
        raise EchecBanc("record_id non unique : Splink ne le detecte pas et produit "
                        "silencieusement des paires en double")
    sortie = []
    for nrec in substrat.normalises:
        vals = [nrec.get("record_id"), nrec.get("source_id")]
        vals += [nrec.get(a) for a in cb.ATTRIBUTS]
        vals += [substrat.cle_cp(nrec), substrat.cle_pref(nrec)]
        sortie.append(tuple(None if v in (None, "") else str(v) for v in vals))
    sortie.sort(key=lambda t: t[0])
    return sortie


def connexion():
    """duckdb en mémoire, mono-thread, sans aucune extension téléchargeable."""
    if multiprocessing.cpu_count() < 2:
        raise EchecBanc("splink 4.0.16 fixe salting_partitions = cpu_count() des que "
                        "max_pairs > 1e4 et leve si cpu_count == 1 : machine inadaptee")
    con = duckdb.connect(":memory:")
    con.execute("SET threads TO 1")
    con.execute("SET preserve_insertion_order = true")
    con.execute("SET autoinstall_known_extensions = false")
    con.execute("SET autoload_known_extensions = false")
    return con


def cree_table(con, lgn):
    guillemet = chr(34)
    cols = ", ".join(guillemet + c + guillemet + " VARCHAR" for c in COLONNES)
    con.execute("CREATE TABLE " + NOM_TABLE + " (" + cols + ")")
    con.executemany("INSERT INTO " + NOM_TABLE + " VALUES ("
                    + ", ".join(["?"] * len(COLONNES)) + ")", lgn)


def convergence(session):
    """Splink journalise « EM converged » MÊME sur arrêt par plafond d'itérations.

    Le `logger.info` est placé HORS du test de convergence, après la boucle : un modèle non
    convergé se présente donc comme convergé. On rejuge sur l'historique des paramètres
    plutôt que sur le journal — un banc qui croirait le journal publierait un modèle
    inachevé sous le nom de Splink.
    """
    try:
        from splink.internals.expectation_maximisation import (
            _max_change_in_parameters_comparison_levels as _max_change)
        historique = session._core_model_settings_history
    except Exception as exc:                     # API interne absente ou déplacée
        raise EchecBanc(
            "impossible de verifier la convergence EM sur cette version de splink (%s). "
            "Le banc refuse de publier un modele dont la convergence n'est pas verifiee." % exc)
    n = len(historique) - 1
    if n < 1:
        return False, n, float("inf")
    delta = _max_change(historique)["max_abs_change_value"]
    return (delta < EM_CONVERGENCE), n, delta


def audit_parametres(settings_obj):
    """Trois états distincts, jamais confondus — et un seul est bloquant.

    `niveaux_inertes` : niveau jamais observé, donc pas un paramètre (publié, non bloquant).
    `defauts_silencieux` : niveau PEUPLÉ dont le poids `m` n'a pas été entraîné. BLOQUANT :
    publier un Splink dont un niveau réellement rencontré tourne sur une valeur par défaut,
    puis appeler ce chiffre « Splink », serait le pire des hommes de paille.
    `m_ou_u_degeneres` : poids collé à zéro, signe d'une estimation dégénérée (publié).
    """
    try:
        from splink.internals.constants import LEVEL_NOT_OBSERVED_TEXT
    except Exception:
        LEVEL_NOT_OBSERVED_TEXT = "level not observed in dataset"
    inertes, defauts, degeneres = [], [], []
    for comparaison in settings_obj.comparisons:
        for niveau in comparaison.comparison_levels:
            if niveau.is_null_level:
                continue
            m = getattr(niveau, "_m_probability", None)
            u = getattr(niveau, "_u_probability", None)
            etiquette = [comparaison.output_column_name, niveau.label_for_charts]
            if u is None or u == LEVEL_NOT_OBSERVED_TEXT:
                inertes.append(etiquette + ["u"])
                continue
            if m is None or m == LEVEL_NOT_OBSERVED_TEXT:
                defauts.append(etiquette + ["m"])
                continue
            for quoi, val in (("m", m), ("u", u)):
                try:
                    if float(val) < 1e-6:
                        degeneres.append(etiquette + [quoi, float(val)])
                except (TypeError, ValueError):
                    defauts.append(etiquette + [quoi])
    return {"niveaux_inertes": inertes, "defauts_silencieux": defauts,
            "m_ou_u_degeneres": degeneres}


def sha256_configuration() -> str:
    """Empreinte de la configuration GELÉE, citée dans l'artefact et vérifiée par un test.

    Elle interdit qu'un réglage bouge entre la lecture d'un résultat et la publication : la
    configuration de l'adversaire est gelée au même titre que les critères de lecture.
    """
    canon = json.dumps({
        "regle_em": REGLE_EM_UNION,
        "regles_deterministes": REGLES_DETERMINISTES,
        "recall": RECALL_DECLARE, "seuil_natif": SEUIL_NATIF,
        "graine_u": GRAINE_U, "max_pairs_u": MAX_PAIRS_U,
        "em_convergence": EM_CONVERGENCE, "max_iterations": MAX_ITERATIONS,
        "threads": 1, "colonnes": list(COLONNES),
        "attributs": list(cb.ATTRIBUTS),
    }, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def execute(substrat, bras: str = "apparie", avec_departement: bool = False,
            recall: float = RECALL_DECLARE) -> dict:
    """Exécute Splink et rend le contrat commun. Aucune métrique de qualité n'est calculée.

    `bras="apparie"` impose l'ensemble candidat du moteur (bras A) ; `bras="naturel"` laisse
    Splink appliquer ses propres règles (bras B). Les paramètres restants ne servent qu'aux
    sensibilités déclarées, et leurs valeurs par défaut sont celles du modèle de tête.
    """
    t0 = time.time()
    logging.getLogger("splink").setLevel(logging.ERROR)
    con = connexion()
    cree_table(con, lignes(substrat))

    regles = ([block_on("cle_cp"), block_on("cle_pref")] if bras == "apparie"
              else regles_blocking_naturel())
    linker = Linker(NOM_TABLE, construit_settings(regles, avec_departement),
                    db_api=DuckDBAPI(connection=con), set_up_basic_logging=False)

    # `max_pairs >= C(n,2)` rend l'échantillonnage EXHAUSTIF : `u` est alors estimé sur le
    # produit cartésien entier, sans aucun aléa. Restreindre ce support à `C0` (sensibilité
    # SENS_2) n'est PAS exposé par l'API 4.0.16 sans réimplémenter l'estimation de `u` — ce
    # qui produirait un Splink modifié plutôt que Splink. La sensibilité est donc publiée
    # NON EXÉCUTÉE avec ce motif, plutôt que simulée par un paramètre qui n'agirait pas.
    t_u = time.time()
    linker.training.estimate_u_using_random_sampling(max_pairs=MAX_PAIRS_U, seed=GRAINE_U)
    duree_u = time.time() - t_u

    # λ par la PROCÉDURE DOCUMENTÉE de la bibliothèque : elle compte les paires attrapées par
    # des règles d'égalité stricte — aucune étiquette n'y entre — et divise par un rappel
    # SUPPOSÉ, déclaré a priori. Le défaut usine 1e-4 supposerait ~14 paires liées sur
    # 143 916 : manifestement trop bas pour une fixture de dédoublonnage, et pénalisant pour
    # Splink. Le choix va donc dans le sens DÉFAVORABLE au moteur maison.
    linker.training.estimate_probability_two_random_records_match(
        REGLES_DETERMINISTES, recall=recall)

    # UNE session EM, sur la RÈGLE D'UNION : elle entraîne exactement sur la population qui
    # sera notée — le même régime que l'EM du moteur. `fix_probability_two_random_records_match`
    # est OBLIGATOIRE : λ libre fait converger l'EM vers une solution dégénérée.
    t_em = time.time()
    session = linker.training.estimate_parameters_using_expectation_maximisation(
        REGLE_EM_UNION, fix_probability_two_random_records_match=True)
    converge, n_iter, delta = convergence(session)
    if not converge:
        raise EchecBanc(f"EM non convergee ({n_iter} iterations, delta {delta:g}) : le banc "
                        f"refuse de publier un modele inacheve sous le nom de Splink")
    duree_em = time.time() - t_em

    settings_obj = linker._settings_obj
    audit = audit_parametres(settings_obj)
    if audit["defauts_silencieux"]:
        raise EchecBanc("poids sur defauts silencieux : " + repr(audit["defauts_silencieux"]))
    lam = float(settings_obj._probability_two_random_records_match)
    prior_bits = math.log2(lam / (1.0 - lam))

    t_p = time.time()
    enregs = linker.inference.predict(threshold_match_probability=0.0).as_record_dict()
    duree_p = time.time() - t_p
    con.close()

    scores, ecart_max = [], 0.0
    for rec in enregs:
        a, b = cb.cle(rec["record_id_l"], rec["record_id_r"])
        mw = float(rec["match_weight"])
        mp = float(rec["match_probability"])
        # L'identité entre poids et probabilité est VÉRIFIÉE, pas supposée : si elle cassait,
        # le score livré et le verdict natif décriraient deux modèles différents.
        attendu = 1.0 / (1.0 + 2.0 ** (-mw)) if -300 < mw < 300 else (0.0 if mw <= 0 else 1.0)
        ecart_max = max(ecart_max, abs(attendu - mp))
        scores.append({
            "record_id_a": a, "record_id_b": b,
            "poids_match": round(mw - prior_bits, cb.DECIMALES_LIVRAISON),
            "verdict_natif": cb.MATCH if mp >= SEUIL_NATIF else cb.NON_MATCH,
            "match_weight_splink": mw,
            "match_probability_splink": round(mp, cb.DECIMALES_LIVRAISON),
        })
    if ecart_max > 1e-6:
        raise EchecBanc(f"match_probability incoherente avec match_weight (ecart {ecart_max:g})")
    scores.sort(key=lambda s: (s["record_id_a"], s["record_id_b"]))

    diagnostic = {
        "systeme": NOM, "bras": bras,
        "version_splink": _version_splink(),
        "lambda": lam, "prior_bits": prior_bits, "recall_declare": recall,
        "note_echelle": ("poids_match livre = match_weight MOINS log2(lambda/(1-lambda)) : "
                         "meme grandeur physique que le R du moteur, donc meme signification "
                         "de la frontiere 0. Transformation MONOTONE : aucun classement change."),
        "seuil_natif_match_probability": SEUIL_NATIF,
        "ecart_max_probabilite_vs_poids": ecart_max,
        "em": {"regle": REGLE_EM_UNION, "iterations": n_iter, "dernier_delta": delta,
               "plafond": MAX_ITERATIONS, "converge": True,
               "note": ("convergence rejugee sur l'historique des parametres : le journal de "
                        "splink annonce « converged » meme sur arret par plafond")},
        "audit_parametres": audit,
        "blocking": {"regles": [_regle_lisible(r) for r in regles],
                     "avec_departement": avec_departement},
        "support_estimation_u": "produit_cartesien_exhaustif (max_pairs >= C(n,2))",
        "graine_u": GRAINE_U, "max_pairs_u": MAX_PAIRS_U, "threads_duckdb": 1,
        "n_paires": len(scores),
        "durees_s": {"u": round(duree_u, 3), "em": round(duree_em, 3),
                     "predict": round(duree_p, 3), "total": round(time.time() - t0, 3)},
        "sha256_configuration": sha256_configuration(),
    }
    return {"systeme": NOM, "scores": scores, "diagnostic": diagnostic}


def _version_splink() -> str:
    import splink
    return getattr(splink, "__version__", "inconnue")


def _regle_lisible(regle) -> str:
    """Le SQL de la règle, et jamais son `repr`.

    Le `repr` par défaut d'un objet Splink contient son ADRESSE MÉMOIRE, qui change à chaque
    exécution : l'artefact cesserait d'être reproductible pour une raison purement cosmétique,
    et le contrôle de déterminisme échouerait en désignant un faux coupable. Publier le SQL
    est en outre ce qu'un lecteur veut voir — une règle de blocking se conteste sur son SQL.
    """
    try:
        return regle.get_blocking_rule("duckdb").blocking_rule_sql
    except Exception:
        return type(regle).__name__
