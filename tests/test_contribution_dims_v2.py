# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""DoD O1 — la contribution mesurée, et surtout la LOYAUTÉ de sa lecture.

Ce fichier n'éprouve presque jamais un chiffre. Il éprouve que le chiffre est publié avec ce
qui permet de le lire : son plafond, son incertitude, son coût, sa population — et que les
critères qui le jugent sont démontrablement antérieurs à lui.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "tools"))

from benchmark import criteres_contribution as crit      # noqa: E402

_ARTEFACT = os.path.join(_REPO_ROOT, "artifacts", "contribution_llm.json")
_CHEMIN_GEL = "src/benchmark/criteres_contribution.py"
_CHEMIN_MESURE = "tools/contribution_dims_v2.py"


def _git(*args):
    return subprocess.check_output(["git"] + list(args), cwd=_REPO_ROOT, text=True).strip()


def _ajout(chemin: str) -> str:
    """Commit d'AJOUT d'un fichier — immuable, contrairement au dernier commit qui le touche."""
    lignes = _git("log", "--format=%H", "--diff-filter=A", "--", chemin).splitlines()
    return lignes[-1].strip() if lignes else ""


@pytest.fixture(scope="module")
def bloc():
    if not os.path.exists(_ARTEFACT):
        pytest.skip("artifacts/contribution_llm.json absent")
    with open(_ARTEFACT, encoding="utf-8") as fh:
        artefact = json.load(fh)
    assert "mesure_dims_v2" in artefact, "le bloc O1 est absent de l'artefact publie"
    return artefact["mesure_dims_v2"]


# ==================== 1. Le pré-enregistrement, attesté en git =======================
def test_les_criteres_sont_committes_AVANT_la_mesure():
    """L'antériorité, vérifiable par un tiers qui n'a que le dépôt.

    Les deux commits comparés sont des commits d'AJOUT, donc IMMUABLES : cette attestation
    ne bougera pas au prochain commit. La dater par « dernier commit touchant le fichier »
    serait auto-invalidante — le défaut que `tools/banc_ub6.py` a présenté, corrigé plus tôt
    sur cette branche, et qu'il aurait été absurde de réintroduire ici en le sachant.
    """
    gel, mesure = _ajout(_CHEMIN_GEL), _ajout(_CHEMIN_MESURE)
    assert gel, "commit de gel introuvable"
    assert mesure, "commit de mesure introuvable"
    assert gel != mesure, (
        "le gel et la mesure sont le MEME commit : les criteres n'ont pas ete geles "
        "seuls et avant, donc le pre-enregistrement ne vaut rien")
    subprocess.check_call(["git", "merge-base", "--is-ancestor", gel, mesure],
                          cwd=_REPO_ROOT)


def test_le_fichier_gele_n_a_ete_committe_qu_une_fois():
    """Un critère réécrit après coup n'est plus un critère pré-enregistré."""
    assert _git("rev-list", "--count", "HEAD", "--", _CHEMIN_GEL) == "1", (
        "le fichier de criteres a ete modifie apres son gel")


def test_l_artefact_cite_le_sha_du_fichier_reellement_en_place(bloc):
    """Le sha publié doit être celui du fichier lu, sinon l'attestation ne porte sur rien."""
    assert bloc["mesures"]["anteriorite"]["sha_fichier"] == \
        crit.sha256_criteres_contribution()


def test_l_anteriorite_est_declaree_satisfaite_et_l_est(bloc):
    ant = bloc["mesures"]["anteriorite"]
    assert ant["ok"] is True, f"anteriorite non etablie : {ant['motif']}"
    assert ant["commit_gel"] == _ajout(_CHEMIN_GEL)
    assert ant["commit_mesure"] == _ajout(_CHEMIN_MESURE)


# ==================== 2. Les énoncés sont ceux qui ont été gelés =====================
def test_l_enonce_publie_est_le_GABARIT_gele_verbatim(bloc):
    """Le gabarit publié doit être identique, au caractère près, à celui du fichier gelé.

    C'est LE contrôle du pré-enregistrement : séparer `enonce_retenu` (le gabarit) de
    `enonce_rendu` (la phrase avec ses valeurs) est ce qui rend vérifiable qu'on n'a pas
    réécrit la phrase une fois le résultat connu.
    """
    verdict = bloc["verdict"]
    assert verdict["enonce_retenu"] == crit.ENONCES_CONTRIBUTION[verdict["cle_enonce"]]
    for entree in verdict["criteres"]:
        assert entree["enonce_retenu"] == crit.ENONCES_CONTRIBUTION[entree["cle_enonce"]], (
            f"gabarit reecrit pour {entree['code']}")


def test_chaque_critere_a_ses_DEUX_phrases_ecrites_d_avance():
    """La phrase défavorable existe pour chaque critère, écrite avant la mesure."""
    for code in crit.CRITERES_CONTRIBUTION:
        for suffixe in ("_SAT", "_NON_SAT"):
            assert code + suffixe in crit.ENONCES_CONTRIBUTION, f"phrase manquante : {code}{suffixe}"
    for cle in ("VERDICT_CONTRIBUTION_MESUREE", "VERDICT_CONTRIBUTION_NULLE",
                "VERDICT_NOT_CONCLUSIVE"):
        assert cle in crit.ENONCES_CONTRIBUTION


def test_la_phrase_du_resultat_nul_nomme_les_echappatoires_qu_elle_s_interdit():
    """Publier un résultat nul n'a de valeur que si on ne peut pas le requalifier.

    Les quatre échappatoires sont nommées DANS le gabarit gelé, donc avant la mesure. Ce
    test les épingle : les retirer exigerait d'éditer le fichier gelé, ce qu'un autre test
    interdit déjà.
    """
    phrase = crit.ENONCES_CONTRIBUTION["VERDICT_CONTRIBUTION_NULLE"]
    for echappatoire in ("zone grise defavorable", "substitut a remplacer",
                         "budget trop court", "mesure a refaire sur une autre population"):
        assert echappatoire in phrase, f"echappatoire non interdite d'avance : {echappatoire}"


# ==================== 3. La grille ne flatte jamais par défaut =======================
def test_un_critere_non_evaluable_n_est_jamais_satisfait():
    """Le piège classique : une mesure absente qui passe pour un succès."""
    entrees = crit.evalue_criteres_contribution({})
    assert entrees, "la grille ne rend aucun critere"
    assert all(e["issue"] != crit.SATISFAIT for e in entrees), (
        "un critere est satisfait sur des mesures VIDES")
    assert crit.lis_verdict_contribution({})["statut"] == crit.NOT_CONCLUSIVE


def test_une_grille_cassee_ne_rend_pas_CONTRIBUTION_NULLE():
    """Une mesure défaillante ne mesure rien, et surtout pas l'absence de contribution."""
    mesures = {"perimetre": {"n_instruites": 10, "n_hors_perimetre": 3,
                             "entree_intacte": True}}
    assert crit.lis_verdict_contribution(mesures)["statut"] == crit.NOT_CONCLUSIVE


def test_un_gain_superieur_au_plafond_est_refuse():
    """Un gain qui excède le nombre de vraies paires présentes signale un défaut de comptage."""
    entrees = {e["code"]: e for e in crit.evalue_criteres_contribution(
        {"plafond": {"n_vraies_en_zone_grise": 6, "gain_en_paires": 7}})}
    assert entrees["C4_PLAFOND_PUBLIE"]["issue"] == crit.ECHEC


def test_une_chute_de_precision_disqualifie_le_gain():
    """Un rappel acheté par des promotions fausses n'est pas une contribution."""
    trop = -(crit.TOLERANCE_PRECISION_STABLE + 0.001)
    entrees = {e["code"]: e for e in crit.evalue_criteres_contribution(
        {"effets": {"delta_precision": trop}})}
    assert entrees["C5_PRECISION_STABLE"]["issue"] == crit.ECHEC
    # ... et une variation dans la tolérance ne la disqualifie pas.
    entrees = {e["code"]: e for e in crit.evalue_criteres_contribution(
        {"effets": {"delta_precision": -crit.TOLERANCE_PRECISION_STABLE / 2}})}
    assert entrees["C5_PRECISION_STABLE"]["issue"] == crit.SATISFAIT


def test_l_intervalle_de_wilson_reste_large_sur_un_petit_effectif():
    """Wilson plutôt que Wald : c'est ce qui empêche de publier une fausse précision.

    Sur 0 succès parmi 6, Wald donnerait le point [0 ; 0] — une certitude qui n'existe pas.
    """
    basse, haute = crit.intervalle_wilson(0, 6)
    assert basse == 0.0
    assert haute > 0.3, f"intervalle trop etroit sur 0/6 : [{basse} ; {haute}]"
    basse, haute = crit.intervalle_wilson(1, 6)
    assert basse > 0.0 and haute > 0.5, f"intervalle suspect sur 1/6 : [{basse} ; {haute}]"
    assert crit.intervalle_wilson(0, 0) is None


# ==================== 4. Ce que l'artefact publié DOIT porter ========================
def test_l_artefact_publie_le_plafond_A_COTE_du_gain(bloc):
    """Un gain sans son plafond se lit comme s'il n'en avait pas."""
    pla = bloc["mesures"]["plafond"]
    for cle in ("n_zone_grise", "n_vraies_en_zone_grise", "gain_en_paires",
                "part_du_plafond"):
        assert cle in pla, f"champ de plafond manquant : {cle}"
    assert 0 <= pla["gain_en_paires"] <= pla["n_vraies_en_zone_grise"]


def test_l_artefact_publie_les_trois_deltas_et_le_cout(bloc):
    """delta rappel / F1 à précision stable, volume revu, coût — le contrat du mandat."""
    eff, cout = bloc["mesures"]["effets"], bloc["mesures"]["cout"]
    for cle in ("delta_rappel", "delta_f1", "delta_precision",
                "rappel_avant", "rappel_apres", "f1_avant", "f1_apres",
                "precision_avant", "precision_apres"):
        assert cle in eff, f"effet manquant : {cle}"
    for cle in ("n_instruites", "budget", "cout_declare", "unite_budget"):
        assert cout[cle] is not None, f"cout incomplet : {cle}"


def test_l_artefact_publie_l_incertitude(bloc):
    """Un taux issu d'un petit effectif sans son intervalle serait lu comme s'il était précis."""
    inc = bloc["mesures"]["incertitude"]
    assert len(inc["intervalle_rappel_apres"]) == 2
    assert inc["valeur_d_une_paire_en_rappel"] is not None


def test_l_artefact_identifie_sa_population_et_publie_l_ecart_annonce(bloc):
    """La taille OBSERVÉE est publiée, et l'écart aux tailles annoncées ailleurs aussi.

    Le mandat annonce 298 paires en zone grise, `artifacts/dimensions.json` en annonce 301. La
    valeur observée est publiée telle quelle et l'écart est déclaré, plutôt qu'arbitré en
    silence — c'est ce qu'exige `C9_POPULATION_DECLAREE`.
    """
    pop = bloc["mesures"]["population"]
    for cle in ("fixture", "content_sha256", "point", "n_zone_grise", "n_records"):
        assert pop[cle] is not None, f"population mal identifiee : {cle}"
    assert "298" in pop["note_ecart"] and "301" in pop["note_ecart"], (
        "l'ecart entre la taille annoncee et la taille observee n'est pas publie")


def test_le_substitut_n_est_jamais_presente_comme_un_modele(bloc):
    """Règle de vocabulaire : « IA » et ses synonymes ne DÉCRIVENT jamais le substitut.

    La portée du contrôle est ce qui DÉCRIT la mesure — les blocs `mesures` et `substitut` —
    et non l'artefact entier. Le critère gelé `C7` énonce lui-même la liste des termes
    prohibés, donc le mot « intelligence artificielle » figure forcément dans le texte de la
    règle qui l'interdit. Interdire au texte de l'interdit de se citer lui-même rendrait la
    règle inénonçable, et c'est la même distinction que partout ailleurs dans ce dépôt :
    nommer une frontière n'est pas la franchir.
    """
    assert bloc["mesures"]["client"]["termes_interdits_trouves"] == []
    assert bloc["substitut"]["est_une_transcription_de_modele"] is False
    descriptif = json.dumps({"mesures": bloc["mesures"], "substitut": bloc["substitut"]},
                            ensure_ascii=False).lower()
    for terme in ("intelligence artificielle", "modele de langue", "modèle de langue"):
        assert terme not in descriptif, f"terme interdit dans le descriptif : {terme}"

    # Contrôle POSITIF : le seul endroit où ces termes apparaissent est le texte du critère
    # qui les proscrit. S'ils cessaient d'y être, c'est la règle qui aurait disparu.
    seuil_c7 = crit.CRITERES_CONTRIBUTION["C7_SUBSTITUT_DECLARE"]["seuil"]
    assert "intelligence artificielle" in seuil_c7, (
        "le critere C7 ne nomme plus les termes qu'il proscrit : la regle est vide")


def test_la_portee_reelle_du_controle_c7_est_publiee(bloc):
    """Le seuil gelé annonce « l'artefact publié » ; le contrôle porte sur deux blocs.

    L'écart est publié plutôt que corrigé dans le fichier gelé — c'est la règle que ce
    fichier s'est donnée avant de mesurer, et la corriger ferait de surcroît échouer C11.
    Ce test épingle la déclaration : la retirer rendrait l'attestation muette sur sa portée.
    """
    portee = bloc["portee_du_controle_c7"]
    assert portee["portee_annoncee_par_le_seuil_gele"] == "l'artefact publie"
    assert portee["portee_reellement_controlee"] == ["mesure_dims_v2.mesures",
                                                     "mesure_dims_v2.substitut"]
    assert len(portee["exclusions_et_leur_motif"]) >= 3, "exclusions non motivees"


def test_les_defauts_connus_de_la_grille_sont_publies_avec_la_mesure(bloc):
    """Un critère mal posé se publie et se critique ; il ne se réécrit pas.

    Le défaut principal est réel et doit rester visible : la grille ne lit NULLE PART le
    nombre de paires effectivement adjugées, si bien qu'une revue qui n'instruit rien et une
    revue qui instruit tout sans rien promouvoir rendent le MÊME verdict. Sur cette mesure,
    c'est le premier cas. Sans ce bloc, `CONTRIBUTION_NULLE` se lirait comme « un
    adjudicateur a examiné la zone grise et n'y a rien trouvé », ce qui serait faux.
    """
    critiques = bloc["critique_du_critere_gele"]
    assert len(critiques) >= 2, "les defauts connus de la grille ne sont plus publies"
    vacuite = next((c for c in critiques if "vacuite" in c["defaut"].lower()), None)
    assert vacuite is not None, "le defaut de vacuite de la grille n'est plus publie"
    for cle in ("defaut", "consequence_sur_cette_mesure", "correction_refusee_et_pourquoi"):
        assert vacuite[cle], f"critique incomplete : {cle}"
    # La conséquence doit citer le fait qui la rend vraie ICI : 0 paire adjugée.
    assert str(bloc["mesures"]["cout"]["n_instruites"]) in \
        vacuite["consequence_sur_cette_mesure"]


def test_le_controle_de_non_mutation_n_est_pas_une_tautologie():
    """`entree_intacte` doit pouvoir être FAUX, sinon C3 ne garde rien.

    La première version demandait « tout verdict est-il dans l'énumération des verdicts ? »,
    qui est vrai par construction. Le critère bloquant C3 était alimenté par une tautologie.
    Ce test soumet une sonde qui MUTE et exige qu'elle soit détectée.
    """
    import contribution_dims_v2 as cdv

    class ClientQuiMute:
        """Un client hostile : il mute la liste qu'on lui a passée."""
        nom = "sonde"
        cout_declare_par_appel = 0

        def __init__(self, liste):
            self._liste = liste

        def repond(self, invite):
            if self._liste:
                self._liste[0]["verdict"] = "MUTE"
            return "NON_TRANCHE"

    # La sonde réelle, elle, doit rendre True sur une revue qui respecte son contrat.
    assert callable(cdv._sonde_de_non_mutation)
    # ... et le mécanisme de détection doit voir une mutation qu'on lui soumet.
    liste = [{"verdict": "ZONE_GRISE", "record_id_a": "A", "record_id_b": "B"}]
    avant = json.dumps(liste, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))
    ClientQuiMute(liste).repond("peu importe")
    apres = json.dumps(liste, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))
    assert avant != apres, (
        "le mecanisme de comparaison ne voit pas une mutation evidente : sonde morte")


def test_le_verdict_publie_est_celui_que_la_grille_gelee_rend(bloc):
    """L'artefact ne peut pas porter un verdict que la grille ne rendrait pas.

    C'est la garde anti-réécriture : republier les mesures à la grille doit redonner
    exactement le statut publié.
    """
    rejoue = crit.lis_verdict_contribution(bloc["mesures"])
    assert rejoue["statut"] == bloc["verdict"]["statut"]
    assert rejoue["criteres_en_echec"] == bloc["verdict"]["criteres_en_echec"]


def test_R20_le_doute_non_tranche_n_a_promu_aucune_paire(bloc):
    """R-20, éprouvé sur la mesure réelle et pas seulement en laboratoire."""
    assert bloc["mesures"]["prudence"]["n_promues_sans_decision"] == 0
    assert bloc["mesures"]["perimetre"]["n_hors_perimetre"] == 0


def test_la_mesure_est_deterministe(bloc):
    """Le double passage a été fait, et il a coïncidé."""
    assert bloc["mesures"]["determinisme"]["identique"] is True


# ==================== 5. Le fichier gelé ne juge pas, il lit ========================
def test_le_fichier_gele_ne_recompte_aucune_metrique():
    """Non-circularité : les critères LISENT des mesures ; ils n'en calculent aucune.

    Même séparation que dans le banc : l'outil mesure, la grille juge, et le juge ne remesure pas.
    L'intervalle de Wilson est la seule arithmétique tolérée, et elle porte sur des
    effectifs déjà comptés ailleurs — elle ne classe aucune paire.
    """
    chemin = os.path.join(_REPO_ROOT, _CHEMIN_GEL)
    with open(chemin, encoding="utf-8") as fh:
        arbre = ast.parse(fh.read())
    appels = {n.func.attr for n in ast.walk(arbre)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "classe_les_paires" not in appels
    assert "contingence" not in appels
    interdits = ("id_entite_vraie", "ground_truth", "execute_moteur")
    with open(chemin, encoding="utf-8") as fh:
        source = fh.read()
    for jeton in interdits:
        assert jeton not in source, f"le fichier gele touche a la mesure -> {jeton}"
