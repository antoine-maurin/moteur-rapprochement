# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Produit `artifacts/contribution_llm.json` (O2).

    .venv\\Scripts\\python tools/contribution_llm.py

## Pourquoi ce fichier vit HORS de `src/engine/`
Mesurer ce qu'une revue apporte exige de lire la vérité terrain. Le moteur ne doit jamais
la lire — c'est la frontière de non-circularité, et c'est ce qui fait que la mesure de qualité
reste une preuve au lieu d'un raisonnement circulaire. La frontière est donc **le répertoire** :
`src/engine/` décide, `tools/` mesure. (Le garde-fou lexical du dépôt, qui bloque les
jetons anglais de métrique en zone moteur, ne suffirait pas à lui seul : il se contourne
d'un tiret bas. Ce qui tient réellement, c'est que le moteur n'importe ni `os`, n'appelle
ni `open`, et ne nomme aucun jeton de vérité terrain — ce que la suite éprouve.)

## Statut de cette mesure — INSTRUMENTATION DE BUILD, PAS LA PREUVE
La mesure de qualité autoritaire est le scoreur, indépendant par construction, sur un
jeu de calibration distinct du jeu d'évaluation. Ce qui est produit ici est une
instrumentation de chantier destinée à répondre à une seule question : *la revue
apporte-t-elle quelque chose ?* La réponse est publiée telle quelle, y compris — et
surtout — quand elle est nulle.

## Le fait central que cet artefact doit rendre indissimulable
La zone grise dimensionnée ne contient **qu'une seule** paire réellement liée, et cette
paire s'y trouve parce que le dimensionnement a posé `t_mu` exactement sur son agrégat,
que la décision à trois zones exclut par une inégalité stricte. Autrement dit : le doute
que la revue peut lever est celui que le dimensionnement a fabriqué. Mesurée contre l'état du
moteur d'AVANT le dimensionnement, la contribution maximale de la revue est **nulle**.

Un lecteur qui n'ouvrirait que le JSON doit tomber sur ce fait, pas sur un gain apparent.
C'est pourquoi `contexte_amont` est un bloc de premier niveau et non une note de bas de
page, et pourquoi le gain éventuel est nommé `restitution_...` et non « récupération ».

## Reproductibilité
Le contenu porteur est **entier** (numérateurs, dénominateurs, effectifs). Les taux sont
publiés en plus, arrondis à `DECIMALES_TAUX`. Aucun flottant non fini, aucun horodatage,
aucune durée d'exécution, aucun chemin dérivé : l'artefact se régénère à l'identique, ce
qu'un test vérifie.
"""
from __future__ import annotations

import json
import os
import sys

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RACINE, "src"))

import engine                                          # noqa: E402
from engine import llm_client as clt                   # noqa: E402
from engine import llm_review as rev                   # noqa: E402
from engine import compare as cmp                      # noqa: E402
from generator import generate_pack                    # noqa: E402

#: La mesure O1 vit dans SON PROPRE fichier, et ce n'est pas cosmétique : l'antériorité
#: du gel se prouve contre un commit d'AJOUT, qui est immuable. La dater par « dernier
#: commit touchant le fichier de mesure » serait auto-invalidant — le défaut exact que
#: `tools/banc_ub6.py` a présenté. Voir l'en-tête de `contribution_dims_v2`.
sys.path.insert(0, os.path.join(_RACINE, "tools"))
import contribution_dims_v2 as cdv                     # noqa: E402

CHEMIN_ARTEFACT = os.path.join(_RACINE, "artifacts", "contribution_llm.json")
#: Littéral POSIX en dur : dérivé d'un `os.path`, il changerait de forme selon le système.
CHEMIN_PUBLIE = "artifacts/contribution_llm.json"

GRAINE_POPULATION = "SP_CYCLE_001::GEN-01::seed-0001"
N_ENTITES = 400
#: Populations de CONTRÔLE, hors de celle sur laquelle les seuils ont été dimensionnés.
#: Sans elles, toute « capacité de récupération » constatée serait une propriété de
#: l'échantillon d'ajustement, présentée comme une propriété du module.
CONTROLES = (("SP_CYCLE_001::GEN-01::seed-0002", 400),
             ("HOLDOUT::seed-0007", 400))

#: Arrondi des taux publiés (le contenu porteur, lui, est entier).
DECIMALES_TAUX = 9


def _taux(numerateur: int, denominateur: int):
    """Taux arrondi, ou `None` si le dénominateur est nul.

    Jamais de `inf` ni de `NaN` : `json.dump` les écrit (JSON non standard) et `nan != nan`
    rendrait la comparaison de régénération définitivement fausse, sans message lisible.
    """
    if denominateur <= 0:
        return None
    return round(numerateur / denominateur, DECIMALES_TAUX)


def _ecart(apres, avant):
    """Écart signé entre deux taux publiés, ou `None` si l'un manque.

    Calculé sur les valeurs ARRONDIES telles qu'elles sont publiées, de sorte qu'un
    lecteur puisse refaire la soustraction sur l'artefact et retrouver exactement le
    champ — un écart calculé sur les valeurs non arrondies ne se recouperait pas.
    """
    if apres is None or avant is None:
        return None
    return round(apres - avant, DECIMALES_TAUX)


def _index_verite(pack: dict) -> dict:
    """`record_id -> identifiant d'entité`. Lu ICI et nulle part ailleurs."""
    return {g["record_id"]: g["id_entite_vraie"] for g in pack["ground_truth"]}


def _est_lien(correspondance: dict, verite: dict) -> bool:
    return verite[correspondance["record_id_a"]] == verite[correspondance["record_id_b"]]


def _comptes(correspondances, verite: dict) -> dict:
    """Effectifs ENTIERS d'un état du moteur (aucun taux ici)."""
    match = [c for c in correspondances if c["verdict"] == engine.MATCH]
    grise = [c for c in correspondances if c["verdict"] == engine.ZONE_GRISE]
    return {
        "n_paires": len(correspondances),
        "n_match": len(match),
        "n_match_lies": sum(1 for c in match if _est_lien(c, verite)),
        "n_zone_grise": len(grise),
        "n_zone_grise_lies": sum(1 for c in grise if _est_lien(c, verite)),
        "n_paires_liees": sum(1 for c in correspondances if _est_lien(c, verite)),
    }


def _n_paires_liees_totales(pack: dict) -> int:
    """Paires réellement liées dans le pack, AVANT tout blocking.

    Publier ce dénominateur en plus de celui des paires candidates n'est pas une coquetterie
    : rapporter un rappel aux seules paires ayant survécu au blocking masque les liens que
    le blocking a perdus, et gonfle mécaniquement le taux. Les deux sont publiés.
    """
    par_entite = {}
    for entree in pack["ground_truth"]:
        par_entite.setdefault(entree["id_entite_vraie"], 0)
        par_entite[entree["id_entite_vraie"]] += 1
    return sum(n * (n - 1) // 2 for n in par_entite.values())


# --- Règles CANDIDATES d'adjudication — DÉCLARÉES, AUCUNE N'EST LIVRÉE ---------------
# Elles ne sont pas l'adjudicateur du produit : ce sont les hypothèses que l'on aurait pu
# retenir faute de modèle. Les mesurer toutes, et publier le tableau, est ce qui rend
# visible qu'AUCUNE n'est sélectionnable sans regarder les réponses — et que sélectionner
# celle qui gagne serait exactement la circularité que la frontière de non-circularité interdit.
def _n_desaccords(correspondance: dict) -> int:
    return sum(1 for niveau in correspondance["composantes"].values()
               if niveau == cmp.DESACCORD)


REGLES_CANDIDATES = (
    ("identifiant_et_nom_concordants",
     "courriel en accord fort ET nom en accord fort",
     lambda c: (c["composantes"]["accord_email"] == cmp.ACCORD_FORT
                and c["composantes"]["accord_nom"] == cmp.ACCORD_FORT)),
    ("aucun_desaccord",
     "aucun des 8 attributs en desaccord",
     lambda c: _n_desaccords(c) == 0),
    ("tolerance_du_moteur",
     "au plus 2 attributs en desaccord (la tolerance observee de l'ensemble MATCH)",
     lambda c: _n_desaccords(c) <= 2),
    ("abstention",
     "ne promeut rien : la regle effectivement LIVREE, faute d'adjudicateur",
     lambda c: False),
)


def _panneau_de_sensibilite(correspondances, verite: dict) -> list:
    """Ce que chaque règle candidate AURAIT fait. Mesuré, publié, jamais livré."""
    grise = [c for c in correspondances if c["verdict"] == engine.ZONE_GRISE]
    base = _comptes(correspondances, verite)
    panneau = []
    for nom, enonce, regle in REGLES_CANDIDATES:
        promues = [c for c in grise if regle(c)]
        justes = sum(1 for c in promues if _est_lien(c, verite))
        n_match = base["n_match"] + len(promues)
        n_match_lies = base["n_match_lies"] + justes
        panneau.append({
            "regle": nom,
            "enonce": enonce,
            "livree": nom == "abstention",
            "n_promues": len(promues),
            "n_promues_liees": justes,
            "n_promues_non_liees": len(promues) - justes,
            "n_match_apres": n_match,
            "n_match_lies_apres": n_match_lies,
            "taux_justesse_apres": _taux(n_match_lies, n_match),
            "taux_rappel_apres_sur_paires_candidates": _taux(n_match_lies,
                                                             base["n_paires_liees"]),
        })
    return panneau


def _etat_moteur(records, t_mu=None, t_lambda=None):
    if t_mu is None:
        return engine.execute_moteur(records)
    return engine.execute_moteur(
        records, engine.ParametresMoteur(t_mu=t_mu, t_lambda=t_lambda))


def construis_rapport(graine: str = GRAINE_POPULATION, n_entites: int = N_ENTITES) -> dict:
    """Exécute la revue LIVRÉE sur la population de démonstration et mesure son apport."""
    seuils = json.load(open(os.path.join(_RACINE, "artifacts", "thresholds_sized.json"),
                            encoding="utf-8"))["seuils_dimensionnes"]
    t_mu, t_lambda = seuils["t_mu"], seuils["t_lambda"]

    pack = generate_pack(graine, n_entities=n_entites)
    records = pack["records"]
    verite = _index_verite(pack)

    avant_dim = _comptes(_etat_moteur(records)["correspondances"], verite)
    resultat = _etat_moteur(records, t_mu, t_lambda)
    correspondances = resultat["correspondances"]
    apres_dim = _comptes(correspondances, verite)

    # --- La revue TELLE QU'ELLE EST LIVRÉE ------------------------------------------
    # Aucun modèle local n'est joignable : le client l'annonce, la revue trace le repli et
    # laisse chaque paire indéterminée. C'est l'exécution réelle, pas une
    # simulation de l'indisponibilité.
    client = clt.ClientIndisponible()
    revue = rev.revue_des_correspondances(
        correspondances, {r["record_id"]: r for r in engine.normalise_records(records)},
        client, budget=None)
    apres_revue = _comptes(revue["correspondances"], verite)
    retenues = rev.ensemble_de_match(revue["correspondances"])
    n_retenues_liees = sum(1 for c in retenues if _est_lien(c, verite))

    n_liees_totales = _n_paires_liees_totales(pack)
    gain = n_retenues_liees - apres_dim["n_match_lies"]

    # Les trois états successifs, sur le MÊME dénominateur (le blocking ne change pas) :
    # avant le dimensionnement, après lui, puis après la revue.
    rappel_avant_dim = _taux(avant_dim["n_match_lies"], avant_dim["n_paires_liees"])
    rappel_apres_dim = _taux(apres_dim["n_match_lies"], apres_dim["n_paires_liees"])
    rappel_apres_revue = _taux(n_retenues_liees, apres_dim["n_paires_liees"])

    controles = []
    for graine_c, n_c in CONTROLES:
        pack_c = generate_pack(graine_c, n_entities=n_c)
        verite_c = _index_verite(pack_c)
        corr_c = _etat_moteur(pack_c["records"], t_mu, t_lambda)["correspondances"]
        comptes_c = _comptes(corr_c, verite_c)
        grise_c = [c for c in corr_c if c["verdict"] == engine.ZONE_GRISE]
        controles.append({
            "graine": graine_c,
            "n_zone_grise": comptes_c["n_zone_grise"],
            "n_zone_grise_liees": comptes_c["n_zone_grise_lies"],
            "n_grises_sans_aucun_desaccord": sum(1 for c in grise_c
                                                 if _n_desaccords(c) == 0),
            "plafond_de_restitution": comptes_c["n_zone_grise_lies"],
        })

    return {
        "_lisez_moi": (
            "Contribution MESUREE de la revue de zone grise (unite U-B3, mandat "
            "DISP-UB3-01, SEF-LLM-4). LIRE 'contexte_amont' EN PREMIER. Fait central : la "
            "zone grise dimensionnee ne contient qu'UNE paire reellement liee, et elle s'y "
            "trouve parce que le dimensionnement a pose t_mu exactement sur son agregat, "
            "qu'une inegalite stricte exclut de MATCH. Le doute que la revue peut lever est "
            "celui que le dimensionnement a fabrique : mesuree contre l'etat du moteur "
            "d'AVANT le dimensionnement, la contribution maximale est NULLE. De plus, "
            "aucun adjudicateur n'est joignable dans ce build (aucun runtime de modele "
            "local n'est declare, runtime hors ligne strict), donc la revue livree "
            "n'instruit AUCUNE paire. La contribution mesuree est donc NULLE en nombre de "
            "liens restitues, et le rappel net est en RETRAIT par rapport a l'etat "
            "d'avant le dimensionnement (voir contexte_amont."
            "delta_rappel_net_vs_avant_dimensionnement, qui est NEGATIF) : le "
            "dimensionnement a retire une paire que la revue ne rend pas. Le plafond de ce "
            "delta est zero — la revue ne peut, au mieux, que revenir au point de depart. "
            "Instrumentation de chantier, PAS la preuve : la mesure de qualite autoritaire "
            "est l'unite U-B5, independante par construction."),
        "mandat": "DISP-UB3-01",
        "statut": "PROVISOIRE",
        "gap": "GAP-A",
        "contexte_amont": {
            "n_match_avant_dimensionnement": avant_dim["n_match"],
            "n_match_lies_avant_dimensionnement": avant_dim["n_match_lies"],
            "n_zone_grise_avant_dimensionnement": avant_dim["n_zone_grise"],
            "n_zone_grise_liees_avant_dimensionnement": avant_dim["n_zone_grise_lies"],
            "taux_rappel_avant_dimensionnement": rappel_avant_dim,
            "taux_rappel_apres_dimensionnement": rappel_apres_dim,
            "taux_rappel_apres_revue": rappel_apres_revue,
            # MESURÉ, jamais posé. Un zéro écrit en dur sous un nom de mesure serait
            # favorable par construction et increvable : il publierait la thèse au lieu
            # de la vérifier, dans l'artefact même dont c'est l'objet. Le plafond (ce que
            # la revue pourrait AU MIEUX rendre) est publié à part, sous son propre nom.
            "delta_rappel_net_vs_avant_dimensionnement": _ecart(rappel_apres_revue,
                                                                rappel_avant_dim),
            "plafond_de_delta_rappel_net_vs_avant_dimensionnement": _ecart(
                _taux(apres_dim["n_match_lies"] + apres_dim["n_zone_grise_lies"],
                      apres_dim["n_paires_liees"]),
                rappel_avant_dim),
            "note": (
                "Le dimensionnement a RETIRE de MATCH la paire que la revue pourrait "
                "restituer : son agregat vaut exactement t_mu, et la decision a trois "
                "zones exclut l'egalite. Un gain publie par rapport a l'etat POST "
                "dimensionnement serait vrai et trompeur. Le delta ci-dessus est mesure "
                "par rapport a l'etat ANTERIEUR au dimensionnement : il est NEGATIF ou nul "
                "tant que la revue ne restitue pas la paire retiree, et son plafond est "
                "zero — la revue ne peut, au mieux, que revenir au point de depart."),
        },
        "plafond": {
            "n_zone_grise": apres_dim["n_zone_grise"],
            "n_zone_grise_liees": apres_dim["n_zone_grise_lies"],
            "note": ("Aucune revue, si parfaite soit-elle, ne peut restituer plus de paires "
                     "liees qu'il n'y en a dans la zone grise. Ce plafond borne TOUTE "
                     "affirmation de gain."),
        },
        "revue_livree": {
            "client": revue["trace"]["client"],
            "adjudicateur_joignable": client.disponible(),
            "n_zone_grise": revue["trace"]["n_zone_grise"],
            "n_tentees": revue["trace"]["n_tentees"],
            "n_revues": revue["trace"]["n_revues"],
            "n_non_revues": revue["trace"]["n_non_revues"],
            "motifs_non_revue": revue["trace"]["motifs_non_revue"],
            "decisions": revue["trace"]["decisions"],
            "mode_strict": revue["trace"]["mode_strict"],
            "unite_budget": revue["trace"]["unite_budget"],
        },
        "contribution_mesuree": {
            "n_liens_restitues": gain,
            "restitution_de_paires_retirees_par_le_dimensionnement": gain,
            "n_match_avant_revue": apres_dim["n_match"],
            "n_match_apres_revue": len(retenues),
            "n_match_lies_avant_revue": apres_dim["n_match_lies"],
            "n_match_lies_apres_revue": n_retenues_liees,
            "taux_justesse_avant_revue": _taux(apres_dim["n_match_lies"],
                                               apres_dim["n_match"]),
            "taux_justesse_apres_revue": _taux(n_retenues_liees, len(retenues)),
            "taux_rappel_avant_revue_sur_paires_candidates": _taux(
                apres_dim["n_match_lies"], apres_dim["n_paires_liees"]),
            "taux_rappel_apres_revue_sur_paires_candidates": _taux(
                n_retenues_liees, apres_dim["n_paires_liees"]),
            "taux_rappel_apres_revue_sur_paires_liees_totales": _taux(
                n_retenues_liees, n_liees_totales),
            "n_paires_liees_candidates": apres_dim["n_paires_liees"],
            "n_paires_liees_totales": n_liees_totales,
            "note_denominateurs": (
                "Deux denominateurs sont publies : les paires liees ayant survecu au "
                "blocking, et toutes les paires liees du pack. Le premier flatte le taux "
                "en masquant les liens perdus au blocking ; publier les deux interdit de "
                "choisir le plus avantageux."),
        },
        "volume_revu": {
            "n_paires_soumises": revue["trace"]["n_tentees"],
            "n_paires_du_perimetre": revue["trace"]["n_zone_grise"],
            "part_du_perimetre_instruite": _taux(revue["trace"]["n_tentees"],
                                                 revue["trace"]["n_zone_grise"]),
        },
        "cout": {
            "cout_pour_1000_paires": None,
            "cout_total": None,
            "motif": (
                "NON MESURABLE dans ce build, et declare tel plutot que rempli d'un "
                "substitut : aucun adjudicateur n'a ete execute, donc il n'existe ni appel, "
                "ni jeton, ni duree a rapporter. Une duree d'horloge serait de toute facon "
                "proscrite ici, l'artefact devant se regenerer a l'identique."),
            "unite_budget": revue["trace"]["unite_budget"],
            "cout_declare_par_appel_du_client": client.cout_declare_par_appel,
        },
        "panneau_de_sensibilite": {
            "_lisez_moi": (
                "Ce que chaque regle candidate AURAIT fait. AUCUNE n'est livree, sauf "
                "'abstention'. Ce tableau existe pour rendre visible qu'aucune n'est "
                "selectionnable sans regarder les reponses : la regle qui gagne est celle "
                "qui isole l'unique paire liee, et la choisir POUR CELA serait la "
                "circularite que CC1 interdit. Les regles plausibles a priori, elles, "
                "degradent la justesse — jusqu'a 154 promotions erronees."),
            "regles": _panneau_de_sensibilite(correspondances, verite),
        },
        "controles_hors_echantillon": {
            "_lisez_moi": (
                "Populations distinctes de celle sur laquelle les seuils ont ete "
                "dimensionnes. Une capacite de restitution qui ne s'observerait que sur la "
                "population d'ajustement serait une propriete de l'echantillon, pas du "
                "module."),
            "populations": controles,
        },
        "population_demonstration": {
            "source": "generateur GEN_001 (unite U-B1), population BULK",
            "graine": graine,
            "n_entites": n_entites,
            "n_records": len(records),
            "n_paires_candidates": apres_dim["n_paires"],
        },
        "seuils_employes": {"t_mu": t_mu, "t_lambda": t_lambda,
                            "source": "artifacts/thresholds_sized.json (mandat DISP-DIMS-01)"},
        "outil_producteur": "tools/contribution_llm.py",
        # O1 : la RE-MESURE sur la zone grise DIMS-v2 reelle de FX_001 V1.2. Le bloc
        # ci-dessus reste ce qu'il etait — la demonstration de la revue sur SA population
        # generee — et n'est pas reecrit : les deux mesures portent sur deux populations
        # differentes, et effacer la premiere pour loger la seconde ferait disparaitre le
        # point de comparaison sans que rien ne le signale.
        "mesure_dims_v2": cdv.bloc_dims_v2(),
    }


def ecris_artefact(rapport: dict, chemin: str = CHEMIN_ARTEFACT) -> str:
    """Écrit l'artefact en JSON canonique (clés triées) : régénérable à l'identique."""
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rapport, fh, sort_keys=True, ensure_ascii=False, indent=2,
                  allow_nan=False)
        fh.write("\n")
    return chemin


def main() -> int:
    rapport = construis_rapport()
    ecris_artefact(rapport)
    amont = rapport["contexte_amont"]
    contribution = rapport["contribution_mesuree"]
    revue = rapport["revue_livree"]
    sys.stdout.buffer.write(
        (f"artefact ecrit : {CHEMIN_PUBLIE}\n"
         f"  adjudicateur joignable : {revue['adjudicateur_joignable']}\n"
         f"  paires du perimetre : {revue['n_zone_grise']} | instruites : "
         f"{revue['n_revues']} | non instruites : {revue['n_non_revues']} "
         f"({revue['motifs_non_revue']})\n"
         f"  plafond de restitution : {rapport['plafond']['n_zone_grise_liees']} paire(s)\n"
         f"  liens restitues : {contribution['n_liens_restitues']}\n"
         f"  rappel : {amont['taux_rappel_avant_dimensionnement']} (avant dim.) -> "
         f"{amont['taux_rappel_apres_dimensionnement']} (apres dim.) -> "
         f"{amont['taux_rappel_apres_revue']} (apres revue)\n"
         f"  delta rappel net vs avant dimensionnement : "
         f"{amont['delta_rappel_net_vs_avant_dimensionnement']} "
         f"(plafond atteignable : "
         f"{amont['plafond_de_delta_rappel_net_vs_avant_dimensionnement']})\n"
         f"  statut : PROVISOIRE (calibration différée)\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
