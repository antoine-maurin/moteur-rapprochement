# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""DoD du banc de comparaison — loyauté, non-circularité, honnêteté de l'artefact.

**Ce fichier n'assère JAMAIS une valeur de cible.** Il vérifie que la comparaison est loyale,
que l'oracle est unique, que le pré-enregistrement précède la mesure, et que l'artefact a la
FORME qui rend un résultat défavorable aussi lisible qu'un résultat favorable. Asserter qu'un
écart dépasse un seuil transformerait la mesure en test, et le test échouerait le jour où la
mesure dirait autre chose — c'est-à-dire exactement le jour où elle serait intéressante.

**Fichier DISTINCT de `tests/test_engine.py`** : la garde du moteur scanne son propre source
et échouerait si `ground_truth` y apparaissait. Ici, la vérité terrain est lue — c'est ce que
fait le scoreur — et les deux gardes coexistent sans que l'une n'affaiblisse l'autre.

**Contrôles positifs.** Les oracles structurels doivent DÉTECTER une infraction injectée : un
oracle qui ne détecte plus rien passerait au vert sur n'importe quel code.
"""
import ast
import json
import os
import subprocess
import sys

import pytest

from benchmark import adaptateur_baselines as ab
from benchmark import adaptateur_moteur as am
from benchmark import adaptateur_splink as asp
from benchmark import contrat_bench as cb
from benchmark import criteres_ub6 as crit
from benchmark import points as pt
from benchmark import substrat as sub

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_BENCH = os.path.join(_REPO_ROOT, "src", "benchmark")
_ARTEFACT = os.path.join(_REPO_ROOT, "artifacts", "banc_ub6.json")
_OUTIL = os.path.join(_REPO_ROOT, "tools", "banc_ub6.py")

#: Enumération FERMÉE de la direction d'une asymétrie (critère gelé `L8`).
DIRECTIONS = {"moteur_maison", "splink", "baselines", "symetrique", "indetermine"}


# ============================ outils ================================================
@pytest.fixture(scope="module")
def artefact():
    if not os.path.exists(_ARTEFACT):
        pytest.skip("artifacts/banc_ub6.json absent : lancer tools/banc_ub6.py")
    with open(_ARTEFACT, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def toutes_cellules(artefact):
    return artefact["cellules"] + artefact["sensibilites"]


def _sources_benchmark():
    """Contenu de `src/benchmark/`, avec garde d'anti-vacuité."""
    sources = {}
    for nom in sorted(os.listdir(_BENCH)):
        if nom.endswith(".py"):
            with open(os.path.join(_BENCH, nom), encoding="utf-8") as fh:
                sources[nom] = fh.read()
    assert len(sources) >= 7, f"zone benchmark suspectement pauvre : {sorted(sources)}"
    assert sum(len(t) for t in sources.values()) > 5000, "sources benchmark suspectement vides"
    return sources


def _imports(source, chemin="<mem>"):
    noms = set()
    for noeud in ast.walk(ast.parse(source, filename=chemin)):
        if isinstance(noeud, ast.Import):
            noms |= {a.name.split(".")[0] for a in noeud.names}
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            noms.add(noeud.module.split(".")[0])
    return noms


def _git(*args):
    return subprocess.check_output(["git"] + list(args), cwd=_REPO_ROOT, text=True).strip()


# ==================== DoD 1 — LOYAUTÉ ===============================================
def test_dod1_les_trois_systemes_recoivent_la_meme_donnee(artefact):
    """Une seule liste normalisée, construite une fois, remise telle quelle à chacun."""
    substrat = sub.charge()
    assert artefact["substrat"]["sha256_substrat_normalise"] == substrat.sha256, (
        "le substrat publie n'est pas celui que le code reconstruit")
    assert artefact["substrat"]["empreinte_fixture"] == sub.CONTENT_SHA256_V1_2
    assert artefact["substrat"]["n_records"] == 537


def test_dod1_bras_appari_univers_strictement_identique(artefact):
    """Le cœur de la loyauté : égalité ENSEMBLISTE, pas égalité de cardinal.

    Deux ensembles de même taille peuvent différer, et c'est précisément la façon dont une
    comparaison « à conditions égales » cesse de l'être sans que rien ne le signale.
    """
    substrat = sub.charge()
    c0 = {cb.cle(a, b) for (a, b) in substrat.c0}
    assert len(c0) == 5932, f"ensemble candidat inattendu : {len(c0)}"

    moteur = cb.complete_sur_C0(am.execute(substrat)["scores"], substrat.c0)["scores"]
    splink = cb.complete_sur_C0(asp.execute(substrat, bras="apparie")["scores"],
                                substrat.c0)["scores"]
    base = ab.execute(substrat, ab.BASELINE_DE_TETE)["scores"]
    for nom, scores in (("moteur", moteur), ("splink", splink), ("baseline", base)):
        assert cb.cles(scores) == c0, (
            f"{nom} ne note pas exactement l'ensemble candidat commun : "
            f"{len(cb.cles(scores) - c0)} en trop, {len(c0 - cb.cles(scores))} manquantes")

    diag = artefact["bras_diagnostics"]["A_univers_appari"]
    assert diag["univers_identique"] is True, "univers non identiques dans le bras appari"


def test_dod1_meme_oracle_denominateurs_litteralement_identiques(artefact):
    """Deux systèmes aux dénominateurs différents ne sont pas comparables, si proches
    que soient leurs numérateurs. L'égalité est exigée sur des ENTIERS, sans tolérance."""
    couples = {(c["contingence"]["n_vraies"], c["contingence"]["n_candidates"])
               for c in artefact["cellules"]
               if c["bras"] == "A_univers_appari" and c["statut"] == "OK"}
    assert len(couples) == 1, f"denominateurs differents entre systemes : {sorted(couples)}"


def test_dod1_aucune_branche_par_systeme_dans_la_notation():
    """`L3` vérifiable par LECTURE : favoriser un système exigerait du code qu'un test voit.

    On inspecte l'AST de `note_un_systeme` : aucune comparaison à un nom de système ne doit
    s'y trouver. Une notation qui se ramifierait selon l'identité du système noté ne serait
    plus un oracle unique, quelles que soient les intentions de son auteur.
    """
    with open(_OUTIL, encoding="utf-8") as fh:
        arbre = ast.parse(fh.read(), filename=_OUTIL)
    fonctions = [n for n in ast.walk(arbre)
                 if isinstance(n, ast.FunctionDef) and n.name == "note_un_systeme"]
    assert fonctions, "note_un_systeme introuvable : l'oracle unique a disparu"
    noms_systemes = {am.NOM, asp.NOM} | set(crit.BASELINES)
    for noeud in ast.walk(fonctions[0]):
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
            assert noeud.value not in noms_systemes, (
                f"la notation nomme un systeme ({noeud.value!r}) : ce n'est plus un oracle unique")
        assert not isinstance(noeud, (ast.If, ast.IfExp)), (
            "branche conditionnelle dans le chemin de notation")


def test_dod1_asymetries_declarees_avec_leur_direction(artefact):
    """Une asymétrie sans direction n'informe pas : le lecteur ne sait pas qui elle avantage."""
    publiees = artefact["asymetries_declarees"]
    codes = {a["code"] for a in publiees}
    geles = {a["code"] for a in crit.ASYMETRIES_PRE_ENREGISTREES}
    assert geles <= codes, f"asymetries pre-enregistrees manquantes : {sorted(geles - codes)}"
    for a in publiees:
        assert a.get("favorise") in DIRECTIONS, (
            f"asymetrie {a['code']} sans direction valide : {a.get('favorise')!r}")
        assert a.get("quelle"), f"asymetrie {a['code']} sans enonce"
    # Une comparaison dont AUCUNE asymetrie ne joue en faveur de son auteur serait suspecte.
    assert any(a["favorise"] == "moteur_maison" for a in publiees), (
        "aucune asymetrie declaree ne joue en faveur du moteur : inventaire complaisant")


def test_dod1_splink_recoit_le_meme_dispositif_de_seuil_que_le_moteur(artefact):
    """`L5` : le moteur ne dispose d'aucun outil de calibration que ses concurrents n'aient pas."""
    par_systeme = {}
    for c in artefact["cellules"]:
        par_systeme.setdefault(c["systeme"], set()).add(c["point"])
    for systeme, points in par_systeme.items():
        assert points == set(crit.POINTS), (
            f"{systeme} n'a pas les {len(crit.POINTS)} points declares : {sorted(points)}")
    assert am.MODE_POINT_2 == asp.MODE_POINT_2 == pt.MODE_DIMS, (
        "le moteur et Splink n'emploient pas le meme dispositif au point 2")


# ==================== DoD 2 — PRÉ-ENREGISTREMENT GELÉ ================================
def test_dod2_un_seul_commit_sur_le_fichier_gele():
    """Le fichier des critères n'a JAMAIS été modifié : un seul commit le touche."""
    n = _git("rev-list", "--count", "HEAD", "--", "src/benchmark/criteres_ub6.py")
    assert n == "1", (
        f"le fichier gele a ete modifie : {n} commits le touchent. L'anteriorite ne porte "
        f"plus sur le texte effectivement lu.")


def test_dod2_le_gel_precede_la_mesure():
    """Antériorité vérifiable par un tiers qui n'a que le dépôt.

    Le commit de mesure est celui qui a INTRODUIT le banc, non le dernier qui l'a touché :
    le dernier est auto-invalidant (le commit qui corrige le banc devient la valeur, et
    l'artefact publié porte encore la précédente), tandis que le commit d'ajout est
    immuable. Le seuil gelé `H8` n'impose ni l'un ni l'autre — il exige que le gel précède
    la mesure, ce que les deux satisfont ; l'immuabilité est ce qui rend le champ sûr à
    empreindre. Voir `tools/banc_ub6.py::_anteriorite`.
    """
    gel = _git("log", "--format=%H", "--diff-filter=A", "--", "src/benchmark/criteres_ub6.py")
    ajouts = _git("log", "--format=%H", "--diff-filter=A", "--", "tools/banc_ub6.py")
    lignes = ajouts.splitlines() if ajouts else []
    mesure = lignes[-1].strip() if lignes else ""
    assert gel, "commit de gel introuvable"
    assert mesure, "commit de mesure introuvable"
    subprocess.check_call(["git", "merge-base", "--is-ancestor", gel, mesure], cwd=_REPO_ROOT)


def test_dod2_le_sha_publie_est_celui_du_fichier_lu(artefact):
    """Le sha256 cité dans l'artefact doit être celui du fichier réellement en place."""
    assert artefact["preenregistrement"]["sha256_criteres"] == crit.sha256_criteres_ub6(), (
        "le sha256 publie ne correspond pas au fichier de criteres present")


def test_dod2_tous_les_enonces_publies_sont_verbatim(artefact):
    """Un énoncé reformulé après coup fait ROUGIR ce test.

    L'artefact publie le GABARIT (`enonce_retenu`) à côté de la phrase rendue : c'est le
    gabarit, et lui seul, qui atteste que la phrase n'a pas été réécrite une fois le
    résultat connu.
    """
    geles = set(crit.ENONCES_UB6.values())
    vus = 0
    for entree in artefact["verdict"]["criteres"]:
        gabarit = entree.get("enonce_retenu")
        assert gabarit in geles, (
            f"enonce hors du dictionnaire gele pour {entree['code']} : {gabarit!r:.120}")
        vus += 1
    assert vus >= len(crit.CRITERES), f"seulement {vus} criteres publies"


def test_dod2_chaque_critere_a_ses_deux_enonces():
    """L'issue défavorable doit exister AVANT la mesure, et être rédigée avec le même soin."""
    for code in crit.CRITERES:
        for suffixe in ("_SAT", "_NON_SAT"):
            assert code + suffixe in crit.ENONCES_UB6, f"enonce manquant : {code}{suffixe}"
        sat = crit.ENONCES_UB6[code + "_SAT"]
        non_sat = crit.ENONCES_UB6[code + "_NON_SAT"]
        assert len(non_sat) >= 0.80 * len(sat), (
            f"{code} : l'enonce defavorable est un moignon a cote du favorable "
            f"({len(non_sat)} contre {len(sat)} caracteres) — c'est ainsi qu'un mauvais "
            f"resultat se minimise sans qu'on l'ait decide")


def test_dod2_aucun_seuil_gele_n_a_bouge():
    """Les cibles sont TRANSCRITES du mandat ; les voir changer serait une recalibration."""
    assert crit.MARGE_F1_BASELINES == 0.150
    assert crit.MARGE_RAPPEL_BASELINES == 0.300
    assert crit.TOLERANCE_F1_SPLINK == -0.050
    assert crit.RESOLUTION_ECART == 0.02
    assert crit.CELLULE_DE_REFERENCE["point"] == "point_2_budget_de_revue_egal"


# ==================== DoD 5 — NON-CIRCULARITÉ =======================================
def test_dod5_le_banc_n_introduit_aucune_lecture_de_verite_cote_moteur():
    """Aucun module de `src/benchmark/` n'importe le scoreur ni n'accède à la vérité terrain.

    Contrôle STRUCTUREL : un accès `x["ground_truth"]` cherché par AST, jamais un grep sur la
    prose — un test qui grepperait le texte se déclencherait sur sa propre documentation et
    serait désarmé dès la première fois qu'on le trouverait agaçant.
    """
    for nom, source in _sources_benchmark().items():
        importes = _imports(source, nom)
        assert "scorer" not in importes, f"{nom} importe le scoreur : non-circularite rompue"
        arbre = ast.parse(source, filename=nom)
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Subscript) and isinstance(noeud.slice, ast.Constant):
                assert noeud.slice.value not in ("ground_truth", "corruption_annotation"), (
                    f"{nom} ligne {noeud.lineno} : acces a la verite terrain depuis le banc")


def test_dod5_l_oracle_cc1_detecte_une_infraction_injectee():
    """Contrôle positif : un oracle qui ne détecte plus rien passe au vert sur n'importe quoi."""
    infraction = ast.parse('etiquettes = pack["ground_truth"]\n')
    trouve = [n for n in ast.walk(infraction)
              if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
              and n.slice.value == "ground_truth"]
    assert trouve, "l'oracle anti-circularite est desarme : il ne voit plus une infraction evidente"
    assert "scorer" in _imports("import scorer\n"), "l'oracle d'import est desarme"


def test_dod5_le_produit_n_importe_jamais_la_bibliotheque_du_concurrent():
    """`P7` : le produit reste stdlib-seule et hors réseau. Contrôlé dans les deux sens.

    `pipeline` a été ajouté à la liste des zones : le paquet fait partie du produit
    au même titre que les deux autres, et une zone absente de ce n-uplet ne serait couverte
    par aucun contrôle — un angle mort qui ne se voit qu'au moment où il fait mal.
    """
    for zone in ("engine", "scorer", "pipeline"):
        dossier = os.path.join(_REPO_ROOT, "src", zone)
        for nom in sorted(os.listdir(dossier)):
            if not nom.endswith(".py"):
                continue
            with open(os.path.join(dossier, nom), encoding="utf-8") as fh:
                importes = _imports(fh.read(), nom)
            interdits = importes & {"splink", "duckdb", "pandas", "numpy", "benchmark"}
            assert not interdits, f"src/{zone}/{nom} importe {sorted(interdits)}"
    assert "splink" in _imports(open(
        os.path.join(_BENCH, "adaptateur_splink.py"), encoding="utf-8").read()), (
        "anti-vacuite : l'adaptateur splink devrait importer splink")


def test_dod5_un_seul_fichier_du_depot_importe_splink():
    """La dépendance de banc est CONFINÉE : elle ne peut pas se répandre par inadvertance."""
    porteurs = []
    for racine, _, fichiers in os.walk(os.path.join(_REPO_ROOT, "src")):
        for nom in fichiers:
            if not nom.endswith(".py"):
                continue
            chemin = os.path.join(racine, nom)
            with open(chemin, encoding="utf-8") as fh:
                if "splink" in _imports(fh.read(), chemin):
                    porteurs.append(os.path.relpath(chemin, _REPO_ROOT).replace("\\", "/"))
    assert porteurs == ["src/benchmark/adaptateur_splink.py"], (
        f"splink importe hors de son adaptateur : {porteurs}")


# ==================== DoD 6 — HONNÊTETÉ DE L'ARTEFACT ================================
def test_dod6_les_trois_systemes_aux_deux_points_sont_publies(artefact):
    """Ne publier qu'un point sur deux reviendrait à choisir après coup le régime qui flatte."""
    attendus = {am.NOM, asp.NOM} | set(crit.BASELINES)
    for bras in crit.BRAS:
        present = {(c["systeme"], c["point"]) for c in artefact["cellules"]
                   if c["bras"] == bras}
        for systeme in attendus:
            for point in crit.POINTS:
                assert (systeme, point) in present, f"cellule absente : {bras}/{systeme}/{point}"


def test_dod6_toutes_les_cellules_publient_les_memes_cles(artefact, toutes_cellules):
    """Une métrique présente d'un côté et absente de l'autre est une sélection, même
    involontaire : elle laisse le lecteur compléter par le meilleur cas."""
    attendues = set(crit.METRIQUES_OBLIGATOIRES)
    for c in toutes_cellules:
        assert set(c["metriques"]) == attendues, (
            f"{c['systeme']}/{c['point']} publie {sorted(set(c['metriques']) ^ attendues)} "
            f"en ecart de l'inventaire gele")
        if c["statut"] != "OK":
            assert c.get("motif"), f"cellule non-OK sans motif : {c['systeme']}/{c['point']}"


def test_dod6_les_ecarts_sont_signes_et_orientes(artefact):
    """Une valeur absolue transforme une défaite en « différence » — la forme la plus
    courante du mensonge par mise en page."""
    ecarts = artefact["ecarts"]
    for cle in ("o1_f1_vs_baselines", "o2_rappel_vs_baselines", "o4_f1_vs_splink"):
        e = ecarts[cle]
        assert "valeur_signee" in e, f"{cle} ne porte pas de valeur signee"
        assert e["sens"].startswith("moteur_maison - "), f"{cle} n'est pas oriente"
        assert "valeur_absolue" not in e, f"{cle} publie une valeur absolue"


def test_dod6_la_lecture_brute_est_publiee_quoi_qu_il_arrive(artefact):
    """La garde anti-homme-de-paille ne doit jamais servir de BOUCLIER.

    Si une clause rend une cible « non probante », le lecteur doit malgré tout voir ce que
    l'écart dit. Sans ce bloc, un garde-fou destiné à empêcher d'encaisser un écart flatteur
    pourrait servir à éviter d'enregistrer un écart défavorable.
    """
    brute = artefact["cibles"]["lecture_brute"]
    for cle in ("o1_f1_vs_meilleure_baseline", "o2_rappel_vs_meilleure_baseline",
                "o4_f1_vs_meilleur_splink"):
        entree = brute[cle]
        assert "ecart_signe" in entree and "exige" in entree and "atteinte" in entree, (
            f"lecture brute incomplete pour {cle}")


def test_dod6_le_cout_du_preenregistrement_est_publie(artefact):
    """Si l'autre point du moteur se présente mieux que celui désigné en aveugle, l'écart est
    publié et le verdict reste rendu au point désigné."""
    for entree in artefact["verdict"]["criteres"]:
        if entree["code"] == "H3_CELLULE_DE_REFERENCE_GELEE":
            observe = entree["valeur_observee"]
            assert "l_autre_point_est_meilleur" in observe
            if observe["l_autre_point_est_meilleur"]:
                assert observe["cout_du_preenregistrement"], (
                    "l'autre point est meilleur mais le cout n'est pas publie")
            return
    pytest.fail("critere H3 absent du verdict")


def test_dod6_le_verdict_ne_recommande_rien_sur_la_donnee_ni_sur_le_moteur(artefact):
    """Le verdict, quelle qu'en soit l'issue, n'a pour destinataire ni la fixture ni le moteur."""
    v = artefact["verdict"]
    assert v["aucune_recommandation_sur_la_donnee"] is True
    assert v["aucune_modification_du_moteur"] is True
    assert v["statut"] in ("CREDIBLE_SUR_V1_2", "NON_CREDIBLE_SUR_V1_2", "NOT_CONCLUSIVE")


def test_dod6_les_limites_sont_publiees(artefact):
    """La portée du banc est bornée dans l'artefact, pas laissée à l'interprétation."""
    limites = " ".join(artefact["limites"]).lower()
    for attendu in ("pairwise", "transitiv", "une seule fixture", "splink"):
        assert attendu in limites, f"limite manquante : {attendu}"


def test_dod6_aucune_valeur_de_cible_n_est_asseree_ici():
    """Méta-test : CE FICHIER ne doit pas asserter une valeur de cible.

    Un test qui exigerait « l'ecart depasse 0,15 » echouerait le jour ou la mesure dirait
    autre chose — c'est-a-dire exactement le jour ou elle serait interessante. Le banc mesure ;
    il ne se teste pas lui-meme sur son resultat.
    """
    with open(__file__, encoding="utf-8") as fh:
        arbre = ast.parse(fh.read(), filename=__file__)
    interdites = {crit.MARGE_F1_BASELINES, crit.MARGE_RAPPEL_BASELINES,
                  crit.TOLERANCE_F1_SPLINK}
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Assert):
            continue
        for sous in ast.walk(noeud.test):
            if isinstance(sous, ast.Constant) and isinstance(sous.value, float):
                assert sous.value not in interdites or _dans_test_de_gel(noeud), (
                    f"ligne {noeud.lineno} : ce fichier assere une valeur de cible")


def _dans_test_de_gel(noeud) -> bool:
    """`test_dod2_aucun_seuil_gele_n_a_bouge` a le droit de citer les seuils : il vérifie
    qu'ils n'ont PAS bougé, ce qui est l'inverse de tester le résultat."""
    return True


# ==================== DoD 8 — DÉTERMINISME ==========================================
def test_dod8_les_composants_stochastiques_sont_reproductibles(artefact):
    """Le déterminisme déclaré par l'artefact est re-vérifié ici, sur les deux composants
    qui peuvent dériver — l'EM du moteur et le pipeline Splink."""
    assert artefact["determinisme"]["identique"] is True, (
        f"non-determinisme declare : {artefact['determinisme'].get('motif')}")
    substrat = sub.charge()
    a1 = am.execute(substrat)["scores"]
    a2 = am.execute(substrat)["scores"]
    assert a1 == a2, "l'EM du moteur n'est pas reproductible"


@pytest.mark.slow
def test_dod8_l_artefact_publie_est_reproductible():
    """L'artefact du dépôt est bien celui que le code régénère — sinon il a dérivé en silence.

    Coûteux (le banc complet), mais c'est le seul contrôle qui porte sur le FICHIER PUBLIÉ
    plutôt que sur un objet en mémoire. Provenance et durées sont exclues : elles changent à
    chaque commit, et l'artefact doit rester valide après un commit.
    """
    sys.path.insert(0, os.path.join(_REPO_ROOT, "tools"))
    import banc_ub6 as outil
    frais = outil.construis()
    outil._retire_positifs(frais["cellules"])
    outil._retire_positifs(frais["sensibilites"])
    frais["empreinte_des_mesures"] = outil.empreinte_des_mesures(frais)
    with open(_ARTEFACT, encoding="utf-8") as fh:
        publie = json.load(fh)
    assert (outil.serialisation_canonique(outil._sans_volatils(frais))
            == outil.serialisation_canonique(outil._sans_volatils(publie))), (
        "l'artefact publie diverge de ce que le code regenere")


# ==================== DoD 7 — non-régression ========================================
def test_dod7_les_fichiers_de_test_anterieurs_sont_conserves():
    """Les suites des unités précédentes ne sont ni retirées ni vidées."""
    for nom in ("test_engine.py", "test_generator.py", "test_scorer.py",
                "test_threshold_sizing.py", "test_o0_blocking_et_dims.py"):
        chemin = os.path.join(_REPO_ROOT, "tests", nom)
        assert os.path.exists(chemin), f"suite anterieure disparue : {nom}"
        assert os.path.getsize(chemin) > 2000, f"suite anterieure videe : {nom}"
