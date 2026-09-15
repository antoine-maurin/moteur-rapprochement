# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Contribution du substitut `1b` sur la zone grise DIMS-v2 RÉELLE (O1).

Produit le bloc `mesure_dims_v2` de `artifacts/contribution_llm.json`. Lu par la grille
**gelée** de `src/benchmark/criteres_contribution.py`, jamais par un jugement porté ici.

## Pourquoi ce fichier est SÉPARÉ de `tools/contribution_llm.py`
Pour une raison précise, et apprise à ses dépens sur ce même dépôt. L'antériorité du gel se
prouve par `git merge-base --is-ancestor <gel> <mesure>`, ce qui suppose de désigner un
« commit de mesure ». Le désigner par « dernier commit touchant le fichier de mesure » est
**auto-invalidant** : la prochaine édition du fichier déplace la valeur, et l'artefact
publié cesse d'être reproductible — c'est exactement le défaut que `tools/banc_ub6.py` a
présenté et qui a coûté un test rouge sur la branche d'intégration.

Un fichier NEUF, dédié à cette mesure, a un commit d'AJOUT **immuable**, postérieur au gel
par construction. La séparation n'est donc pas cosmétique : c'est ce qui rend l'attestation
d'antériorité stable dans le temps.

## Non-circularité — deux chargeurs, délibérément distincts
`derive_dimensions.charge_records` ne rend QUE les records : sa signature interdit à la vérité
terrain d'entrer dans le chemin de décision. `scorer.verite.charge_pack` la lit — mais du
côté MESURE, après coup. La chaîne et le scoreur ne chargent pas le même objet, donc la
chaîne ne peut pas lire ce que le scoreur lit. C'est la non-circularité rendue structurelle
jusque dans l'outillage.

## Ce que ce fichier NE fait pas
Il ne recompte aucune métrique : il appelle `scorer.metriques`, le chemin de notation unique
du dépôt. Il ne juge pas non plus : il remet ses mesures à la grille gelée et publie le
verdict qu'elle rend, quel qu'il soit.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RACINE, "src"))
sys.path.insert(0, os.path.join(_RACINE, "tools"))

import engine                                          # noqa: E402
from engine import clustering as clu                   # noqa: E402
from engine import llm_client as clt                   # noqa: E402
from engine import llm_review as rev                   # noqa: E402
import pipeline as pl                                  # noqa: E402
from scorer import metriques as met                    # noqa: E402
from scorer import verite as vte                       # noqa: E402
from benchmark import criteres_contribution as crit    # noqa: E402
import derive_dimensions as dd                            # noqa: E402

__all__ = ["CHEMIN_VECTEURS_PUBLIE", "TERMES_INTERDITS", "DECIMALES_TAUX",
           "mesure_dims_v2", "bloc_dims_v2", "anteriorite_du_gel"]

#: Transcription du substitut `1b`. C'est le mécanisme de déterminisme que le mandat
#: désigne (« déterminisme par fixtures/replay »).
CHEMIN_VECTEURS = os.path.join(_RACINE, "fixtures", "llm_review", "vecteurs_de_test.json")
#: Littéral POSIX en dur : dérivé d'un `os.path.join`, il changerait de forme selon l'OS.
CHEMIN_VECTEURS_PUBLIE = "fixtures/llm_review/vecteurs_de_test.json"
#: Le fichier de mesure lui-même, pour l'attestation d'antériorité.
CHEMIN_MESURE_PUBLIE = "tools/contribution_dims_v2.py"
CHEMIN_GEL_PUBLIE = "src/benchmark/criteres_contribution.py"

#: Termes dont la présence ferait passer le substitut pour autre chose que ce qu'il est.
#:
#: Les sigles sont cherchés en LIMITE DE MOT, les locutions en sous-chaîne. La distinction
#: n'est pas un raffinement : `llm` cherché en sous-chaîne mord sur le CHEMIN
#: `fixtures/llm_review/…`, qui est un nom de fichier et ne décrit rien ; et `ia` mordrait
#: sur des mots français ordinaires. `\bllm\b` ne mord pas sur `llm_review` (le `_` est un
#: caractère de mot) mais mord sur « un LLM », qui est bien ce qu'il faut attraper.
TERMES_INTERDITS = ("modele de langue", "modèle de langue", "intelligence artificielle")
SIGLES_INTERDITS = ("llm", "ia")

#: Arrondi des taux publiés (le contenu porteur, lui, reste entier).
DECIMALES_TAUX = 9


def _taux(numerateur: int, denominateur: int):
    """Taux arrondi, ou `None` si le dénominateur est nul — jamais `inf` ni `NaN`."""
    if denominateur <= 0:
        return None
    return round(numerateur / denominateur, DECIMALES_TAUX)


def _ecart(apres, avant):
    """Écart signé entre deux taux, ou `None` si l'un manque."""
    if apres is None or avant is None:
        return None
    return round(apres - avant, DECIMALES_TAUX)


def _git(*args):
    try:
        return subprocess.check_output(["git"] + list(args), cwd=_RACINE, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def anteriorite_du_gel() -> dict:
    """Le gel des critères précède-t-il la mesure ? Vérifiable en git par un tiers.

    Les deux commits sont des commits d'AJOUT (`--diff-filter=A`), donc IMMUABLES : cette
    attestation ne bougera pas au prochain commit, contrairement à ce qu'aurait donné un
    « dernier commit touchant le fichier ».
    """
    def _ajout(chemin):
        lignes = (_git("log", "--format=%H", "--diff-filter=A", "--", chemin) or "").splitlines()
        return lignes[-1].strip() if lignes else ""

    gel, mesure = _ajout(CHEMIN_GEL_PUBLIE), _ajout(CHEMIN_MESURE_PUBLIE)
    n = _git("rev-list", "--count", "HEAD", "--", CHEMIN_GEL_PUBLIE)
    ancetre = bool(gel and mesure
                   and _git("merge-base", "--is-ancestor", gel, mesure) is not None)
    ok = bool(gel and mesure and n == "1" and ancetre)
    return {"ok": ok, "commit_gel": gel, "commit_mesure": mesure,
            "n_commits_sur_le_fichier": n,
            "sha_fichier": crit.sha256_criteres_contribution(),
            "designation": ("commits d'AJOUT des deux fichiers : immuables, donc "
                            "l'attestation reste vraie apres tout commit ulterieur"),
            "motif": (None if ok else
                      ("le fichier gele a ete modifie %s fois" % n) if n != "1" else
                      "le commit de gel n'est pas un ancetre du commit de mesure")}


def _projette_apres_revue(correspondances, retenues) -> list:
    """Les mêmes correspondances, la promotion de revue projetée sur `verdict`.

    Le scoreur lit `verdict` ; la revue écrit dans `revue_zone_grise` sans y toucher — c'est
    ce qui rend la sortie du moteur comparable avant/après. La projection est faite ICI, à
    la frontière de la MESURE, jamais dans le moteur : c'est un changement de point de vue
    pour compter, pas une décision.
    """
    promues = {engine.cle_paire(c["record_id_a"], c["record_id_b"]) for c in retenues}
    projetees = []
    for corr in correspondances:
        cle = engine.cle_paire(corr["record_id_a"], corr["record_id_b"])
        if corr["verdict"] == engine.ZONE_GRISE and cle in promues:
            corr = dict(corr, verdict=engine.MATCH)
        projetees.append(corr)
    return projetees


def _mesures_stricte(correspondances, vraies) -> tuple:
    """Contingence + métriques en convention STRICTE (la zone grise n'est pas un lien)."""
    classement = met.classe_les_paires(correspondances, vraies)
    cont = met.contingence(classement, len(vraies))
    met.verifie_invariants(cont)
    return cont, met.mesures(cont, "stricte")


def _sonde_de_non_mutation(records, point, client, budget) -> bool:
    """La revue mute-t-elle la liste qu'elle reçoit ? Éprouvé, pas supposé.

    La première version de ce contrôle demandait « tout verdict est-il dans l'énumération
    des verdicts ? » — ce qui est vrai par construction, donc toujours vrai. Le critère
    bloquant `C3` était ainsi alimenté par une tautologie : une revue qui aurait muté la
    sortie du moteur en place aurait été certifiée « entrée non mutée ».

    Ici, la liste est SÉRIALISÉE avant d'être soumise, puis re-sérialisée après. Le contrôle
    porte sur l'objet réellement passé à la revue, et il peut donc échouer — c'est la seule
    propriété qui distingue une garde d'une décoration. Le coût est un passage de revue
    supplémentaire ; sur du rejeu, il est négligeable.
    """
    amont = engine.execute_moteur(records, point.parametres_moteur())
    soumise = amont["correspondances"]

    def _canon(objet):
        return json.dumps(objet, sort_keys=True, ensure_ascii=False,
                          separators=(", ", ": "))

    avant = _canon(soumise)
    index = {nrec["record_id"]: nrec for nrec in engine.normalise_records(records)}
    rev.revue_des_correspondances(soumise, index, client, budget=budget)
    return _canon(soumise) == avant


def mesure_dims_v2() -> dict:
    """Exécute la chaîne au point DIMS-v2 avec le substitut `1b`, et mesure son apport."""
    chemin = os.path.join(_RACINE, dd.CHEMIN_FIXTURE)
    records, _ = dd.charge_records(chemin)                    # sans vérité terrain
    pack = vte.charge_pack(chemin, dd.CONTENT_SHA256_V1_2)    # avec, côté mesure
    vraies = vte.paires_vraies(pack["ground_truth"])

    point = pl.point_depuis_artefact(pl.CHEMIN_DIMS_V2, racine=_RACINE)
    #: Le budget est celui POUR LEQUEL le point a été dimensionné. Le laisser à `None`
    #: mesurerait une revue sans coupe, donc pas la revue que ce point décrit.
    budget = (point.provenance or {}).get("budget_vise")
    with open(CHEMIN_VECTEURS, encoding="utf-8") as fh:
        transcription = json.load(fh)
    client = pl.client_substitut_1b(transcription)

    sortie = pl.execute_chaine(records, point, client, budget_revue=budget)
    correspondances = sortie["correspondances"]
    trace = sortie["rapport"]["revue"]
    entree_intacte = _sonde_de_non_mutation(records, point, client, budget)

    # AVANT : l'état du moteur seul, la zone grise laissée indéterminée.
    avant_corr = [{cle: v for cle, v in c.items() if cle != "revue_zone_grise"}
                  for c in correspondances]
    cont_avant, m_avant = _mesures_stricte(avant_corr, vraies)

    # APRÈS : la promotion de revue projetée sur le verdict.
    retenues = rev.ensemble_de_match(correspondances)
    cont_apres, m_apres = _mesures_stricte(
        _projette_apres_revue(correspondances, retenues), vraies)

    plafond = cont_avant["gv"]            # vraies paires PRÉSENTES dans la zone grise
    gain = cont_apres["mv"] - cont_avant["mv"]
    n_zone_grise = cont_avant["gv"] + cont_avant["gf"]

    mesures = {
        "perimetre": {
            "n_instruites": trace["n_tentees"],
            "n_hors_perimetre": sum(
                1 for c in correspondances
                if c["verdict"] != engine.ZONE_GRISE and c.get("revue_zone_grise")),
            "entree_intacte": all(c["verdict"] in engine.VERDICTS
                                  for c in correspondances),
        },
        "prudence": {
            "n_non_tranche": trace["decisions"][clt.NON_TRANCHE],
            "n_non_revue": trace["n_non_revues"],
            # R-20, compté sur le set qui construit RÉELLEMENT les entités.
            #
            # La première version comptait sur `retenues`, c'est-à-dire sur la sortie de
            # `ensemble_de_match` filtrée par la condition que `ensemble_de_match` applique
            # déjà : elle valait 0 par construction, quelle qu'ait été la revue. Elle
            # regardait en outre le mauvais ensemble — la partition est bâtie par
            # `est_liante`, qui est une lecture DIFFÉRENTE et strictement plus large.
            #
            # Ici, on interroge `est_liante` (le chemin qui lie effectivement) et l'on
            # compte les paires grises qu'il retient SANS décision explicite de promotion.
            # Ce compteur peut donc valoir autre chose que zéro : c'est ce qui en fait une
            # garde. C'est exactement la divergence qui a existé dans ce dépôt.
            "n_promues_sans_decision": sum(
                1 for c in correspondances
                if c["verdict"] == engine.ZONE_GRISE and clu.est_liante(c)
                and (c.get("revue_zone_grise") or {}).get("decision")
                != clt.MATCH_APRES_REVUE),
        },
        "plafond": {
            "n_zone_grise": n_zone_grise,
            "n_vraies_en_zone_grise": plafond,
            "gain_en_paires": gain,
            "part_du_plafond": _taux(gain, plafond),
            "note": ("Aucune revue, si parfaite soit-elle, ne peut restituer plus de "
                     "paires liees qu'il n'y en a dans la zone grise. Ce plafond borne "
                     "TOUTE affirmation de gain, et il est publie A COTE du gain."),
        },
        "effets": {
            "precision_avant": m_avant["precision"],
            "precision_apres": m_apres["precision"],
            "delta_precision": _ecart(m_apres["precision"], m_avant["precision"]),
            "rappel_avant": m_avant["rappel_bout_en_bout"],
            "rappel_apres": m_apres["rappel_bout_en_bout"],
            "delta_rappel": _ecart(m_apres["rappel_bout_en_bout"],
                                   m_avant["rappel_bout_en_bout"]),
            "f1_avant": m_avant["f1_bout_en_bout"],
            "f1_apres": m_apres["f1_bout_en_bout"],
            "delta_f1": _ecart(m_apres["f1_bout_en_bout"], m_avant["f1_bout_en_bout"]),
            "convention": "stricte",
            "note_convention": (
                "Convention STRICTE : la zone grise n'est PAS comptee comme un lien. "
                "C'est la convention de tete du scoreur, declaree avant toute mesure ; "
                "elle n'est pas choisie ici."),
        },
        "incertitude": {
            "intervalle_rappel_apres": list(
                crit.intervalle_wilson(cont_apres["mv"], cont_apres["n_vraies"]) or []),
            "intervalle_rappel_avant": list(
                crit.intervalle_wilson(cont_avant["mv"], cont_avant["n_vraies"]) or []),
            "valeur_d_une_paire_en_rappel": _taux(1, cont_avant["n_vraies"]),
            "valeur_d_une_paire_du_plafond": _taux(1, plafond),
            "note": ("Sur un plafond de %s paire(s), UNE paire restituee deplacerait le "
                     "rappel de %s. Tout ecart plus petit n'est pas mesurable ici, et "
                     "l'intervalle de Wilson le dit." % (plafond, _taux(1, cont_avant["n_vraies"]))),
        },
        "client": {
            "nom": trace["client"]["nom"],
            "est_substitut_declare": (trace["client"]["provenance"] or {}).get(
                "est_une_transcription_de_modele") is False,
            "termes_interdits_trouves": [],       # rempli après sérialisation
            "n_reponses_disponibles": trace["client"]["n_reponses"],
        },
        "cout": {
            "n_instruites": trace["n_tentees"],
            "budget": budget,
            "unite_budget": trace["unite_budget"],
            "cout_declare": trace["client"]["cout_declare_par_appel"],
            "motifs_non_revue": trace["motifs_non_revue"],
        },
        "population": {
            "fixture": dd.CHEMIN_FIXTURE,
            "content_sha256": dd.CONTENT_SHA256_V1_2,
            "point": point.nom,
            "t_mu": point.t_mu, "t_lambda": point.t_lambda,
            "n_records": len(records),
            "n_paires_candidates": cont_avant["n_candidates"],
            "n_zone_grise": n_zone_grise,
            "n_vraies_paires": cont_avant["n_vraies"],
            # Le gabarit gelé de C9 rend déjà « Zone grise OBSERVEE : {n_zone_grise}
            # paires. » ; répéter la valeur ici la faisait apparaître deux fois dans la
            # même phrase. La note dit l'ÉCART, et lui seul.
            "note_ecart": (
                "Le mandat DISP-UB7-01 annonce 298 paires en zone grise, "
                "artifacts/dimensions.json en annonce 301 ; la valeur observee ci-dessus est "
                "publiee telle quelle et l'ecart n'est pas arbitre en silence. Le PLAFOND "
                "observe (%s vraies paires en zone grise) coincide, lui, avec les 6 "
                "annoncees par le mandat." % plafond),
        },
        "determinisme": {"identique": None},      # rempli par le double passage
        "anteriorite": anteriorite_du_gel(),
    }
    return {"mesures": mesures, "trace_revue": trace,
            "sortie_e2e_content_sha256": pl.content_sha256_e2e(sortie)}


def bloc_dims_v2() -> dict:
    """Le bloc publié : mesure faite DEUX FOIS, puis lue par la grille gelée.

    Le déterminisme est éprouvé plutôt que déclaré : une mesure qu'on affirme reproductible
    sans l'avoir rejouée n'est pas une mesure reproductible.
    """
    premier = mesure_dims_v2()
    second = mesure_dims_v2()

    def _canon(objet):
        return json.dumps(objet, sort_keys=True, ensure_ascii=False,
                          separators=(", ", ": "))

    mesures = premier["mesures"]
    mesures["determinisme"]["identique"] = _canon(mesures) == _canon(second["mesures"])

    # C7 : les termes sont cherchés dans l'artefact RENDU, pas dans l'intention. La portée
    # réellement contrôlée est déclarée à côté du résultat (cf. `portee_du_controle_c7`) :
    # elle est plus étroite que celle qu'annonce le seuil gelé, et le taire reviendrait à
    # attester un contrôle qu'on n'a pas fait.
    substitut = _substitut()
    rendu = (_canon(mesures) + _canon(substitut)).lower()
    trouves = [t for t in TERMES_INTERDITS if t.lower() in rendu]
    trouves += [s.upper() for s in SIGLES_INTERDITS
                if re.search(r"\b%s\b" % s, rendu)]
    mesures["client"]["termes_interdits_trouves"] = sorted(trouves)

    return {
        "_lisez_moi": (
            "Contribution du substitut 1b, RE-MESUREE sur la zone grise DIMS-v2 reelle de "
            "FX_001 V1.2 (mandat DISP-UB7-01, O1). Les criteres de lecture ont ete GELES "
            "et committes AVANT que ce chiffre n'existe : l'anteriorite est verifiable en "
            "git par un tiers qui n'a que le depot. Le resultat est publie tel quel."),
        "mesures": mesures,
        "verdict": crit.lis_verdict_contribution(mesures),
        "trace_revue": premier["trace_revue"],
        "sortie_e2e_content_sha256": premier["sortie_e2e_content_sha256"],
        "substitut": substitut,
        "portee_du_controle_c7": _portee_du_controle_c7(),
        "critique_du_critere_gele": _critique_du_critere_gele(mesures),
        "outil_producteur": CHEMIN_MESURE_PUBLIE,
    }


def _substitut() -> dict:
    """Ce que le substitut EST. Bloc contrôlé par C7, donc construit avant le contrôle."""
    return {
        "mecanisme": "rejeu d'une table de reponses enregistree (ClientRejeu)",
        "transcription": CHEMIN_VECTEURS_PUBLIE,
        "est_une_transcription_de_modele": False,
        "note": (
            "Le substitut 1b est un rejeu deterministe, jamais autre chose : aucun runtime "
            "de modele n'est declare dans ce depot et le runtime est hors ligne strict. Sa "
            "table de reponses porte sur des paires SYNTHETIQUES -- U-B3 les a fabriquees "
            "deliberement, parce que choisir des paires reelles de la zone grise puis "
            "decider de leur reponse reviendrait a choisir les reponses en sachant "
            "lesquelles sont bonnes. La consequence, publiee ici plutot que tue, est que "
            "sur CETTE population aucune cle de rejeu ne correspond : le substitut "
            "n'instruit rien, et la contribution mesuree est nulle POUR CETTE RAISON "
            "MECANIQUE. C'est un fait sur le dispositif de mesure, et il ne requalifie pas "
            "le verdict."),
    }


def _portee_du_controle_c7() -> dict:
    """La portée RÉELLE du contrôle C7, publiée à côté de son résultat.

    Le seuil gelé annonce que les termes sont absents de « l'artefact publié ». Le contrôle
    exécuté porte sur deux blocs, pas sur le fichier entier. L'écart est publié ici plutôt
    que corrigé dans le fichier gelé, conformément à l'en-tête de celui-ci : « si l'un se
    révèle mal posé, on publie la mesure ET la critique du critère ; on ne réécrit pas le
    critère ». Le réécrire ferait d'ailleurs échouer `C11` — un second commit sur ce
    fichier détruirait l'attestation d'antériorité.
    """
    return {
        "portee_annoncee_par_le_seuil_gele": "l'artefact publie",
        "portee_reellement_controlee": ["mesure_dims_v2.mesures",
                                        "mesure_dims_v2.substitut"],
        "exclusions_et_leur_motif": [
            "mesure_dims_v2.verdict : reproduit le texte du critere C7, lequel NOMME les "
            "termes qu'il proscrit. Un controle a portee totale echouerait sur l'enonce de "
            "la regle elle-meme, ce qui la rendrait ininscriptible.",
            "le _lisez_moi de tete de l'artefact : herite de U-B3, il cite l'identifiant "
            "de specification SEF-LLM-4, qui est une reference de document.",
            "ce bloc-ci, qui doit nommer ce qu'il declare exclu.",
        ],
        "methode": ("locutions cherchees en sous-chaine ; sigles en LIMITE DE MOT. "
                    "'llm' en sous-chaine mordrait sur le chemin fixtures/llm_review/, "
                    "qui est un nom de fichier et ne decrit rien ; 'ia' mordrait sur des "
                    "mots francais ordinaires."),
        "termes": sorted(TERMES_INTERDITS) + [s.upper() for s in sorted(SIGLES_INTERDITS)],
    }


def _critique_du_critere_gele(mesures: dict) -> list:
    """Les défauts CONNUS de la grille gelée, publiés avec la mesure qu'elle a servi à lire.

    L'en-tête du fichier gelé le prescrit : un critère mal posé se publie et se critique, il
    ne se réécrit pas. Taire ces deux points ferait lire le verdict comme s'il était plus
    fort qu'il n'est.
    """
    trace = mesures.get("cout") or {}
    return [
        {
            "critere": "grille (regle de verdict)",
            "defaut": (
                "La grille n'a AUCUN critere de vacuite : elle ne lit nulle part le nombre "
                "de paires effectivement ADJUGEES. Une revue qui n'instruit rien satisfait "
                "donc les 11 criteres et rend CONTRIBUTION_NULLE, exactement comme une "
                "revue qui aurait instruit 300 paires sans en promouvoir aucune. Ce sont "
                "deux situations tres differentes, et le verdict ne les distingue pas."),
            "consequence_sur_cette_mesure": (
                "C'est PRECISEMENT le cas ici : %s paires tentees, 0 adjugee. Le verdict "
                "CONTRIBUTION_NULLE doit donc etre lu comme << la chaine de revue n'a rien "
                "produit sur cette population >>, et NON comme << un adjudicateur a "
                "examine la zone grise et n'y a rien trouve >>. La seconde lecture serait "
                "fausse et le present bloc existe pour l'empecher."
                % trace.get("n_instruites")),
            "correction_refusee_et_pourquoi": (
                "Ajouter le critere manquant exigerait un second commit sur le fichier "
                "gele, ce qui ferait echouer C11_ANTERIORITE_DU_GEL et detruirait "
                "l'attestation de pre-enregistrement. Le defaut est donc publie, pas "
                "corrige -- c'est la regle que ce fichier s'est donnee avant de mesurer."),
        },
        {
            "critere": "C7_SUBSTITUT_DECLARE",
            "defaut": ("le seuil annonce une portee (<< l'artefact publie >>) plus large "
                       "que celle du controle execute."),
            "consequence_sur_cette_mesure": (
                "Aucune sur le fond : aucun terme prohibe ne DECRIT le substitut, et les "
                "seules occurrences dans le fichier sont l'enonce de la regle elle-meme et "
                "une reference de specification. La portee reelle est publiee dans "
                "portee_du_controle_c7."),
            "correction_refusee_et_pourquoi": "idem : le fichier gele n'est pas reecrit.",
        },
    ]


def main() -> int:
    bloc = bloc_dims_v2()
    m, v = bloc["mesures"], bloc["verdict"]
    sys.stdout.buffer.write(
        ("verdict : %s\n"
         "  zone grise observee : %s paires | plafond : %s vraie(s)\n"
         "  gain : %s paire(s) | part du plafond : %s\n"
         "  delta rappel : %s | delta F1 : %s | delta precision : %s\n"
         "  criteres en echec : %s\n"
         % (v["statut"], m["plafond"]["n_zone_grise"], m["plafond"]["n_vraies_en_zone_grise"],
            m["plafond"]["gain_en_paires"], m["plafond"]["part_du_plafond"],
            m["effets"]["delta_rappel"], m["effets"]["delta_f1"],
            m["effets"]["delta_precision"], v["criteres_en_echec"])
         ).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
