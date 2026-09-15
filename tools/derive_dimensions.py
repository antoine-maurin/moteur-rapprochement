# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Re-dérivation TRAÇABLE des seuils DIMS-v2 sur FX_001 V1.2 (O0b).

    .venv\\Scripts\\python tools/derive_dimensions.py

## Pourquoi ce fichier existe
Les seuils DIMS mesurés informellement par le scoreur (`Tλ ≈ −2,41` / `Tμ ≈ +2,32`)
**ne doivent pas être recopiés**. Deux raisons, et la seconde suffit à elle seule :

1. ils ont été dérivés sur l'ensemble candidat à TROIS passes, que le retrait de `SDX_NOM`
   (O0a) vient de modifier — les recopier décrirait un moteur qui n'existe plus ;
2. une constante recopiée n'a **pas de provenance**. Un seuil qu'on ne peut pas re-dériver est
   un seuil qu'on ne peut pas contester : il devient un paramètre libre, et un paramètre libre
   dans un banc de comparaison est exactement ce qu'un lecteur hostile doit pouvoir suspecter.

La dette §12.1 du verdict DIMS se solde donc ici : les seuils deviennent un **événement de
build**, daté par un commit, reproductible par quiconque relance ce script.

## Non-circularité — ce fichier est structurellement incapable de tricher
Il n'importe QUE `engine`. Ni `scorer`, ni `splink`. Il ne lit que `pack["records"]`, et la
vérité terrain n'est jamais chargée : `ground_truth` n'apparaît pas dans ce fichier, et un test
le vérifie par analyse du code source. C'est ce qui permet d'affirmer que les seuils DIMS-v2
sont **non supervisés** — non parce qu'on l'a voulu, mais parce que ce programme n'a pas accès
à ce qu'il faudrait pour faire autrement.

L'empreinte de la fixture est recalculée ici avec `hashlib` plutôt qu'en appelant le scoreur :
faire dépendre les seuils du moteur d'un module de mesure mettrait un scoreur dans leur
provenance, ce qui est précisément ce que la non-circularité interdit.

## Ce que le dimensionnement fait, et ne fait pas
`threshold_sizing` place `Tλ < Tμ` sur la SEULE distribution de `R`, de sorte que la bande
grise capture environ un **budget de revue**. Il choisit un VOLUME de revue, pas un taux
d'erreur : ce n'est pas une calibration, et aucune valeur cible de qualité n'y entre.
Les seuils restent **PROVISOIRES**, comme ils l'étaient pour la revue de zone grise.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RACINE, "src"))

import engine                                            # noqa: E402
from engine import threshold_sizing as ts                # noqa: E402

#: Chemin POSIX relatif à la racine du repo (aucun chemin absolu OS-spécifique).
CHEMIN_FIXTURE = "fixtures/FIXTURE_PACK_GT_V1_2.json"
CHEMIN_ARTEFACT = os.path.join("artifacts", "dimensions.json")
CONTENT_SHA256_V1_2 = "66f627edb37022dcecab04dae9c327b342d8dfbb785533ffe8017919000117a2"

#: Canonicalisation de l'empreinte du pack V1.2, telle que SON manifest la déclare. V1.1
#: hachait quatre blocs ; V1.2 a retiré `zone_intention_design`. Le jeu de clés fait donc
#: partie de la référence — c'est la même discipline que `scorer.verite`, réimplémentée ici
#: pour que ce fichier n'ait aucune dépendance vers la zone de mesure (cf. ci-dessus).
CLES_CANONICALISEES = ("records", "ground_truth", "corruption_annotation")

#: Budget de revue, repris tel quel de `engine.BUDGET_REVUE_DEFAUT` (60 paires/min x 5 min).
#: Non re-dérivé ici : le débit réel de la revue de zone grise n'est toujours pas mesuré.
BUDGET_REVUE = ts.BUDGET_REVUE_DEFAUT


def empreinte_pack(pack: dict) -> str:
    """`content_sha256` du pack : sha256 des octets UTF-8 de la forme canonique, manifest EXCLU."""
    canon = json.dumps({k: pack[k] for k in CLES_CANONICALISEES},
                       sort_keys=True, ensure_ascii=False, separators=(', ', ': '))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def charge_records(chemin: str) -> tuple:
    """Ouvre le pack en LECTURE SEULE, vérifie son empreinte, et ne rend QUE les records.

    La signature est la garde : elle ne rend pas le pack. Un appelant ne peut donc pas, par
    inadvertance, faire entrer `ground_truth` dans la suite du calcul.
    """
    with open(chemin, encoding="utf-8") as fh:
        pack = json.load(fh)
    obtenue = empreinte_pack(pack)
    if obtenue != CONTENT_SHA256_V1_2:
        raise ValueError(
            f"empreinte de pack divergente : attendu {CONTENT_SHA256_V1_2}, obtenu {obtenue}. "
            f"La fixture n'est pas celle que le mandat designe.")
    return pack["records"], obtenue


def _git(*args):
    """Sortie d'une commande git, ou `None` si le dépôt n'est pas interrogeable.

    La provenance ne doit jamais faire échouer un calcul : si git est indisponible, le champ
    est nul et le dit, plutôt que d'interrompre la dérivation.
    """
    try:
        return subprocess.check_output(["git"] + list(args), cwd=_RACINE, text=True).strip()
    except Exception:
        return None


def construis(chemin_fixture: str = CHEMIN_FIXTURE, budget_revue: int = BUDGET_REVUE) -> dict:
    """Rejoue le moteur puis le module DIMS sur V1.2, et assemble l'artefact de provenance."""
    records, empreinte = charge_records(os.path.join(_RACINE, chemin_fixture))

    passes = engine.PASSES_DEFAUT                 # ("CP", "PREF") depuis O0a
    params = engine.ParametresMoteur(passes_blocking=passes)
    sortie = engine.execute_moteur(records, params)
    correspondances = sortie["correspondances"]

    dimensionnement = ts.dimensionne_depuis_correspondances(
        correspondances, budget_revue=budget_revue, frontiere=ts.FRONTIERE_NEUTRE)

    # Empreinte de la DISTRIBUTION qui a produit les seuils : c'est elle qui rend la
    # dérivation contestable. Un tiers qui obtient la même distribution doit obtenir les
    # mêmes seuils ; s'il obtient une autre distribution, il sait immédiatement pourquoi.
    valeurs_r = [c["poids_match"] for c in correspondances]
    empreinte_r = hashlib.sha256(
        json.dumps(sorted(valeurs_r), separators=(",", ":")).encode("utf-8")).hexdigest()

    return {
        "_lisez_moi": (
            "Seuils DIMS-v2, RE-DERIVES sur FX_001 V1.2 apres le retrait de la passe SDX_NOM. "
            "Ils ne sont PAS recopies de la "
            "mesure informelle anterieure du scoreur : celle-ci portait sur l'ensemble candidat a "
            "trois passes, qui n'existe plus. Cet artefact est l'evenement de build qui solde "
            "la dette 12.1 du verdict DIMS. Seuils PROVISOIRES : ils placent un volume "
            "de revue, ils ne pretendent pas etre optimaux, et aucune valeur cible de qualite "
            "n'y entre."),
        "objectif": "O0b",
        "statut": "PROVISOIRE",
        "gap": "calibration différée",
        "seuils_dimensions": {
            "t_mu": dimensionnement["t_mu"],
            "t_lambda": dimensionnement["t_lambda"],
            "frontiere": dimensionnement["frontiere"],
            "budget_vise": dimensionnement["budget_vise"],
            "budget_atteint": dimensionnement["budget_atteint"],
            "ecart_au_budget": dimensionnement["ecart_au_budget"],
            "taille_zone_grise": dimensionnement["taille_zone_grise"],
            "budget_sature": dimensionnement["budget_sature"],
            "methode": dimensionnement["methode"],
            "repli": dimensionnement["repli"],
            "motif_repli": dimensionnement["motif_repli"],
            "provisoire": dimensionnement["provisoire"],
        },
        "derivation": {
            "nature": "RE-RUN du module threshold_sizing, jamais une constante recopiee",
            "module": "engine.threshold_sizing.dimensionne_depuis_correspondances",
            "entree": ("la seule liste des poids_match (R) des correspondances du moteur ; "
                       "aucune autre information de la correspondance n'entre dans le calcul"),
            "n_paires_notees": len(correspondances),
            "empreinte_distribution_r": empreinte_r,
            "statistiques_r": dimensionnement["statistiques_r"],
            "reproductible_par": ("relancer tools/derive_dimensions.py sur la meme fixture et le "
                                  "meme commit de moteur redonne ces seuils au bit pres"),
        },
        "configuration_moteur": {
            "passes_blocking": list(passes),
            "longueur_prefixe": params.longueur_prefixe,
            "t_mu_amont": params.t_mu,
            "t_lambda_amont": params.t_lambda,
            "note_amont": ("les seuils AMONT sont les placeholders : le dimensionnement lit la "
                           "distribution de R, qui ne depend pas des seuils"),
            "passes_retirees_du_defaut": {
                nom: dict(detail) for nom, detail in engine.PASSES_RETIREES_DU_DEFAUT.items()},
        },
        "cc1": {
            "verite_terrain_lue": False,
            "modules_importes": ["engine"],
            "note": ("ce programme n'importe pas le scoreur et ne charge jamais ground_truth : "
                     "le dimensionnement est non supervise par CONSTRUCTION, pas par promesse"),
        },
        "provenance": {
            "fixture": {
                "chemin_relatif_repo": chemin_fixture,
                "content_sha256_recalcule": empreinte,
                "content_sha256_attendu": CONTENT_SHA256_V1_2,
            },
            "commit_engine": _git("rev-parse", "HEAD"),
            "branche": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "version_python": sys.version.split()[0],
            "graine_em": params.graine_em,
            "budget": {
                "valeur": budget_revue,
                "debit_par_minute": ts.DEBIT_REVUE_PAR_MINUTE_PROVISOIRE,
                "duree_minutes": ts.DUREE_REVUE_MINUTES_PROVISOIRE,
                "statut": "PROVISOIRE : le debit reel de la revue de zone grise n'est pas mesure",
            },
        },
        "estimation_em": {
            "convergence": (sortie["rapport"].get("estimation") or {}).get("convergence"),
            "iterations": (sortie["rapport"].get("estimation") or {}).get("iterations"),
            "repli": (sortie["rapport"].get("estimation") or {}).get("repli"),
            "note": ("l'estimation EM est NON SUPERVISEE : aucune etiquette n'y entre, donc "
                     "aucune fuite de verite terrain n'est possible a cette etape"),
        },
    }


def serialisation_canonique(rapport: dict) -> str:
    """JSON canonique, trié, sans horodatage : deux exécutions donnent le même fichier."""
    return json.dumps(rapport, sort_keys=True, ensure_ascii=False, indent=1) + "\n"


def ecris_artefact(rapport: dict, chemin: str) -> None:
    with open(chemin, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(serialisation_canonique(rapport))


def main() -> int:
    rapport = construis()
    ecris_artefact(rapport, os.path.join(_RACINE, CHEMIN_ARTEFACT))
    s = rapport["seuils_dimensions"]
    lignes = [
        "artefact ecrit : " + CHEMIN_ARTEFACT,
        "",
        "-- seuils DIMS-v2 (re-derives sur V1.2, passes %s) --"
        % (",".join(rapport["configuration_moteur"]["passes_blocking"])),
        "  T_mu      = %s" % s["t_mu"],
        "  T_lambda  = %s" % s["t_lambda"],
        "  frontiere = %s" % s["frontiere"],
        "  budget    = %s vise / %s atteint (ecart %s)"
        % (s["budget_vise"], s["budget_atteint"], s["ecart_au_budget"]),
        "",
        "  paires notees            : %s" % rapport["derivation"]["n_paires_notees"],
        "  empreinte distribution R : %s" % rapport["derivation"]["empreinte_distribution_r"][:16],
        "  verite terrain lue       : %s" % rapport["cc1"]["verite_terrain_lue"],
    ]
    sys.stdout.buffer.write(("\n".join(lignes) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
