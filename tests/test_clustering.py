# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Tests d'unité — clustering, clôture transitive et couverture (DoD 1/2/3/5/6/7/8).

Lancement depuis la racine du repo de build : `python -m pytest tests/ -q`.

**DATA-INDÉPENDANCE STRICTE — c'est la contrainte structurante de ce fichier.** Aucun test
ici ne lit la moindre fixture. Les entrées sont des ensembles de liens SYNTHÉTIQUES à
structure connue, écrits à la main : une chaîne, un cycle, une étoile, deux composantes
disjointes. Motif : les seuils du moteur vont bouger, donc l'ensemble des paires MATCH sur
un jeu réel va changer — un test qui figerait une partition observée casserait au premier
recalibrage sans qu'aucun défaut n'ait été introduit. L'algorithme, lui, ne change pas. Un
méta-test (§8) fait de cette contrainte un ORACLE plutôt qu'une intention.

**Non-circularité.** La clôture ne lit aucune étiquette de référence. Trois oracles indépendants le
prouvent : par signature (la fonction ne reçoit que verdicts et identifiants), par lecture
de l'arbre syntaxique (l'ensemble des clés lues est CLOS), et par comportement (enrichir les
entrées d'une colonne d'annotation ne déplace pas la partition d'un pouce).

**Contrôles positifs.** Chaque oracle structurel doit DÉTECTER une infraction injectée : un
oracle qui ne détecte plus rien passerait au vert sur n'importe quel code.
"""
import ast
import collections
import inspect
import itertools
import json
import os
import re
import subprocess
import sys

import pytest

from engine import clustering as clu

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_SRC = os.path.join(_REPO_ROOT, "src")
_ENGINE = os.path.join(_SRC, "engine")
_MODULES_U_B4 = ("clustering.py", "fusion.py")

MATCH = "MATCH"
NON_MATCH = "NON_MATCH"
ZONE_GRISE = "ZONE_GRISE"


# ============================ outils de test =========================================
def garde_non_vacuite(**quantites):
    """Refuse un test qui passerait sur une population vide.

    Sans elle, une fabrique cassée rendant zéro arête ferait passer au vert la moitié de
    cette suite : une partition en singletons satisfait la couverture, la disjonction et la
    canonicité — elle ne prouve simplement rien.
    """
    for nom, valeur in quantites.items():
        assert valeur, f"oracle vide : {nom} = {valeur!r} (le test ne prouverait rien)"


def _corr(a, b, verdict=MATCH, decision=None):
    """Fabrique une CORRESPONDENCE minimale mais conforme au protocole de `decide.py`."""
    return {"record_id_a": a, "record_id_b": b, "poids_match": 12.5, "verdict": verdict,
            "revue_zone_grise": ({"statut": "en_attente", "decision": decision,
                                  "unite_responsable": "revue_zone_grise"}
                                 if verdict == ZONE_GRISE else None),
            "bloc_origine": ["CP:75001"], "n_composantes_informatives": 8,
            "garde_r20_appliquee": False}


def _liens(*paires):
    """Raccourci : une liste de CORRESPONDENCE liantes depuis des couples littéraux."""
    return [_corr(a, b) for (a, b) in paires]


def _source_module(nom_fichier):
    with open(os.path.join(_ENGINE, nom_fichier), encoding="utf-8") as fh:
        return fh.read()


def _sources_u_b4():
    """Sources des deux modules de clustering et de fusion, avec garde anti-vacuité."""
    sources = {nom: _source_module(nom) for nom in _MODULES_U_B4}
    assert sum(len(t) for t in sources.values()) > 5000, "sources suspectement vides"
    return sources


def _definitions(source):
    """Noms des fonctions et classes DÉFINIES dans un module (AST)."""
    types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    return {n.name for n in ast.walk(ast.parse(source)) if isinstance(n, types)}


def _noms_importes(arbre):
    """Modules importés par un arbre AST, en remontant aux importations relatives."""
    noms = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            noms.update(alias.name.split(".")[0] for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.level:
                noms.add("." * noeud.level + (noeud.module or ""))
            elif noeud.module:
                noms.add(noeud.module.split(".")[0])
    return noms


# ------------------- oracle NAÏF et INDÉPENDANT (parcours en largeur) ----------------
def _composantes_par_parcours(univers, aretes):
    """Composantes connexes par un parcours en largeur délibérément inefficace.

    Écrit ici, et non dans le module produit : c'est un SECOND chemin de calcul, et c'est
    le seul oracle qui pince la SUR-fusion. Couverture totale, disjonction, non-vacuité et
    « toute arête est intra-groupe » sont TOUTES satisfaites par une implémentation qui
    rendrait l'univers entier en un seul groupe ; seule une référence indépendante voit la
    différence. `collections` est autorisé ici — la liste blanche C7 ne porte que sur
    `src/engine/`.
    """
    voisins = {rid: set() for rid in univers}
    for a, b in aretes:
        voisins[a].add(b)
        voisins[b].add(a)
    vus = set()
    groupes = []
    for depart in sorted(univers):
        if depart in vus:
            continue
        composante = []
        file = collections.deque([depart])
        vus.add(depart)
        while file:
            courant = file.popleft()
            composante.append(courant)
            for voisin in sorted(voisins[courant]):
                if voisin not in vus:
                    vus.add(voisin)
                    file.append(voisin)
        groupes.append(sorted(composante))
    return sorted(groupes)


def verifie_partition(partition, univers):
    """Propriétés MATHÉMATIQUES d'une partition, appliquées à tous les cas de ce fichier."""
    plats = [rid for groupe in partition for rid in groupe]
    assert sorted(plats) == sorted(univers), (
        f"couverture rompue : {sorted(plats)} != {sorted(univers)}")
    assert len(set(plats)) == len(plats), f"groupes non disjoints : {partition}"
    assert all(groupe for groupe in partition), f"groupe vide dans la partition : {partition}"
    for groupe in partition:
        assert groupe == sorted(groupe), f"membres non triés : {groupe}"
    assert partition == sorted(partition), f"groupes non ordonnés : {partition}"


# =================== 1. Clôture transitive — DoD-1 ===================================
def test_transitivite_a_b_et_b_c_donnent_un_seul_groupe():
    """Le cœur du mandat : A~B et B~C => {A,B,C}, sans que (A,C) ait jamais été produite."""
    partition = clu.cloture_transitive(_liens(("A", "B"), ("B", "C")), ["A", "B", "C"])
    assert partition == [["A", "B", "C"]]


def test_transitivite_sur_une_chaine_donnee_en_ordre_adverse():
    """Les arêtes arrivent dans le pire ordre possible : la chaîne doit quand même se fermer.

    Pince la fusion « en une passe » (fusionner chaque arête avec le groupe déjà construit) :
    elle est intégralement reproductible et pourtant FAUSSE — sur cet ordre elle rendrait
    plusieurs morceaux au lieu d'une chaîne. Un test en ordre naturel ne la verrait pas.
    """
    univers = ["A", "B", "C", "D", "E"]
    aretes = _liens(("D", "E"), ("A", "B"), ("C", "D"), ("B", "C"))
    assert clu.cloture_transitive(aretes, univers) == [["A", "B", "C", "D", "E"]]


def test_cycle_et_arete_redondante_ne_changent_rien():
    """Un cycle n'ajoute pas de membre, et une arête déjà connue ne casse pas la clôture."""
    univers = ["A", "B", "C"]
    cycle = _liens(("A", "B"), ("B", "C"), ("A", "C"))
    assert clu.cloture_transitive(cycle, univers) == [["A", "B", "C"]]
    redondant = _liens(("A", "B"), ("B", "A"), ("A", "B"), ("B", "C"))
    assert clu.cloture_transitive(redondant, univers) == [["A", "B", "C"]]


def test_deux_composantes_disjointes_restent_disjointes():
    """La clôture ne relie que ce qui est relié : deux groupes, pas un."""
    univers = ["A", "B", "C", "D"]
    partition = clu.cloture_transitive(_liens(("A", "B"), ("C", "D")), univers)
    assert partition == [["A", "B"], ["C", "D"]]
    verifie_partition(partition, univers)


def test_les_singletons_sont_conserves():
    """Un enregistrement sans aucun lien forme son propre groupe.

    C'est la propriété que perd toute implémentation qui déduit l'univers des seules
    arêtes : la sortie resterait une partition parfaitement bien formée, et l'erreur serait
    rigoureusement invisible.
    """
    univers = ["A", "B", "C", "D", "E"]
    partition = clu.cloture_transitive(_liens(("A", "B")), univers)
    assert partition == [["A", "B"], ["C"], ["D"], ["E"]]
    verifie_partition(partition, univers)


def test_aucun_lien_donne_autant_de_groupes_que_de_records():
    """Le piège est la clause de garde `if not aretes: return []`, qui perdrait tout."""
    univers = ["A", "B", "C"]
    partition = clu.cloture_transitive([], univers)
    assert partition == [["A"], ["B"], ["C"]]
    verifie_partition(partition, univers)


def test_univers_vide_donne_une_partition_vide_et_non_un_groupe_vide():
    """`[]` et non `[[]]` : un groupe vide n'est pas une entité, c'est une donnée fausse."""
    assert clu.cloture_transitive([], []) == []


def test_chaine_tres_longue_sans_debordement_de_pile():
    """2000 maillons : la compression de chemin doit être itérative, jamais récursive.

    Un jeu d'essai de quelques dizaines d'enregistrements ne verrait jamais ce défaut.
    """
    univers = [f"R{n:05d}" for n in range(2000)]
    aretes = _liens(*[(univers[i], univers[i + 1]) for i in range(len(univers) - 1)])
    partition = clu.cloture_transitive(aretes, univers)
    assert partition == [sorted(univers)]
    verifie_partition(partition, univers)


# =================== 2. Minimalité contre un oracle INDÉPENDANT ======================
_FORMES = {
    "chaine": (["A", "B", "C"], [("A", "B"), ("B", "C")]),
    "chaine_longue": (["A", "B", "C", "D", "E"],
                      [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")]),
    "cycle_c3": (["A", "B", "C"], [("A", "B"), ("B", "C"), ("A", "C")]),
    "cycle_c4": (["A", "B", "C", "D"],
                 [("A", "B"), ("B", "C"), ("C", "D"), ("A", "D")]),
    "etoile": (["H", "A", "B", "C", "D", "E"],
               [("H", "A"), ("H", "B"), ("H", "C"), ("H", "D"), ("H", "E")]),
    "graphe_complet_k4": (["A", "B", "C", "D"],
                          [("A", "B"), ("A", "C"), ("A", "D"),
                           ("B", "C"), ("B", "D"), ("C", "D")]),
    "pont_entre_deux_triangles": (["A", "B", "C", "D", "E", "F"],
                                  [("A", "B"), ("B", "C"), ("A", "C"), ("C", "D"),
                                   ("D", "E"), ("E", "F"), ("D", "F")]),
    "arbre": (["A", "B", "C", "D", "E"],
              [("A", "B"), ("A", "C"), ("B", "D"), ("B", "E")]),
    "biparti": (["A", "B", "X", "Y"], [("A", "X"), ("A", "Y"), ("B", "X"), ("B", "Y")]),
    "deux_composantes": (["A", "B", "C", "D"], [("A", "B"), ("C", "D")]),
    "isoles": (["A", "B", "C"], []),
}


def test_la_cloture_coincide_avec_un_parcours_en_largeur_independant():
    """Cas 2 : le SEUL oracle qui pince la sur-fusion, sur onze formes de graphe.

    Couverture, disjonction, non-vacuité et « toute arête est intra-groupe » sont toutes
    satisfaites par une implémentation qui rendrait l'univers entier en un groupe unique.
    Seule une référence calculée autrement voit la différence.
    """
    for nom, (univers, paires) in sorted(_FORMES.items()):
        obtenue = clu.cloture_transitive(_liens(*paires), univers)
        attendue = _composantes_par_parcours(univers, paires)
        assert obtenue == attendue, f"forme {nom} : {obtenue} != {attendue}"
        verifie_partition(obtenue, univers)
    # Contrôle POSITIF : l'oracle naïf DISTINGUE bien, sinon il validerait tout.
    univers, paires = _FORMES["deux_composantes"]
    assert len(_composantes_par_parcours(univers, paires)) == 2, (
        "l'oracle naïf ne separe plus deux composantes evidentes : oracle mort")
    garde_non_vacuite(formes=_FORMES)


# =================== 3. Ordre canonique et déterminisme — DoD-2 ======================
def test_ordre_canonique_membres_tries_et_groupes_ordonnes():
    """Membres triés ; groupes ordonnés par plus petit membre. Aucun ex aequo possible."""
    univers = ["Z", "M", "A", "K"]
    partition = clu.cloture_transitive(_liens(("Z", "M")), univers)
    assert partition == [["A"], ["K"], ["M", "Z"]]


def test_l_ordre_est_lexicographique_et_non_numerique():
    """`REC_10000` précède `REC_9999`. Contre-intuitif, donc figé : un futur « correctif »
    de tri naturel changerait toutes les sorties sans qu'aucun autre test ne rougisse."""
    univers = ["REC_9999", "REC_10000"]
    assert clu.cloture_transitive([], univers) == [["REC_10000"], ["REC_9999"]]


def test_l_ordre_des_groupes_ne_suit_pas_leur_taille():
    """Trier par taille ferait dépendre l'ordre d'une grandeur que tout recalibrage déplace."""
    univers = ["A", "M", "N", "O"]
    partition = clu.cloture_transitive(_liens(("M", "N"), ("N", "O")), univers)
    assert partition == [["A"], ["M", "N", "O"]], "l'ordre suit la taille et non les membres"


def test_invariance_par_permutation_des_entrees():
    """24 permutations d'arêtes x 2 ordres d'univers : la SÉRIALISATION doit être identique.

    La comparaison porte sur la sérialisation, pas sur une partition re-normalisée :
    comparer des ensembles rendrait le test aveugle à l'ORDRE, qui est la moitié de ce
    qu'on veut prouver.
    """
    univers = ["A", "B", "C", "D", "E"]
    paires = [("A", "B"), ("B", "C"), ("D", "E"), ("A", "C")]
    attendue = json.dumps(clu.cloture_transitive(_liens(*paires), univers), sort_keys=True)
    n_essais = 0
    for permutation in itertools.permutations(paires):
        for sens in (univers, list(reversed(univers))):
            obtenue = json.dumps(clu.cloture_transitive(_liens(*permutation), sens),
                                 sort_keys=True)
            assert obtenue == attendue, f"ordre {permutation} : {obtenue} != {attendue}"
            n_essais += 1
    assert n_essais == 48, f"oracle maigre : {n_essais} permutations"


def test_invariance_par_renommage_monotone():
    """Un renommage qui préserve l'ordre préserve la STRUCTURE ET l'ordre de sortie.

    Le pendant non monotone est testé juste après : il documente que l'ordre de sortie suit
    les identifiants, et non la forme du graphe. Les deux ensemble disent exactement ce que
    la canonicité garantit — et ce qu'elle ne garantit pas.
    """
    univers = ["A", "B", "C", "D"]
    paires = [("A", "B"), ("C", "D")]
    sigma = {"A": "A1", "B": "B1", "C": "C1", "D": "D1"}     # strictement croissant
    directe = clu.cloture_transitive(_liens(*paires), univers)
    renommee = clu.cloture_transitive(
        _liens(*[(sigma[a], sigma[b]) for a, b in paires]), [sigma[r] for r in univers])
    assert renommee == [[sigma[r] for r in groupe] for groupe in directe]


def test_un_renommage_non_monotone_transporte_la_partition_mais_pas_l_ordre():
    """L'ordre de sortie suit les identifiants : c'est une propriété, pas un défaut."""
    univers = ["A", "B", "C", "D"]
    paires = [("A", "B"), ("C", "D")]
    sigma = {"A": "Z", "B": "Y", "C": "B", "D": "A"}          # inverse l'ordre
    renommee = clu.cloture_transitive(
        _liens(*[(sigma[a], sigma[b]) for a, b in paires]), [sigma[r] for r in univers])
    assert renommee == [["A", "B"], ["Y", "Z"]]
    assert {frozenset(g) for g in renommee} == {frozenset(["A", "B"]), frozenset(["Y", "Z"])}


_SCRIPT_ENFANT = """\
import json, sys
sys.path.insert(0, {src!r})
from engine import clustering as clu
donnees = json.loads({donnees!r})
partition = clu.cloture_transitive(donnees["correspondances"], donnees["univers"])
couverture = clu.couverture_transitive(partition, donnees["correspondances"])
sortie = json.dumps({{"partition": partition, "couverture": couverture}},
                    sort_keys=True, ensure_ascii=False, separators=(", ", ": "))
sys.stdout.buffer.write(sortie.encode('utf-8'))
"""


def test_determinisme_inter_processus(tmp_path):
    """DoD-2 : deux PROCESSUS distincts, deux `PYTHONHASHSEED` DIFFÉRENTS, une seule sortie.

    Deux fois la même graine rendrait le test aveugle à sa propre cible. Et dans UN seul
    processus, l'ordre d'itération d'un `set` est stable : un test intra-processus est
    STRUCTURELLEMENT incapable de voir une non-détermination d'ensemble.
    """
    univers = ["REC_003", "REC_001", "REC_010", "REC_002", "REC_007"]
    correspondances = _liens(("REC_001", "REC_003"), ("REC_003", "REC_010"))
    donnees = json.dumps({"univers": univers, "correspondances": correspondances})
    script = tmp_path / "run_cloture.py"
    script.write_text(_SCRIPT_ENFANT.format(src=_SRC, donnees=donnees), encoding="utf-8")
    graines = ("0", "12345")
    sorties = []
    for graine in graines:
        env = dict(os.environ, PYTHONHASHSEED=graine, PYTHONIOENCODING="utf-8")
        proc = subprocess.run([sys.executable, str(script)], capture_output=True, env=env)
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
        sorties.append(proc.stdout)
    assert sorties[0], "sortie enfant vide : oracle vide"
    assert sorties[0] == sorties[1], (
        f"deux processus (PYTHONHASHSEED {graines[0]} puis {graines[1]}), deux sorties")
    partition = clu.cloture_transitive(correspondances, univers)
    attendu = json.dumps({"partition": partition,
                          "couverture": clu.couverture_transitive(partition, correspondances)},
                         sort_keys=True, ensure_ascii=False, separators=(", ", ": "))
    assert attendu.encode("utf-8") == sorties[0]


# =================== 4. Couverture par transitivité — DoD-6 ==========================
_COUVERTURES = {
    #  forme                      -> (internes, directes, recuperees)
    "chaine": (3, 2, 1),
    "cycle_c3": (3, 3, 0),
    "graphe_complet_k4": (6, 6, 0),
    "etoile": (15, 5, 10),
    "chaine_longue": (10, 4, 6),
    "deux_composantes": (2, 2, 0),
    "isoles": (0, 0, 0),
}


def test_les_comptes_de_couverture_sur_des_structures_connues():
    """DoD-6 : sept structures dont chaque chiffre pince un défaut d'implémentation nommé.

    Le TRIANGLE COMPLET (0 récupérée) est indispensable : il prouve que le compte n'est pas
    structurellement positif — un oracle limité à la chaîne passerait sur une implémentation
    qui rendrait toujours au moins 1. K4 pince l'erreur d'un cran (`n(n+1)/2` donnerait 10).
    DEUX COMPOSANTES pince le `C(N,2)` global, qui donnerait 6 et 4 au lieu de 2 et 0 — et
    le nombre faux serait ici le plus gros, donc le plus flatteur.
    """
    for nom, (internes, directes, recuperees) in sorted(_COUVERTURES.items()):
        univers, paires = _FORMES[nom]
        correspondances = _liens(*paires)
        partition = clu.cloture_transitive(correspondances, univers)
        obtenue = clu.couverture_transitive(partition, correspondances)
        assert obtenue["n_paires_internes"] == internes, f"{nom} : internes"
        assert obtenue["n_paires_directes"] == directes, f"{nom} : directes"
        assert obtenue["n_paires_recuperees"] == recuperees, f"{nom} : recuperees"
    garde_non_vacuite(structures=_COUVERTURES)
    assert any(v[2] > 0 for v in _COUVERTURES.values()), (
        "aucune structure ne recupere de paire : l'oracle serait vide")


def test_le_compte_coincide_avec_une_enumeration_independante():
    """Second chemin de calcul : le TEST énumère lui-même les paires intra-groupe.

    Le module publie un COMPTE ; le croisement compte/énumération appartient au test.
    """
    n_verifs = 0
    for nom, (univers, paires) in sorted(_FORMES.items()):
        correspondances = _liens(*paires)
        partition = clu.cloture_transitive(correspondances, univers)
        couverture = clu.couverture_transitive(partition, correspondances)
        directes = {tuple(sorted(p)) for p in paires}
        induites = set()
        for groupe in partition:
            induites |= {tuple(sorted(p)) for p in itertools.combinations(groupe, 2)}
        assert couverture["n_paires_internes"] == len(induites), f"{nom} : internes"
        assert couverture["n_paires_directes"] == len(directes), f"{nom} : directes"
        assert couverture["n_paires_recuperees"] == len(induites - directes), f"{nom}"
        n_verifs += 1
    assert n_verifs == len(_FORMES)


def test_les_proprietes_arithmetiques_de_la_couverture():
    """Trois invariants, sur toutes les formes, plus la somme des entités."""
    for nom, (univers, paires) in sorted(_FORMES.items()):
        correspondances = _liens(*paires)
        partition = clu.cloture_transitive(correspondances, univers)
        couverture = clu.couverture_transitive(partition, correspondances)
        assert 0 <= couverture["n_paires_directes"] <= couverture["n_paires_internes"], nom
        assert (couverture["n_paires_internes"]
                == couverture["n_paires_directes"] + couverture["n_paires_recuperees"]), nom
        assert couverture["n_paires_recuperees"] >= 0, nom
        assert len(couverture["par_entite"]) == len(partition), nom
        for cle in ("n_paires_internes", "n_paires_directes", "n_paires_recuperees"):
            assert couverture[cle] == sum(e[cle] for e in couverture["par_entite"]), (nom, cle)
            # Le TOTAL aussi, et pas seulement le detail : c'est au niveau global qu'un
            # taux viendrait s'installer, et `5.0 == 5` laisserait passer un flottant.
            assert isinstance(couverture[cle], int), (
                f"{nom} : le TOTAL {cle} n'est pas un entier — premier symptome d'un taux")
            assert all(isinstance(e[cle], int) for e in couverture["par_entite"]), (
                f"{nom} : {cle} n'est pas un entier — premier symptome d'un taux")


def test_la_reinjection_des_paires_induites_annule_la_recuperation():
    """Vérifie la DÉFINITION des compteurs, pas seulement leur arithmétique.

    Un compteur défini comme « paires ajoutées depuis la dernière fois » donnerait le même
    résultat au premier passage et divergerait au second. En réinjectant les C(n,2) paires
    du groupe comme liens directs, la partition ne bouge pas et la récupération tombe à 0.
    """
    univers, paires = _FORMES["etoile"]
    partition = clu.cloture_transitive(_liens(*paires), univers)
    induites = [p for groupe in partition for p in itertools.combinations(groupe, 2)]
    reinjecte = _liens(*induites)
    assert clu.cloture_transitive(reinjecte, univers) == partition
    couverture = clu.couverture_transitive(partition, reinjecte)
    assert couverture["n_paires_directes"] == couverture["n_paires_internes"]
    assert couverture["n_paires_recuperees"] == 0


def test_le_par_entite_decrit_chaque_groupe():
    """`par_entite` suit l'ordre de la partition et reste auto-descriptif."""
    univers = ["A", "B", "C", "D", "E"]
    correspondances = _liens(("A", "B"), ("B", "C"), ("D", "E"))
    partition = clu.cloture_transitive(correspondances, univers)
    couverture = clu.couverture_transitive(partition, correspondances)
    assert [e["membres"] for e in couverture["par_entite"]] == partition
    assert couverture["par_entite"][0] == {"membres": ["A", "B", "C"], "n_paires_internes": 3,
                                           "n_paires_directes": 2, "n_paires_recuperees": 1}


def test_la_couverture_refuse_une_partition_incoherente_DANS_LES_DEUX_SENS():
    """Les deux gardes sont SYMÉTRIQUES, et il faut bien les deux.

    Sens 1 — une arête TRAVERSE deux groupes : partition plus fine que les correspondances.
    Sens 2 — un groupe n'est pas CONNEXE pour les arêtes reçues : partition plus grossière.
    Le sens 2 est le dangereux, et c'est celui qu'une garde unique laisse passer : il gonfle
    `n_paires_recuperees` jusqu'au maximum, puisque `C(n,2)` explose pendant que le compte
    direct stagne. Le nombre faux serait, là encore, le plus flatteur — donc le plus cru.
    """
    with pytest.raises(ValueError, match="deux groupes distincts"):        # sens 1
        clu.couverture_transitive([["A"], ["B"]], _liens(("A", "B")))
    with pytest.raises(ValueError, match="n'est pas connexe"):             # sens 2
        clu.couverture_transitive([["A", "B", "C", "D"]], _liens(("A", "B")))
    with pytest.raises(ValueError, match="n'est pas connexe"):             # cas extrême
        clu.couverture_transitive([["A", "B", "C"]], [])
    with pytest.raises(ValueError):
        clu.couverture_transitive([["A"], ["A"]], [])
    with pytest.raises(ValueError):
        clu.couverture_transitive([["A"]], _liens(("A", "Z")))


def test_des_correspondances_deja_consommees_ne_passent_pas_pour_une_absence_de_lien():
    """Le cas réaliste du sens 2 : un ITÉRATEUR épuisé par la clôture.

    Sans la garde de connexité, le second appel verrait zéro arête sur un groupe de trois et
    annoncerait 3 paires récupérées au lieu d'une — un chiffre spectaculaire produit par un
    bug d'appel, et rigoureusement muet.
    """
    correspondances = iter(_liens(("A", "B"), ("B", "C")))
    partition = clu.cloture_transitive(correspondances, ["A", "B", "C"])
    assert partition == [["A", "B", "C"]]
    with pytest.raises(ValueError, match="n'est pas connexe"):
        clu.couverture_transitive(partition, correspondances)


def test_le_compte_ne_porte_aucune_cle_evaluative():
    """DoD-6 : ce sont des CARDINAUX, pas une mesure de qualité (celle-ci est dans le scoreur)."""
    univers, paires = _FORMES["chaine"]
    correspondances = _liens(*paires)
    couverture = clu.couverture_transitive(
        clu.cloture_transitive(correspondances, univers), correspondances)
    interdits = ("taux", "ratio", "gain", "score", "qualite", "f1", "justesse", "exactitude")
    cles = set(couverture) | {c for e in couverture["par_entite"] for c in e}
    fautives = sorted(c for c in cles for mot in interdits if mot in c.lower())
    assert not fautives, f"cle evaluative dans la couverture : {fautives}"
    # Contrôle POSITIF : l'oracle doit mordre sur une clé fautive injectée.
    assert [c for c in ["taux_de_recuperation"] for mot in interdits if mot in c.lower()], (
        "l'oracle de cle evaluative ne detecte plus une infraction evidente : oracle mort")


def test_aucune_division_dans_le_module_de_cloture():
    """Structurel : pas de taux possible, et pas de division par zéro sur un jeu vide.

    Rend l'absence de mesure STRUCTURELLE et non déclarative. `//` est un `FloorDiv` et
    resterait permis ; le module n'en a pas besoin, `math.comb` faisant le travail.
    """
    arbre = ast.parse(_source_module("clustering.py"))
    divisions = [n for n in ast.walk(arbre) if isinstance(n, ast.Div)]
    assert not divisions, f"division dans clustering.py : {len(divisions)} occurrence(s)"
    assert [n for n in ast.walk(ast.parse("t = a / b\n")) if isinstance(n, ast.Div)], (
        "l'oracle de division ne detecte plus une division evidente : oracle mort")


# =================== 5. La partition dérive des VERDICTS — DoD-7 =====================
def test_est_liante_sur_cinq_correspondances_ecrites_a_la_main():
    """La frontière exacte du lien, cas par cas. C'est ici que vit la catastrophe muette.

    Le dict de revue est TRUTHY : une garde écrite `or correspondance["revue_zone_grise"]`
    ferait entrer TOUTE la zone grise et produirait un groupe géant d'allure normale.
    """
    assert clu.est_liante(_corr("A", "B", MATCH)) is True
    assert clu.est_liante(_corr("A", "B", NON_MATCH)) is False
    assert clu.est_liante(_corr("A", "B", ZONE_GRISE)) is False
    assert clu.est_liante(_corr("A", "B", ZONE_GRISE, decision=MATCH)) is True
    assert clu.est_liante(_corr("A", "B", ZONE_GRISE, decision=NON_MATCH)) is False


def test_est_liante_sur_les_jetons_que_la_revue_emet_reellement():
    """Les cinq cas ci-dessus n'éprouvaient QUE des jetons que la revue n'émet jamais.

    `est_liante` comparait `decision` à `MATCH`, le jeton du moteur. L'énumération fermée de
    la revue (`llm_client.DECISIONS`) ne contient pas `MATCH` : elle rend `MATCH_APRES_REVUE`,
    `NON_MATCH_APRES_REVUE` ou `NON_TRANCHE`. La branche « revue » était donc structurellement
    INATTEIGNABLE, et le test ci-dessus la déclarait couverte en lui soumettant une valeur
    hors énumération. Une paire promue par la revue ne produisait aucune arête, en silence.

    R-20 est éprouvé ici même : `NON_TRANCHE` reste gris — le doute non tranché ne devient
    JAMAIS un lien.
    """
    assert clu.est_liante(_corr("A", "B", ZONE_GRISE, decision="MATCH_APRES_REVUE")) is True
    assert clu.est_liante(
        _corr("A", "B", ZONE_GRISE, decision="NON_MATCH_APRES_REVUE")) is False
    assert clu.est_liante(_corr("A", "B", ZONE_GRISE, decision="NON_TRANCHE")) is False
    # Le piège de sous-chaîne, épinglé : le jeton de REJET contient le jeton de PROMOTION.
    assert "MATCH_APRES_REVUE" in "NON_MATCH_APRES_REVUE", (
        "l'hypothèse du piège a changé : relire la garde d'égalité de est_liante")


def test_le_jeton_de_promotion_ne_derive_pas_de_u_b3():
    """`clustering` RE-DÉCLARE le jeton plutôt que d'importer `llm_client` (liste blanche).

    Le prix d'une re-déclaration est la dérive silencieuse. Cet oracle la rend impossible :
    si la revue renomme son jeton de promotion, il échoue ici plutôt que de laisser la clôture
    ignorer sans bruit toutes les paires promues.
    """
    from engine import llm_client as clt
    assert clu.MATCH_APRES_REVUE == clt.MATCH_APRES_REVUE, (
        "le jeton re-déclaré par clustering a dérivé de celui de la revue")
    assert clu.JETONS_LIANTS == (MATCH, clt.MATCH_APRES_REVUE)
    # Les jetons NON liants de l'énumération fermée le restent, tous.
    assert set(clt.DECISIONS) - set(clu.JETONS_LIANTS) == {
        clt.NON_MATCH_APRES_REVUE, clt.NON_TRANCHE}


def test_le_canari_de_la_zone_grise_en_attente():
    """DoD-7 : 1 lien + 5 zones grises en attente => 5 groupes, JAMAIS 1 groupe de 6.

    Le test le plus important du fichier : il pince en une assertion la confusion entre
    « il y a un dict de revue » et « la revue a conclu au lien ».
    """
    univers = ["A", "B", "C", "D", "E", "F"]
    correspondances = [_corr("A", "B", MATCH)] + [
        _corr(a, b, ZONE_GRISE) for a, b in
        [("B", "C"), ("C", "D"), ("D", "E"), ("E", "F"), ("A", "F")]]
    partition = clu.cloture_transitive(correspondances, univers)
    assert partition == [["A", "B"], ["C"], ["D"], ["E"], ["F"]]
    assert len(partition) == 5, "la zone grise en attente a ete traitee comme un lien"


def test_une_revue_concluante_reouvre_la_transitivite():
    """La branche `MATCH ∪ MATCH_APRÈS_REVUE` du mandat, morte aujourd'hui, éprouvée ici."""
    univers = ["A", "B", "C"]
    correspondances = [_corr("A", "B", MATCH), _corr("B", "C", ZONE_GRISE, decision=MATCH)]
    assert clu.cloture_transitive(correspondances, univers) == [["A", "B", "C"]]


def test_la_transitivite_l_emporte_sur_un_non_match_interne():
    """A~B, B~C, et (A,C) jugée NON_MATCH : un seul groupe, sans signalement.

    Décision assumée et documentée : implémenter « ne pas fusionner » serait une contrainte
    d'exclusion, ce qui n'est PAS une clôture transitive — le résultat dépendrait alors de
    l'ordre des arêtes — et supprimerait le phénomène même que la couverture doit compter.
    """
    univers = ["A", "B", "C"]
    correspondances = _liens(("A", "B"), ("B", "C")) + [_corr("A", "C", NON_MATCH)]
    assert clu.cloture_transitive(correspondances, univers) == [["A", "B", "C"]]


def test_cc1_comportemental_une_colonne_d_annotation_ne_deplace_rien():
    """DoD-7 : enrichir les entrées d'une étiquette de référence ne change RIEN.

    Les TESTS ont le droit de nommer ces jetons — c'est ce qu'ils injectent. Le module, lui,
    ne doit ni les lire ni les laisser transparaître : la partition doit être identique au
    caractère près.
    """
    univers = ["A", "B", "C"]
    correspondances = _liens(("A", "B"), ("B", "C"))
    nue = clu.cloture_transitive(correspondances, univers)
    enrichies = []
    for correspondance in correspondances:
        copie = dict(correspondance)
        copie["id_entite_vraie"] = "E1"
        copie["ground_truth"] = True
        copie["zone_intention_design"] = "piege"
        enrichies.append(copie)
    assert clu.cloture_transitive(enrichies, univers) == nue
    couverture = clu.couverture_transitive(nue, enrichies)
    serialisee = json.dumps(couverture, sort_keys=True, ensure_ascii=False)
    for jeton in ("id_entite_vraie", "ground_truth", "zone_intention_design", "piege"):
        assert jeton not in serialisee, f"{jeton} a transpire dans la sortie"


def test_cc1_fermeture_par_signature():
    """La clôture ne reçoit que des verdicts et des identifiants : deux paramètres, pas trois."""
    parametres = list(inspect.signature(clu.cloture_transitive).parameters)
    assert parametres == ["correspondances", "univers"], (
        f"signature elargie : {parametres} — une etiquette pourrait desormais entrer")
    assert list(inspect.signature(clu.couverture_transitive).parameters) == [
        "partition", "correspondances"]


def test_cc1_les_cles_lues_par_la_cloture_forment_un_ensemble_clos():
    """DoD-7 par AST : le module ne lit QUE ces six clés, et cet inventaire est CLOS.

    Toute clé supplémentaire — donc toute étiquette de référence — fait échouer ce test sans
    qu'il faille l'avoir prévue par son nom.
    """
    autorisees = {"record_id_a", "record_id_b", "verdict", "revue_zone_grise",
                  "decision", "record_id"}
    arbre = ast.parse(_source_module("clustering.py"))
    lues = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Subscript) and isinstance(noeud.slice, ast.Constant) \
                and isinstance(noeud.slice.value, str):
            lues.add(noeud.slice.value)
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute) \
                and noeud.func.attr == "get" and noeud.args \
                and isinstance(noeud.args[0], ast.Constant) \
                and isinstance(noeud.args[0].value, str):
            lues.add(noeud.args[0].value)
    assert lues <= autorisees, f"cles lues hors inventaire clos : {sorted(lues - autorisees)}"
    garde_non_vacuite(cles_lues=lues)
    # Contrôle POSITIF : l'oracle doit voir une lecture d'étiquette injectée.
    fautif = ast.parse('v = pack["id_entite_vraie"]\nw = rec.get("ground_truth")\n')
    detectees = set()
    for noeud in ast.walk(fautif):
        if isinstance(noeud, ast.Subscript) and isinstance(noeud.slice, ast.Constant):
            detectees.add(noeud.slice.value)
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute) \
                and noeud.func.attr == "get":
            detectees.add(noeud.args[0].value)
    assert detectees == {"id_entite_vraie", "ground_truth"}, (
        f"l'oracle de cles lues ne detecte plus une infraction flagrante : {detectees}")


# =================== 6. Doctrine d'erreur — refus explicites =========================
def test_les_identifiants_non_conformes_sont_refuses():
    """`{1: x, True: y, 1.0: z}` s'effondre en UNE clé : trois sommets deviendraient un.

    L'erreur surviendrait AVANT la clôture, sans exception ni trace. La chaîne vide est
    refusée pour la raison symétrique : falsy, elle disparaîtrait de toute garde `if rid:`.

    Les univers sont HOMOGÈNES et les assertions portent sur le MESSAGE. Un univers mixte
    comme `["A", 1]` ferait lever le `sorted()` en aval avec un `TypeError` lui aussi : le
    test passerait sans que la garde existe. C'est la différence entre « la garde a levé »
    et « une opération en aval a échoué ».
    """
    for univers in ([1, 2], [True, False], [b"A", b"B"], [1.0, 2.0], [None, None]):
        with pytest.raises(TypeError, match="record_id doit etre une chaine"):
            clu.cloture_transitive([], univers)
    with pytest.raises(ValueError, match="record_id vide"):
        clu.cloture_transitive([], ["A", ""])
    with pytest.raises(ValueError, match="duplique"):
        clu.cloture_transitive([], ["A", "A"])
    # La même frontière vaut pour la consolidation, qui a sa propre copie de la garde.
    with pytest.raises(TypeError, match="record_id doit etre une chaine"):
        clu.univers_depuis_records([{"record_id": 1}])


def test_une_chaine_passee_pour_une_collection_est_refusee():
    """Miroir exact du défaut précédent : un identifiant y devient PLUSIEURS sommets.

    Une `str` est itérable de `str` : chaque caractère passerait la garde d'identifiant et
    deviendrait un sommet, sans erreur ni trace, et la sortie resterait une partition
    parfaitement bien formée — donc l'erreur serait invisible. Le déclencheur réaliste est
    l'appel à un seul enregistrement, écrit `(corrs, rid)` au lieu de `(corrs, [rid])`.
    """
    for univers in ("R1", "ABC", b"ABC"):
        with pytest.raises(TypeError):
            clu.cloture_transitive([], univers)
    with pytest.raises(TypeError):
        clu.couverture_transitive(["AB"], [])


def test_la_couverture_refuse_un_groupe_non_ordonne_ou_non_canonique():
    """Même garde que la consolidation : la même partition ne peut pas être refusée par
    l'une et propagée en silence par l'autre.

    Un groupe passé en `set` rendrait `membres` dépendant de la graine de hachage — la
    sortie divergerait d'un processus à l'autre pour une entrée identique, sans qu'aucun
    compte ne bouge, donc sans que rien ne lève.
    """
    liens = _liens(("A", "B"))
    with pytest.raises(TypeError):
        clu.couverture_transitive([{"B", "A"}], liens)
    with pytest.raises(TypeError):
        clu.couverture_transitive([frozenset(["A", "B"])], liens)
    with pytest.raises(ValueError, match="non canonique"):
        clu.couverture_transitive([["B", "A"]], liens)
    assert clu.couverture_transitive([["A", "B"]], liens)["par_entite"][0]["membres"] == ["A", "B"]


def test_une_arete_reflexive_est_refusee():
    """`blocking.py` la rend structurellement impossible : sa présence signale une régression.

    L'absorber la masquerait, et son dégât serait entièrement dans le compte, où elle
    rendrait le nombre de paires récupérées négatif sur un singleton.
    """
    with pytest.raises(ValueError):
        clu.cloture_transitive(_liens(("A", "A")), ["A"])
    with pytest.raises(ValueError):
        clu.cle_paire("A", "A")


def test_une_arete_liante_hors_univers_est_refusee():
    """Les deux replis sont pires : ignorer tronque en silence, adopter invente un fantôme."""
    with pytest.raises(ValueError):
        clu.cloture_transitive(_liens(("A", "Z")), ["A", "B"])


def test_les_correspondances_non_liantes_hors_univers_sont_ignorees():
    """On ne valide que ce qu'on consomme : un NON_MATCH citant un inconnu ne gêne personne."""
    partition = clu.cloture_transitive(
        [_corr("A", "Z", NON_MATCH), _corr("Y", "Z", ZONE_GRISE)], ["A", "B"])
    assert partition == [["A"], ["B"]]


def test_cle_paire_canonise_les_deux_sens():
    """La clôture ne présume pas l'invariant `a < b` du producteur : elle le rétablit."""
    assert clu.cle_paire("B", "A") == ("A", "B") == clu.cle_paire("A", "B")
    assert clu.aretes_liantes(_liens(("B", "A"), ("A", "B"))) == [("A", "B")]


def test_aretes_liantes_rend_une_liste_canonique_triee_et_dedupliquee():
    """`aretes_liantes` est PUBLIQUE : son contrat de tri doit être tenu par une assertion.

    Il n'était garanti que par le fait que ses deux appelants re-trient derrière. Une
    fonction exportée est consommée telle quelle : le contrat doit valoir pour l'appelant
    qui n'a pas lu l'implémentation.
    """
    desordre = _liens(("M", "Z"), ("A", "B"), ("B", "A"), ("K", "C"), ("M", "Z"))
    obtenues = clu.aretes_liantes(desordre)
    assert obtenues == [("A", "B"), ("C", "K"), ("M", "Z")]
    assert obtenues == sorted(obtenues), "contrat de tri rompu"
    assert len(obtenues) == len(set(obtenues)), "contrat de deduplication rompu"
    assert clu.aretes_liantes([]) == []
    assert clu.aretes_liantes([_corr("A", "B", NON_MATCH)]) == []
    garde_non_vacuite(aretes=obtenues)


def test_univers_depuis_records_ne_projette_que_l_identifiant():
    """Commodité DÉFENSIVE : aucune valeur d'attribut ne peut atteindre la clôture."""
    records = [{"record_id": "B", "nom": "Durand", "id_entite_vraie": "E1"},
               {"record_id": "A", "nom": "Dupont"}]
    assert clu.univers_depuis_records(records) == ["A", "B"]
    with pytest.raises(ValueError):
        clu.univers_depuis_records([{"nom": "sans identifiant"}])
    with pytest.raises(ValueError):
        clu.univers_depuis_records([{"record_id": "A"}, {"record_id": "A"}])


def test_aucun_assert_ne_porte_d_invariant_dans_les_modules_produits():
    """`python -O` supprime les `assert` : un invariant qui s'évapore sous une option
    d'exécution est exactement le mode de défaillance que cette unité combat."""
    for nom, source in _sources_u_b4().items():
        fautifs = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Assert)]
        assert not fautifs, f"{nom} : {len(fautifs)} assert(s) — invariants effaçables par -O"
    assert [n for n in ast.walk(ast.parse("assert x\n")) if isinstance(n, ast.Assert)], (
        "l'oracle anti-assert ne detecte plus un assert evident : oracle mort")


# =================== 7. Non-circularité / C7 structurels sur les deux modules ========
def test_cc1_grep_aucune_etiquette_de_reference_dans_les_modules_u_b4():
    """DoD-5 : les jetons de référence sont absents des deux modules, retours à la ligne
    et continuations aplatis — un identifiant coupé en deux ne passe pas au travers."""
    interdits = ("id_entite_vraie", "ground_truth", "zone_intention_design")
    for nom, source in _sources_u_b4().items():
        aplati = source.replace("\\\n", "").replace("\n", " ")
        for jeton in interdits:
            assert jeton not in aplati, f"{nom} : acces a une etiquette de reference ({jeton})"
    coupe = 'v = pack["id_entite_\\\n' + 'vraie"]'
    assert "id_entite_vraie" in coupe.replace("\\\n", "").replace("\n", " "), (
        "l'aplatissement ne rattrape plus un identifiant coupe : oracle mort")


def test_cc1_les_modules_u_b4_n_importent_pas_la_zone_de_mesure():
    """La frontière moteur / mesure vaut aussi pour les modules neufs."""
    for nom, source in _sources_u_b4().items():
        interdits = {n for n in _noms_importes(ast.parse(source)) if "scorer" in n}
        assert not interdits, f"{nom} : couplage a la zone de mesure -> {sorted(interdits)}"
    infraction = ast.parse("import scorer.metriques\n")
    assert {n for n in _noms_importes(infraction) if "scorer" in n}, (
        "l'oracle de couplage ne detecte plus une infraction evidente : oracle mort")


def test_c7_les_modules_u_b4_n_importent_que_la_bibliotheque_standard():
    """Liste BLANCHE : chaque ajout de dépendance doit être une décision, pas un oubli.

    Les importations relatives sont nommées une par une plutôt que repliées sur un « . » :
    la liste dit alors exactement de quels modules du cœur l'unité dépend — `decide` pour la
    seule constante de verdict, `normalize` pour la clé de vote — et toute autre attache
    interne, `blocking` ou `compare` en particulier, fait échouer ce test.
    """
    autorises = {".decide", ".normalize", "__future__", "math"}
    for nom, source in _sources_u_b4().items():
        importes = _noms_importes(ast.parse(source))
        assert importes <= autorises, (
            f"{nom} : import hors liste blanche -> {sorted(importes - autorises)}")
    assert "math" in _noms_importes(ast.parse(_source_module("clustering.py")))
    assert ".normalize" in _noms_importes(ast.parse(_source_module("fusion.py")))


def test_perimetre_u_b4_ne_reconstruit_pas_le_coeur_decisionnel():
    """La frontière est BILATÉRALE : l'unité consomme les verdicts du cœur, elle ne les refait pas.

    Symétrique du périmètre que `tests/test_engine.py` fait porter sur la zone moteur : ici,
    on interdit à l'unité de redéfinir la normalisation, le blocking, la comparaison ou la
    décision — un second chemin de décision rendrait le moteur ininterprétable.
    """
    coeur = re.compile(r"^(estime_|oriente_classes$|table_de_poids$|agregat$|verdict_"
                       r"|correspondance[s]?$|normalise_|soundex$|cles_de_blocking$"
                       r"|vecteur_|similarite|genere_paires)", re.IGNORECASE)
    revue = re.compile(r"_llm\b|llm_", re.IGNORECASE)
    for nom, source in _sources_u_b4().items():
        definitions = _definitions(source)
        garde_non_vacuite(**{f"definitions_{nom}": definitions})
        fautifs = sorted(n for n in definitions if coeur.search(n) or revue.search(n))
        assert not fautifs, f"{nom} : reconstruction hors perimetre -> {fautifs}"
    interdits = {n for n in _noms_importes(ast.parse(_source_module("clustering.py")))}
    assert "blocking" not in interdits and "compare" not in interdits
    assert coeur.search("verdict_3_zones") and revue.search("revue_llm_zone_grise"), (
        "les motifs de perimetre ne mordent plus : oracle mort")


# =================== 8. Data-indépendance — méta-oracle, DoD-8 =======================
def _jetons_de_dependance_aux_donnees():
    """Fragments assemblés à l'exécution.

    Écrits en clair, ils se compteraient eux-mêmes et l'oracle mesurerait sa propre présence
    plutôt que celle d'une dépendance réelle.
    """
    return ("synth" + "_env", "FIXTURE" + "_PACK", "V1" + "_2", "execute" + "_moteur")


def test_meta_aucun_test_de_ce_fichier_ne_depend_d_un_jeu_de_donnees():
    """DoD-8 : la data-indépendance devient un ORACLE, et cesse d'être une intention.

    Les seuils du moteur vont bouger : tout test qui figerait une partition observée sur un
    jeu réel casserait au premier recalibrage, sans qu'aucun défaut n'ait été introduit.
    """
    with open(os.path.abspath(__file__), encoding="utf-8") as fh:
        arbre = ast.parse(fh.read())
    for jeton in _jetons_de_dependance_aux_donnees():
        fautives = [n.value for n in ast.walk(arbre)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                    and jeton in n.value]
        assert not fautives, f"dependance a un jeu de donnees ({jeton}) : {fautives}"
    # Le seul `open` toléré est la lecture de sources par les oracles structurels : jamais
    # l'ouverture d'un jeu de données.
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name) \
                and noeud.func.id == "open":
            cible = ast.dump(noeud.args[0]) if noeud.args else ""
            assert "__file__" in cible or "_ENGINE" in cible, (
                f"ouverture d'un fichier de donnees dans les tests : {cible}")
    importes = _noms_importes(arbre)
    assert not {n for n in importes if n in ("generator", "scorer")}, (
        f"import hors perimetre dans les tests : {sorted(importes)}")


def test_meta_les_oracles_de_ce_fichier_ne_sont_pas_vides():
    """Anti-vacuité mordante : le jeu de formes DOIT contenir de quoi prouver quelque chose.

    Sans cette garde, un `_FORMES` réduit à des singletons laisserait passer toute la
    section couverture avec des zéros partout.
    """
    tailles = [len(_composantes_par_parcours(u, p)) for u, p in _FORMES.values()]
    garde_non_vacuite(formes=_FORMES, tailles=tailles)
    groupes = [g for u, p in _FORMES.values() for g in _composantes_par_parcours(u, p)]
    assert any(len(g) >= 3 for g in groupes), "aucun groupe de taille >= 3 : oracle vide"
    assert any(v[2] > 0 for v in _COUVERTURES.values()), "aucune paire recuperee : oracle vide"
