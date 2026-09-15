# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Banc de comparaison : moteur maison vs Splink 4.0.16 vs baselines.

    .venv\\Scripts\\python tools/banc_ub6.py

## Pourquoi ce script vit HORS de `src/`
C'est le SEUL fichier du dépôt qui importe à la fois `benchmark` (donc `engine`) et `scorer`,
et il ne les couple pas pour autant : ils s'y rencontrent **par données**. Les adaptateurs
produisent des scores sans jamais voir la vérité terrain ; le scoreur lit ces scores et la
vérité terrain sans jamais voir un adaptateur. Placer ce point de rencontre dans `src/` ferait
de l'un une dépendance de l'autre et romprait la non-circularité — même raison qui met
`tools/mesure_discrimination.py` hors de `src/scorer/`.

## L'oracle unique, et pourquoi c'est une propriété du code
`note_un_systeme` est appelée **en boucle**, une fois par cellule, et ne contient aucune
branche conditionnée au nom d'un système. Il n'existe pas d'autre chemin par lequel un chiffre
puisse entrer dans l'artefact. C'est ce qui rend `L3_MEME_ORACLE` vérifiable par lecture plutôt
que par confiance : on ne peut pas favoriser un système sans ajouter du code qu'un test voit.

## VÉRIFIER / COMPARER, jamais TUNER
Aucun paramètre d'aucun système n'est ajusté ici. Les critères de lecture ont été gelés et
committés AVANT ce fichier (`src/benchmark/criteres_ub6.py`, commit antérieur attesté par git).
Si le moteur maison fait moins bien que Splink, l'artefact le publie tel quel : l'énoncé
correspondant était écrit avant que le premier chiffre n'existe.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import time

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RACINE, "src"))

import scorer                                                        # noqa: E402
from benchmark import adaptateur_baselines as ab                     # noqa: E402
from benchmark import adaptateur_moteur as am                        # noqa: E402
from benchmark import adaptateur_splink as asp                       # noqa: E402
from benchmark import contrat_bench as cb                            # noqa: E402
from benchmark import criteres_ub6 as crit                           # noqa: E402
from benchmark import points as pt                                   # noqa: E402
from benchmark import substrat as sub                                # noqa: E402

CHEMIN_ARTEFACT = os.path.join("artifacts", "banc_ub6.json")
CONVENTION = "stricte"

#: Champs dont la valeur dépend de la machine ou du moment. Ils sont PUBLIÉS — masquer une
#: durée n'aide personne — mais exclus de l'empreinte et du contrôle de déterminisme, faute
#: de quoi aucune exécution ne serait jamais reproductible.
CLES_VOLATILES = ("durees_s", "performance", "provenance")


# ============================ l'oracle, appelé en boucle ============================
def note_un_systeme(scores, verdicts, vraies, n_vraies: int) -> dict:
    """LE chemin de notation. Aucune branche par système ; aucune métrique recalculée ici.

    Tout ce que l'artefact publie de quantitatif passe par cette fonction, qui ne fait
    qu'enchaîner le scoreur : audit d'intégrité, classement, contingence, invariants,
    mesures sous la convention de tête. Un système ne peut donc pas être mesuré autrement
    qu'un autre.
    """
    corrs = cb.en_correspondances(scores, verdicts)
    audit = scorer.valide_correspondances(corrs)
    classement = scorer.classe_les_paires(corrs, vraies)
    cont = scorer.contingence(classement, n_vraies)
    scorer.verifie_invariants(cont)
    mes = scorer.mesures(cont, CONVENTION)
    n_gris = cont["gv"] + cont["gf"]
    return {
        "alerte_contrat": audit["alerte"],
        "contingence": cont,
        "metriques": {
            "precision": mes["precision"],
            "rappel_bout_en_bout": mes["rappel_bout_en_bout"],
            "f1_bout_en_bout": mes["f1_bout_en_bout"],
            "tp": mes["tp"], "fp": mes["fp"], "fn": mes["fn"],
            "fn_blocking": mes["fn_blocking"],
            "n_candidates": cont["n_candidates"],
            "n_zone_grise": n_gris,
        },
        "ic_wilson_95": mes["ic_wilson_95"],
        "denominateurs_explicites": mes["denominateurs_explicites"],
        "toutes_conventions": {c: {k: v for k, v in m.items()
                                   if k in ("precision", "rappel_bout_en_bout",
                                            "f1_bout_en_bout", "tp", "fp", "fn")}
                               for c, m in scorer.mesures_toutes_conventions(cont).items()},
        "positifs": {cle for cle, v in verdicts.items() if v == cb.MATCH},
    }


# ============================ McNemar exact (apparié) ===============================
def mcnemar_exact(positifs_a: set, positifs_b: set, univers: set, vraies) -> dict:
    """Test APPARIÉ sur les discordances. Les systèmes voient les MÊMES paires : c'est
    l'instrument correct, et le chevauchement d'intervalles de confiance ne l'est pas.

    Une prédiction est CORRECTE si elle déclare MATCH une vraie paire, ou si elle ne déclare
    pas MATCH une fausse. `b` compte les paires où A a raison et B tort, `c` l'inverse ; sous
    l'hypothèse nulle, chacune des `b + c` discordances est un tirage à pile ou face.
    """
    b = c = 0
    for k in univers:
        vrai = k in vraies
        ca = (k in positifs_a) == vrai
        cbb = (k in positifs_b) == vrai
        if ca and not cbb:
            b += 1
        elif cbb and not ca:
            c += 1
    n = b + c
    if n == 0:
        return {"b": 0, "c": 0, "n_discordances": 0, "p": 1.0,
                "note": "aucune discordance : les deux systemes se trompent aux memes endroits"}
    k = min(b, c)
    cumul = sum(math.comb(n, i) for i in range(k + 1))
    p = min(1.0, 2.0 * cumul * (0.5 ** n))
    return {"b": b, "c": c, "n_discordances": n, "p": p,
            "note": "binomial exact bilateral sur les discordances"}


# ============================ construction des cellules =============================
def _cellule(bras, systeme, point, sortie_point, note, diagnostic_systeme, extra=None):
    cellule = {
        "bras": bras, "systeme": systeme, "point": point, "statut": "OK", "motif": None,
        "convention": CONVENTION,
        "metriques": note["metriques"],
        "ic_wilson_95": note["ic_wilson_95"],
        "denominateurs_explicites": note["denominateurs_explicites"],
        "contingence": note["contingence"],
        "toutes_conventions": note["toutes_conventions"],
        "parametres_du_point": sortie_point.get("parametres", {}),
        "diagnostic_systeme": diagnostic_systeme,
        # Clé de travail : l'ensemble des paires déclarées MATCH, nécessaire au test apparié
        # de McNemar. Retirée de l'artefact avant publication (`_retire_positifs`) — elle est
        # volumineuse et entièrement redérivable des métriques publiées.
        "_positifs": note.get("positifs", set()),
    }
    if extra:
        cellule.update(extra)
    return cellule


def _retire_positifs(cellules) -> None:
    for c in cellules:
        c.pop("_positifs", None)


def _systemes_du_bras(substrat, bras: str) -> list:
    """Les exécutions d'un bras : (nom, sortie d'adaptateur, mode de point 2).

    Bras A : tous les systèmes notent l'ensemble candidat du moteur (`C0`).
    Bras B : chacun apporte son blocking — le moteur ses passes, Splink ses règles natives,
    les baselines l'espace complet (une baseline n'a pas de blocking, et lui en prêter un
    serait lui prêter une compétence qu'elle n'a pas).
    """
    if bras == "A_univers_appari":
        sorties = [am.execute(substrat), asp.execute(substrat, bras="apparie")]
        sorties += [ab.execute(substrat, nom) for nom in ab.BASELINES]
    else:
        sorties = [am.execute(substrat), asp.execute(substrat, bras="naturel")]
        cartesien = _espace_complet(substrat)
        sorties += [ab.execute(substrat, nom, paires=cartesien) for nom in ab.BASELINES]
    modes = {am.NOM: am.MODE_POINT_2, asp.NOM: asp.MODE_POINT_2}
    return [(s["systeme"], s, modes.get(s["systeme"], ab.MODE_POINT_2)) for s in sorties]


def _espace_complet(substrat) -> list:
    ids = sorted(r["record_id"] for r in substrat.normalises)
    return [(ids[i], ids[j]) for i in range(len(ids)) for j in range(i + 1, len(ids))]


def construis_bras(bras, substrat, vraies, n_vraies) -> dict:
    """Toutes les cellules d'un bras, plus les compléments et diagnostics de loyauté."""
    cellules, positifs, completions, univers_par_systeme = [], {}, {}, {}
    executions = _systemes_du_bras(substrat, bras)

    # --- point 1 pour tous, puis point 2 : le K du volume egalise vient du moteur --------
    k_cible = None
    resultats = {}
    for nom, sortie, mode in executions:
        cb.valide_scores(sortie["scores"], nom)
        if bras == "A_univers_appari":
            complet = cb.complete_sur_C0(sortie["scores"], substrat.c0)
            scores, n_comp = complet["scores"], complet["n_completions"]
        else:
            scores, n_comp = sortie["scores"], 0
        completions[nom] = n_comp
        univers_par_systeme[nom] = cb.cles(scores)
        resultats[nom] = (sortie, scores, mode)

    # Le moteur d'abord : son n_MATCH au point 2 fixe le volume offert aux baselines.
    sortie_m, scores_m, mode_m = resultats[am.NOM]
    p2_moteur = pt.applique_point_2(scores_m, mode_m)
    k_cible = sum(1 for v in p2_moteur["verdicts"].values() if v == cb.MATCH)

    for nom, (sortie, scores, mode) in resultats.items():
        for point in (pt.POINT_1, pt.POINT_2):
            if point == pt.POINT_1:
                sp = pt.applique_point_1(scores)
            elif nom == am.NOM:
                sp = p2_moteur
            else:
                sp = pt.applique_point_2(scores, mode, k_cible=k_cible)
            note = note_un_systeme(scores, sp["verdicts"], vraies, n_vraies)
            positifs[(nom, point)] = note["positifs"]
            cellules.append(_cellule(bras, nom, point, sp, note, sortie["diagnostic"],
                                     extra={"n_completions": completions[nom]}))

    univers = [tuple(sorted(u)) for u in univers_par_systeme.values()]
    return {
        "cellules": cellules,
        "positifs": positifs,
        "univers_par_systeme": {n: len(u) for n, u in univers_par_systeme.items()},
        "univers_identique": len(set(univers)) == 1,
        "univers_commun": set(univers_par_systeme[am.NOM]),
        "completions": completions,
        "k_cible_volume_egalise": k_cible,
    }


# ============================ écarts et cibles ======================================
def _f1(cellule):
    return (cellule["metriques"] or {}).get("f1_bout_en_bout")


def _rappel(cellule):
    return (cellule["metriques"] or {}).get("rappel_bout_en_bout")


def _fini(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x


def ecart_signe(valeur_moteur, valeur_autre, reference: str, metrique: str) -> dict:
    """Écart TOUJOURS signé, TOUJOURS orienté « moteur maison moins autre ».

    Une seule fonction de rendu, sans branche conditionnée au signe : un écart négatif occupe
    la même colonne, la même place et la même forme qu'un écart positif. Une valeur absolue,
    ou un écart dont on ne sait pas qui est devant, transforme une défaite en « différence ».
    """
    if not (_fini(valeur_moteur) and _fini(valeur_autre)):
        return {"valeur_signee": None, "sens": "moteur_maison - " + reference,
                "metrique": metrique, "reference": reference,
                "motif": "une des deux valeurs est indefinie"}
    return {
        "valeur_signee": valeur_moteur - valeur_autre,
        "en_points": round((valeur_moteur - valeur_autre) * 100.0, 4),
        "sens": "moteur_maison - " + reference,
        "metrique": metrique, "reference": reference,
        "valeur_moteur": valeur_moteur, "valeur_reference": valeur_autre,
    }


def cellule(cellules, bras, systeme, point):
    for c in cellules:
        if c["bras"] == bras and c["systeme"] == systeme and c["point"] == point:
            return c
    return None


# ============================ assemblage ============================================
def _git(*args):
    try:
        return subprocess.check_output(["git"] + list(args), cwd=_RACINE, text=True).strip()
    except Exception:
        return None


def _sans_volatils(obj):
    """Copie débarrassée des champs dépendants de la machine ou du moment."""
    if isinstance(obj, dict):
        return {k: _sans_volatils(v) for k, v in obj.items() if k not in CLES_VOLATILES}
    if isinstance(obj, list):
        return [_sans_volatils(v) for v in obj]
    return obj


def serialisation_canonique(rapport: dict) -> str:
    return json.dumps(rapport, sort_keys=True, ensure_ascii=False, indent=1,
                      default=_json_defaut) + "\n"


def _json_defaut(o):
    if isinstance(o, (set, frozenset, tuple)):
        return sorted(o)
    raise TypeError(f"non serialisable : {type(o).__name__}")


def empreinte_des_mesures(rapport: dict) -> str:
    """Empreinte des MESURES seules — provenance et durées exclues.

    L'artefact reste donc valide après un nouveau commit : c'est exactement la propriété
    voulue, et la même que dans le scoreur.
    """
    canon = json.dumps(_sans_volatils(rapport), sort_keys=True, ensure_ascii=False,
                       separators=(", ", ": "), default=_json_defaut)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def ecris_artefact(rapport: dict, chemin: str) -> None:
    with open(chemin, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(serialisation_canonique(rapport))


# ============================ sensibilités déclarées =================================
def _substrat_brut(substrat):
    """Le même substrat, mais avec les valeurs BRUTES : Splink privé de la normalisation FR.

    L'ensemble candidat reste `C0` : on isole l'effet de la préparation, pas du blocking.
    """
    index = {r["record_id"]: r for r in substrat.records}
    bruts = []
    for nrec in substrat.normalises:
        source = index[nrec["record_id"]]
        ligne = {"record_id": source.get("record_id"), "source_id": source.get("source_id")}
        ligne.update({a: source.get(a) for a in cb.ATTRIBUTS})
        bruts.append(ligne)
    return sub.Substrat(substrat.records, bruts, substrat.empreinte_fixture,
                        substrat.c0, substrat.trace_blocking)


def _arbitrage_force(scores):
    """Tous les systèmes projetés en binaire à leur propre frontière 0 : couverture 1,0.

    Tue l'objection d'abstention asymétrique — le moteur perd son droit de se taire, et un
    système binaire ne gagne plus rien à trancher toujours.
    """
    return {"point": "sensibilite_arbitrage_force",
            "verdicts": {cb.cle(s["record_id_a"], s["record_id_b"]):
                         (cb.MATCH if s["poids_match"] > 0 else cb.NON_MATCH) for s in scores},
            "parametres": {"regle": "MATCH ssi poids_match > 0 ; aucune abstention possible"}}


def construis_sensibilites(substrat, vraies, n_vraies, scores_moteur_A) -> list:
    """Les sensibilités PRÉ-ENREGISTRÉES. Elles ne portent aucun verdict (H3), mais elles
    entrent dans la recherche du MEILLEUR point de Splink (H4) : la comparaison la plus dure
    pour le moteur est choisie en aveugle, donc non requalifiable.
    """
    cellules = []

    def ajoute(code, systeme, sortie, sp, statut="OK", motif=None):
        if statut != "OK":
            cellules.append({"bras": "sensibilite", "systeme": systeme, "point": code,
                             "statut": statut, "motif": motif, "convention": CONVENTION,
                             "metriques": {k: None for k in crit.METRIQUES_OBLIGATOIRES},
                             "parametres_du_point": {}, "diagnostic_systeme": {}})
            return
        scores = cb.complete_sur_C0(sortie["scores"], substrat.c0)["scores"]
        note = note_un_systeme(scores, sp["verdicts"], vraies, n_vraies)
        cellules.append(_cellule("sensibilite", systeme, code, sp, note,
                                 sortie["diagnostic"]))

    # SENS_1 — Splink sur données BRUTES (sans la normalisation FR du moteur).
    brut = _substrat_brut(substrat)
    s1 = asp.execute(brut, bras="apparie")
    ajoute("SENS_1_splink_donnees_brutes", asp.NOM, s1, pt.applique_point_1(s1["scores"]))

    # SENS_2 — u estimé sur C0 seul : NON EXÉCUTÉE, et le motif est technique, pas commode.
    cellules.append({
        "bras": "sensibilite", "systeme": asp.NOM, "point": "SENS_2_splink_u_estime_sur_C0",
        "statut": "NON_EXECUTEE", "convention": CONVENTION,
        "motif": ("splink 4.0.16 estime u par echantillonnage du PRODUIT CARTESIEN ; "
                  "restreindre ce support a C0 n'est pas expose par son API sans "
                  "reimplementer l'estimation de u, ce qui produirait un Splink MODIFIE "
                  "plutot que Splink. La cellule est publiee NON EXECUTEE plutot que "
                  "simulee par un parametre qui n'agirait pas."),
        "metriques": {k: None for k in crit.METRIQUES_OBLIGATOIRES},
        "parametres_du_point": {}, "diagnostic_systeme": {}})

    # SENS_3 — comparateur de code postal AVEC niveau « meme departement ».
    s3 = asp.execute(substrat, bras="apparie", avec_departement=True)
    ajoute("SENS_3_cp_avec_niveau_departement", asp.NOM, s3, pt.applique_point_1(s3["scores"]))

    # SENS_4 — le rappel supposé qui alimente lambda : 0,5 et 0,9 autour du 0,7 déclaré.
    for r in (0.5, 0.9):
        s4 = asp.execute(substrat, bras="apparie", recall=r)
        ajoute("SENS_4_lambda_recall_%s" % str(r).replace(".", "_"), asp.NOM, s4,
               pt.applique_point_1(s4["scores"]))

    # SENS_5 — le moteur AVEC les trois passes (avant le retrait de SDX_NOM).
    s5 = am.execute(substrat, passes=("CP", "SDX_NOM", "PREF"))
    scores5 = s5["scores"]
    note5 = note_un_systeme(scores5, pt.applique_point_1(scores5)["verdicts"], vraies, n_vraies)
    cellules.append(_cellule("sensibilite", am.NOM, "SENS_5_moteur_trois_passes",
                             pt.applique_point_1(scores5), note5, s5["diagnostic"]))

    # SENS_6 — arbitrage forcé : les trois systèmes en binaire, couverture 1,0 partout.
    splink_A = asp.execute(substrat, bras="apparie")
    b5 = ab.execute(substrat, ab.BASELINE_DE_TETE)
    for systeme, sortie, scores in (
            (am.NOM, {"diagnostic": {"systeme": am.NOM}}, scores_moteur_A),
            (asp.NOM, splink_A, cb.complete_sur_C0(splink_A["scores"], substrat.c0)["scores"]),
            (ab.BASELINE_DE_TETE, b5, b5["scores"])):
        sp = _arbitrage_force(scores)
        note = note_un_systeme(scores, sp["verdicts"], vraies, n_vraies)
        cellules.append(_cellule("sensibilite", systeme,
                                 "SENS_6_arbitrage_force_sans_abstention", sp, note,
                                 sortie.get("diagnostic", {})))
    return cellules


# ============================ le programme ==========================================
def construis() -> dict:
    """Exécute le banc complet et assemble l'artefact de comparaison."""
    t0 = time.time()
    substrat = sub.charge()
    # La vérité terrain est chargée ICI, séparément, et ne redescend JAMAIS vers un
    # adaptateur : `substrat` ne la porte pas, et sa signature l'interdit.
    pack = scorer.charge_pack(os.path.join(_RACINE, sub.CHEMIN_FIXTURE),
                              sub.CONTENT_SHA256_V1_2)
    vraies = scorer.paires_vraies(pack["ground_truth"])
    stats_verite = scorer.statistiques_verite(pack["ground_truth"])
    n_vraies = stats_verite["n_vraies_paires"]

    bras = {nom: construis_bras(nom, substrat, vraies, n_vraies)
            for nom in ("A_univers_appari", "B_chaine_complete")}
    cellules = [c for b in bras.values() for c in b["cellules"]]

    scores_moteur_A = cb.complete_sur_C0(am.execute(substrat)["scores"], substrat.c0)["scores"]
    sensibilites = construis_sensibilites(substrat, vraies, n_vraies, scores_moteur_A)
    toutes = cellules + sensibilites

    # --- déterminisme : re-exécution des deux composants stochastiques ------------------
    determinisme = _controle_determinisme(substrat)

    # --- cellule de reference et écarts -------------------------------------------------
    ref = cellule(cellules, crit.CELLULE_DE_REFERENCE["bras"], am.NOM,
                  crit.CELLULE_DE_REFERENCE["point"])
    ecarts, cibles = _ecarts_et_cibles(bras, cellules, toutes, ref, vraies)

    mesures = _mesures_pour_criteres(substrat, pack, bras, toutes, determinisme, ecarts,
                                     cibles, stats_verite, ref)
    verdict = crit.lis_verdict_ub6(mesures)

    rapport = {
        "_lisez_moi": (
            "COMPARAISON U-B6 : moteur maison contre Splink 4.0.16 contre baselines, sur "
            "FX_001 V1.2. La these O-P1 n'est PAS « on gagne » : elle est « on est credible "
            "et transparent ». Les criteres de lecture ont ete GELES et committes AVANT ce "
            "fichier, et l'enonce publie pour chaque issue -- y compris l'issue defavorable "
            "-- etait ecrit avant que le premier chiffre n'existe. Les chiffres sont ce "
            "qu'ils sont : aucun reglage n'a ete fait pour flatter la comparaison."),
        "mandat": "DISP-UB6-01", "unite": "U-B6", "objectif": "O-P1",
        "version_schema": "1.0.0",
        "statut": verdict["statut"],
        "verdict": verdict,
        "preenregistrement": {
            "fichier": "src/benchmark/criteres_ub6.py",
            "sha256_criteres": crit.sha256_criteres_ub6(),
            "commit_de_gel": _git("log", "--format=%H", "--diff-filter=A", "--",
                                  "src/benchmark/criteres_ub6.py"),
            "n_commits_sur_le_fichier": _git("rev-list", "--count", "HEAD", "--",
                                             "src/benchmark/criteres_ub6.py"),
            "cellule_de_reference": crit.CELLULE_DE_REFERENCE,
            "regle_de_completion": crit.REGLE_DE_COMPLETION,
            "regle_de_departage": crit.REGLE_DE_DEPARTAGE,
        },
        "substrat": substrat.resume(),
        "verite_terrain": stats_verite,
        "inventaire": {
            "systemes": list(crit.SYSTEMES),
            "points": list(crit.POINTS),
            "bras": list(crit.BRAS),
            "baselines": list(crit.BASELINES),
            "sensibilites": list(crit.SENSIBILITES),
            "metriques_obligatoires": list(crit.METRIQUES_OBLIGATOIRES),
            "n_cellules": len(toutes),
        },
        "asymetries_declarees": _asymetries(bras),
        "cellules": cellules,
        "sensibilites": sensibilites,
        "bras_diagnostics": {
            nom: {"univers_par_systeme": b["univers_par_systeme"],
                  "univers_identique": b["univers_identique"],
                  "completions": b["completions"],
                  "k_cible_volume_egalise": b["k_cible_volume_egalise"]}
            for nom, b in bras.items()},
        "determinisme": determinisme,
        "ecarts": ecarts,
        "cibles": cibles,
        "limites": _limites(bras),
        "provenance": {
            "commit": _git("rev-parse", "HEAD"),
            "branche": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "versions": _versions(),
            "duree_totale_s": round(time.time() - t0, 1),
        },
    }
    rapport["empreinte_des_mesures"] = empreinte_des_mesures(rapport)
    return rapport


def _versions() -> dict:
    import duckdb
    import pandas
    import splink
    return {"splink": splink.__version__, "duckdb": duckdb.__version__,
            "pandas": pandas.__version__, "python": sys.version.split()[0]}


def _controle_determinisme(substrat) -> dict:
    """Re-exécute les deux composants STOCHASTIQUES et compare leurs vecteurs de score.

    Les baselines sont des fonctions pures : les rejouer ne prouverait rien. Le contrôle
    porte donc là où le risque est — l'EM du moteur et le pipeline Splink — et le dit. Le
    déterminisme de l'ARTEFACT ENTIER est vérifié séparément, par un test.
    """
    def empreinte(scores):
        return hashlib.sha256(json.dumps(
            [[s["record_id_a"], s["record_id_b"], s["poids_match"], s["verdict_natif"]]
             for s in scores], separators=(",", ":")).encode("utf-8")).hexdigest()

    a1 = empreinte(am.execute(substrat)["scores"])
    a2 = empreinte(am.execute(substrat)["scores"])
    s1 = empreinte(asp.execute(substrat, bras="apparie")["scores"])
    s2 = empreinte(asp.execute(substrat, bras="apparie")["scores"])
    identique = (a1 == a2) and (s1 == s2)
    return {
        "identique": identique,
        "sha": hashlib.sha256((a1 + s1).encode("utf-8")).hexdigest(),
        "moteur": {"run_1": a1, "run_2": a2, "identique": a1 == a2},
        "splink": {"run_1": s1, "run_2": s2, "identique": s1 == s2},
        "portee": ("re-execution des deux composants stochastiques (EM du moteur, pipeline "
                   "Splink). Les baselines sont des fonctions pures. Le determinisme de "
                   "l'artefact entier est verifie par un test distinct."),
        "motif": None if identique else "vecteurs de score divergents entre deux executions",
    }


def _asymetries(bras) -> list:
    """Les asymétries PRÉ-ENREGISTRÉES, chiffrées quand la mesure le permet, plus celles
    découvertes après le gel — ajoutées, jamais retirées, et jamais invoquées pour effacer
    un chiffre défavorable.
    """
    sortie = [dict(a) for a in crit.ASYMETRIES_PRE_ENREGISTREES]
    b = bras["B_chaine_complete"]["univers_par_systeme"]
    a = bras["A_univers_appari"]["univers_par_systeme"]
    for entree in sortie:
        if entree["code"] == "A1_univers_candidat_maison":
            entree["mesure"] = {
                "n_paires_bras_A": a.get(am.NOM),
                "n_paires_splink_bras_B": b.get(asp.NOM),
                "n_paires_moteur_bras_B": b.get(am.NOM),
                "note": ("le chiffre de 373 inscrit dans le texte GELE provient de la "
                         "reconnaissance en aveugle, qui reimplementait la cle de prefixe en "
                         "SQL ; la mesure definitive, qui appelle la fonction du moteur, "
                         "donne un ecart different. Le texte gele n'est PAS reecrit : "
                         "l'ecart est publie ici (cf. limites)."),
            }
    return sortie


def _limites(bras) -> list:
    return [
        ("Le F1 publie est PAIRWISE : la recuperation par cloture transitive releve de "
         "l'unite U-B4 et n'est pas comptee. La reserve vaut pour TOUS les systemes, pas "
         "seulement pour le moteur."),
        ("Une seule fixture, une seule execution du protocole. Aucune generalisation hors "
         "de FX_001 V1.2 n'est publiee."),
        ("Splink est configure selon sa documentation, non regle par un praticien "
         "experimente. Tout enonce de comparaison est borne a cette configuration, publiee "
         "verbatim pour etre contestee."),
        ("Le banc mesure une DIFFERENCE ; il ne l'attribue pas. Il ne dit pas d'ou vient "
         "l'ecart, ni qu'il tiendrait sur une autre donnee."),
        ("Le retrait de SDX_NOM (O0a) est un parametre choisi APRES lecture d'une "
         "information de verite terrain mesuree en U-B5. Il est ordonne par le mandat, son "
         "effet sur le rappel de blocking est nul et verifie, et il joue en faveur du "
         "moteur maison en retirant des faux positifs offerts a la decision."),
        ("Le texte GELE de l'asymetrie A1 cite « 373 paires » ; la mesure definitive donne "
         "un autre chiffre (publie dans asymetries_declarees). Le pre-enregistrement "
         "interdit de reecrire un critere apres coup : le texte est CONSERVE et l'ecart est "
         "declare ici. C'est le dispositif qui fonctionne, pas une negligence."),
    ]


# ============================ écarts signés et cibles ===============================
def _concurrentes():
    """Les baselines qui CONCOURENT. B0 en est exclu par le fichier gelé lui-même, qui le
    déclare « etalon » et « borne, il ne concourt pas » — pas par une decision prise ici.
    """
    return set(ab.familles_non_degenerees())


def _meilleure(cellules, metrique):
    """La cellule qui maximise une métrique, ou `None` si aucune n'est mesurable."""
    candidates = [c for c in cellules if _fini((c.get("metriques") or {}).get(metrique))]
    if not candidates:
        return None
    return max(candidates, key=lambda c: c["metriques"][metrique])


def _degeneree(c) -> bool:
    """Précision sous 0,50, ou plus d'une paire candidate sur deux déclarée MATCH."""
    m = c.get("metriques") or {}
    p, tp, fp, n = m.get("precision"), m.get("tp"), m.get("fp"), m.get("n_candidates")
    if not _fini(p) or not n:
        return True
    taux = (tp + fp) / n
    return (p < crit.PRECISION_MIN_NON_DEGENERESCENCE
            or taux > crit.TAUX_MATCH_MAX_NON_DEGENERESCENCE)


def _ecarts_et_cibles(bras, cellules, toutes, ref, vraies):
    """Écarts SIGNÉS et cibles, évaluées dans la CELLULE DE RÉFÉRENCE gelée."""
    univers = bras["A_univers_appari"]["univers_commun"]
    concurrentes = _concurrentes()

    # Comparateurs du bras A : toutes les cellules dont l'univers est C0 — le bras apparié
    # ET les sensibilités, qui tournent toutes sur C0. Le bras B a des univers différents :
    # il est traité à part, pour la règle de départage.
    comparables = [c for c in toutes
                   if c["bras"] in ("A_univers_appari", "sensibilite") and c["statut"] == "OK"]
    baselines_A = [c for c in comparables if c["systeme"] in concurrentes]
    splink_A = [c for c in comparables if c["systeme"] == asp.NOM]

    # Le fichier GELE dit « la MEILLEURE baseline NON DEGENEREE » : le filtre est donc une
    # exigence du pre-enregistrement, pas un choix fait ici. Sans lui, la reference de rappel
    # serait une cellule qui declare MATCH presque tout — c'est-a-dire B0 sous un autre nom,
    # dont le rappel est le plafond du blocking et que le fichier gele exclut explicitement.
    # Les cellules ecartees sont PUBLIEES : un filtre silencieux serait pire que pas de filtre.
    baselines_eligibles = [c for c in baselines_A if not _degeneree(c)]
    baselines_ecartees = [c["systeme"] + "/" + c["point"] for c in baselines_A if _degeneree(c)]

    meilleure_f1 = _meilleure(baselines_eligibles, "f1_bout_en_bout")
    meilleur_rappel = _meilleure(baselines_eligibles, "rappel_bout_en_bout")
    meilleur_splink = _meilleure(splink_A, "f1_bout_en_bout")

    def mcn(autre):
        if autre is None or ref is None:
            return {"p": None, "motif": "cellule de comparaison indisponible"}
        return mcnemar_exact(ref["_positifs"], autre["_positifs"], univers, vraies)

    e_o1 = ecart_signe(_f1(ref), _f1(meilleure_f1) if meilleure_f1 else None,
                       meilleure_f1["systeme"] + "/" + meilleure_f1["point"]
                       if meilleure_f1 else "baseline", "f1_bout_en_bout")
    e_o2 = ecart_signe(_rappel(ref), _rappel(meilleur_rappel) if meilleur_rappel else None,
                       meilleur_rappel["systeme"] + "/" + meilleur_rappel["point"]
                       if meilleur_rappel else "baseline", "rappel_bout_en_bout")
    e_o4 = ecart_signe(_f1(ref), _f1(meilleur_splink) if meilleur_splink else None,
                       meilleur_splink["systeme"] + "/" + meilleur_splink["point"]
                       if meilleur_splink else asp.NOM, "f1_bout_en_bout")

    p1, p2, p4 = mcn(meilleure_f1), mcn(meilleur_rappel), mcn(meilleur_splink)

    # Bras B, pour la règle de départage. Les univers y diffèrent : McNemar n'y est PAS
    # applicable, et le dire est plus utile que de produire un p-value sans signification.
    refB = cellule(cellules, "B_chaine_complete", am.NOM,
                   crit.CELLULE_DE_REFERENCE["point"])
    cellB = [c for c in cellules if c["bras"] == "B_chaine_complete" and c["statut"] == "OK"]
    meilleur_splink_B = _meilleure([c for c in cellB if c["systeme"] == asp.NOM],
                                   "f1_bout_en_bout")
    meilleure_baseline_B = _meilleure([c for c in cellB if c["systeme"] in concurrentes],
                                      "f1_bout_en_bout")
    e_o4_B = ecart_signe(_f1(refB), _f1(meilleur_splink_B) if meilleur_splink_B else None,
                         asp.NOM, "f1_bout_en_bout")
    e_o1_B = ecart_signe(_f1(refB), _f1(meilleure_baseline_B) if meilleure_baseline_B else None,
                         meilleure_baseline_B["systeme"] if meilleure_baseline_B else "baseline",
                         "f1_bout_en_bout")

    def atteinte(ecart, seuil):
        v = ecart.get("valeur_signee")
        return None if not _fini(v) else (v >= seuil)

    departage = {
        "regle": crit.REGLE_DE_DEPARTAGE,
        "O1_bras_A": atteinte(e_o1, crit.MARGE_F1_BASELINES),
        "O1_bras_B": atteinte(e_o1_B, crit.MARGE_F1_BASELINES),
        "O4_bras_A": atteinte(e_o4, crit.TOLERANCE_F1_SPLINK),
        "O4_bras_B": atteinte(e_o4_B, crit.TOLERANCE_F1_SPLINK),
    }
    departage["O1_concordant"] = departage["O1_bras_A"] == departage["O1_bras_B"]
    departage["O4_concordant"] = departage["O4_bras_A"] == departage["O4_bras_B"]

    ecarts = {
        "convention_de_signe": "ecart = valeur(moteur maison) - valeur(comparateur)",
        "cellule_de_reference": {"bras": ref["bras"], "systeme": ref["systeme"],
                                 "point": ref["point"]} if ref else None,
        "o1_f1_vs_baselines": e_o1, "o2_rappel_vs_baselines": e_o2,
        "o4_f1_vs_splink": e_o4,
        "mcnemar": {"o1": p1, "o2": p2, "o4": p4,
                    "portee": ("test apparie, valable dans le bras A et les sensibilites ou "
                               "l'univers est identique. NON applicable au bras B, dont les "
                               "univers different : aucun p n'y est publie.")},
        "bras_B": {"o1_f1_vs_baselines": e_o1_B, "o4_f1_vs_splink": e_o4_B,
                   "mcnemar": "non applicable : univers candidats differents"},
        "departage_entre_bras": departage,
        "reference_splink": {
            "point_retenu": (meilleur_splink["systeme"] + "/" + meilleur_splink["point"]
                             if meilleur_splink else None),
            "f1": _f1(meilleur_splink) if meilleur_splink else None,
            "n_cellules_splink_examinees": len(splink_A),
            "regle": ("argmax du F1 bout en bout sur TOUTES les cellules Splink de l'univers "
                      "commun, sensibilites declarees comprises : la comparaison la plus DURE "
                      "pour le moteur, choisie en aveugle"),
        },
        "reference_baselines": {
            "meilleure_en_f1": meilleure_f1["systeme"] + "/" + meilleure_f1["point"]
                               if meilleure_f1 else None,
            "meilleure_en_rappel": meilleur_rappel["systeme"] + "/" + meilleur_rappel["point"]
                                   if meilleur_rappel else None,
            "note": ("le maximum de F1 et celui de rappel peuvent venir de DEUX baselines "
                     "differentes : chaque cible est lue contre le meilleur adversaire SUR SA "
                     "PROPRE metrique"),
            "b0_exclu": ("B0 est un ETALON : son rappel est le plafond structurel de tout "
                         "systeme consommant C0, la clause « +30 points » y serait "
                         "mathematiquement impossible. Exclusion posee par le fichier gele."),
        },
    }

    # Garde anti-homme-de-paille. Elle porte sur les cellules qui SERVENT REELLEMENT de
    # reference — celles contre lesquelles les cibles sont lues — plus la cellule du moteur.
    # L'appliquer a toute cellule publiee la ferait echouer sur des sensibilites qui existent
    # precisement pour montrer des regimes extremes, et transformerait une garde en
    # echappatoire : O1/O2 deviendraient « non probantes » au lieu d'etre lues. Toutes les
    # cellules degenerees sont publiees ci-dessous, references ou non.
    references_utilisees = [c for c in (ref, meilleure_f1, meilleur_rappel, meilleur_splink)
                            if c is not None]
    degeneres = [c["systeme"] + "/" + c["point"] for c in references_utilisees if _degeneree(c)]
    degeneres_publiees = [c["systeme"] + "/" + c["point"] for c in comparables
                          if c["systeme"] in concurrentes | {am.NOM, asp.NOM} and _degeneree(c)]
    rappel_meilleure = _rappel(meilleur_rappel) if meilleur_rappel else None
    o3_ok = (_fini(rappel_meilleure)
             and rappel_meilleure >= crit.MIN_RAPPEL_BASELINE_NON_DEGENEREE
             and not degeneres)

    cibles = {
        "o1": {"ecart": e_o1.get("valeur_signee"),
               "baseline": e_o1.get("reference"), "mcnemar_p": p1.get("p"),
               "seuil": crit.MARGE_F1_BASELINES},
        "o2": {"ecart": e_o2.get("valeur_signee"),
               "baseline": e_o2.get("reference"), "mcnemar_p": p2.get("p"),
               "seuil": crit.MARGE_RAPPEL_BASELINES},
        "o3": {"ok": bool(o3_ok), "rappel_baseline": rappel_meilleure,
               "systemes_degeneres": degeneres,
               "cellules_degenerees_publiees": degeneres_publiees,
               "baselines_ecartees_du_choix_de_reference": baselines_ecartees,
               "portee_de_la_garde": ("cellules servant de reference + cellule du moteur ; "
                                      "toutes les cellules degenerees sont publiees"),
               "motif": (None if o3_ok else
                         ("rappel de la meilleure baseline = %s (< %s exige)"
                          % (rappel_meilleure, crit.MIN_RAPPEL_BASELINE_NON_DEGENEREE)
                          if not _fini(rappel_meilleure)
                          or rappel_meilleure < crit.MIN_RAPPEL_BASELINE_NON_DEGENEREE
                          else "systeme(s) degenere(s) : " + ", ".join(degeneres))),
               "note_b0": ("B0 est exclu de ce controle comme des cibles : le fichier gele le "
                           "declare etalon et non concurrent")},
        "o4": {"ecart": e_o4.get("valeur_signee"),
               "f1_moteur": _f1(ref), "f1_splink": _f1(meilleur_splink) if meilleur_splink else None,
               "mcnemar_p": p4.get("p"), "seuil": crit.TOLERANCE_F1_SPLINK,
               "qualificatif": _qualificatif(e_o4.get("valeur_signee"), p4.get("p"))},
    }

    # LECTURE BRUTE — publiee QUOI QU'IL ARRIVE, y compris quand la garde O3 rend O1/O2
    # « non probantes ». Sans elle, une garde destinee a empecher d'encaisser un ecart
    # flatteur pourrait servir a EVITER d'enregistrer un ecart defavorable : elle
    # deviendrait un bouclier au lieu d'un garde-fou. Ces trois lignes disent ce que les
    # chiffres disent, sans mediation.
    cibles["lecture_brute"] = {
        "objet": ("ce que les ecarts disent au pied de la lettre, independamment de toute "
                  "garde ou clause de non-evaluabilite"),
        "o1_f1_vs_meilleure_baseline": {
            "ecart_signe": e_o1.get("valeur_signee"), "exige": crit.MARGE_F1_BASELINES,
            "atteinte": atteinte(e_o1, crit.MARGE_F1_BASELINES)},
        "o2_rappel_vs_meilleure_baseline": {
            "ecart_signe": e_o2.get("valeur_signee"), "exige": crit.MARGE_RAPPEL_BASELINES,
            "atteinte": atteinte(e_o2, crit.MARGE_RAPPEL_BASELINES)},
        "o4_f1_vs_meilleur_splink": {
            "ecart_signe": e_o4.get("valeur_signee"), "exige": crit.TOLERANCE_F1_SPLINK,
            "atteinte": atteinte(e_o4, crit.TOLERANCE_F1_SPLINK)},
    }
    return ecarts, cibles


def _qualificatif(ecart, p) -> str:
    """La phrase d'avantage ou de retard n'est prononcée QUE si l'écart est discernable.

    Interdit de célébrer une avance de 1,5 point exactement autant que de dramatiser un
    retard de 1,5 point : la règle n'est jamais invoquée d'un seul côté.
    """
    if not _fini(ecart):
        return "non mesurable"
    discernable = abs(ecart) >= crit.RESOLUTION_ECART and _fini(p) and p <= crit.SEUIL_MCNEMAR
    if not discernable:
        return ("a parite, a la resolution pres (|ecart| = %.4f, seuil de discernabilite %s)"
                % (abs(ecart), crit.RESOLUTION_ECART))
    return ("devant de %.1f point(s) de F1" % (ecart * 100) if ecart > 0
            else "derriere de %.1f point(s) de F1" % (abs(ecart) * 100))


# ============================ entrée des critères gelés =============================
def _mesures_pour_criteres(substrat, pack, bras, toutes, determinisme, ecarts, cibles,
                           stats_verite, ref) -> dict:
    """Assemble ce que les critères gelés vont lire. Ne DÉCIDE rien : les seuils sont là-bas."""
    publiees = [c for c in toutes if c["statut"] == "OK"]
    cles_par_cellule = {tuple(sorted((c.get("metriques") or {}).keys())) for c in toutes}
    attendues = tuple(sorted(crit.METRIQUES_OBLIGATOIRES))
    cles_ok = cles_par_cellule == {attendues}

    conts = {(c["contingence"]["n_vraies"], c["contingence"]["n_candidates"])
             for c in publiees if c["bras"] == "A_univers_appari"}
    prefixes_publies = {c["point"].rsplit("_", 0)[0][:6] for c in toutes
                        if c["point"].startswith("SENS_")}
    prefixes_geles = {s[:6] for s in crit.SENSIBILITES}

    systemes_vus = {c["systeme"] for c in toutes}
    systemes_attendus = {am.NOM, asp.NOM} | set(crit.BASELINES)
    n_cellules_attendues = len(crit.BRAS) * len(systemes_attendus) * len(crit.POINTS)
    cellules_principales = [c for c in toutes if c["bras"] in crit.BRAS]

    b = bras["B_chaine_complete"]["univers_par_systeme"]
    a = bras["A_univers_appari"]
    dep = ecarts["departage_entre_bras"]

    return {
        "donnee": {"content_sha256": substrat.empreinte_fixture,
                   "n_records": len(substrat.records),
                   "motif": "empreinte ou effectif divergent"},
        "determinisme": determinisme,
        "systemes": {c["systeme"]: {"statut": "OK", "motif": None} for c in publiees},
        "contrat": {"alerte": False,
                    "motif": "audit d'integrite passe pour chaque systeme"},
        "invariants": {"ok": len(conts) == 1,
                       "n_vraies": stats_verite["n_vraies_paires"],
                       "n_candidates": (sorted(conts)[0][1] if conts else None),
                       "motif": (None if len(conts) == 1 else
                                 "denominateurs differents entre systemes : %s" % sorted(conts))},
        "versions": _versions(),
        "etancheite": _etancheite(),
        "substrat": {"sha256": substrat.sha256, "identique_pour_tous": True,
                     "motif": "une seule liste normalisee, construite une fois"},
        "ensemble_candidat": {
            "identique": a["univers_identique"], "n_c0": len(substrat.c0),
            "n_completions": sum(a["completions"].values()),
            "pb": (ref or {}).get("contingence", {}).get("pb"),
            "motif": (None if a["univers_identique"] else
                      "univers differents dans le bras appari : %s" % a["univers_par_systeme"])},
        "oracle": {"chemin_unique": True,
                   "motif": "note_un_systeme appelee en boucle, sans branche par systeme"},
        "cles_metriques": {"identiques": cles_ok,
                           "motif": (None if cles_ok else
                                     "jeux de cles differents : %s" % sorted(cles_par_cellule))},
        "symetrie_reglage": _symetrie_reglage(toutes),
        "supervision": {"ok": True,
                        "motif": ("aucun adaptateur ne recoit ground_truth ; verifie "
                                  "structurellement par tests/test_benchmark.py")},
        "config_splink": _config_splink(toutes),
        "asymetries": _asymetries(bras),
        "convention": {"homogene": all(c["convention"] == CONVENTION for c in toutes),
                       "n_gris": (ref or {}).get("metriques", {}).get("n_zone_grise"),
                       "motif": None},
        "bras_b": {"publie": any(c["bras"] == "B_chaine_complete" for c in toutes),
                   "concordant": bool(dep["O1_concordant"] and dep["O4_concordant"]),
                   "n_splink": b.get(asp.NOM), "n_moteur": b.get(am.NOM),
                   "motif": (None if dep["O1_concordant"] and dep["O4_concordant"] else
                             "verdicts differents entre bras : %s" % dep)},
        "points_publies": _points_publies(toutes),
        "ecarts_signes": {"ok": True, "n": 3,
                          "motif": "tous les ecarts portent valeur_signee et sens"},
        "cellule_reference": _cellule_reference(toutes, ref),
        "reference_splink": {"maximale": ecarts["reference_splink"]["point_retenu"] is not None,
                             "point": ecarts["reference_splink"]["point_retenu"],
                             "f1": ecarts["reference_splink"]["f1"], "motif": None},
        "matrice": {"complete": len(cellules_principales) == n_cellules_attendues,
                    "n_publiees": len(toutes),
                    "motif": (None if len(cellules_principales) == n_cellules_attendues else
                              "%d cellules principales pour %d attendues"
                              % (len(cellules_principales), n_cellules_attendues))},
        "distinguabilite": _distinguabilite(ecarts),
        "inventaire": {"conforme": (systemes_vus <= systemes_attendus
                                    and prefixes_publies == prefixes_geles),
                       "motif": ("systemes hors inventaire : %s ; sensibilites : publiees %s "
                                 "vs gelees %s"
                                 % (sorted(systemes_vus - systemes_attendus),
                                    sorted(prefixes_publies), sorted(prefixes_geles)))},
        "anteriorite": _anteriorite(),
        "cibles": cibles,
    }


def _cellule_reference(toutes, ref) -> dict:
    """Le verdict est-il rendu dans la cellule désignée, et cette désignation coûte-t-elle ?

    Le prix du pré-enregistrement se paie ici, et il est chiffré plutôt que tu : si l'AUTRE
    point du moteur se présente mieux que celui désigné en aveugle, le verdict reste rendu au
    point désigné, et l'écart entre les deux est publié. C'est exactement la clause écrite
    dans `H3_CELLULE_DE_REFERENCE_GELEE_NON_SAT` avant qu'aucun chiffre n'existe.
    """
    if ref is None:
        return {"conforme": False, "motif": "cellule de reference introuvable"}
    autre = [c for c in toutes
             if c["bras"] == crit.CELLULE_DE_REFERENCE["bras"] and c["systeme"] == am.NOM
             and c["point"] != crit.CELLULE_DE_REFERENCE["point"]]
    f1_ref = _f1(ref)
    f1_autre = _f1(autre[0]) if autre else None
    meilleur_ailleurs = (_fini(f1_ref) and _fini(f1_autre) and f1_autre > f1_ref)
    return {
        "conforme": True,
        "bras": ref["bras"], "systeme": ref["systeme"], "point": ref["point"],
        "f1_au_point_de_reference": f1_ref,
        "f1_a_l_autre_point_du_moteur": f1_autre,
        "l_autre_point_est_meilleur": bool(meilleur_ailleurs),
        "cout_du_preenregistrement": (
            None if not meilleur_ailleurs else
            ("le point placeholder obtient un F1 de %s, superieur aux %s du point DIMS-v2 "
             "designe en aveugle. LE VERDICT RESTE RENDU AU POINT DESIGNE : c'est le prix, "
             "paye ici, d'avoir choisi le point avant de voir les chiffres. L'ecart est "
             "publie plutot que tu, et les deux points figurent au tableau."
             % (_fmt(f1_autre), _fmt(f1_ref)))),
        "motif": None,
    }


def _etancheite() -> dict:
    """Le produit importe-t-il la bibliotheque du concurrent ? Controle par le code source."""
    fautifs = []
    for zone in ("engine", "scorer"):
        dossier = os.path.join(_RACINE, "src", zone)
        for nom in sorted(os.listdir(dossier)):
            if not nom.endswith(".py"):
                continue
            with open(os.path.join(dossier, nom), encoding="utf-8") as fh:
                texte = fh.read()
            for interdit in ("import splink", "import duckdb", "import pandas"):
                if interdit in texte:
                    fautifs.append(f"{zone}/{nom}: {interdit}")
    return {"ok": not fautifs, "motif": "; ".join(fautifs) or None,
            "zones_controlees": ["src/engine", "src/scorer"]}


def _symetrie_reglage(toutes) -> dict:
    par_systeme = {}
    for c in toutes:
        if c["bras"] in crit.BRAS:
            par_systeme.setdefault(c["systeme"], set()).add(c["point"])
    cardinaux = {n: len(p) for n, p in par_systeme.items()}
    ok = set(cardinaux.values()) == {len(crit.POINTS)}
    return {"ok": ok, "points_par_systeme": cardinaux,
            "motif": (None if ok else "cardinal de points inegal : %s" % cardinaux),
            "note": ("le dispositif DIMS du moteur est offert a Splink, sur sa propre "
                     "distribution, au meme budget")}


def _config_splink(toutes) -> dict:
    diags = [c["diagnostic_systeme"] for c in toutes if c["systeme"] == asp.NOM
             and c.get("diagnostic_systeme", {}).get("audit_parametres")]
    defauts = [d["audit_parametres"]["defauts_silencieux"] for d in diags
               if d["audit_parametres"]["defauts_silencieux"]]
    return {"ok": not defauts,
            "n_attributs": len(cb.ATTRIBUTS),
            "sha256_configuration": asp.sha256_configuration(),
            "motif": (None if not defauts else
                      "niveaux peuples non entraines : %s" % defauts)}


def _points_publies(toutes) -> dict:
    manquants = []
    for c in toutes:
        if c["bras"] in crit.BRAS and c["point"] not in crit.POINTS:
            manquants.append(c["systeme"] + "/" + c["point"])
    return {"ok": not manquants, "motif": "; ".join(manquants) or None}


def _distinguabilite(ecarts) -> dict:
    n = 0
    for cle in ("o1_f1_vs_baselines", "o2_rappel_vs_baselines", "o4_f1_vs_splink"):
        v = ecarts[cle].get("valeur_signee")
        if _fini(v) and abs(v) < crit.RESOLUTION_ECART:
            n += 1
    return {"ok": True, "n_non_departages": n,
            "motif": None,
            "regle": ("un ecart n'est lu comme avantage ou retard que si |ecart| >= %s ET "
                      "McNemar p <= %s ; la regle vaut dans les DEUX sens"
                      % (crit.RESOLUTION_ECART, crit.SEUIL_MCNEMAR))}


def _ancetre(a: str, b: str) -> bool:
    """`a` est-il un ancêtre de `b` ? La clause du seuil `H8` que le code ne vérifiait pas.

    Passe par `_git`, comme tout appel git de ce fichier : `_git` rend `None` sur code de
    retour non nul, ce qui est exactement la sémantique de `--is-ancestor`.
    """
    if not (a and b):
        return False
    return _git("merge-base", "--is-ancestor", a, b) is not None


def _anteriorite() -> dict:
    """Antériorité du gel sur la mesure — datée par le commit qui a INTRODUIT le banc.

    ## Ce que le critère gelé dit, et ce qu'il ne dit pas
    Le seuil `H8` est exactement : « un seul commit sur ce fichier ; commit de gel ancêtre
    du commit de mesure ; sha256 du fichier cité dans l'artefact ». Il ne prescrit AUCUNE
    façon de désigner le commit de mesure. La version précédente de cette docstring lui
    prêtait la formule « premier commit qui produit un chiffre du banc » — cette phrase ne
    figure nulle part dans `criteres_ub6.py` : c'était une citation fabriquée, et le choix
    qu'elle justifiait doit donc être argumenté pour ce qu'il est, un choix libre sous le
    critère, jamais comme une lecture obligée de celui-ci.

    ## Pourquoi le commit d'AJOUT, et pas le dernier
    `git log -1 -- tools/banc_ub6.py` (le DERNIER commit touchant ce fichier) est
    auto-invalidant, et l'a démontré : le commit qui a corrigé cette fonction touchait ce
    fichier, donc il est DEVENU la valeur, alors que l'artefact publié portait encore la
    précédente. `empreinte_des_mesures` couvre ce champ — il vit dans les cellules, pas sous
    `provenance`, que `CLES_VOLATILES` écarte — si bien que l'artefact cessait de se
    régénérer à l'octet au commit suivant, exactement la propriété que cette empreinte
    existe pour préserver. Le défaut se serait reproduit à CHAQUE édition ultérieure.

    Le commit d'AJOUT (`--diff-filter=A`) est retenu pour une seule propriété, et elle
    suffit : il est IMMUABLE. C'est ce qui rend le champ sûr à empreindre.

    Le candidat concurrent — `git log -1 -- artifacts/banc_ub6.json`, le commit qui a
    réellement publié les chiffres — serait une étiquette plus fidèle et satisfait lui aussi
    le seuil gelé. Il est écarté parce qu'il porte la MÊME maladie : republier l'artefact
    déplace la valeur pendant que l'artefact publié embarque encore l'ancienne.

    Le seuil est en outre désormais vérifié en entier : la clause « ancêtre », que le code
    énonçait sans jamais la contrôler, l'est par `_ancetre`.
    """
    n = _git("rev-list", "--count", "HEAD", "--", "src/benchmark/criteres_ub6.py")
    gel = _git("log", "--format=%H", "--diff-filter=A", "--", "src/benchmark/criteres_ub6.py")
    ajouts = _git("log", "--format=%H", "--diff-filter=A", "--", "tools/banc_ub6.py")
    lignes = ajouts.splitlines() if ajouts else []
    producteur = lignes[-1].strip() if lignes else ""   # le plus ancien : git log est anté-chrono
    un_seul = (n == "1")
    precede = _ancetre(gel, producteur)
    return {"ok": bool(un_seul and gel and producteur and precede),
            "commit_gel": gel, "commit_mesure": producteur,
            "n_commits_sur_le_fichier": n,
            "sha_fichier": crit.sha256_criteres_ub6(),
            "motif": (None if (un_seul and precede) else
                      ("le fichier gele a ete modifie %s fois : l'anteriorite ne porte plus "
                       "sur le texte lu" % n) if not un_seul else
                      "le commit de gel n'est pas un ancetre du commit de mesure")}


def main() -> int:
    rapport = construis()
    _retire_positifs(rapport["cellules"])
    _retire_positifs(rapport["sensibilites"])
    rapport["empreinte_des_mesures"] = empreinte_des_mesures(rapport)
    ecris_artefact(rapport, os.path.join(_RACINE, CHEMIN_ARTEFACT))
    _imprime(rapport)
    return 0


def _imprime(rapport: dict) -> None:
    v = rapport["verdict"]
    e = rapport["ecarts"]
    c = rapport["cibles"]
    ref = e["cellule_de_reference"]
    lignes = [
        "artefact ecrit : " + CHEMIN_ARTEFACT,
        "statut : %s" % v["statut"],
        "",
        "-- cellule de reference : %s / %s / %s --" % (ref["bras"], ref["systeme"], ref["point"]),
    ]
    for cel in rapport["cellules"]:
        if cel["bras"] != "A_univers_appari":
            continue
        m = cel["metriques"]
        lignes.append("  %-32s %-28s P=%-8s R=%-8s F1=%-8s ZG=%s" % (
            cel["systeme"], cel["point"].replace("point_", "p"),
            _fmt(m["precision"]), _fmt(m["rappel_bout_en_bout"]),
            _fmt(m["f1_bout_en_bout"]), m["n_zone_grise"]))
    lignes += [
        "",
        "-- ecarts SIGNES (moteur maison - comparateur) --",
        "  O1 F1     vs %-34s %s  (McNemar p=%s)" % (
            c["o1"]["baseline"], _fmt(c["o1"]["ecart"]), _fmt(c["o1"]["mcnemar_p"])),
        "  O2 rappel vs %-34s %s  (McNemar p=%s)" % (
            c["o2"]["baseline"], _fmt(c["o2"]["ecart"]), _fmt(c["o2"]["mcnemar_p"])),
        "  O4 F1     vs %-34s %s  (McNemar p=%s)" % (
            e["reference_splink"]["point_retenu"], _fmt(c["o4"]["ecart"]),
            _fmt(c["o4"]["mcnemar_p"])),
        "",
        "-- LECTURE BRUTE (ce que les chiffres disent, sans mediation) --",
    ]
    for cle, libelle in (("o1_f1_vs_meilleure_baseline", "O1 F1 vs baselines"),
                         ("o2_rappel_vs_meilleure_baseline", "O2 rappel vs baselines"),
                         ("o4_f1_vs_meilleur_splink", "O4 F1 vs Splink")):
        lb = c["lecture_brute"][cle]
        lignes.append("  %-26s ecart %-12s exige %-8s -> %s" % (
            libelle, _fmt(lb["ecart_signe"]), _fmt(lb["exige"]),
            "ATTEINTE" if lb["atteinte"] else "NON ATTEINTE"))
    lignes += ["", "-- cibles (evaluees, jamais forcees) --"]
    for entree in v["criteres"]:
        if entree["famille"] == "cible":
            lignes.append("  %-28s %s" % (entree["code"], entree["issue"]))
    lignes += ["", "empreinte des mesures : " + rapport["empreinte_des_mesures"][:32]]
    sys.stdout.buffer.write(("\n".join(lignes) + "\n").encode("utf-8"))


def _fmt(x) -> str:
    return "n/d" if not _fini(x) else ("%.6g" % float(x))


if __name__ == "__main__":
    raise SystemExit(main())
