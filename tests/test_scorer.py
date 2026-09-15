# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Tests d'unité — scoreur indépendant et vérification de discrimination.

Lancement depuis la racine du repo de build : `python -m pytest tests/ -q`.

**Fichier DISTINCT de `tests/test_engine.py`, et c'est structurel.** La garde du moteur
(`test_les_tests_eux_memes_ne_lisent_pas_la_verite_terrain`) scanne son PROPRE fichier source
et échouerait si `ground_truth` y apparaissait. Le scoreur, lui, DOIT lire la vérité terrain :
mettre ces tests ailleurs n'est pas un rangement, c'est ce qui permet aux deux gardes de
coexister sans que l'une n'affaiblisse l'autre.

**Anti-vacuité.** Chaque test consommant la vraie fixture appelle `garde_non_vacuite` : un
test qui passerait sur zéro paire ne prouverait rien. Un méta-test le vérifie par AST, de
sorte que l'oubli de la garde soit lui-même détecté.

**Contrôles positifs.** Chaque oracle structurel doit DÉTECTER une infraction injectée : un
oracle qui ne détecte plus rien passerait au vert sur n'importe quel code.
"""
import ast
import json
import os
import subprocess
import sys

import pytest

import scorer
from scorer import contrat, couverture, criteres, distribution, metriques
from scorer import rapport as rap
from scorer import split as spl
from scorer import verite, zone_grise

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_SRC = os.path.join(_REPO_ROOT, "src")
_SCORER = os.path.join(_SRC, "scorer")
_ENGINE = os.path.join(_SRC, "engine")
_TOOL = os.path.join(_REPO_ROOT, "tools", "mesure_discrimination.py")
_FIXTURE_CANDIDATES = [
    os.environ.get("GEN_FIXTURE_V1_2", ""),
    os.path.join(_REPO_ROOT, "fixtures", "FIXTURE_PACK_GT_V1_2.json"),
]
_CONTENT_SHA256_V1_2 = "66f627edb37022dcecab04dae9c327b342d8dfbb785533ffe8017919000117a2"

#: Modules de `src/scorer/`, inventaire CLOS : aucun module ne peut y apparaître sans une
#: édition délibérée de ce test.
_MODULES_SCORER_ATTENDUS = ("__init__.py", "contrat.py", "verite.py", "couverture.py",
                            "metriques.py", "distribution.py", "zone_grise.py",
                            "split.py", "criteres.py", "rapport.py")

_STDLIB_AUTORISEE = frozenset({
    "__future__", "hashlib", "json", "math", "os", "re", "ast", "sys", "subprocess",
    "fractions", "typing", "itertools", "collections",
})


# ============================ outils de test =========================================
def _modules_scorer():
    """`{nom_de_fichier: (chemin, arbre AST)}` pour tout `src/scorer/`."""
    sortie = {}
    for nom in sorted(os.listdir(_SCORER)):
        if not nom.endswith(".py"):
            continue
        chemin = os.path.join(_SCORER, nom)
        with open(chemin, encoding="utf-8") as fh:
            sortie[nom] = (chemin, ast.parse(fh.read(), filename=chemin))
    return sortie


def _modules_chaine_de_mesure():
    """`src/scorer/` PLUS l'outil qui produit l'artefact.

    L'outil fait partie du code produit : l'exclure des oracles structurels laisserait sa
    conformite (stdlib, chemins, determinisme) entierement invérifiée.
    """
    cibles = dict(_modules_scorer())
    with open(_TOOL, encoding="utf-8") as fh:
        cibles["mesure_discrimination.py"] = (_TOOL, ast.parse(fh.read(), filename=_TOOL))
    return cibles


def _modules_engine():
    sortie = {}
    for nom in sorted(os.listdir(_ENGINE)):
        if not nom.endswith(".py"):
            continue
        chemin = os.path.join(_ENGINE, nom)
        with open(chemin, encoding="utf-8") as fh:
            sortie[nom] = (chemin, ast.parse(fh.read(), filename=chemin))
    return sortie


def _noms_importes(arbre):
    """Modules importés par un arbre AST, en remontant aux imports relatifs."""
    noms = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                noms.add(alias.name.split(".")[0])
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.level and noeud.level > 0:
                noms.add("." * noeud.level + (noeud.module or ""))
            elif noeud.module:
                noms.add(noeud.module.split(".")[0])
    return noms


def garde_non_vacuite(**quantites):
    """Refuse un test qui passerait sur une population vide.

    Appelée par tout test consommant la vraie fixture. Sans elle, un chargeur cassé rendant
    zéro paire ferait passer au vert la moitié de cette suite.
    """
    for nom, valeur in quantites.items():
        assert valeur, f"oracle vide : {nom} = {valeur!r} (le test ne prouverait rien)"


def _chemin_fixture():
    tentes = []
    for p in _FIXTURE_CANDIDATES:
        if not p:
            continue
        tentes.append(os.path.normpath(p))
        if os.path.exists(p):
            return p
    raise AssertionError(
        "FIXTURE_PACK_GT_V1_2.json introuvable (prerequis DUR). "
        "Chemins essayes : " + " | ".join(tentes))


@pytest.fixture(scope="module")
def pack():
    return verite.charge_pack(_chemin_fixture(), _CONTENT_SHA256_V1_2)


# --------------------------- mini-jeu à vérité ÉCRITE À LA MAIN ----------------------
# 6 enregistrements, 3 entités : {R1,R2,R3}, {R4,R5}, {R6}.
# Clôture = C(3,2) + C(2,2... soit 1) = 3 + 1 = 4 vraies paires. Forêt = 2 + 1 = 3 arêtes.
# L'écart 4 - 3 = 1 est exactement ce que le test `test_cloture_vs_foret` pince.
_GT_MINI = [
    {"record_id": "R1", "id_entite_vraie": "E1"},
    {"record_id": "R2", "id_entite_vraie": "E1"},
    {"record_id": "R3", "id_entite_vraie": "E1"},
    {"record_id": "R4", "id_entite_vraie": "E2"},
    {"record_id": "R5", "id_entite_vraie": "E2"},
    {"record_id": "R6", "id_entite_vraie": "E3"},
]


def _corr(a, b, r, verdict, garde=False, composantes=None, informatives=None):
    """Fabrique une CORRESPONDENCE minimale mais conforme au protocole."""
    comps = composantes or {"accord_nom": "ACCORD_FORT", "accord_prenom": "ACCORD_FORT",
                            "accord_date_naissance": "ACCORD_FORT", "accord_adresse": "ACCORD_FORT",
                            "accord_code_postal": "ACCORD_FORT", "accord_ville": "ACCORD_FORT",
                            "accord_email": "ACCORD_FORT", "accord_telephone": "ACCORD_FORT"}
    n_info = informatives if informatives is not None else sum(
        1 for v in comps.values() if v != "INDETERMINE_MANQUANT")
    return {"record_id_a": a, "record_id_b": b, "poids_match": r, "verdict": verdict,
            "revue_zone_grise": ({"statut": "en_attente"} if verdict == "ZONE_GRISE" else None),
            "bloc_origine": ["CP:75001"], "composantes": comps,
            "poids_par_champ": {k.replace("accord_", ""): 1.0 for k in comps},
            "n_composantes_informatives": n_info, "garde_r20_appliquee": garde}


# ======================= 1. Non-circularité — séparation STRUCTURELLE ================
def test_cc1_le_scoreur_n_importe_pas_le_moteur():
    """Cas 1 : par AST, et non par expression régulière — un commentaire ne doit pas mordre."""
    fautifs = {}
    for nom, (_, arbre) in _modules_scorer().items():
        interdits = {n for n in _noms_importes(arbre) if n in ("engine", "generator")}
        if interdits:
            fautifs[nom] = sorted(interdits)
    assert not fautifs, f"src/scorer importe la zone moteur/generateur : {fautifs}"


def test_cc1_le_moteur_n_importe_pas_le_scoreur():
    """Réciproque : la frontière est bilatérale, sinon elle ne prouve rien."""
    fautifs = {}
    for nom, (_, arbre) in _modules_engine().items():
        interdits = {n for n in _noms_importes(arbre) if n == "scorer"}
        if interdits:
            fautifs[nom] = sorted(interdits)
    assert not fautifs, f"src/engine importe le scoreur : {fautifs}"


def test_cc1_controle_positif_l_oracle_ast_mord_vraiment():
    """Contrôle POSITIF : l'oracle doit DÉTECTER une infraction injectée.

    Sans ce test, un oracle devenu aveugle (mauvais chemin, AST mal parcouru) passerait au
    vert sur n'importe quel code, y compris un code fautif.
    """
    infraction = ast.parse("from engine import decide\nimport generator\n")
    detectes = {n for n in _noms_importes(infraction) if n in ("engine", "generator")}
    assert detectes == {"engine", "generator"}, (
        f"l'oracle anti-circularite ne detecte pas une infraction pourtant flagrante : {detectes}")


def test_cc1_la_verite_terrain_n_est_lue_que_par_verite_py():
    """Anti-vacuité dans l'AUTRE sens : le scoreur DOIT lire la vérité, et à un seul endroit."""
    porteurs = []
    for nom, (chemin, _) in _modules_scorer().items():
        with open(chemin, encoding="utf-8") as fh:
            contenu = fh.read()
        # `ground_truth` en position de CODE (indexation ou parametre), pas en commentaire.
        if 'ground_truth"' in contenu or "ground_truth)" in contenu or "ground_truth," in contenu:
            porteurs.append(nom)
    assert "verite.py" in porteurs, (
        "verite.py ne lit pas ground_truth : le scoreur ne mesurerait rien")
    assert set(porteurs) <= {"verite.py", "rapport.py"}, (
        f"ground_truth lu hors de verite.py (et de son seul appelant rapport.py) : {porteurs}")


def test_inventaire_de_src_scorer_est_clos():
    """Aucun module ne peut apparaître dans `src/scorer/` sans édition délibérée de ce test."""
    presents = tuple(sorted(n for n in os.listdir(_SCORER) if n.endswith(".py")))
    assert presents == tuple(sorted(_MODULES_SCORER_ATTENDUS)), (
        f"inventaire de src/scorer modifie : {presents}")


def test_c7_stdlib_seule():
    """Offline strict : aucune dépendance hors bibliothèque standard.

    L'outil `tools/mesure_discrimination.py` est inclus : il fait partie de la chaine qui
    produit l'artefact, et l'exclure laisserait un tiers du code produit hors de tout oracle
    structurel. Il a droit, LUI SEUL, a importer `engine` et `scorer` : c'est sa raison d'etre.
    """
    for nom, (_, arbre) in _modules_chaine_de_mesure().items():
        autorises = set(_STDLIB_AUTORISEE)
        if nom == "mesure_discrimination.py":
            autorises |= {"engine", "scorer"}
        for module in _noms_importes(arbre):
            if module.startswith("."):
                continue
            assert module in autorises, f"{nom} importe {module!r}, hors liste autorisee"


def test_pas_de_chemin_absolu_os_dans_la_chaine_de_mesure():
    """Aucun chemin absolu OS-spécifique dans le code produit."""
    for nom, (chemin, _) in _modules_chaine_de_mesure().items():
        with open(chemin, encoding="utf-8") as fh:
            contenu = fh.read()
        assert "C:\\" not in contenu and "C:/" not in contenu, f"chemin absolu OS dans {nom}"


def test_aucun_hash_builtin_ni_alea_non_scelle():
    """`hash()` est salé par processus : l'employer casserait la reproductibilité."""
    for nom, (_, arbre) in _modules_chaine_de_mesure().items():
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name):
                assert noeud.func.id != "hash", f"{nom} appelle hash() (sale par processus)"
        assert "random" not in _noms_importes(arbre), f"{nom} importe random"


def test_aucune_sortie_a_forme_de_parametre_moteur():
    """Aucune fonction publique ne rend un objet réinjectable — sauf celle qui le dit.

    Le seuil oracle et le T* calibré sont les seuls chiffres supervisés ; leur nom porte
    l'interdit (`non_reinjectable`), de sorte que toute tentative de les passer au moteur soit
    visible par un simple `grep`.
    """
    suspects = []
    for nom, (_, arbre) in _modules_scorer().items():
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.FunctionDef) or noeud.name.startswith("_"):
                continue
            parametres = {a.arg for a in noeud.args.args + noeud.args.kwonlyargs}
            for retour in _dicts_retournes(noeud):
                cles = {c.value for c in retour.keys
                        if isinstance(c, ast.Constant) and isinstance(c.value, str)}
                if not {"t_mu", "t_lambda"} <= cles:
                    continue
                # Un couple de seuils rendu n'est licite QUE s'il n'est qu'un ECHO de ce qui a
                # ete recu (usage descriptif), ou si le nom de la fonction porte l'interdit.
                echo = {"t_mu", "t_lambda"} <= parametres
                if not echo and "non_reinjectable" not in noeud.name:
                    suspects.append(f"{nom}::{noeud.name}")
    assert not suspects, (
        f"fonctions FABRIQUANT un couple de seuils sans porter 'non_reinjectable' : {suspects}")


def _dicts_retournes(fonction):
    """Dictionnaires littéraux apparaissant dans un `return` de cette fonction."""
    sortie = []
    for noeud in ast.walk(fonction):
        if isinstance(noeud, ast.Return) and noeud.value is not None:
            for interne in ast.walk(noeud.value):
                if isinstance(interne, ast.Dict):
                    sortie.append(interne)
    return sortie


def test_controle_positif_l_oracle_de_reinjection_mord():
    """Contrôle POSITIF : une fonction fabriquant des seuils sans l'étiquette doit être vue."""
    fautif = ast.parse(
        "def propose_seuils(vraies, fausses):\n"
        "    return {'t_mu': 1.0, 't_lambda': -1.0}\n").body[0]
    parametres = {a.arg for a in fautif.args.args}
    cles = set()
    for retour in _dicts_retournes(fautif):
        cles |= {c.value for c in retour.keys if isinstance(c, ast.Constant)}
    assert {"t_mu", "t_lambda"} <= cles
    assert not ({"t_mu", "t_lambda"} <= parametres), (
        "l'oracle de reinjection ne detecterait pas une fabrication de seuils")


def test_le_diagnostic_supervise_porte_le_nom_qui_l_interdit():
    """Contrôle positif du précédent : la fonction supervisée existe et est bien nommée."""
    assert hasattr(spl, "diagnostic_seuil_optimal_non_reinjectable")
    assert "non_reinjectable" in spl.diagnostic_seuil_optimal_non_reinjectable.__name__


# ======================= 2. Vérité terrain — clôture vs forêt ========================
def test_cloture_vs_foret_sur_mini_jeu():
    """Cas 2 : une entité de taille 3 donne 3 vraies paires, et 2 arêtes de provenance.

    C'est le piège n°1 du mandat : dériver les paires de `record_id_origine` sous-estimerait
    le dénominateur du rappel.
    """
    vraies = verite.paires_vraies(_GT_MINI)
    stats = verite.statistiques_verite(_GT_MINI)
    assert len(vraies) == 4, f"cloture attendue a 4 paires, obtenue {len(vraies)}"
    assert stats["n_paires_foret_pour_memoire"] == 3
    assert stats["ecart_cloture_foret"] == 1
    assert ("R1", "R3") in vraies, "la paire transitive R1-R3 doit etre une vraie paire"
    assert ("R1", "R6") not in vraies, "R6 est un singleton : aucune vraie paire"


def test_la_signature_interdit_de_deriver_les_paires_de_la_provenance():
    """`paires_vraies` ne reçoit QUE `ground_truth` : la porte est fermée par la signature."""
    import inspect
    params = list(inspect.signature(verite.paires_vraies).parameters)
    assert params == ["ground_truth"], f"signature elargie : {params}"


def test_record_id_duplique_dans_la_verite_leve():
    """Une vérité ambiguë est une raison d'arrêter, pas de choisir (« dernier gagne » proscrit)."""
    with pytest.raises(ValueError):
        verite.partition_entites(_GT_MINI + [{"record_id": "R1", "id_entite_vraie": "E9"}])


def test_orientation_des_cles_est_canonique():
    """La clé est re-dérivée des deux côtés : l'ordre d'entrée ne doit rien changer."""
    assert contrat.cle_paire("R2", "R1") == ("R1", "R2") == contrat.cle_paire("R1", "R2")
    with pytest.raises(ValueError):
        contrat.cle_paire("R1", "R1")


def test_aucune_cloture_transitive_sur_les_predictions():
    """Interdiction symétrique : propager les MATCH emprunterait le clustering."""
    noms = [n for n in dir(scorer) if "clotur" in n.lower() or "transitiv" in n.lower()]
    assert not noms, f"une fonction de cloture est exposee : {noms}"


# ======================= 3. Contingence et métriques =================================
def _mini_classement(correspondances):
    vraies = verite.paires_vraies(_GT_MINI)
    classement = metriques.classe_les_paires(correspondances, vraies)
    return classement, metriques.contingence(classement, len(vraies))


def test_invariants_de_contingence():
    """Cas 3 : les deux identités de partition, sur des ENTIERS."""
    corrs = [_corr("R1", "R2", 20.0, "MATCH"), _corr("R1", "R3", 0.5, "ZONE_GRISE"),
             _corr("R2", "R3", -20.0, "NON_MATCH"), _corr("R1", "R6", 15.0, "MATCH")]
    classement, cont = _mini_classement(corrs)
    metriques.verifie_invariants(cont)
    assert cont == {**cont, "mv": 1, "mf": 1, "gv": 1, "gf": 0, "nv": 1, "nf": 0, "pb": 1}
    assert cont["mv"] + cont["gv"] + cont["nv"] + cont["pb"] == 4


def test_invariant_rompu_est_detecte():
    """Contrôle positif : une contingence fausse doit lever, pas passer."""
    with pytest.raises(AssertionError):
        metriques.verifie_invariants({"mv": 1, "mf": 0, "gv": 0, "gf": 0, "nv": 0, "nf": 0,
                                      "pb": 0, "n_vraies": 99, "n_candidates": 1,
                                      "n_vraies_candidates": 1})


def test_metriques_en_fractions_exactes():
    """P/R/F1 pinnés à la main sur une contingence littérale, sans aucune donnée."""
    cont = {"mv": 3, "mf": 1, "gv": 1, "gf": 2, "nv": 1, "nf": 10, "pb": 2,
            "n_vraies": 7, "n_candidates": 18, "n_vraies_candidates": 5}
    m = metriques.mesures(cont, "stricte")
    assert (m["tp"], m["fp"], m["fn"]) == (3, 1, 4)
    assert m["precision"] == 3 / 4
    assert m["rappel_bout_en_bout"] == 3 / 7          # denominateur |M| ENTIER
    assert m["rappel_post_blocking"] == 3 / 5         # denominateur restreint aux candidates
    assert m["f1_bout_en_bout"] == pytest.approx(2 * (3 / 4) * (3 / 7) / ((3 / 4) + (3 / 7)))
    assert m["fn_blocking"] == 2 and m["fn_scoring"] == 2


def test_le_denominateur_du_rappel_inclut_les_perdues_au_blocking():
    """Le point qui fait disparaître une perte de blocking d'un rapport de qualité."""
    cont = {"mv": 5, "mf": 0, "gv": 0, "gf": 0, "nv": 0, "nf": 0, "pb": 5,
            "n_vraies": 10, "n_candidates": 5, "n_vraies_candidates": 5}
    m = metriques.mesures(cont, "stricte")
    assert m["rappel_bout_en_bout"] == 0.5, "le rappel de tete doit compter les perdues"
    assert m["rappel_post_blocking"] == 1.0, "le rappel conditionnel doit valoir 1"


def test_precision_indefinie_est_none_et_non_zero():
    """`0/0` n'est pas `0` : un zéro se propagerait silencieusement dans toute comparaison."""
    cont = {"mv": 0, "mf": 0, "gv": 0, "gf": 0, "nv": 2, "nf": 3, "pb": 0,
            "n_vraies": 2, "n_candidates": 5, "n_vraies_candidates": 2}
    m = metriques.mesures(cont, "stricte")
    assert m["precision"] is None
    assert "0/0" in m["motif_precision"]
    assert m["f1_bout_en_bout"] is None


def test_intervalle_de_wilson_encadre_et_reste_dans_zero_un():
    """Wilson plutôt que Wald : ce dernier dégénère précisément aux proportions extrêmes."""
    bas, haut = metriques.intervalle_wilson(271, 271)
    assert 0.0 <= bas <= 1.0 and haut == 1.0 and bas < 1.0
    bas, haut = metriques.intervalle_wilson(251, 271)
    assert bas < 251 / 271 < haut


def test_abstention_est_toujours_flanquee_de_sa_couverture():
    """Chow (1970) : un classifieur à option de rejet paraît meilleur sur ce qu'il décide.

    Le DÉNOMINATEUR du rappel sous abstention est pinné, et pas seulement la couverture :
    retirer les paires grises du numérateur sans les retirer du dénominateur du rappel serait
    l'erreur naturelle, et elle passerait inaperçue si seule la couverture était verifiée.
    """
    cont = {"mv": 3, "mf": 1, "gv": 1, "gf": 2, "nv": 1, "nf": 10, "pb": 2,
            "n_vraies": 7, "n_candidates": 18, "n_vraies_candidates": 5}
    a = metriques.metriques_sous_abstention(cont)
    assert a["couverture"] == (18 - 3) / 18
    assert a["n_paires_abstenues"] == 3
    assert a["precision"] == 3 / 4
    assert a["rappel"] == 3 / 6, "le denominateur doit etre |M| prive des vraies paires grises"
    assert a["f1"] == pytest.approx(2 * (3 / 4) * (3 / 6) / ((3 / 4) + (3 / 6)))
    assert "couverture" in a["avertissement"]


def test_intervalle_de_wilson_valeur_pinnee():
    """Le niveau de confiance publié doit être le bon : une valeur est pinnée numériquement.

    Sans cela, remplacer `z = 1,96` par `z = 1,0` publierait des intervalles a 68 % sous
    l'etiquette « 95 % » sans qu'aucun test ne rougisse.
    """
    bas, haut = metriques.intervalle_wilson(251, 271)
    assert bas == pytest.approx(0.889, abs=1e-3)
    assert haut == pytest.approx(0.952, abs=1e-3)
    # Demi-largeur ~2 points pres de 0,97 sur 271 : c'est le socle de resolution declare.
    b2, h2 = metriques.intervalle_wilson(263, 271)
    assert (h2 - b2) / 2 == pytest.approx(0.020, abs=0.004)


def test_audit_d_integrite_detecte_chaque_anomalie():
    """Le préalable bloquant P0 : chaque anomalie doit lever l'alerte, et le cas propre non.

    C'est l'audit dont dépend le statut NOT_CONCLUSIVE ; s'il ne mordait pas, une jointure
    cassee produirait des metriques d'apparence normale.
    """
    propre = [_corr("R1", "R2", 1.0, "MATCH"), _corr("R3", "R4", -1.0, "NON_MATCH")]
    assert contrat.valide_correspondances(propre)["alerte"] is False
    assert contrat.valide_correspondances(propre, 2)["alerte"] is False

    anomalies = {
        "doublon": [_corr("R1", "R2", 1.0, "MATCH"), _corr("R1", "R2", 2.0, "MATCH")],
        "verdict_inconnu": [_corr("R1", "R2", 1.0, "PEUT_ETRE")],
        "poids_nan": [_corr("R1", "R2", float("nan"), "MATCH")],
        "poids_infini": [_corr("R1", "R2", float("inf"), "MATCH")],
    }
    for nom, corrs in anomalies.items():
        constats = contrat.valide_correspondances(corrs)
        assert constats["alerte"] is True, f"anomalie non detectee : {nom}"
        assert constats["motif"], f"anomalie {nom} detectee sans motif"
    # Orientation non canonique : construite a la main (le fabricant respecte la convention).
    inverse = dict(_corr("R1", "R2", 1.0, "MATCH"), record_id_a="R2", record_id_b="R1")
    assert contrat.valide_correspondances([inverse])["alerte"] is True
    # Ecart de cardinalite avec la trace du moteur.
    assert contrat.valide_correspondances(propre, 99)["alerte"] is True
    # Auto-paire : la cle leve avant meme l'audit, ce qui est la garde la plus dure.
    with pytest.raises(ValueError):
        contrat.cle_de_correspondance(_corr("R1", "R1", 1.0, "MATCH"))


# ======================= 4. Bornes du doute — atteignables ===========================
def test_les_bornes_encadrent_les_quatre_conventions():
    cont = {"mv": 3, "mf": 1, "gv": 2, "gf": 2, "nv": 1, "nf": 10, "pb": 1,
            "n_vraies": 7, "n_candidates": 19, "n_vraies_candidates": 6}
    bornes = zone_grise.bornes_du_doute(cont)
    toutes = metriques.mesures_toutes_conventions(cont)
    f1s = [m["f1_bout_en_bout"] for m in toutes.values() if m["f1_bout_en_bout"] is not None]
    assert bornes["pessimiste"]["f1"] <= min(f1s) + 1e-12
    assert bornes["optimiste"]["f1"] >= max(f1s) - 1e-12


def test_enumeration_exhaustive_des_resolutions_de_bande():
    """Les bornes sont ATTEIGNABLES : l'énumération des 4 résolutions le démontre.

    Prendre le meilleur numérateur et le meilleur dénominateur sur des résolutions
    DIFFÉRENTES donnerait un F1 supérieur à tout F1 réalisable — une borne vraie de personne.
    """
    cont = {"mv": 3, "mf": 1, "gv": 1, "gf": 1, "nv": 1, "nf": 10, "pb": 1,
            "n_vraies": 6, "n_candidates": 17, "n_vraies_candidates": 5}
    bornes = zone_grise.bornes_du_doute(cont)
    realisables = []
    for promue_vraie in (0, 1):                # la vraie grise est-elle resolue en MATCH ?
        for promue_fausse in (0, 1):           # la fausse grise l'est-elle ?
            tp = cont["mv"] + promue_vraie
            fp = cont["mf"] + promue_fausse
            p = tp / (tp + fp)
            r = tp / cont["n_vraies"]
            realisables.append(2 * p * r / (p + r))
    assert bornes["pessimiste"]["f1"] == pytest.approx(min(realisables))
    assert bornes["optimiste"]["f1"] == pytest.approx(max(realisables))


# ======================= 5. Zone grise — lue sur le VERDICT ==========================
def test_zone_grise_lue_sur_le_verdict_jamais_sur_les_seuils():
    """Le piège n°6 : une paire gardée R-20 porte `R = 0.0` et tombe DANS la bande.

    La reconstruire par comparaison de seuils la verserait en zone grise et fausserait la
    composition. La source de vérité est le verdict.
    """
    corrs = [
        _corr("R1", "R2", 20.0, "MATCH"),
        _corr("R1", "R3", 0.0, "NON_MATCH", garde=True, informatives=0,
              composantes={f"accord_{a}": "INDETERMINE_MANQUANT" for a in
                           ("nom", "prenom", "date_naissance", "adresse", "code_postal",
                            "ville", "email", "telephone")}),
        _corr("R4", "R5", 0.5, "ZONE_GRISE"),
    ]
    vraies = verite.paires_vraies(_GT_MINI)
    comp = zone_grise.composition(corrs, vraies, len(vraies), len(corrs))
    assert comp["n_gris"] == 1, "la paire gardee R-20 ne doit PAS compter en zone grise"
    rec = zone_grise.reconciliation_de_bande(corrs, t_mu=1.0, t_lambda=-1.0)
    assert rec["n_dans_la_bande_par_seuils"] == 2      # la gardee ET la grise
    assert rec["n_zone_grise_par_verdict"] == 1
    assert rec["n_gardees_dans_la_bande"] == 1
    assert rec["coherent"] and rec["ecart_bande_vs_verdict"] == 0


def test_composition_de_bande_oracle_litteral():
    """`part_minoritaire` porte l'axe « doute exercé » : elle est pinnée sur un cas à la main.

    Bande de 4 paires, 1 vraie et 3 fausses : `part_minoritaire = 1/4`, `purete = 1/4`,
    `entropie = -0,25·log2(0,25) - 0,75·log2(0,75) ≈ 0,8113`. Sans cet oracle, inverser `min`
    en `max` traverserait toute la DoD sans un seul echec.
    """
    vraies = verite.paires_vraies(_GT_MINI)
    bande = [_corr("R1", "R2", 0.5, "ZONE_GRISE"),      # vraie (E1)
             _corr("R1", "R6", 0.5, "ZONE_GRISE"),      # fausse
             _corr("R2", "R6", 0.4, "ZONE_GRISE"),      # fausse
             _corr("R3", "R6", 0.3, "ZONE_GRISE")]      # fausse
    comp = zone_grise.composition(bande, vraies, len(vraies), len(bande))
    assert comp["n_gris"] == 4
    assert comp["n_vraies_gris"] == 1 and comp["n_fausses_gris"] == 3
    assert comp["part_minoritaire"] == 0.25
    assert comp["purete"] == 0.25
    assert comp["entropie_bits"] == pytest.approx(0.811278, abs=1e-6)
    assert comp["rappel_en_jeu"] == 1 / 4


def test_part_minoritaire_est_une_fonction_partagee():
    """La formule est nommée et unique : la sensibilité ne peut pas en diverger.

    L'analyse de sensibilite du rapport a besoin de la grandeur sur des effectifs PERTURBES.
    Lui faire recopier la formule laisserait deux definitions se separer en silence.
    """
    assert zone_grise.part_minoritaire(1, 3) == 0.25
    assert zone_grise.part_minoritaire(3, 1) == 0.25, "la fonction doit etre symetrique"
    assert zone_grise.part_minoritaire(0, 0) is None
    source = ast.dump(ast.parse(open(os.path.join(_SCORER, "rapport.py"),
                                     encoding="utf-8").read()))
    assert "part_minoritaire" in source
    assert "'min'" not in source or "part_minoritaire" in source
    # La sensibilite doit APPELER la fonction, pas recalculer min(...)/n.
    with open(os.path.join(_SCORER, "rapport.py"), encoding="utf-8") as fh:
        texte = fh.read()
    assert "zgr.part_minoritaire(gv2, gf2)" in texte, (
        "l'analyse de sensibilite recopie la formule au lieu de l'appeler")


def test_gain_d_une_revue_parfaite_et_amplitude_sont_distincts():
    """Deux grandeurs que l'on confond aisément, et que l'artefact doit publier séparément.

    L'amplitude compare le meilleur relecteur au PIRE ; le gain compare le meilleur relecteur
    a l'ABSENCE de revue. C'est le gain qui repond a « la revue a-t-elle matiere a instruire ».
    """
    cont = {"mv": 3, "mf": 1, "gv": 2, "gf": 20, "nv": 1, "nf": 10, "pb": 1,
            "n_vraies": 7, "n_candidates": 37, "n_vraies_candidates": 6}
    b = zone_grise.bornes_du_doute(cont)
    tete = metriques.mesures(cont, "stricte")["f1_bout_en_bout"]
    assert b["f1_convention_de_tete"] == pytest.approx(tete)
    assert b["gain_d_une_revue_parfaite_f1"] == pytest.approx(b["optimiste"]["f1"] - tete)
    assert b["largeur_intervalle_f1"] == pytest.approx(b["optimiste"]["f1"]
                                                       - b["pessimiste"]["f1"])
    assert b["gain_d_une_revue_parfaite_f1"] < b["largeur_intervalle_f1"], (
        "le gain doit etre strictement inferieur a l'amplitude des qu'il y a des fausses grises")


def test_irreductibilite_distingue_bande_pure_et_bande_mixte():
    """Z3 : si chaque valeur de `R` est pure, un meilleur SEUIL résout la bande."""
    vraies = verite.paires_vraies(_GT_MINI)
    pure = [_corr("R1", "R2", 1.0, "ZONE_GRISE"), _corr("R4", "R6", 2.0, "ZONE_GRISE")]
    mixte = [_corr("R1", "R2", 1.0, "ZONE_GRISE"), _corr("R4", "R6", 1.0, "ZONE_GRISE")]
    assert zone_grise.irreductibilite(pure, vraies)["plancher_bayes_bande"] == 0
    assert zone_grise.irreductibilite(mixte, vraies)["plancher_bayes_bande"] == 1
    assert zone_grise.irreductibilite(mixte, vraies)["part_paires_mixtes"] == 1.0


# ======================= 6. Distribution et séparation ===============================
def test_auc_ex_aequo_vaut_exactement_un_demi():
    """Populations identiques : rangs moyens obligent, l'AUC vaut 0,5 EXACTEMENT."""
    a = distribution.auc_mann_whitney([1.0, 1.0, 1.0], [1.0, 1.0])
    assert a["valeur"] == 0.5


def test_auc_separation_parfaite_vaut_un():
    a = distribution.auc_mann_whitney([10.0, 11.0], [-1.0, 0.0])
    assert a["valeur"] == 1.0


def test_ovl_calcule_a_la_main():
    """Oracle indépendant : 2 seaux, 4 valeurs, recouvrement de 0,5 vérifiable de tête."""
    r = distribution.recouvrement([0.5, 1.5], [0.5, 10.5], pas=1.0)
    assert r["ovl"] == pytest.approx(0.5)
    assert r["tvd"] == pytest.approx(0.5)


def test_quantile_accorde_avec_la_methode_declaree():
    """Méthode réimplémentée : pinnée sur un vecteur littéral, sans importer le moteur."""
    assert distribution.quantile([0.0, 1.0, 2.0, 3.0], 0.5) == pytest.approx(1.5)
    assert distribution.quantile([0.0, 1.0, 2.0, 3.0], 0.0) == 0.0
    assert distribution.quantile([5.0], 0.9) == 5.0


def test_marge_de_separation_est_signee():
    assert distribution.marge_de_separation([10.0], [1.0])["marge"] == 9.0
    assert distribution.marge_de_separation([10.0], [1.0])["supports_disjoints"] is True
    assert distribution.marge_de_separation([1.0], [10.0])["marge"] == -9.0


def test_plancher_de_bayes_compte_les_valeurs_mixtes():
    p = distribution.plancher_bayes_sur_r([1.0, 2.0], [1.0, 3.0])
    assert p["plancher_bayes"] == 1 and p["n_valeurs_mixtes"] == 1


def test_histogramme_signale_le_hors_support_sans_etendre_la_grille():
    h = distribution.histogramme([0.5, 1000.0], pas=1.0)
    assert h["n_hors_support"] == 1
    assert h["bornes_declarees"] == [-128.0, 128.0]


def test_recouvrement_refuse_de_chiffrer_sur_une_grille_saturee():
    """Une valeur hors grille disparaît des deux histogrammes : l'OVL paraîtrait plus faible.

    Deux populations IDENTIQUES placees hors de la grille donneraient `ovl = 0`, soit une
    separation parfaite apparente sur des distributions confondues. Le recouvrement est donc
    rendu NON EVALUABLE plutot qu'optimiste.
    """
    r = distribution.recouvrement([1000.0, 1001.0], [1000.0, 1001.0], pas=1.0)
    assert r["ovl"] is None, "une grille saturee ne doit pas produire un chiffre optimiste"
    assert r["grille_saturee"] is True and r["n_hors_support"] == 4
    assert "hors de la grille" in r["motif"]
    propre = distribution.recouvrement([0.5, 1.5], [0.5, 1.5], pas=1.0)
    assert propre["ovl"] == pytest.approx(1.0) and propre["grille_saturee"] is False


def test_conversion_auc_publie_les_deux_perimetres():
    """Le denominateur de l'AUC est le nombre de paires SCOREES, pas |M|.

    Le critere gele C1 emploie |M| ; le defaut est conserve (regle de non-revision) et la
    conversion coherente publiee a cote. Ce test pinne les DEUX, pour que l'ecart reste
    visible et ne puisse pas etre efface par megarde.
    """
    # 3 vraies scorees dont une entierement mal classee, 3 fausses, +1 vraie perdue => |M| = 4.
    sep = distribution.separation([0.0, 20.0, 30.0], [1.0, 2.0, 3.0], n_vraies_total=4)
    assert sep["denominateur_de_l_auc"] == 3
    assert sep["auc"] == pytest.approx(2 / 3)
    assert sep["paires_scorees_equivalentes_mal_classees"] == pytest.approx(1.0), (
        "sur le perimetre coherent, exactement UNE paire est entierement mal classee")
    assert sep["paires_vraies_equivalentes_mal_classees"] == pytest.approx(4 / 3)


def test_pairs_quality_oracle_litteral():
    """Le plancher de trivialité contre lequel la précision se lit."""
    assert couverture.pairs_quality(3, 12) == 0.25
    assert couverture.pairs_quality(0, 5) == 0.0
    assert couverture.pairs_quality(1, 0) is None
    assert couverture.taux_de_reduction(0, 10) == 1.0
    assert couverture.n_paires_possibles(537) == 143916


def test_rappel_blocking_sur_mini_jeu_a_verite_ecrite_a_la_main():
    """Le plafond : ce que la chaîne ne peut pas trouver, quels que soient les seuils."""
    vraies = verite.paires_vraies(_GT_MINI)          # 4 vraies paires
    candidates = [("R1", "R2"), ("R1", "R3"), ("R1", "R6")]   # R2-R3 et R4-R5 non proposees
    pc = couverture.rappel_blocking(candidates, vraies)
    assert pc["n_vraies"] == 4
    assert pc["n_vraies_survivantes"] == 2
    assert pc["n_vraies_perdues"] == 2
    assert pc["pair_completeness"] == 0.5
    assert sorted(pc["perdues"]) == [("R2", "R3"), ("R4", "R5")]
    assert pc["plafond_de_rappel"] == 0.5


def test_contribution_par_passe_repere_une_passe_redondante():
    """Une passe de marginale nulle est intégralement redondante — constat descriptif."""
    vraies = verite.paires_vraies(_GT_MINI)
    corrs = [dict(_corr("R1", "R2", 5.0, "MATCH"), bloc_origine=["CP:75001", "PREF:dupo"]),
             dict(_corr("R1", "R3", 5.0, "MATCH"), bloc_origine=["CP:75001"])]
    par_passe = couverture.contribution_par_passe(corrs, vraies)["par_passe"]
    assert par_passe["PREF"]["pc_seule"] > 0
    assert par_passe["PREF"]["pc_marginale"] == 0.0, (
        "PREF n'apporte que R1-R2, deja trouvee par CP : sa marginale est nulle")
    assert par_passe["CP"]["pc_marginale"] > 0


def test_le_seuil_oracle_porte_son_etiquette():
    o = distribution.seuil_oracle_f1([10.0, 11.0], [-1.0, 0.0], 2)
    assert "ORACLE" in o["statut"] and "NE PAS reporter" in o["statut"]


# ======================= 7. Split — par ENTITÉ, sans fuite ===========================
def test_split_par_entite_aucune_vraie_paire_a_cheval():
    """Le cluster est l'unité d'indépendance : aucune vraie paire ne peut être coupée."""
    groupes = verite.entites(_GT_MINI)
    aff = spl.partitionne_entites(groupes)
    rep = spl.repartit_paires(sorted(verite.paires_vraies(_GT_MINI)), aff["par_record"])
    assert rep["a_cheval"] == [], f"vraie(s) paire(s) a cheval : {rep['a_cheval']}"


def test_toute_paire_a_cheval_est_fausse():
    """Propriété DÉMONTRABLE : deux entités distinctes ne partagent aucune vraie paire."""
    groupes = verite.entites(_GT_MINI)
    aff = spl.partitionne_entites(groupes)
    vraies = verite.paires_vraies(_GT_MINI)
    toutes = [contrat.cle_paire(a, b)
              for i, a in enumerate(sorted(aff["par_record"]))
              for b in sorted(aff["par_record"])[i + 1:]]
    rep = spl.repartit_paires(toutes, aff["par_record"])
    garde_non_vacuite(paires_a_cheval=rep["a_cheval"])
    assert all(cle not in vraies for cle in rep["a_cheval"])


def test_split_stable_a_l_ajout_d_une_entite():
    """Fonction PURE de l'identifiant : aucun schéma par index ou par rang n'offre cela."""
    avant = spl.partitionne_entites(verite.entites(_GT_MINI))["par_entite"]
    elargi = _GT_MINI + [{"record_id": "R7", "id_entite_vraie": "E4"},
                         {"record_id": "R8", "id_entite_vraie": "E4"}]
    apres = spl.partitionne_entites(verite.entites(elargi))["par_entite"]
    for ent, pli in avant.items():
        assert apres[ent] == pli, f"l'ajout d'une entite a deplace {ent}"


def test_split_ne_depend_pas_du_hash_builtin():
    """Deux processus sous des `PYTHONHASHSEED` différents doivent affecter à l'identique."""
    script = (
        "import sys, json; sys.path.insert(0, %r);"
        "from scorer import split, verite;"
        "gt=%s;"
        "print(json.dumps(split.partitionne_entites(verite.entites(gt))['par_entite'], sort_keys=True))"
        % (_SRC, json.dumps(_GT_MINI))
    )
    sorties = []
    for graine in ("0", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=graine)
        sorties.append(subprocess.check_output([sys.executable, "-c", script], env=env,
                                               text=True).strip())
    assert sorties[0] == sorties[1], "le split depend du salage de hash() : determinisme rompu"


# ======================= 8. Critères PRÉ-ENREGISTRÉS =================================
def test_codes_de_criteres_bijectifs(pack):
    """Ni critère muet, ni critère surnuméraire : la comparaison va dans LES DEUX SENS."""
    verdict = _rapport_reel(pack)["verdict"]
    emis = {c["code"] for c in verdict["criteres"]}
    assert emis == set(criteres.CRITERES), (
        f"ecart entre criteres emis et declares : {emis ^ set(criteres.CRITERES)}")


def test_enonces_de_verdict_sont_verbatim(pack):
    """IMPOSSIBLE de reformuler la lecture après avoir vu les chiffres."""
    verdict = _rapport_reel(pack)["verdict"]
    gabarits = set(criteres.ENONCES.values())
    retenus = [c["enonce_retenu"] for c in verdict["criteres"] if "enonce_retenu" in c]
    garde_non_vacuite(enonces_retenus=retenus)
    for gabarit in retenus:
        assert gabarit in gabarits, f"enonce hors du verbatim pre-enregistre : {gabarit[:80]}"


def test_les_deux_issues_symetriques_existent_dans_le_verbatim():
    """L'issue flatteuse a SA phrase, écrite avant la mesure — le cœur de l'anti-circularité."""
    assert "RESULTAT VRAI" in criteres.ENONCES["RAPPEL_SATURE"]
    assert "RESULTAT VRAI A PUBLIER" in criteres.ENONCES["MOTEUR_EXCELLENT_RESULTAT_A_PUBLIER"]
    assert "credible et mesurable" in criteres.ENONCES["RAPPEL_EXERCE"]
    for cle in ("ZONE_GRISE_NON_TRIVIALE", "ZONE_GRISE_TRIVIALE"):
        assert cle in criteres.ENONCES


def test_aucune_recommandation_sur_la_donnee(pack):
    """Discipline lexicale : le verdict n'a jamais la donnée pour destinataire."""
    rapport = _rapport_reel(pack)
    assert rapport["verdict"]["aucune_recommandation_sur_la_donnee"] is True
    texte = json.dumps(rapport, ensure_ascii=False).lower()
    for interdit in ("plus dure", "plus difficile", "durcir la donnee", "rendre la fixture"):
        assert interdit not in texte, f"formulation prescriptive envers la donnee : {interdit!r}"


def test_criteres_evalues_sur_les_deux_branches_opposees():
    """Les deux issues doivent produire une lecture : aucune branche n'est morte."""
    socle = dict(alerte_plomberie=False, n_vraies_paires=271, n_vraies_paires_candidates=264,
                 n_paires_candidates=6000, tp=250, precision=0.9, taux_match=0.05,
                 part_vraies_paires_corrompues=0.9, au_moins_une_vraie_paire_non_triviale=True,
                 part_fn_expliques=0.95, part_fn_au_dessus_de_la_mediane_des_vraies=0.05,
                 n_perdues_blocking=7, n_manquees_decision=14, rappel_blocking=0.97,
                 ic_wilson_rappel=[0.9, 0.96], n_gris=300, part_gris=0.05,
                 plancher_bayes_r=200, ap=0.9, plage_commune=[-5.0, 5.0])
    exerce = dict(socle, rappel_bout_en_bout=0.92, f1_bout_en_bout=0.9,
                  n_vraies_gris=20, n_fausses_gris=280, part_minoritaire=0.066,
                  part_paires_mixtes=0.3, plancher_bayes_bande=15, rappel_en_jeu=0.07,
                  largeur_intervalle_f1=0.05, auc_dans_la_zone_grise=0.5, auc=0.97, ovl=0.08,
                  marge_de_separation=-5.0, rappel_optimiste=0.99, rappel_pessimiste=0.92)
    sature = dict(socle, rappel_bout_en_bout=0.999, tp=271, f1_bout_en_bout=0.995,
                  n_vraies_gris=0, n_fausses_gris=300, part_minoritaire=0.0,
                  part_paires_mixtes=0.0, plancher_bayes_bande=0, rappel_en_jeu=0.0,
                  largeur_intervalle_f1=0.0, auc_dans_la_zone_grise=None, auc=1.0, ovl=0.0,
                  marge_de_separation=3.0, rappel_optimiste=0.999, rappel_pessimiste=0.999,
                  n_manquees_decision=0, n_perdues_blocking=0)
    v_exerce, v_sature = criteres.lis_verdict(exerce), criteres.lis_verdict(sature)
    assert v_exerce["triplet"]["decision_exercee"] is True
    assert v_sature["triplet"]["decision_exercee"] is False
    assert v_sature["triplet"]["doute_exerce"] is False
    codes_sature = {c["code"]: c["issue"] for c in v_sature["criteres"]}
    assert codes_sature["D1_MOTEUR_EXCELLENT"] == "MOTEUR_EXCELLENT_RESULTAT_A_PUBLIER"
    assert codes_sature["C1_SEPARATION"] == "SUPPORTS_DISJOINTS"


# ======================= 9. Artefact — forme et déterminisme =========================
_RAPPORT_CACHE = {}


def _rapport_reel(pack):
    """Construit l'artefact une seule fois pour toute la session (le moteur coûte ~13 s)."""
    if "r" not in _RAPPORT_CACHE:
        sys.path.insert(0, os.path.join(_REPO_ROOT, "tools"))
        import mesure_discrimination as outil
        _RAPPORT_CACHE["r"] = outil.construis()
    return _RAPPORT_CACHE["r"]


def test_forme_de_l_artefact(pack):
    """Aucune clé ne peut manquer ni apparaître selon la branche : le schéma est une décision."""
    attendu = {
        "_lisez_moi", "version_schema", "mandat", "unite", "objectif", "statut", "provenance",
        "preenregistrement", "conventions", "alerte_plomberie", "controles_prealables",
        "verite_terrain", "profil_des_vraies_paires", "couverture_blocking", "distribution_r",
        "regimes", "split", "diagnostic_supervise_non_reinjectable", "verdict", "limites",
        "empreinte_des_mesures",
    }
    rapport = _rapport_reel(pack)
    assert set(rapport) == attendu, f"schema de tete modifie : {set(rapport) ^ attendu}"
    assert set(rapport["regimes"]) == {"seuils_placeholder", "seuils_dimensionnes"}
    forme_a, forme_b = (set(rapport["regimes"]["seuils_placeholder"]),
                        set(rapport["regimes"]["seuils_dimensionnes"]))
    assert forme_a == forme_b, f"les deux regimes n'ont pas la meme forme : {forme_a ^ forme_b}"
    assert "aucun_horodatage" not in rapport
    for interdit in ("timestamp", "date_execution", "genere_le"):
        assert interdit not in json.dumps(rapport), f"horodatage present : {interdit}"


def test_mesures_reelles_non_vacuees(pack):
    """Anti-vacuité sur la vraie fixture : la mesure porte bien sur quelque chose."""
    rapport = _rapport_reel(pack)
    reg = rapport["regimes"]["seuils_dimensionnes"]
    garde_non_vacuite(
        n_vraies_paires=rapport["verite_terrain"]["n_vraies_paires"],
        n_paires_candidates=reg["cardinaux"]["n_candidates"],
        n_match=reg["cardinaux"]["n_match"])
    assert rapport["verite_terrain"]["n_vraies_paires"] == 271
    assert rapport["verite_terrain"]["n_entites"] == 320
    assert rapport["verite_terrain"]["n_paires_foret_pour_memoire"] == 217


def test_les_mesures_exigees_par_le_mandat_sont_presentes(pack):
    """DoD §7.3 : distribution de R (vraies/fausses), P/R/F1, zone grise, rappel de blocking."""
    rapport = _rapport_reel(pack)
    principal = rapport["distribution_r"]["par_perimetre"]["principal"]
    garde_non_vacuite(r_des_vraies=principal["vraies"]["n"],
                      r_des_fausses=principal["fausses"]["n"])
    assert principal["vraies"]["n"] > 0 and principal["fausses"]["n"] > 0
    for cle in ("auc", "ovl", "ks_d", "marge_de_separation"):
        assert principal["separation"][cle] is not None
    tete = rapport["regimes"]["seuils_dimensionnes"]["mesures_par_convention"]["stricte"]
    for cle in ("precision", "rappel_bout_en_bout", "f1_bout_en_bout"):
        assert tete[cle] is not None
    # Identites, et non un `>= 0` toujours vrai : le compte des perdues, celui des
    # survivantes et la liste enumeree doivent se refermer sur |M|.
    cb = rapport["couverture_blocking"]
    n_vraies = rapport["verite_terrain"]["n_vraies_paires"]
    assert cb["rappel_blocking"] is not None
    assert cb["n_vraies_perdues"] + cb["n_vraies_survivantes"] == n_vraies
    assert cb["rappel_blocking"] == pytest.approx(cb["n_vraies_survivantes"] / n_vraies)
    assert cb["pertes"]["n_perdues"] == cb["n_vraies_perdues"]
    if not cb["pertes"]["enumeration_tronquee"]:
        assert len(cb["pertes"]["paires_perdues"]) == cb["n_vraies_perdues"]
    assert 0.0 <= cb["taux_de_reduction"] <= 1.0
    assert 0.0 <= cb["pairs_quality"] <= 1.0
    zg = rapport["regimes"]["seuils_dimensionnes"]["zone_grise"]["composition"]
    assert zg["n_gris"] is not None and zg["n_vraies_gris"] is not None


def test_empreinte_des_mesures_est_stable_et_non_circulaire(pack):
    """L'empreinte ne se couvre pas elle-même, et ne bouge pas si seule la provenance change."""
    rapport = dict(_rapport_reel(pack))
    empreinte = rapport["empreinte_des_mesures"]
    assert rap.empreinte_des_mesures(rapport) == empreinte
    modifie = dict(rapport, provenance=dict(rapport["provenance"], commit_engine="0" * 40))
    assert rap.empreinte_des_mesures(modifie) == empreinte, (
        "l'empreinte des mesures depend de la provenance : elle ne mesurerait plus les mesures")


def test_determinisme_inter_processus():
    """Deux processus, deux `PYTHONHASHSEED` : la même empreinte de mesures.

    Un double appel dans le MÊME processus ne prouverait rien — c'est précisément le salage
    par processus de `hash()` que ce test cherche à détecter.

    Le rapport ENTIER est comparé, privé du seul bloc `provenance` (qui dépend de l'état de
    git). Se limiter à `empreinte_des_mesures` ne couvrirait que 5 des sous-arbres publiés et
    laisserait le verdict, les contrôles et les limites hors de tout contrôle de reproductibilité.
    """
    script = (
        "import sys, json, hashlib; sys.path.insert(0, %r); sys.path.insert(0, %r);\n"
        "import mesure_discrimination as o, scorer\n"
        "r = o.construis()\n"
        "r.pop('provenance', None)\n"
        "print(r['empreinte_des_mesures'])\n"
        "print(hashlib.sha256(scorer.serialisation_canonique(r).encode('utf-8')).hexdigest())\n"
        % (_SRC, os.path.join(_REPO_ROOT, "tools"))
    )
    sorties = []
    for graine in ("0", "98765"):
        env = dict(os.environ, PYTHONHASHSEED=graine)
        sorties.append(subprocess.check_output([sys.executable, "-c", script], env=env,
                                               text=True, cwd=_REPO_ROOT).strip().splitlines())
    assert sorties[0] == sorties[1], f"mesures non reproductibles inter-processus : {sorties}"
    assert len(sorties[0]) == 2
    garde_non_vacuite(empreinte=sorties[0][0], rapport_entier=sorties[0][1])


# ======================= 10. La fixture est CONSOMMÉE, jamais éditée =================
def test_la_fixture_n_est_jamais_ouverte_en_ecriture():
    """Aucun `open(..., "w")` ni aucune écriture vers la zone de test, par analyse AST."""
    cibles = dict(_modules_scorer())
    with open(_TOOL, encoding="utf-8") as fh:
        cibles["mesure_discrimination.py"] = (_TOOL, ast.parse(fh.read()))
    for nom, (chemin, arbre) in cibles.items():
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name) \
                    and noeud.func.id == "open":
                modes = [a.value for a in noeud.args[1:] if isinstance(a, ast.Constant)]
                modes += [k.value.value for k in noeud.keywords
                          if k.arg == "mode" and isinstance(k.value, ast.Constant)]
                for mode in modes:
                    if any(c in str(mode) for c in ("w", "a", "+")):
                        assert nom == "rapport.py", (
                            f"{nom} ouvre un fichier en ecriture hors de l'ecriture d'artefact")
    with open(_TOOL, encoding="utf-8") as fh:
        source_outil = fh.read()
    assert "fixtures/FIXTURE_PACK_GT_V1_2.json" in source_outil, "l'outil doit bien designer la fixture"
    assert 'ecris_artefact' in source_outil


def test_l_empreinte_de_la_fixture_est_verifiee_a_l_ouverture(pack):
    """Un écart d'empreinte doit lever : mesurer sur une autre donnée invaliderait tout."""
    assert verite.empreinte_pack(pack) == _CONTENT_SHA256_V1_2
    with pytest.raises(ValueError):
        verite.charge_pack(_chemin_fixture(), "0" * 64)


# ======================= 11. Méta-test de la garde d'anti-vacuité ====================
def test_le_fichier_artefact_publie_est_a_jour(pack):
    """DoD n°3 au sens LITTÉRAL : le contrôle porte sur le FICHIER, pas sur un objet en mémoire.

    Sans ce test, `artifacts/discrimination_v1_2.json` pourrait deriver du code sans qu'aucun
    oracle ne le voie — la forme et la fraicheur du fichier PUBLIE seraient invérifiées.
    L'empreinte des mesures exclut la provenance : le fichier reste donc valide apres un
    nouveau commit, ce qui est exactement la propriete voulue.
    """
    chemin = os.path.join(_REPO_ROOT, "artifacts", "discrimination_v1_2.json")
    assert os.path.exists(chemin), "l'artefact du mandat n'est pas publie"
    with open(chemin, encoding="utf-8") as fh:
        publie = json.load(fh)
    frais = _rapport_reel(pack)
    assert set(publie) == set(frais), "le fichier publie n'a pas la forme courante"
    assert publie["empreinte_des_mesures"] == frais["empreinte_des_mesures"], (
        "le fichier publie ne correspond plus au code : regenerer "
        "tools/mesure_discrimination.py")
    assert publie["verdict"]["sha256_criteres"] == criteres.sha256_criteres(), (
        "le fichier publie cite d'autres criteres que ceux du depot")
    garde_non_vacuite(empreinte_publiee=publie["empreinte_des_mesures"])


def test_meta_les_tests_consommant_la_fixture_appellent_la_garde():
    """Un oracle de méthode : l'oubli de la garde est lui-même détecté.

    Les tests qui construisent l'artefact réel passent par `_rapport_reel`, dont l'un des
    consommateurs au moins doit appeler la garde ; ceux qui lisent directement le pack aussi.
    """
    with open(os.path.abspath(__file__), encoding="utf-8") as fh:
        arbre = ast.parse(fh.read())
    appellent = set()
    consomment = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.FunctionDef) and noeud.name.startswith("test_"):
            source = ast.dump(noeud)
            if "garde_non_vacuite" in source:
                appellent.add(noeud.name)
            if "_rapport_reel" in source or "'pack'" in source:
                consomment.add(noeud.name)
    assert appellent, "aucun test n'appelle la garde d'anti-vacuite : l'oracle est mort"
    # INCLUSION, et non simple intersection : un seul test conforme suffisait a satisfaire
    # l'ancienne formulation, quel que soit l'etat des autres. Les exemptions sont NOMMEES,
    # de sorte qu'en ajouter une soit une decision visible dans le diff.
    exemptes = {
        "test_forme_de_l_artefact",            # oracle de SCHEMA : la vacuite ne l'affecte pas
        "test_codes_de_criteres_bijectifs",    # compare deux ensembles de codes, pas des donnees
        "test_aucune_recommandation_sur_la_donnee",   # oracle lexical sur le texte publie
        "test_empreinte_des_mesures_est_stable_et_non_circulaire",  # compare le rapport a lui-meme
        "test_l_empreinte_de_la_fixture_est_verifiee_a_l_ouverture",  # oracle d'integrite
    }
    manquants = consomment - appellent - exemptes
    assert not manquants, (
        f"tests consommant la fixture sans garde d'anti-vacuite ni exemption nommee : "
        f"{sorted(manquants)}")
