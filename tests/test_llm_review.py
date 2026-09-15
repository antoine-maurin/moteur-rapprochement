# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Tests d'unité — revue hors ligne du doute en zone grise.

Lancement depuis la racine du repo de build : `python -m pytest tests/ -q`.

**Non-circularité.** Ces tests ne lisent JAMAIS la vérité terrain. La population de
démonstration provient du générateur, mais seul son tableau `records` est extrait.
Aucune attente n'est dérivée d'une étiquette : ce qui est éprouvé ici est le **mécanisme**
de la revue (périmètre, prudence, déterminisme du rejeu, repli tracé), jamais la justesse
d'une adjudication. La mesure de ce que la revue apporte vit dans `tools/`, seule zone où
la vérité terrain est permise, et son honnêteté est éprouvée sur la FORME de l'artefact.

**Aucun modèle de langue n'est exécuté.** Aucun runtime de modèle local n'est déclaré dans
le manifeste de dépendances et le runtime est hors ligne strict. Les fixtures sont des
**vecteurs fabriqués** pour la DoD, et l'un des tests vérifie que le fichier le déclare —
un corpus qui se présenterait comme une transcription de modèle serait la seule faute
irrattrapable de cette unité.
"""
import ast
import copy
import json
import os
import re
import sys

import pytest

import engine
from engine import llm_client as clt
from engine import llm_review as rev
from engine import compare as cmp

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_SRC = os.path.join(_REPO_ROOT, "src")
_TOOLS = os.path.join(_REPO_ROOT, "tools")
_MODULES_U_B3 = ("llm_client.py", "llm_review.py")
_FIXTURE = os.path.join(_REPO_ROOT, "fixtures", "llm_review", "vecteurs_de_test.json")
_ARTEFACT = os.path.join(_REPO_ROOT, "artifacts", "contribution_llm.json")

GRAINE_POPULATION = "SP_CYCLE_001::GEN-01::seed-0001"
N_ENTITES_BULK = 400

#: Tests dont l'objet est le MOTEUR : ils ne doivent lire aucune vérité terrain.
#: `test_generator.py` en est exclu à dessein — le générateur PRODUIT la vérité terrain,
#: l'éprouver exige donc de la lire.
_TESTS_SANS_VERITE_TERRAIN = ("test_engine.py", "test_threshold_sizing.py",
                              "test_llm_review.py")

sys.path.insert(0, _TOOLS)
import contribution_llm as outil_contribution            # noqa: E402
import enregistre_vecteurs_revue as outil_vecteurs       # noqa: E402


# ================================ Fixtures ==========================================
@pytest.fixture(scope="module")
def transcription():
    """Transcription rejouable, chargée depuis le disque par l'OUTIL (jamais le moteur)."""
    return outil_vecteurs.charge_fixture(_FIXTURE)


@pytest.fixture(scope="module")
def client(transcription):
    return clt.ClientRejeu(transcription)


@pytest.fixture(scope="module")
def paires_synthetiques():
    """Paires INVENTÉES + leur index normalisé : aucune donnée de population, donc
    aucune étiquette possible. C'est le support des cas de mécanisme."""
    from engine import normalize as nrm
    index, paires = {}, []
    for vecteur in outil_vecteurs.VECTEURS + [outil_vecteurs.VECTEUR_SANS_REPONSE]:
        a, b = nrm.normalise_record(vecteur["a"]), nrm.normalise_record(vecteur["b"])
        index[a["record_id"]] = a
        index[b["record_id"]] = b
        paires.append((vecteur, a["record_id"], b["record_id"]))
    return index, paires


def _correspondance(record_id_a, record_id_b, verdict, poids=0.0):
    """CORRESPONDENCE minimale de la forme que rend le moteur."""
    return {
        "record_id_a": record_id_a, "record_id_b": record_id_b,
        "poids_match": poids, "verdict": verdict,
        "revue_zone_grise": ({"statut": "en_attente", "decision": None,
                              "unite_responsable": "revue_zone_grise"}
                             if verdict == engine.ZONE_GRISE else None),
        "bloc_origine": ["bloc_test"],
        "composantes": {"accord_" + j: cmp.DESACCORD for j in engine.ATTRIBUTS_COMPARE},
        "poids_par_champ": {j: 0.0 for j in engine.ATTRIBUTS_COMPARE},
        "n_composantes_informatives": 8, "garde_r20_appliquee": False,
    }


@pytest.fixture(scope="module")
def correspondances_synthetiques(paires_synthetiques):
    """Toutes les paires fabriquées en ZONE_GRISE, plus un MATCH et un NON_MATCH témoins."""
    _, paires = paires_synthetiques
    liste = [_correspondance(a, b, engine.ZONE_GRISE) for _, a, b in paires]
    liste.append(_correspondance("SYN_M1", "SYN_M2", engine.MATCH, 40.0))
    liste.append(_correspondance("SYN_N1", "SYN_N2", engine.NON_MATCH, -40.0))
    return liste


@pytest.fixture(scope="module")
def records_bulk():
    """Population BULK de démonstration — `records` SEULS (garde de non-circularité)."""
    from generator import generate_pack
    return generate_pack(GRAINE_POPULATION, n_entities=N_ENTITES_BULK)["records"]


@pytest.fixture(scope="module")
def moteur_bulk(records_bulk):
    """Sortie du moteur sous les seuils DIMENSIONNÉS : l'état que la revue instruit."""
    seuils = json.load(open(os.path.join(_REPO_ROOT, "artifacts",
                                         "thresholds_sized.json"), encoding="utf-8"))
    seuils = seuils["seuils_dimensionnes"]
    resultat = engine.execute_moteur(
        records_bulk,
        engine.ParametresMoteur(t_mu=seuils["t_mu"], t_lambda=seuils["t_lambda"]))
    index = {r["record_id"]: r for r in engine.normalise_records(records_bulk)}
    return resultat["correspondances"], index


# ===================== 1. Rejeu déterministe (cas 1) ================================
def test_le_rejeu_est_deterministe(correspondances_synthetiques, paires_synthetiques,
                                   client):
    """Cas 1 : à fixtures données, deux exécutions rendent une sortie IDENTIQUE."""
    index, _ = paires_synthetiques
    une = rev.revue_des_correspondances(correspondances_synthetiques, index, client)
    deux = rev.revue_des_correspondances(correspondances_synthetiques, index, client)
    assert engine.sortie_canonique(une) == engine.sortie_canonique(deux)
    # Garde anti-vacuité : la sortie comparée porte bien des décisions, pas un vide.
    assert une["trace"]["n_revues"] > 0


def test_la_revue_ne_mute_pas_son_entree(correspondances_synthetiques,
                                         paires_synthetiques, client):
    """L'entrée reste comparable à l'octet près : la revue rend une liste NEUVE.

    Sans cette garantie, une revue exécutée dans un test contaminerait toute fixture
    partagée, et le symptôme apparaîtrait ailleurs — dans un test de déterminisme du
    moteur, qui serait alors diagnostiqué comme une régression de déterminisme.
    """
    index, _ = paires_synthetiques
    temoin = copy.deepcopy(correspondances_synthetiques)
    rendu = rev.revue_des_correspondances(correspondances_synthetiques, index, client)
    assert correspondances_synthetiques == temoin, "l'entrée a été mutée"
    n_detaches = 0
    for avant, apres in zip(correspondances_synthetiques, rendu["correspondances"]):
        if avant["verdict"] != engine.ZONE_GRISE:
            continue
        n_detaches += 1
        assert avant["revue_zone_grise"] is not apres["revue_zone_grise"], (
            "le marqueur de revue est PARTAGÉ avec l'entrée : mutation différée")
    assert n_detaches > 0, "aucune paire de zone grise : oracle vide"


#: Script enfant du test de déterminisme inter-processus. La revue y est rejouée de bout
#: en bout, depuis le chargement de la transcription jusqu'à la sortie canonique.
_SCRIPT_ENFANT = '''
import sys
sys.path.insert(0, {src!r})
sys.path.insert(0, {tools!r})
import engine
from engine import llm_client as clt, llm_review as rev, normalize as nrm
import enregistre_vecteurs_revue as ov

index, correspondances = {{}}, []
for vecteur in ov.VECTEURS + [ov.VECTEUR_SANS_REPONSE]:
    a = nrm.normalise_record(vecteur["a"])
    b = nrm.normalise_record(vecteur["b"])
    index[a["record_id"]] = a
    index[b["record_id"]] = b
    correspondances.append({{
        "record_id_a": a["record_id"], "record_id_b": b["record_id"],
        "poids_match": 0.0, "verdict": "ZONE_GRISE",
        "revue_zone_grise": {{"statut": "en_attente", "decision": None,
                             "unite_responsable": "revue_zone_grise"}},
        "bloc_origine": [], "composantes": {{}}, "poids_par_champ": {{}},
        "n_composantes_informatives": 8, "garde_r20_appliquee": False}})

client = clt.ClientRejeu(ov.charge_fixture({fixture!r}))
rendu = rev.revue_des_correspondances(correspondances, index, client)
sys.stdout.buffer.write(engine.sortie_canonique(rendu).encode("utf-8"))
'''


def test_le_rejeu_est_deterministe_entre_processus(tmp_path):
    """Cas 1 : deux PROCESSUS distincts rejouent à l'identique.

    Les deux tournent sous des `PYTHONHASHSEED` **DIFFÉRENTS** : le `hash()` des chaînes
    étant salé par processus, une graine commune rendrait le test aveugle à sa propre
    cible. C'est la garantie qui compte pour le déterminisme — une revue reproductible dans un seul
    processus ne prouve rien sur la reproductibilité d'un run à l'autre.
    """
    import subprocess
    script = tmp_path / "rejoue_revue.py"
    script.write_text(_SCRIPT_ENFANT.format(src=_SRC, tools=_TOOLS, fixture=_FIXTURE),
                      encoding="utf-8")
    graines = ("0", "12345")
    sorties = []
    for graine in graines:
        env = dict(os.environ, PYTHONHASHSEED=graine, PYTHONIOENCODING="utf-8")
        proc = subprocess.run([sys.executable, str(script)], capture_output=True, env=env)
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
        sorties.append(proc.stdout)
    assert sorties[0], "sortie enfant vide : oracle vide"
    assert sorties[0] == sorties[1], (
        f"deux processus (PYTHONHASHSEED {graines[0]} puis {graines[1]}), "
        f"deux sorties : déterminisme violé")


def test_la_cle_de_rejeu_ne_depend_pas_de_l_ordre_des_enregistrements(
        paires_synthetiques):
    """Soumettre `(a, b)` ou `(b, a)` pose la même question, donc rend la même clé."""
    index, paires = paires_synthetiques
    for _, a, b in paires:
        directe = clt.cle_de_charge(clt.charge_de_revue(index[a], index[b]))
        inverse = clt.cle_de_charge(clt.charge_de_revue(index[b], index[a]))
        assert directe == inverse


def test_la_cle_replie_les_ecritures_unicode_equivalentes():
    """Deux écritures Unicode visuellement identiques rendent la MÊME clé.

    Le courriel est le seul des 8 attributs dont la normalisation ne retire pas les
    diacritiques (c'est une clé structurée, on n'y touche pas) : c'est donc le seul qui
    peut porter jusqu'au hachage une composition non repliée. Sans repli NFC, deux sources
    écrivant le même courriel différemment recevraient deux réponses distinctes — et le
    défaut n'apparaîtrait que sur la première source réelle qui en contient.
    """
    compose = {"record_id": "U1", "email": "josé@example.fr"}      # é précomposé
    decompose = {"record_id": "U2", "email": "josé@example.fr"}   # e + accent
    assert compose["email"] != decompose["email"], "les deux écritures doivent différer"
    autre = {"record_id": "U3", "nom": "temoin"}
    assert (clt.cle_de_charge(clt.charge_de_revue(compose, autre))
            == clt.cle_de_charge(clt.charge_de_revue(decompose, autre)))


# ===================== 2. Sortie bornée (cas 2) =====================================
def test_la_decision_est_dans_l_enumeration_et_renseignee_ssi_zone_grise(
        correspondances_synthetiques, paires_synthetiques, client):
    """Cas 2 : `revue_zone_grise` renseigné SSI ZONE_GRISE ; décision dans l'énumération."""
    index, _ = paires_synthetiques
    rendu = rev.revue_des_correspondances(correspondances_synthetiques, index, client)
    vus = set()
    for corr in rendu["correspondances"]:
        renseigne = corr["revue_zone_grise"] is not None
        assert renseigne == (corr["verdict"] == engine.ZONE_GRISE), (
            f"{corr['record_id_a']}/{corr['record_id_b']} : verdict={corr['verdict']} "
            f"mais revue renseignée={renseigne}")
        if renseigne:
            marqueur = corr["revue_zone_grise"]
            assert marqueur["statut"] in rev.STATUTS
            assert marqueur["decision"] in clt.DECISIONS + (None,)
            vus.add(corr["verdict"])
    # Garde anti-vacuité : l'équivalence est éprouvée dans LES DEUX sens.
    verdicts = {c["verdict"] for c in rendu["correspondances"]}
    assert engine.ZONE_GRISE in verdicts and verdicts - {engine.ZONE_GRISE}


def test_les_paires_deja_tranchees_ne_sont_jamais_touchees(
        correspondances_synthetiques, paires_synthetiques, client):
    """Cas 2 : MATCH et NON_MATCH traversent la revue à l'identique."""
    index, _ = paires_synthetiques
    rendu = rev.revue_des_correspondances(correspondances_synthetiques, index, client)
    avant = {(c["record_id_a"], c["record_id_b"]): c
             for c in correspondances_synthetiques if c["verdict"] != engine.ZONE_GRISE}
    apres = {(c["record_id_a"], c["record_id_b"]): c
             for c in rendu["correspondances"] if c["verdict"] != engine.ZONE_GRISE}
    assert avant.keys() == apres.keys()
    for identite, correspondance in avant.items():
        assert correspondance == apres[identite], f"paire déjà tranchée modifiée : {identite}"
    assert avant, "aucune paire déjà tranchée dans l'échantillon : oracle vide"


# ===================== 3. Prudence R-20 (cas 3) =====================================
def test_non_tranche_reste_en_zone_grise_et_n_est_jamais_promue(
        correspondances_synthetiques, paires_synthetiques, client):
    """Cas 3 : une paire `NON_TRANCHE` reste indéterminée — jamais promue en lien."""
    index, _ = paires_synthetiques
    rendu = rev.revue_des_correspondances(correspondances_synthetiques, index, client)
    retenues = {(c["record_id_a"], c["record_id_b"])
                for c in rev.ensemble_de_match(rendu["correspondances"])}
    n_non_tranchees = 0
    for corr in rendu["correspondances"]:
        marqueur = corr["revue_zone_grise"] or {}
        if marqueur.get("decision") == clt.NON_TRANCHE:
            n_non_tranchees += 1
            assert corr["verdict"] == engine.ZONE_GRISE, "verdict réécrit"
            assert (corr["record_id_a"], corr["record_id_b"]) not in retenues, (
                "une paire NON_TRANCHE a été promue en lien")
    assert n_non_tranchees >= 2, (
        f"trop peu de NON_TRANCHE pour éprouver la prudence ({n_non_tranchees})")


def test_une_paire_explicitement_rejetee_n_entre_jamais_dans_l_ensemble_de_match(
        correspondances_synthetiques, paires_synthetiques, client):
    """Le piège de sous-chaîne, éprouvé chez le CONSOMMATEUR et non plus au seul analyseur.

    `analyse_reponse` est gardé contre la confusion `NON_MATCH_APRES_REVUE` /
    `MATCH_APRES_REVUE`, mais `ensemble_de_match` relit la décision une seconde fois : s'il
    la testait par appartenance de sous-chaîne plutôt que par égalité, une paire
    EXPLICITEMENT rejetée serait retenue comme lien. C'est l'assertion NÉGATIVE qui manquait
    — sans elle, la mutation `== MATCH_APRES_REVUE` -> `in decision` laisse toute la suite
    au vert tout en promouvant les rejets.
    """
    index, _ = paires_synthetiques
    rendu = rev.revue_des_correspondances(correspondances_synthetiques, index, client)
    rejetees = {(c["record_id_a"], c["record_id_b"]) for c in rendu["correspondances"]
                if (c["revue_zone_grise"] or {}).get("decision")
                == clt.NON_MATCH_APRES_REVUE}
    retenues = {(c["record_id_a"], c["record_id_b"])
                for c in rev.ensemble_de_match(rendu["correspondances"])}
    # Garde anti-vacuité : sans rejet dans l'échantillon, l'oracle ne prouverait rien.
    assert rejetees, "aucune paire rejetée dans l'échantillon : oracle vide"
    assert not (rejetees & retenues), (
        f"paire(s) rejetée(s) promue(s) en lien : {sorted(rejetees & retenues)}")


def test_le_jeton_de_rejet_ne_peut_pas_etre_lu_comme_une_promotion():
    """Le piège de sous-chaîne : `NON_MATCH_APRES_REVUE` CONTIENT `MATCH_APRES_REVUE`.

    Un analyseur écrit avec `in`, `startswith` ou `endswith` promeut un rejet. C'est le
    défaut le plus coûteux imaginable ici — sur une population dont l'ensemble MATCH est
    exact, une seule promotion erronée est une régression visible.
    """
    assert "NON_MATCH_APRES_REVUE".find("MATCH_APRES_REVUE") == 4, (
        "le piège a disparu : ce test n'a plus d'objet")
    cas = {
        "DECISION: MATCH_APRES_REVUE": clt.MATCH_APRES_REVUE,
        "DECISION: NON_MATCH_APRES_REVUE": clt.NON_MATCH_APRES_REVUE,
        "DECISION: NON_TRANCHE": clt.NON_TRANCHE,
        "MATCH_APRES_REVUE": clt.NON_TRANCHE,                  # non ancré -> abstention
        "DECISION: MATCH_APRES_REVUE\nDECISION: NON_MATCH_APRES_REVUE": clt.NON_TRANCHE,
        "je pense que MATCH": clt.NON_TRANCHE,
        "": clt.NON_TRANCHE,
    }
    for texte, attendu in cas.items():
        decision, _ = clt.analyse_reponse(texte)
        assert decision == attendu, f"{texte!r} -> {decision} (attendu {attendu})"
    # Contrôle POSITIF : un analyseur naïf, lui, se ferait piéger. Si cette écriture
    # cessait d'être fautive, le test ci-dessus n'aurait plus rien à garder.
    naif = "NON_MATCH_APRES_REVUE"
    assert clt.MATCH_APRES_REVUE in naif, "l'oracle du piège est mort"


def test_une_reponse_qui_n_est_pas_du_texte_est_refusee():
    """Un accès manqué rendant `None` ne doit pas se lire comme une abstention."""
    for entree in (None, 0, [], {"decision": "MATCH_APRES_REVUE"}):
        with pytest.raises(TypeError):
            clt.analyse_reponse(entree)


# ===================== 4. Capacité de restitution (cas 4) ===========================
def test_le_module_peut_produire_une_promotion(correspondances_synthetiques,
                                               paires_synthetiques, client):
    """Cas 4 : le mécanisme SAIT promouvoir — éprouvé sur des vecteurs FABRIQUÉS.

    Volontairement éprouvé hors de la population de démonstration. Un test de capacité qui
    ne passerait que là où les seuils ont été dimensionnés serait un test d'ajustement
    déguisé : les populations de contrôle ne contiennent aucune paire liée en zone grise,
    et l'artefact le publie. Aucune capacité de RÉTROGRADATION d'un faux positif n'est
    éprouvée — le mandat l'exclut, les données ne la permettant pas.
    """
    index, _ = paires_synthetiques
    rendu = rev.revue_des_correspondances(correspondances_synthetiques, index, client)
    decisions = rendu["trace"]["decisions"]
    assert decisions[clt.MATCH_APRES_REVUE] >= 1, "aucune promotion possible"
    assert decisions[clt.NON_MATCH_APRES_REVUE] >= 1, "aucun rejet possible"
    retenues = rev.ensemble_de_match(rendu["correspondances"])
    identites = {(c["record_id_a"], c["record_id_b"]) for c in retenues}
    assert ("SYN_A1", "SYN_B1") in identites, "la paire promue n'entre pas dans l'ensemble"
    assert ("SYN_M1", "SYN_M2") in identites, "un MATCH du moteur a été perdu"


# ===================== 5. Repli borné et tracé (cas 5) ==============================
def test_adjudicateur_indisponible_laisse_tout_en_zone_grise(
        correspondances_synthetiques, paires_synthetiques):
    """Cas 5 : adjudicateur injoignable -> aucune promotion, branche TRACÉE."""
    index, _ = paires_synthetiques
    rendu = rev.revue_des_correspondances(
        correspondances_synthetiques, index, clt.ClientIndisponible())
    trace = rendu["trace"]
    assert trace["n_revues"] == 0
    assert trace["motifs_non_revue"]["adjudicateur_indisponible"] == trace["n_zone_grise"]
    assert trace["client"]["motif_indisponibilite"], "repli SILENCIEUX : aucun motif tracé"
    for corr in rendu["correspondances"]:
        if corr["verdict"] == engine.ZONE_GRISE:
            assert corr["revue_zone_grise"]["statut"] == rev.NON_REVUE
            assert corr["revue_zone_grise"]["decision"] is None
    assert not [c for c in rev.ensemble_de_match(rendu["correspondances"])
                if c["verdict"] == engine.ZONE_GRISE]


def test_budget_epuise_laisse_le_reste_en_zone_grise(correspondances_synthetiques,
                                                     paires_synthetiques, client):
    """Cas 5 : sous budget, les paires non instruites restent indéterminées et tracées."""
    index, _ = paires_synthetiques
    rendu = rev.revue_des_correspondances(correspondances_synthetiques, index, client,
                                          budget=2)
    trace = rendu["trace"]
    assert trace["n_tentees"] == 2
    assert trace["motifs_non_revue"]["budget_epuise"] == trace["n_zone_grise"] - 2
    assert trace["n_revues"] + trace["n_non_revues"] == trace["n_zone_grise"]
    assert trace["unite_budget"] == "paires_tentees"


def test_la_coupe_budgetaire_ne_depend_pas_du_cout_declare_du_client(
        correspondances_synthetiques, paires_synthetiques, transcription):
    """Changer de client ne doit PAS changer l'ensemble instruit.

    Si le coût déclaré d'un client entrait dans la coupe, remplacer le client changerait
    les paires revues, donc la contribution mesurée — et le remplacement passerait pour une
    variation de qualité alors qu'il ne serait qu'une variation de tarif.
    """
    index, _ = paires_synthetiques

    class ClientCher(clt.ClientRejeu):
        cout_declare_par_appel = 1000

    instruits = []
    for classe in (clt.ClientRejeu, ClientCher):
        rendu = rev.revue_des_correspondances(
            correspondances_synthetiques, index, classe(transcription), budget=3)
        instruits.append({(c["record_id_a"], c["record_id_b"])
                          for c in rendu["correspondances"]
                          if (c["revue_zone_grise"] or {}).get("statut") == rev.REVUE})
    assert instruits[0] == instruits[1], "le tarif du client déplace l'ensemble instruit"
    assert instruits[0], "aucune paire instruite : oracle vide"


def test_un_rate_de_rejeu_est_trace_et_ne_fabrique_aucune_reponse(
        correspondances_synthetiques, paires_synthetiques, client):
    """Une paire absente de la transcription reste indéterminée, avec son motif."""
    index, _ = paires_synthetiques
    rendu = rev.revue_des_correspondances(correspondances_synthetiques, index, client)
    manquantes = [c for c in rendu["correspondances"]
                  if (c["revue_zone_grise"] or {}).get("motif") == "reponse_absente"]
    assert len(manquantes) == 1, "le vecteur volontairement non enregistré n'est pas tracé"
    assert manquantes[0]["revue_zone_grise"]["decision"] is None
    assert rendu["trace"]["motifs_non_revue"]["reponse_absente"] == 1


def test_l_identite_de_conservation_est_portee_par_la_trace(
        correspondances_synthetiques, paires_synthetiques, client):
    """`n_revues + n_non_revues + n_en_attente == n_zone_grise`, et rien n'est oublié."""
    index, _ = paires_synthetiques
    trace = rev.revue_des_correspondances(
        correspondances_synthetiques, index, client)["trace"]
    assert trace["n_revues"] + trace["n_non_revues"] + trace["n_en_attente"] == \
        trace["n_zone_grise"]
    assert trace["n_en_attente"] == 0, "une paire du périmètre n'a pas été orchestrée"
    assert set(trace["motifs_non_revue"]) == set(rev.MOTIFS_NON_REVUE), (
        "jeu de motifs non fixe : un motif absent serait indiscernable d'un motif à zéro")


# ===================== 6. Contribution : présence et forme (cas 6) =================
def test_artefact_de_contribution_present_et_de_forme_attendue():
    """Cas 6 : l'artefact porte le delta, le volume et le coût — FORME, pas valeur cible."""
    assert os.path.exists(_ARTEFACT), f"artefact absent : {_ARTEFACT}"
    with open(_ARTEFACT, encoding="utf-8") as fh:
        artefact = json.load(fh)
    for bloc in ("contexte_amont", "plafond", "revue_livree", "contribution_mesuree",
                 "volume_revu", "cout", "panneau_de_sensibilite",
                 "controles_hors_echantillon"):
        assert bloc in artefact, f"bloc manquant : {bloc}"
    amont = artefact["contexte_amont"]
    for cle in ("n_match_avant_dimensionnement", "taux_rappel_avant_dimensionnement",
                "delta_rappel_net_vs_avant_dimensionnement"):
        assert cle in amont, f"contexte amont incomplet : {cle}"
    contribution = artefact["contribution_mesuree"]
    for cle in ("n_liens_restitues", "n_match_lies_avant_revue",
                "n_match_lies_apres_revue", "n_paires_liees_candidates",
                "n_paires_liees_totales"):
        assert isinstance(contribution[cle], int), (
            f"{cle} doit être ENTIER : un contenu porteur entier est reproductible "
            f"à l'octet, un taux flottant ne l'est pas")
    assert artefact["volume_revu"]["n_paires_du_perimetre"] >= 0
    assert "cout_pour_1000_paires" in artefact["cout"]
    assert artefact["cout"]["motif"], "coût non renseigné ET non justifié"
    assert artefact["statut"] == "PROVISOIRE"


def test_l_artefact_ne_surevalue_pas_la_contribution():
    """Cas 6 : le gain publié ne peut pas dépasser le plafond, ni le contexte manquer.

    Le fait décisif — la paire restituable est celle que le dimensionnement avait retirée —
    doit être porté par des CHAMPS MACHINE, pas par une prose que personne ne lit. Un
    lecteur qui n'ouvrirait que le JSON doit tomber dessus.
    """
    with open(_ARTEFACT, encoding="utf-8") as fh:
        artefact = json.load(fh)
    plafond = artefact["plafond"]["n_zone_grise_liees"]
    gain = artefact["contribution_mesuree"]["n_liens_restitues"]
    assert 0 <= gain <= plafond, f"gain {gain} au-delà du plafond {plafond}"
    amont = artefact["contexte_amont"]
    assert amont["taux_rappel_avant_dimensionnement"] >= \
        amont["taux_rappel_apres_dimensionnement"], (
        "le contexte amont doit montrer ce que le dimensionnement a retiré")
    # Le delta doit être MESURÉ, pas posé. L'assertion est une IDENTITÉ entre champs
    # voisins : elle échoue si la valeur est écrite en dur et que les taux bougent — ce
    # qu'une comparaison à une constante ne pourrait jamais faire. Un zéro codé en dur
    # sous un nom de mesure serait favorable par construction et increvable.
    delta = amont["delta_rappel_net_vs_avant_dimensionnement"]
    assert delta == round(amont["taux_rappel_apres_revue"]
                          - amont["taux_rappel_avant_dimensionnement"], 9), (
        f"delta publié {delta} incohérent avec les taux voisins : champ non mesuré")
    assert delta <= 0.0, (
        "un delta POSITIF par rapport à l'état d'avant le dimensionnement signifierait "
        "que la revue a fait mieux que le moteur non dimensionné : impossible ici")
    assert amont["plafond_de_delta_rappel_net_vs_avant_dimensionnement"] == 0.0, (
        "le plafond du gain net est nul : la revue ne peut que revenir au point de départ")
    # Le tableau des règles candidates doit montrer qu'AUCUNE n'est livrée sauf l'abstention.
    regles = artefact["panneau_de_sensibilite"]["regles"]
    livrees = [r["regle"] for r in regles if r["livree"]]
    assert livrees == ["abstention"], f"une règle d'adjudication est livrée : {livrees}"
    couteuses = [r for r in regles if r["n_promues_non_liees"] > 0]
    assert couteuses, (
        "le panneau doit publier au moins une règle plausible qui DÉGRADE la justesse : "
        "sans elle, le lecteur ne voit pas pourquoi aucune n'est sélectionnable")


def test_l_artefact_se_regenere_a_l_identique():
    """Cas 6 : l'artefact est reproductible — il n'est pas édité à la main.

    Test volontairement coûteux (il ré-exécute le moteur sur plusieurs populations) et
    volontairement NON marqué « lent » : un test de régénération que l'on désélectionne est
    exactement la manière dont un chiffre retouché à la main survit.
    """
    with open(_ARTEFACT, encoding="utf-8") as fh:
        publie = json.load(fh)
    assert outil_contribution.construis_rapport() == publie, (
        "l'artefact publié ne correspond plus à ce que l'outil produit")


# ===================== 7. Non-circularité / C7 structurels (cas 7) =================
def _sources_u_b3():
    """Contenu des modules de la revue de zone grise, avec garde d'existence et anti-vacuité."""
    sources = {}
    for nom_fichier in _MODULES_U_B3:
        chemin = os.path.join(_SRC, "engine", nom_fichier)
        assert os.path.exists(chemin), f"module de la revue absent : {chemin}"
        with open(chemin, encoding="utf-8") as fh:
            sources[nom_fichier] = fh.read()
    assert sum(len(t) for t in sources.values()) > 5000, "sources de la revue suspectement vides"
    return sources


def _cles_lues(source):
    """Clés de chaînes lues par indexation ou par `.get`/`.pop`/`.setdefault` (AST)."""
    cles = set()
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.Subscript) and isinstance(noeud.slice, ast.Constant):
            if isinstance(noeud.slice.value, str):
                cles.add(noeud.slice.value)
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute):
            if noeud.func.attr in ("get", "pop", "setdefault") and noeud.args:
                if isinstance(noeud.args[0], ast.Constant) and \
                        isinstance(noeud.args[0].value, str):
                    cles.add(noeud.args[0].value)
    return cles


def test_cc1_la_revue_ne_lit_de_la_decision_que_son_identite_et_son_verdict():
    """Cas 7 : structurellement, la revue ne lit aucune donnée de décision du moteur.

    L'assertion est en liste BLANCHE, close. `poids_match` en est ABSENT, et c'est le point
    : la revue ne voit pas l'agrégat de vraisemblance, donc elle ne peut pas se contenter
    de le re-seuiller. Une revue qui relirait l'agrégat n'apporterait, au mieux, que ce que
    le moteur savait déjà.
    """
    cles = _cles_lues(_sources_u_b3()["llm_review.py"])
    interdites = {"poids_match", "poids_par_champ", "composantes", "similarites",
                  "bloc_origine", "n_composantes_informatives", "garde_r20_appliquee"}
    fautives = cles & interdites
    assert not fautives, f"la revue lit des données de décision du moteur : {sorted(fautives)}"
    autorisees = {"record_id_a", "record_id_b", "verdict", "revue_zone_grise", "decision",
                  "n_revues", "n_non_revues", "n_en_attente",
                  "budget_epuise", "adjudicateur_indisponible", "reponse_absente"}
    assert cles <= autorisees, f"clé hors liste blanche : {sorted(cles - autorisees)}"
    # Contrôle POSITIF : le collecteur voit bien un accès qu'on lui soumet.
    assert _cles_lues('x = corr["poids_match"]\ny = d.get("ground_truth")') == \
        {"poids_match", "ground_truth"}, "collecteur de clés mort"


def test_cc1_l_invite_ne_transporte_que_les_attributs_compares():
    """Cas 7 : une colonne surnuméraire ne peut PAS atteindre l'adjudicateur.

    Oracle de comportement, plus fort qu'un grep : on soumet un enregistrement portant une
    annotation étrangère et l'on vérifie qu'elle n'apparaît ni dans la charge, ni dans
    l'invite, ni dans la clé. La normalisation projette déjà défensivement sur les 8
    attributs comparés ; ceci éprouve que la revue n'ouvre pas de porte dérobée.
    """
    intrus = "ENT_SECRETE_0042"
    a = {"record_id": "X1", "nom": "dupont", "email": "d@example.fr",
         "id_entite_vraie": intrus, "zone_intention_design": "MATCH"}
    b = {"record_id": "X2", "nom": "dupont", "email": "d@example.fr"}
    charge = clt.charge_de_revue(a, b)
    rendu = json.dumps(charge, ensure_ascii=False) + clt.invite_de_charge(charge)
    assert intrus not in rendu, "une annotation étrangère atteint l'adjudicateur"
    assert "id_entite_vraie" not in rendu and "zone_intention_design" not in rendu
    assert [e["attribut"] for e in charge["attributs"]] == list(engine.ATTRIBUTS_COMPARE)
    # La clé ne bouge pas quand on retire l'intrus : il n'entre donc pas dans la question.
    propre = {cle: valeur for cle, valeur in a.items()
              if cle not in ("id_entite_vraie", "zone_intention_design")}
    assert clt.cle_de_charge(charge) == clt.cle_de_charge(clt.charge_de_revue(propre, b))


def _tous_les_modules_moteur():
    """TOUS les fichiers `.py` de `src/engine/`, sous-paquets compris.

    Le parcours est RÉCURSIF et dérivé du répertoire, non d'un n-uplet figé : un oracle
    qui itère sur une liste écrite à la main ne couvre que les modules auxquels on a pensé,
    et un module déposé à côté — ou un sous-paquet — y échapperait en silence.
    """
    dossier = os.path.join(_SRC, "engine")
    sources = {}
    for racine, _, fichiers in os.walk(dossier):
        if "__pycache__" in racine:
            continue
        for nom in sorted(fichiers):
            if not nom.endswith(".py"):
                continue
            chemin = os.path.join(racine, nom)
            relatif = os.path.relpath(chemin, dossier).replace(os.sep, "/")
            with open(chemin, encoding="utf-8") as fh:
                sources[relatif] = fh.read()
    assert len(sources) >= 8, f"zone moteur suspectement vide : {sorted(sources)}"
    return sources


def test_c7_aucun_module_du_moteur_ne_fait_d_entree_sortie():
    """Cas 7 / C7 : ni `open`, ni réseau, dans AUCUN module de la zone moteur.

    `open` est un BUILTIN : la liste blanche d'imports, qui lit l'AST des importations, ne
    le verrait pas passer. Sans cet oracle, « aucune entrée/sortie dans le moteur » ne
    serait garanti par rien — et la revue, qui consomme des fixtures, est précisément l'unité
    tentée d'en ouvrir une. L'oracle porte sur TOUS les modules, pas sur les seuls modules
    de la revue : la contrainte est celle de la zone, pas celle d'une unité.
    """
    interdits_appels = {"open", "eval", "exec", "compile", "__import__", "input"}
    interdits_attributs = {"urlopen", "connect", "request", "socket", "system", "popen"}
    for nom_fichier, source in _tous_les_modules_moteur().items():
        for noeud in ast.walk(ast.parse(source)):
            if not isinstance(noeud, ast.Call):
                continue
            if isinstance(noeud.func, ast.Name):
                assert noeud.func.id not in interdits_appels, (
                    f"{nom_fichier} : appel proscrit -> {noeud.func.id}()")
            elif isinstance(noeud.func, ast.Attribute):
                assert noeud.func.attr not in interdits_attributs, (
                    f"{nom_fichier} : appel proscrit -> {noeud.func.attr}")
    # Contrôle POSITIF : l'oracle détecte bien les deux formes qu'on lui soumet.
    for fautif in ('fh = open("fixtures/x.json")', 'urllib.request.urlopen(u)'):
        vu = False
        for noeud in ast.walk(ast.parse(fautif)):
            if isinstance(noeud, ast.Call):
                nom = getattr(noeud.func, "id", None) or getattr(noeud.func, "attr", None)
                vu = vu or nom in (interdits_appels | interdits_attributs)
        assert vu, f"oracle d'entrée/sortie mort sur {fautif!r}"


def test_les_fixtures_ne_se_presentent_pas_comme_une_transcription_de_modele():
    """Cas 7 : la provenance VOYAGE avec la valeur, en champ machine.

    Un `_lisez_moi` ne suit pas un fichier que l'on recopie ; un champ, si. Aucun modèle de
    langue n'est exécuté dans ce build : le corpus doit le DÉCLARER, faute de quoi le nom
    du répertoire suffirait à le faire passer pour autre chose.
    """
    with open(_FIXTURE, encoding="utf-8") as fh:
        fixture = json.load(fh)
    provenance = fixture["provenance"]
    assert provenance["est_une_transcription_de_modele"] is False
    assert provenance["modele"] is None
    assert provenance["nature"] == "VECTEURS_DE_TEST_FABRIQUES"
    assert fixture["entete"] == clt.entete_de_projection()


def test_une_transcription_d_une_autre_projection_est_refusee(transcription):
    """Le verrou de paramètres : une transcription périmée est REFUSÉE, pas rejouée.

    C'est ce que la clé, à elle seule, ne peut pas couvrir : elle décrit la question, pas la
    manière dont la question a été construite. Sans ce verrou, changer la projection
    laisserait rejouer un corpus qui répond à autre chose, sans un seul raté.
    """
    perimee = json.loads(json.dumps(transcription))
    perimee["entete"]["projection"] = "niveaux_d_accord_v0"
    with pytest.raises(clt.TranscriptionIncompatible):
        clt.ClientRejeu(perimee)


def test_une_reponse_vide_est_refusee_au_chargement(transcription):
    """Un enregistrement raté ne doit pas pouvoir se blanchir en abstention."""
    abimee = json.loads(json.dumps(transcription))
    cle = sorted(abimee["reponses"])[0]
    abimee["reponses"][cle]["texte"] = "   "
    with pytest.raises(clt.TranscriptionIncompatible):
        clt.ClientRejeu(abimee)


def test_une_cle_dupliquee_dans_la_fixture_est_refusee():
    """`json.load` écraserait silencieusement un doublon : le chargeur doit lever.

    C'est le hook RÉELLEMENT employé par `charge_fixture` qui est éprouvé ici, et non une
    copie écrite pour le test — une copie ne dirait rien du chargeur.
    """
    with pytest.raises(ValueError):
        json.loads('{"a": 1, "a": 2}',
                   object_pairs_hook=outil_vecteurs.refuse_doublon)
    # Contrôle POSITIF : sans doublon, le même hook laisse passer.
    assert json.loads('{"a": 1, "b": 2}',
                      object_pairs_hook=outil_vecteurs.refuse_doublon) == {"a": 1, "b": 2}


def test_les_outils_n_importent_ni_reseau_ni_calcul_flottant_externe():
    """Cas 7 : `tools/` est la zone de mesure — elle doit rester hors ligne et déterministe.

    Aucun oracle structurel ne couvrait `tools/` jusqu'ici, alors que c'est le seul endroit
    où un appel réseau ou une dépendance de calcul apparaîtrait. `numpy` / `pandas` sont
    proscrits ici pour une raison distincte du hors-ligne : l'ordre de sommation de leurs
    noyaux n'est pas garanti, ce qui réintroduirait du non-déterminisme dans un artefact
    censé se régénérer à l'octet.

    Les deux interdits sont SÉPARÉS depuis le merge de bout en bout, parce qu'ils n'ont pas la même
    force. Le hors-ligne ne souffre aucune exception : aucun outil, jamais, n'ouvre de
    socket. Le calcul flottant externe, lui, en souffre UNE, nommée : `banc_ub6.py` pilote
    Splink, dont l'interface d'entrée est un `DataFrame` — la dépendance est la raison
    d'être du banc, pas un oubli. L'exception est bornée à ce fichier et compensée : la
    reproductibilité de son artefact est éprouvée directement, par
    `tests/test_benchmark.py::test_dod8_l_artefact_publie_est_reproductible`, qui régénère
    le banc et le compare à l'octet au fichier publié. C'est un contrôle PLUS fort que
    l'interdit d'import qu'il remplace, et cette compensation est vérifiée ci-dessous : si
    ce test disparaît, l'exception cesse d'être couverte et celui-ci échoue.
    """
    reseau = {"requests", "urllib", "urllib3", "http", "socket", "websockets"}
    calcul_externe = {"numpy", "pandas", "sklearn", "torch", "transformers"}
    #: Seule exception, NOMMÉE. Un motif large aurait laissé entrer le prochain outil.
    exceptions_calcul = {"banc_ub6.py"}
    for nom_fichier in sorted(f for f in os.listdir(_TOOLS) if f.endswith(".py")):
        with open(os.path.join(_TOOLS, nom_fichier), encoding="utf-8") as fh:
            arbre = ast.parse(fh.read())
        importes = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                importes.update(a.name.split(".")[0] for a in noeud.names)
            elif isinstance(noeud, ast.ImportFrom) and not noeud.level and noeud.module:
                importes.add(noeud.module.split(".")[0])
        proscrits = reseau if nom_fichier in exceptions_calcul else reseau | calcul_externe
        fautifs = importes & proscrits
        assert not fautifs, f"tools/{nom_fichier} : dépendance proscrite -> {sorted(fautifs)}"

    # L'exception ne doit pas survivre au fichier qui la motive.
    presents = set(os.listdir(_TOOLS))
    assert exceptions_calcul <= presents, (
        f"exception accordée à un outil disparu : {sorted(exceptions_calcul - presents)}")
    # ... ni à la disparition de la garde qui la compense.
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "test_benchmark.py"), encoding="utf-8") as fh:
        arbre_garde = ast.parse(fh.read())
    garde = next((n for n in ast.walk(arbre_garde)
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "test_dod8_l_artefact_publie_est_reproductible"), None)
    assert garde is not None, (
        "la compensation de l'exception banc_ub6.py a disparu : soit la garde de "
        "reproductibilité revient, soit l'exception d'import tombe")
    # Le NOM ne suffit pas : un corps vidé, ou un `pytest.skip` en tête, laisserait
    # l'exception verte alors que la compensation n'existe plus. La garde doit donc encore
    # ASSERTER quelque chose, et ne pas se désamorcer elle-même.
    assert [n for n in ast.walk(garde) if isinstance(n, ast.Assert)], (
        "la garde de reproductibilité n'assère plus rien : compensation vide")
    desamorcages = {"skip", "xfail"}
    appels = {n.func.attr for n in ast.walk(garde)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not (appels & desamorcages), (
        f"la garde de reproductibilité se désamorce elle-même : {sorted(appels & desamorcages)}")
    # Contrôle POSITIF : l'oracle mord encore sur une infraction qu'on lui soumet.
    soumis = ast.parse("import pandas as pd\nimport socket\n")
    vus = {a.name.split(".")[0] for n in ast.walk(soumis)
           if isinstance(n, ast.Import) for a in n.names}
    assert vus & (reseau | calcul_externe) == {"pandas", "socket"}, "oracle mort"


def test_les_tests_du_moteur_ne_lisent_pas_la_verite_terrain():
    """Cas 7 : aucun test du MOTEUR n'accède à la vérité terrain par indexation.

    Élargi à tous les fichiers de test qui portent sur le moteur — la garde d'origine ne
    couvrait que `test_engine.py`, si bien qu'un test de la revue aurait pu affirmer « la revue
    restitue telle paire » en lisant l'étiquette, et rester vert. `test_generator.py` en est
    exclu à dessein : le générateur PRODUIT la vérité terrain, l'éprouver exige de la lire.

    L'oracle est en AST et non en sous-chaîne, parce que les deux ne disent pas la même
    chose : `pack["id_entite_vraie"]` est un ACCÈS, alors que `'x = pack["id_entite_vraie"]'`
    est une chaîne — le contrôle positif que ces fichiers emploient légitimement pour
    prouver que leurs propres gardes sont vivantes. Un grep confondrait les deux et
    interdirait d'écrire un contrôle positif ; c'est exactement ce qu'il ne faut pas.
    """
    interdits = {"id_entite_vraie", "ground_truth", "zone_intention_design"}
    dossier = os.path.dirname(os.path.abspath(__file__))
    for nom_fichier in _TESTS_SANS_VERITE_TERRAIN:
        chemin = os.path.join(dossier, nom_fichier)
        assert os.path.exists(chemin), f"fichier de test attendu absent : {nom_fichier}"
        with open(chemin, encoding="utf-8") as fh:
            arbre = ast.parse(fh.read())
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Subscript) and isinstance(noeud.slice, ast.Constant):
                assert noeud.slice.value not in interdits, (
                    f"{nom_fichier} ligne {noeud.lineno} : accès indexé à "
                    f"{noeud.slice.value}")
    # Contrôle POSITIF : l'oracle voit un accès réel, et NE voit pas une chaîne qui en
    # porte le texte — les deux moitiés comptent.
    def _acces(source):
        return [n.slice.value for n in ast.walk(ast.parse(source))
                if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)]
    jeton = "id_entite" + "_vraie"
    assert _acces("gt = pack[" + repr(jeton) + "]") == [jeton], "oracle d'accès mort"
    assert _acces("temoin = " + repr("pack[" + repr(jeton) + "]")) == [], (
        "l'oracle confond une chaîne avec un accès : il interdirait les contrôles positifs")


def test_la_mesure_de_contribution_vit_hors_du_moteur():
    """Cas 7 : le moteur DÉCIDE, il ne mesure pas — la frontière est le répertoire."""
    for nom_fichier, source in _sources_u_b3().items():
        for motif in (r"\bprecision\b", r"\brecall\b", r"\bf1[_ ]?score\b",
                      r"\btrue_positive", r"\bfalse_positive", r"\bconfusion_matrix"):
            trouve = re.search(motif, source, re.IGNORECASE)
            assert not trouve, f"{nom_fichier} : recompte de métrique -> {trouve.group(0)!r}"
        assert "id_entite_vraie" not in source.replace("\\\n", "").replace("\n", " ")
    # La mesure, elle, existe bien — mais dans `tools/`.
    with open(os.path.join(_TOOLS, "contribution_llm.py"), encoding="utf-8") as fh:
        assert "id_entite_vraie" in fh.read(), (
            "la mesure ne lit aucune vérité terrain : elle ne mesure donc rien")
