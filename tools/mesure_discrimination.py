# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Produit `artifacts/discrimination_v1_2.json` (objectifs O2/O3).

    .venv\\Scripts\\python tools/mesure_discrimination.py

## Pourquoi ce script vit HORS de `src/`
C'est le SEUL fichier du dépôt qui importe à la fois `engine` et `scorer`, et il ne les couple
pas pour autant : ils s'y rencontrent **par données**. Le moteur produit des CORRESPONDENCE
sans jamais voir la vérité terrain ; le scoreur lit ces CORRESPONDENCE et la vérité terrain
sans jamais voir le moteur. Placer ce point de rencontre dans `src/` ferait de l'un une
dépendance de l'autre et romprait la non-circularité — la même raison qui met
`tools/dimensionne_seuils.py` hors de `src/engine/`.

## Deux régimes de seuils, publiés côte à côte
- `seuils_placeholder`  : Tμ = +8, Tλ = −8 — la bande spontanée, non dimensionnée.
- `seuils_dimensionnes` : Tμ/Tλ issus de `threshold_sizing` REJOUÉ sur V1.2, non supervisé.

Aucun des deux n'est désigné comme « le bon » : le sélectionner au vu des mesures serait déjà
une calibration. Les deux ont une forme d'artefact identique, et le régime dimensionné sert de
référence aux quantités qui ne dépendent pas des seuils (la distribution de `R` est publiée
une seule fois, hors des régimes — `R` ne dépend pas d'eux).

## La fixture est CONSOMMÉE, jamais éditée
Elle est ouverte en lecture seule et son `content_sha256` est revérifié à l'ouverture : un
écart arrête le programme. Aucune écriture vers la zone de test n'existe dans ce fichier ; un
test le vérifie par analyse du code source.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RACINE, "src"))

import engine                                            # noqa: E402
import scorer                                            # noqa: E402
from engine import threshold_sizing as ts                # noqa: E402

#: Chemin POSIX relatif à la racine du repo (aucun chemin absolu OS-spécifique).
CHEMIN_FIXTURE = "fixtures/FIXTURE_PACK_GT_V1_2.json"
#: Empreinte attendue — celle que le manifest du pack déclare, recalculée au 1er pas du scoreur
#: (mandat §2, `source_env_hash`).
CONTENT_SHA256_V1_2 = "66f627edb37022dcecab04dae9c327b342d8dfbb785533ffe8017919000117a2"

#: Passes de blocking sous lesquelles cet artefact a été PUBLIÉ.
#: Épinglées ICI, et non héritées de `blocking.PASSES_DEFAUT`, depuis que le banc de
#: comparaison a retiré `SDX_NOM` du défaut (objectif O0a). Ce retrait est qualifié
#: d'« exécution ADDITIONNELLE », avec « l'antériorité des paramètres préservée » : la mesure
#: de discrimination du scoreur continue donc de décrire le moteur TEL QU'IL ÉTAIT MESURÉ, et
#: n'est pas réécrite par un changement de défaut survenu dans une unité ultérieure. La
#: comparaison du banc, elle, tourne sur le nouveau défaut : les deux coexistent sans qu'aucune
#: n'efface l'autre, ce qui est exactement le sens d'une exécution additionnelle.
PASSES_PUBLIEES = ("CP", "SDX_NOM", "PREF")


def _git(*args) -> str:
    """Sortie d'une commande git, ou `None` si le dépôt n'est pas interrogeable.

    La provenance ne doit jamais faire échouer une mesure : si git est indisponible, le champ
    est nul et le dit, plutôt que d'interrompre le calcul.
    """
    try:
        return subprocess.check_output(["git"] + list(args), cwd=_RACINE, text=True).strip()
    except Exception:
        return None


def _arbre_propre_hors_artefact() -> bool:
    """L'arbre de travail est-il propre, une fois l'artefact de sortie mis de côté ?"""
    etat = _git("status", "--porcelain")
    if etat is None:
        return None
    cible = scorer.CHEMIN_ARTEFACT.replace("\\", "/")
    restant = [ligne for ligne in etat.splitlines()
               if cible not in ligne.replace("\\", "/")]
    return not restant


def provenance(pack: dict, parametres_par_regime: dict, rapport_moteur: dict) -> dict:
    """Tout ce qui permet à un tiers de refaire exactement cette mesure."""
    estimation = rapport_moteur.get("estimation") or {}
    return {
        "fixture": {
            "chemin_relatif_repo": CHEMIN_FIXTURE,
            "content_sha256_recalcule": scorer.empreinte_pack(pack),
            "content_sha256_attendu": CONTENT_SHA256_V1_2,
            "seal_declare": (pack.get("manifest") or {}).get("seal_sha256_16"),
            "version_declaree": (pack.get("manifest") or {}).get("version"),
            "canonicalisation": (
                "sha256(UTF-8(json.dumps({records, ground_truth, corruption_annotation}, "
                "sort_keys=True, ensure_ascii=False, separators=(', ', ': ')))) ; manifest exclu"),
            "note_canonicalisation": (
                "V1.2 a RETIRE la cle 'zone_intention_design' presente en V1.1 : la "
                "canonicalisation a 4 cles ne s'y applique pas. Le jeu de "
                "cles fait donc partie de la reference, et il est celui que le manifest du pack "
                "declare lui-meme."),
        },
        "commit_engine": _git("rev-parse", "HEAD"),
        "commit_de_gel_des_criteres": _git("log", "-1", "--format=%H", "--",
                                           "src/scorer/criteres.py"),
        "branche": _git("rev-parse", "--abbrev-ref", "HEAD"),
        # L'artefact que cette execution produit est EXCLU du controle de proprete : sa
        # presence en cours d'ecriture salirait l'arbre a chaque run, et le champ ne dirait
        # plus rien du code qui a produit la mesure — la seule chose qu'il doive attester.
        "arbre_de_travail_propre": _arbre_propre_hors_artefact(),
        "note_proprete": ("l'artefact produit par cette execution est exclu du controle : le "
                          "champ atteste l'etat du CODE, pas celui de sa sortie"),
        "version_python": sys.version.split()[0],
        "parametres_moteur_par_regime": parametres_par_regime,
        "estimation_em": {
            "convergence": estimation.get("convergence"),
            "iterations": estimation.get("iterations"),
            "repli": estimation.get("repli"),
            "motif_repli": estimation.get("motif_repli"),
            "champs_repli": estimation.get("champs_repli"),
            "echange_de_classes": estimation.get("echange_de_classes"),
            "graine": estimation.get("graine"),
            "p": estimation.get("p"),
            "note": ("l'estimation EM est NON SUPERVISEE : aucune etiquette n'y entre, donc "
                     "aucune fuite de verite terrain n'est possible a cette etape"),
        },
        "graine_split_scellee": scorer.GRAINE_SPLIT_SCELLEE,
        "version_scoreur": "U-B5 / scorer 1.0",
    }


def construis(chemin_fixture: str = CHEMIN_FIXTURE) -> dict:
    """Exécute le moteur sous les deux régimes et assemble l'artefact."""
    chemin = os.path.join(_RACINE, chemin_fixture)
    pack = scorer.charge_pack(chemin, CONTENT_SHA256_V1_2)
    records = pack["records"]                    # le moteur ne recoit QUE les records

    # --- Régime 1 : les placeholders declares, bande spontanee -----------------------
    params_placeholder = engine.ParametresMoteur(passes_blocking=PASSES_PUBLIEES)
    sortie_placeholder = engine.execute_moteur(records, params_placeholder)

    # --- Dimensionnement NON SUPERVISE : ne lit que poids_match et un budget ---------
    dimensionnement = ts.dimensionne_depuis_correspondances(
        sortie_placeholder["correspondances"])
    params_dimensionnes = engine.ParametresMoteur(t_mu=dimensionnement["t_mu"],
                                                  t_lambda=dimensionnement["t_lambda"],
                                                  passes_blocking=PASSES_PUBLIEES)
    sortie_dimensionnee = engine.execute_moteur(records, params_dimensionnes)

    regimes = {
        "seuils_placeholder": {
            "correspondances": sortie_placeholder["correspondances"],
            "rapport_moteur": sortie_placeholder["rapport"],
            "seuils": {
                "t_mu": params_placeholder.t_mu, "t_lambda": params_placeholder.t_lambda,
                "frontiere": None, "budget_vise": None, "budget_atteint": None,
                "methode": "placeholders declares a +/- 8 bits (GAP-A), non calibres",
                "provisoire": True,
            },
        },
        "seuils_dimensionnes": {
            "correspondances": sortie_dimensionnee["correspondances"],
            "rapport_moteur": sortie_dimensionnee["rapport"],
            "seuils": {
                "t_mu": dimensionnement["t_mu"], "t_lambda": dimensionnement["t_lambda"],
                "frontiere": dimensionnement["frontiere"],
                "budget_vise": dimensionnement["budget_vise"],
                "budget_atteint": dimensionnement["budget_atteint"],
                "methode": dimensionnement["methode"],
                "provisoire": dimensionnement["provisoire"],
            },
        },
    }
    prov = provenance(
        pack,
        {"seuils_placeholder": {"t_mu": params_placeholder.t_mu,
                                "t_lambda": params_placeholder.t_lambda},
         "seuils_dimensionnes": {"t_mu": params_dimensionnes.t_mu,
                                 "t_lambda": params_dimensionnes.t_lambda}},
        sortie_dimensionnee["rapport"])
    return scorer.construis_rapport(pack, regimes, prov)


def _imprime(rapport: dict) -> None:
    """Résumé console : le triplet de verdict et les chiffres qui le fondent."""
    verdict = rapport["verdict"]
    reg = rapport["regimes"]["seuils_dimensionnes"]
    tete = reg["mesures_par_convention"][rapport["regimes"]["seuils_dimensionnes"]["convention_de_tete"]]
    sep = rapport["distribution_r"]["par_perimetre"]["principal"]["separation"]
    zg = reg["zone_grise"]
    lignes = [
        "artefact ecrit : " + scorer.CHEMIN_ARTEFACT,
        "statut : %s" % verdict["statut"],
        "",
        "-- regime SEUILS DIMENSIONNES, convention stricte --",
        "  precision            = %s" % tete["precision"],
        "  rappel bout en bout  = %s  (IC95 %s)" % (tete["rappel_bout_en_bout"],
                                                    tete["ic_wilson_95"]["rappel_bout_en_bout"]),
        "  F1 bout en bout      = %s" % tete["f1_bout_en_bout"],
        "  rappel de blocking   = %s  (%d vraie(s) paire(s) perdue(s) avant tout scoring)"
        % (rapport["couverture_blocking"]["rappel_blocking"],
           rapport["couverture_blocking"]["n_vraies_perdues"]),
        "",
        "-- separation des distributions de R --",
        "  auc = %s   (%s paire(s) equivalente(s) mal classee(s))"
        % (sep["auc"], sep["paires_vraies_equivalentes_mal_classees"]),
        "  ovl = %s   marge = %s" % (sep["ovl"], sep["marge_de_separation"]),
        "",
        "-- zone grise --",
        "  %d paires : %d vraies / %d fausses ; part mixte = %s ; plancher de Bayes = %s"
        % (zg["composition"]["n_gris"], zg["composition"]["n_vraies_gris"],
           zg["composition"]["n_fausses_gris"], zg["irreductibilite"]["part_paires_mixtes"],
           zg["irreductibilite"]["plancher_bayes_bande"]),
        "",
        "-- TRIPLET DE VERDICT --",
        "  blocking exerce : %s" % verdict["triplet"]["blocking_exerce"],
        "  decision exercee: %s" % verdict["triplet"]["decision_exercee"],
        "  doute exerce    : %s" % verdict["triplet"]["doute_exerce"],
        "",
        verdict["lecture_globale"],
        "",
        "empreinte des mesures : " + rapport["empreinte_des_mesures"],
    ]
    sys.stdout.buffer.write(("\n".join(lignes) + "\n").encode("utf-8"))


def main() -> int:
    rapport = construis()
    scorer.ecris_artefact(rapport, os.path.join(_RACINE, scorer.CHEMIN_ARTEFACT))
    _imprime(rapport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
