# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Oracles des trois surfaces.

## Un oracle qui ne peut pas échouer ne prouve rien
Les revues adversariales de ce projet ont trouvé, à chaque unité, des gardes qui ne gardaient
rien : oracles inertes, tests tautologiques, branches inatteignables. Chaque oracle de ce
fichier porte donc son **contrôle positif** — on lui soumet une violation fabriquée et on
exige qu'il la voie. Un scan de jargon qui ne détecterait pas le mot « Splink » injecté dans
la Vitrine passerait au vert sur une Vitrine truffée de jargon ; c'est ce test-là qui dit que
le premier a du sens.

Ce n'est pas une précaution théorique : le contrôle positif de « aucun chiffre en dur » a
effectivement échoué à la première écriture, sur un oracle qui effaçait du texte toutes les
écritures possibles des valeurs mesurées — donc « 9 », « 7 », « 0 » — et dissolvait ainsi le
chiffre inventé qu'on lui soumettait. Sans son contrôle positif, cet oracle serait au vert
aujourd'hui, et ne garderait rien.

Les quatre propriétés sous garde :

* `G4` — le chiffre d'affiche de la Vitrine et sa contrepartie en Salle des machines sont la
  même mesure, lue une seule fois.
* Non-circularité — aucune surface n'importe le scoreur ; les surfaces d'affichage n'importent même
  pas le moteur ; rien n'est recompté.
* Règle de vocabulaire — la Vitrine ne contient aucun jargon R&D ni aucun nom de concurrent, et
  aucune surface ne revendique un code fabriqué par une IA. Le mot « IA » lui-même est PERMIS depuis
  le briefing de clôture : il désigne une capacité du produit, et c'est un argument d'achat.
  La règle et la raison du changement sont dans `surfaces.vue.JARGON_INTERDIT`.
* Déterminisme / `C4` — le bac à sable est déterministe et tient son budget.

Plus la propriété qui porte tout le mandat : **aucun chiffre affiché n'est écrit en dur**.
"""
from __future__ import annotations

import ast
import hashlib
import html as H
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time

import pytest

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RACINE, "src"))

from surfaces import app, bac_a_sable, format as fmt, lecture, vue   # noqa: E402


# ============================ fixtures ============================

@pytest.fixture(scope="module")
def modele():
    return vue.construit(racine=_RACINE)


@pytest.fixture(scope="module")
def pages(modele):
    """Le HTML RENDU des trois surfaces. C'est ce que le lecteur voit qui est jugé."""
    extra_bac = {
        "extrait_json": json.dumps(
            modele["demonstration"]["extrait"]["records"], ensure_ascii=False),
        "champs": list(bac_a_sable.CHAMPS_RECORD),
        "longueur_max_valeur": bac_a_sable.LONGUEUR_MAX_VALEUR,
    }
    return {
        "vitrine": app.rend("vitrine.html", modele),
        "salle_des_machines": app.rend("salle_des_machines.html", modele),
        "bac_a_sable": app.rend("bac_a_sable.html", modele, **extra_bac),
        "dossier_technique": app.rend("dossier_technique.html", modele),
    }


@pytest.fixture(scope="module")
def point():
    from pipeline import point as pt
    return pt.point_depuis_artefact(pt.CHEMIN_DIMS_V2, racine=_RACINE)


#: Attributs qui portent du texte AU LECTEUR : une infobulle se lit au survol, un `aria-label`
#: se lit à voix haute, une `meta description` s'affiche dans un aperçu de lien. Les retirer
#: avec les balises laissait passer tout jargon qui s'y serait logé — le scan aurait juré que
#: la Vitrine était propre en n'ayant pas regardé là où le lecteur regarde.
ATTRIBUTS_LUS = ("title", "alt", "aria-label", "placeholder", "content")


def _texte_visible(html: str) -> str:
    """Le texte que le lecteur lit : corps ET attributs porteurs de texte, entités résolues."""
    sans = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S | re.I)
    portes = []
    for attribut in ATTRIBUTS_LUS:
        portes += re.findall(r"\b" + attribut + r"\s*=\s*\"([^\"]*)\"", sans, flags=re.I)
        portes += re.findall(r"\b" + attribut + r"\s*=\s*'([^']*)'", sans, flags=re.I)
    sans = re.sub(r"<[^>]+>", " ", sans) + " " + " ".join(portes)
    return H.unescape(sans).replace(" ", " ").replace(" ", " ")


# ============================ G4 — une seule vérité ============================

def test_g4_le_chiffre_d_affiche_est_la_meme_mesure_dans_les_deux_surfaces(modele, pages):
    """La Vitrine projette le rappel ; la Salle des machines le publie. Une seule valeur."""
    _verifie_g4(modele, pages)
    # Et cette valeur brute est bien celle du banc, pas une copie.
    banc = lecture.charge(_RACINE)["banc"]
    cellule = lecture.cellule(banc, *vue.CELLULE_MOTEUR)
    assert modele["chiffre_affiche"]["valeur_brute"] == cellule["metriques"]["rappel_bout_en_bout"]


def _verifie_g4(modele, pages):
    """Le corps de la propriété G4, isolé pour qu'un contrôle positif puisse l'EXERCER.

    Un contrôle positif qui se contenterait de vérifier une propriété de son propre fixture
    sans appeler ce code ne prouverait rien sur le détecteur — c'est précisément le motif que
    ce fichier dit chasser, et il s'y était laissé prendre.
    """
    brut = modele["chiffre_affiche"]["valeur_brute"]
    assert fmt.nombre(brut) in _texte_visible(pages["salle_des_machines"]), (
        "la Salle des machines doit publier la valeur exacte du chiffre d'affiche")
    sur_dix = modele["chiffre_affiche"]["sur_dix"]
    assert f"{sur_dix} doublons sur 10" in _texte_visible(pages["vitrine"])
    assert sur_dix == int(brut * 10), "la projection doit dériver de la valeur brute"

    # Le TROISIÈME registre de la même mesure : la phrase de lecture simple de la Salle des
    # machines, « environ N % des doublons » (briefing de clôture, point 1). Le « 92 % » ne
    # doit jamais être écrit en dur — c'est exactement ce que cette assertion refuse.
    pourcent = modele["chiffre_affiche"]["pourcent_entier"]
    assert pourcent == math.floor(brut * 100), (
        "le pourcentage d'affiche ne derive pas du rappel mesure : le « environ N % » de la "
        "Salle des machines serait un chiffre invente")
    # L'espace fine insécable de « 92 % » est normalisée des deux côtés : `_texte_visible`
    # la remplace par une espace ordinaire, et une comparaison littérale échouerait sur une
    # page parfaitement correcte — un oracle qui rougit pour un caractère invisible finit
    # désarmé plutôt que corrigé.
    ecrit = re.sub(r"\s+", " ", fmt.pourcent(pourcent, 0))
    assert ecrit in re.sub(r"\s+", " ", _texte_visible(pages["salle_des_machines"])), (
        "la phrase de lecture simple doit porter le pourcentage LU du rappel")


def test_g4_controle_positif_une_divergence_serait_vue(modele):
    """CONTRÔLE POSITIF : une vue dont le chiffre d'affiche a dérivé DOIT faire échouer G4.

    On rend réellement les deux gabarits avec un modèle corrompu et on exige que le corps de
    la propriété lève. La version précédente n'appelait ni `vue`, ni `app.rend`, ni le corps
    du test : elle comparait deux nombres qu'elle venait d'écrire elle-même.
    """
    corrompu = json.loads(json.dumps(modele))
    corrompu["chiffre_affiche"]["valeur_brute"] = 0.5432   # une mesure venue d'ailleurs
    pages_corrompues = {
        "vitrine": app.rend("vitrine.html", corrompu),
        "salle_des_machines": app.rend("salle_des_machines.html", corrompu),
    }
    with pytest.raises(AssertionError):
        _verifie_g4(corrompu, pages_corrompues)


def test_g4_controle_positif_le_pourcentage_seul_derive_est_garde(modele, pages):
    """CONTRÔLE POSITIF du TROISIÈME registre, isolé — et il fallait l'isoler.

    Le contrôle précédent corrompt `valeur_brute` : `_verifie_g4` lève alors dès sa PREMIÈRE
    assertion, et les deux assertions sur le pourcentage ne sont jamais exécutées. Elles
    étaient donc gardées par un contrôle qui ne les atteignait pas — la classe exacte de
    défaut que ce fichier dit chasser. Ici, on ne corrompt QUE `pourcent_entier`.
    """
    corrompu = json.loads(json.dumps(modele))
    corrompu["chiffre_affiche"]["pourcent_entier"] = 99      # un chiffre venu d'ailleurs
    pages_corrompues = {
        "vitrine": app.rend("vitrine.html", corrompu),
        "salle_des_machines": app.rend("salle_des_machines.html", corrompu),
    }
    with pytest.raises(AssertionError):
        _verifie_g4(corrompu, pages_corrompues)


#: La classe dont le gabarit MARQUE le seul pourcentage d'une face de vente qui ne soit pas
#: une mesure : la complétude que l'arbitrage humain tient (« Le 100 %, c'est vous qui le
#: tenez »). Ce n'est pas une affirmation de performance — la page dit qui TIENT la
#: complétude, pas qui l'atteint — et c'est une autre grandeur que le rappel du moteur.
#:
#: Le marquage est ce qui rend la garde décidable sans lire le contexte. Toute échappatoire
#: est ici UNIQUE, VISIBLE dans le gabarit, et de valeur fixée par le modèle : un futur
#: auteur qui voudrait écrire un pourcentage devra le lire d'une mesure, ou poser ce
#: marquage — donc faire un geste qu'une relecture voit.
CLASSE_COMPLETUDE = "completude"


def _pourcentages_affiches(texte: str) -> list:
    """Les pourcentages écrits dans le texte visible, sous toutes leurs espaces."""
    return re.findall(r"(\d+(?:[.,]\d+)?)\s*%", re.sub(r"\s+", " ", texte))


def _sans_completude(html: str) -> str:
    """Le HTML privé des éléments marqués comme non-mesure."""
    return re.sub(
        r"<(\w+)[^>]*\bclass\s*=\s*\"[^\"]*\b" + CLASSE_COMPLETUDE + r"\b[^\"]*\"[^>]*>"
        r".*?</\1>", " ", html, flags=re.S | re.I)


def _completudes_marquees(html: str) -> list:
    """Les pourcentages portés PAR le marquage. Il ne doit y en avoir qu'un, et valoir 100."""
    marques = re.findall(
        r"<(\w+)[^>]*\bclass\s*=\s*\"[^\"]*\b" + CLASSE_COMPLETUDE + r"\b[^\"]*\"[^>]*>"
        r"(.*?)</\1>", html, flags=re.S | re.I)
    return [p for _balise, contenu in marques
            for p in _pourcentages_affiches(H.unescape(re.sub(r"<[^>]+>", " ", contenu)))]


@pytest.mark.parametrize("surface", ["vitrine", "salle_des_machines", "bac_a_sable"])
def test_aucun_pourcentage_de_performance_non_mesure_en_vente(pages, modele, surface):
    """Tout pourcentage de PERFORMANCE affiché en vente vient du rappel mesuré.

    La garde ne porte pas sur les littéraux mais sur la provenance : un taux qui dit ce que
    le moteur obtient est une mesure lue, ou il n'est rien. Elle est née d'un vrai trou —
    un « 100 » routé par le modèle échappait aux deux gardes de chiffres, celle de la source
    parce qu'aucun littéral n'était écrit, celle du rendu parce que le jeton venait du modèle.

    Le seul pourcentage qui sorte de cette règle est celui que le gabarit MARQUE comme
    n'étant pas une mesure — la complétude tenue par l'arbitrage humain — et il a son propre
    oracle juste en dessous, qui en fixe la valeur et l'unicité.
    """
    autorises = {str(modele["chiffre_affiche"]["pourcent_entier"])}
    trouves = set(_pourcentages_affiches(_texte_visible(_sans_completude(pages[surface]))))
    orphelins = trouves - autorises
    assert not orphelins, (
        f"{surface} affiche des pourcentages de performance qui ne derivent pas du rappel "
        f"mesure : {sorted(orphelins)}. Un taux affiche est une mesure lue, ou il n'est rien.")


def test_le_seul_pourcentage_non_mesure_est_la_completude_tenue_par_l_utilisateur(pages,
                                                                                  modele):
    """L'échappatoire existe, elle est unique, et sa valeur ne se choisit pas dans le gabarit.

    Trois propriétés, et chacune ferme une dérive différente : la valeur vient du modèle
    (personne ne l'écrit à la main), il n'y en a qu'UNE sur toute la vente (le marquage ne
    devient pas un passe-droit qu'on essaime), et elle est sur la Salle des machines (la page
    qui explique le dispositif), pas sur la Vitrine.
    """
    attendue = str(modele["controle_humain"]["completude_pourcent"])
    par_surface = {surface: _completudes_marquees(pages[surface])
                   for surface in app.SURFACES_DE_VENTE}
    toutes = [p for valeurs in par_surface.values() for p in valeurs]
    assert toutes == [attendue], (
        f"le marquage de completude doit porter exactement une fois la valeur du modele "
        f"({attendue}) sur l'ensemble de la vente ; trouve {par_surface}")
    assert par_surface["salle_des_machines"] == [attendue], (
        "la completude tenue par l'utilisateur se dit sur la page qui explique le dispositif")


@pytest.mark.parametrize("injection,ou", [
    # Un taux de performance inventé, marqué ou non : vu dans les deux cas.
    ("<p>99,9 % de fiabilité sur vos fichiers.</p>", "performance"),
    ("<p>Nous retrouvons 98 % des doublons.</p>", "performance"),
    # Le 100 % SANS son marquage : il redevient un taux de performance, donc une faute.
    ("<p>pour atteindre 100 %</p>", "performance"),
    ("<p>jusqu'à 100&nbsp;%</p>", "performance"),
    # Le marquage détourné : une autre valeur que celle du modèle.
    ('<p>Le <span class="completude">98 %</span>, c\'est vous.</p>', "completude"),
    # Le marquage essaimé : un second, ailleurs sur la même page.
    ('<p>Le <span class="completude">100 %</span> partout.</p>', "completude"),
])
def test_controle_positif_un_pourcentage_non_mesure_serait_vu(pages, modele, injection, ou):
    """CONTRÔLE POSITIF des deux gardes : chacune sur la classe de faute qu'elle prétend voir.

    Les quatre premiers cas doivent être vus par la garde de PERFORMANCE — y compris le
    « 100 % » écrit sans son marquage, qui redevient alors un taux comme un autre. Les deux
    derniers doivent être vus par la garde de la COMPLÉTUDE : une valeur détournée, et un
    marquage essaimé sur la page.
    """
    pollue = pages["salle_des_machines"].replace("</main>", injection + "</main>")
    if ou == "performance":
        autorises = {str(modele["chiffre_affiche"]["pourcent_entier"])}
        trouves = set(_pourcentages_affiches(_texte_visible(_sans_completude(pollue))))
        assert trouves - autorises, (
            f"la garde de performance ne voit pas {injection!r} : elle ne garde rien")
    else:
        attendue = str(modele["controle_humain"]["completude_pourcent"])
        assert _completudes_marquees(pollue) != [attendue], (
            f"la garde de completude ne voit pas {injection!r} : elle ne garde rien")


def _nombre_fr(texte: str) -> float:
    """Relit un nombre tel qu'il est ÉCRIT sur la page (virgule décimale, signe moins typo)."""
    return float(texte.replace(fmt.MOINS, "-").replace(" ", "").replace(",", "."))


def test_g4_les_ecarts_se_recoupent_sur_LA_PAGE_pas_seulement_dans_le_modele(modele, pages):
    """Un évaluateur qui soustrait les nombres AFFICHÉS doit retrouver l'écart AFFICHÉ.

    C'est le défaut trouvé sur la maquette : la ligne Splink montrée n'était pas celle contre
    laquelle l'écart était calculé, et la soustraction donnait −0,004 au lieu de −0,017. Le
    vérifier sur le modèle ne suffit pas — le défaut historique était précisément un modèle
    juste rendu dans une page trompeuse : il se reformerait en changeant le gabarit, sans
    qu'aucun test ne bouge.
    """
    # Les cibles chiffrées vivent au dossier technique depuis une révision, et le bloc de
    # parité l'a rejoint au briefing de clôture : la comparaison a quitté la face de vente.
    # On vérifie le recoupement LÀ OÙ CHAQUE CHIFFRE EST AFFICHÉ — un oracle qui regarderait
    # la mauvaise page ne garderait rien, et c'est le déplacement qui vient de le montrer :
    # ce test a rougi à la seconde où le tableau comparatif a quitté la Salle des machines.
    texte = _texte_visible(pages["dossier_technique"])

    for cible in modele["cibles"]:
        moteur_ecrit = fmt.nombre(cible["valeur_moteur"])
        reference_ecrite = fmt.nombre(cible["reference_valeur"])
        points_ecrits = fmt.signe(cible["en_points"], 1)
        for morceau in (moteur_ecrit, reference_ecrite, points_ecrits):
            assert morceau in texte, (
                f"cible {cible['code']} : {morceau!r} n'est pas sur la page, donc le lecteur "
                f"ne peut pas refaire la soustraction qu'on lui demande de croire")
        # La soustraction des deux nombres ÉCRITS redonne l'écart ÉCRIT, à la résolution
        # d'affichage près (les valeurs sont à trois décimales, l'écart en points).
        recalcule = (_nombre_fr(moteur_ecrit) - _nombre_fr(reference_ecrite)) * 100
        assert abs(recalcule - _nombre_fr(points_ecrits)) < 0.15, (
            f"cible {cible['code']} : la page affiche {moteur_ecrit} et {reference_ecrite}, "
            f"dont la difference vaut {recalcule:.2f} points, mais annonce {points_ecrits} "
            f"points. Deux chiffres justes et une lecture fausse.")

    # Le bloc de parité, au dossier technique : F1 du moteur, F1 du comparateur, écart.
    f1_moteur = fmt.nombre(modele["moteur"]["f1"])
    f1_reference = fmt.nombre(modele["splink_reference"]["f1"])
    ecart_ecrit = fmt.signe(modele["parite"]["ecart_f1"])
    for morceau in (f1_moteur, f1_reference, ecart_ecrit):
        assert morceau in texte, f"bloc de parite : {morceau!r} absent de la page"
    assert abs((_nombre_fr(f1_moteur) - _nombre_fr(f1_reference))
               - _nombre_fr(ecart_ecrit)) < 0.001, (
        "la soustraction des deux F1 affiches ne redonne pas l'ecart affiche")


def test_g4_controle_positif_une_page_incoherente_serait_vue(modele):
    """CONTRÔLE POSITIF : afficher la cellule Splink par défaut sous l'écart de la meilleure
    — le défaut EXACT de la maquette — doit faire échouer le recoupement.

    La page inspectée est le dossier technique, seule surface à porter la comparaison depuis
    le briefing de clôture. Laisser le contrôle sur la Salle des machines l'aurait rendu
    inerte : il aurait cherché des nombres qui n'y sont plus, et se serait tu.
    """
    corrompu = json.loads(json.dumps(modele))
    corrompu["splink_reference"] = corrompu["splink_defaut"]   # la ligne ne colle plus a l'ecart
    texte = _texte_visible(app.rend("dossier_technique.html", corrompu))
    f1_moteur = fmt.nombre(corrompu["moteur"]["f1"])
    f1_reference = fmt.nombre(corrompu["splink_reference"]["f1"])
    ecart_ecrit = fmt.signe(corrompu["parite"]["ecart_f1"])
    assert all(m in texte for m in (f1_moteur, f1_reference, ecart_ecrit))
    assert abs((_nombre_fr(f1_moteur) - _nombre_fr(f1_reference))
               - _nombre_fr(ecart_ecrit)) >= 0.001, (
        "l'oracle de recoupement ne voit pas la ligne Splink substituee : il ne garde rien")


# ============================ Non-circularité — le scoreur reste dehors ==========================

def _imports_du_module(chemin: str) -> set:
    """Les racines de paquet importées par un fichier, par analyse de l'AST."""
    with open(chemin, encoding="utf-8") as fh:
        arbre = ast.parse(fh.read(), filename=chemin)
    racines = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            racines.update(alias.name.split(".")[0] for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.level == 0 and noeud.module:
                racines.add(noeud.module.split(".")[0])
    return racines


def _modules_surfaces() -> list:
    dossier = os.path.join(_RACINE, "src", "surfaces")
    return [os.path.join(dossier, f) for f in sorted(os.listdir(dossier))
            if f.endswith(".py")]


def test_cc1_aucune_surface_n_importe_le_scoreur():
    for chemin in _modules_surfaces():
        assert "scorer" not in _imports_du_module(chemin), (
            f"{os.path.basename(chemin)} importe le scoreur : la surface pourrait recompter "
            f"ce qu'elle affiche, et l'independance montree en Salle des machines serait fausse")


def test_cc1_les_modules_d_affichage_n_importent_meme_pas_le_moteur():
    """`lecture` et `vue` n'ont besoin que de JSON. Le bac à sable, lui, a le droit."""
    for nom in ("lecture.py", "vue.py", "format.py"):
        chemin = os.path.join(_RACINE, "src", "surfaces", nom)
        racines = _imports_du_module(chemin)
        assert "engine" not in racines, f"{nom} importe le moteur sans en avoir besoin"
        assert "scorer" not in racines


def test_cc1_controle_positif_le_detecteur_voit_un_import_injecte(tmp_path):
    """CONTRÔLE POSITIF : un module qui importe le scoreur DOIT être vu."""
    faux = tmp_path / "surface_fautive.py"
    faux.write_text("import json\nfrom scorer import metriques\n", encoding="utf-8")
    assert "scorer" in _imports_du_module(str(faux)), (
        "le detecteur d'import ne voit pas un `from scorer import ...` : il ne garde rien")

    autre = tmp_path / "surface_fautive2.py"
    autre.write_text("import scorer.metriques as m\n", encoding="utf-8")
    assert "scorer" in _imports_du_module(str(autre))


def _arithmetique_entre_mesures(chemin: str) -> list:
    """Les opérations arithmétiques dont les DEUX opérandes sont des valeurs, pas des constantes.

    C'est la signature d'un recomptage. Une mise en forme combine toujours une valeur et une
    constante d'écriture (`valeur * 100`, `rappel * 10`) ; recomposer un F1 demande
    `2 * p * r / (p + r)`, où `p + r` et `p * r` mettent deux mesures face à face.

    Comparer les VALEURS ne peut pas attraper cette faute : sur les artefacts livrés,
    `2pr/(p+r)` est bit-identique au F1 publié. La garde ne peut donc être que structurelle —
    ce qui rendait le test précédent, fondé sur une égalité numérique, vrai par construction
    et incapable d'échouer sur la violation qu'il nommait.
    """
    with open(chemin, encoding="utf-8") as fh:
        arbre = ast.parse(fh.read(), filename=chemin)
    fautifs = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.BinOp):
            continue
        # `Add` est exclu : en Python, `+` est aussi la concaténation de chaînes, et la mise
        # en forme française en fait partout (« ", ".join(noms) + " et " + dernier »). Le
        # retenir noierait la garde sous des faux positifs, et une garde bruyante finit
        # désactivée. Rien n'est perdu : recomposer une métrique demande un produit et une
        # division, tous deux couverts — `2 * p * r / (p + r)` est pris par `(2*p) * r`.
        if not isinstance(noeud.op, (ast.Sub, ast.Mult, ast.Div)):
            continue
        litteral = (ast.Constant,)
        gauche_const = isinstance(noeud.left, litteral)
        droite_const = isinstance(noeud.right, litteral)
        if not gauche_const and not droite_const:
            fautifs.append((os.path.basename(chemin), noeud.lineno))
    return fautifs


def test_cc1_aucune_metrique_n_est_recomposee():
    """Aucun module d'affichage ne met deux mesures face à face dans un calcul."""
    fautifs = []
    for nom in ("vue.py", "format.py", "lecture.py"):
        fautifs += _arithmetique_entre_mesures(
            os.path.join(_RACINE, "src", "surfaces", nom))
    assert not fautifs, (
        f"arithmetique entre deux valeurs non constantes : {fautifs}. Une mise en forme "
        f"combine une mesure et une constante ; combiner deux mesures, c'est recompter.")


def test_cc1_controle_positif_un_recomptage_serait_vu(tmp_path):
    """CONTRÔLE POSITIF : le détecteur doit voir un F1 recomposé — et se taire sur une mise
    en forme légitime, sans quoi il serait désactivé au premier faux positif."""
    fautif = tmp_path / "vue_fautive.py"
    fautif.write_text(
        "def f(p, r):\n"
        "    return 2 * p * r / (p + r)\n", encoding="utf-8")
    assert _arithmetique_entre_mesures(str(fautif)), (
        "le detecteur ne voit pas un F1 recompose : il ne garde rien")

    innocent = tmp_path / "format_innocent.py"
    innocent.write_text(
        "import math\n"
        "def pourcent(v):\n"
        "    return v * 100\n"
        "def sur_dix(v):\n"
        "    return math.floor(v * 10)\n", encoding="utf-8")
    assert not _arithmetique_entre_mesures(str(innocent)), (
        "le detecteur crie sur une mise en forme : il serait desactive en pratique")


def test_cc1_les_producteurs_d_artefacts_d_interface_n_importent_pas_le_scoreur():
    """`tools/produit_artefacts_ui.py` et `tools/produit_scenarios.py` figent des DÉCISIONS.

    Leur docstring l'affirme et adosse l'affirmation à ce fichier de tests ; jusqu'ici aucun
    oracle ne regardait ces deux fichiers-là, et la promesse était donc gratuite. Elle compte
    d'autant plus depuis que `produit_artefacts_ui` lit la vérité terrain : ce qu'il faut
    garantir n'est pas qu'il ignore les réponses — il les lit, pour écarter un exemple
    trompeur — mais qu'il n'ait AUCUN moyen d'en tirer une note.
    """
    for nom in ("produit_artefacts_ui.py", "produit_scenarios.py"):
        racines = _imports_du_module(os.path.join(_RACINE, "tools", nom))
        assert "scorer" not in racines, (
            f"tools/{nom} importe le scoreur : un producteur d'artefact d'affichage pourrait "
            f"y noter ce que le moteur a decide, et la separation montree serait fausse")


def test_cc1_les_metriques_exposees_sont_celles_de_la_convention_stricte(modele):
    """La convention est gardée par la VALEUR, pas par son nom.

    Vérifier que le champ `convention` vaut la chaîne « stricte » ne garde rien : un gabarit
    pouvait publier le F1 optimiste (0,931 au lieu de 0,919, 1,2 point offert) sous une
    étiquette restée juste. On compare donc chaque métrique exposée à celle de `metriques`,
    qui EST la convention stricte, au bit près.
    """
    banc = lecture.charge(_RACINE)["banc"]
    for cle, identite in (("moteur", vue.CELLULE_MOTEUR),
                          ("splink_defaut", vue.CELLULE_SPLINK_DEFAUT),
                          ("splink_reference", vue.CELLULE_SPLINK_REFERENCE),
                          ("baseline", vue.CELLULE_BASELINE)):
        stricte = lecture.cellule(banc, *identite)["metriques"]
        for champ, source in (("precision", "precision"),
                              ("rappel", "rappel_bout_en_bout"),
                              ("f1", "f1_bout_en_bout")):
            assert modele[cle][champ] == stricte[source], (
                f"{cle}.{champ} ne vient pas de la convention stricte")


# ============================ L'accord des libellés ============================

@pytest.mark.parametrize("champs,attendu", [
    (["email"], "renseigné"),            # masculin singulier
    (["ville"], "renseignée"),           # féminin singulier — la branche qui manquait
    (["email", "nom"], "renseignés"),    # masculin pluriel
    (["ville", "adresse"], "renseignées"),   # féminin pluriel
    (["ville", "nom"], "renseignés"),    # mixte : masculin, règle française
])
def test_le_participe_s_accorde_au_genre_et_au_nombre_des_champs(champs, attendu):
    """La carte héros écrit « l'e-mail n'est renseigné que d'un seul côté ».

    Sur « la ville », l'accord fait à la main donnait « la ville n'est renseigné ». Les
    données du jour n'exercent que la branche masculine — le champ manquant du cas héros est
    l'e-mail — donc la faute serait restée invisible jusqu'au jour où le héros change. Les
    cinq combinaisons sont éprouvées, pas la seule que les données présentent.
    """
    assert fmt.accorde("renseigné", champs) == attendu


# ============================ Règle de vocabulaire — la Vitrine sans jargon ======================

#: Le vocabulaire proscrit en Vitrine, plus les noms d'outils tiers.
#:
#: « IA » n'y est PLUS, et le retrait est doctrinal, pas laxiste : le mot désigne une
#: capacité du produit — lire un document dégradé, trancher un cas ambigu — et l'acheteur le
#: connaît, là où il ne connaît pas « LLM », qui reste proscrit. Un scan de texte ne peut pas
#: distinguer « IA-capacité » de « IA-fabrication » : il ne cherche donc plus le mot du tout,
#: plutôt que de simuler une lecture de contexte qu'il n'a pas. Ce qui prend le relais est
#: `_revendication_de_fabrication_par_ia`, qui cherche des LOCUTIONS entières et décidables.
TERMES_INTERDITS_VITRINE = list(vue.JARGON_INTERDIT) + ["fellegi-sunter", "duckdb", "dedupe"]


def _jargon_trouve(texte: str, termes=None) -> list:
    termes = termes or TERMES_INTERDITS_VITRINE
    minuscule = texte.lower()
    return [t for t in termes if re.search(r"\b" + re.escape(t) + r"\b", minuscule)]


def _revendication_de_fabrication_par_ia(texte: str) -> list:
    """Les locutions qui attribueraient la FABRICATION du code à une IA.

    C'est la seule affirmation sur l'IA que ce projet ne peut pas soutenir : le produit est
    conçu et vérifié par un ingénieur, et la copie de la Vitrine le dit. Interdit sur les
    QUATRE surfaces, dossier technique compris — un dossier qui revendiquerait un code
    généré démonterait la Vitrine qui affirme l'inverse.

    La garde porte sur des locutions, jamais sur le mot « IA » seul : c'est ce qui la rend
    décidable. « Notre IA lit vos factures » et « notre code est généré par IA » ne diffèrent
    pas par un mot mais par une phrase, et seule la seconde est fausse.
    """
    minuscule = re.sub(r"\s+", " ", texte.lower())
    return [locution for locution in vue.FABRICATION_PAR_IA_INTERDITE
            if locution in minuscule]


def test_cc4_la_vitrine_ne_contient_aucun_jargon(pages):
    trouves = _jargon_trouve(_texte_visible(pages["vitrine"]))
    assert not trouves, f"jargon trouve en Vitrine : {trouves}"


@pytest.mark.parametrize("surface", ["vitrine", "salle_des_machines", "bac_a_sable",
                                     "dossier_technique"])
def test_aucune_surface_ne_revendique_un_code_fabrique_par_ia(pages, surface):
    """Le produit est conçu et vérifié par un ingénieur. Aucune page ne dit le contraire."""
    trouves = _revendication_de_fabrication_par_ia(_texte_visible(pages[surface]))
    assert not trouves, (
        f"{surface} revendique un code fabrique par une IA : {trouves}. C'est la seule "
        f"affirmation sur l'IA que ce projet ne peut pas soutenir.")


@pytest.mark.parametrize("injection", [
    "Ce démonstrateur est codé par IA, de bout en bout.",
    "Chaque surface est générée par IA en quelques minutes.",
    "Le moteur a été écrit par une IA.",
    "Tout le module de comparaison est développé par IA.",
    # Les cinq suivantes passaient toutes la première écriture de la garde, qui ne connaissait
    # que codé/généré/écrit/développé/fabriqué/programmé/rédigé. « Conçu » manquait — le mot
    # même que la copie emploie pour dire l'inverse (« conçu et vérifié par un ingénieur »).
    # Une garde qui rate la négation exacte de la phrase qu'elle protège ne garde rien.
    "Ce moteur est conçu par une IA.",
    "Le code a été créé par IA.",
    "Entièrement réalisé par une intelligence artificielle.",
    "Produit par IA de bout en bout.",
    "Fait par une IA, en une nuit.",
])
def test_controle_positif_une_revendication_de_code_par_ia_serait_vue(pages, injection):
    """CONTRÔLE POSITIF : la garde qui a REMPLACÉ le bannissement du mot « IA » doit mordre.

    Sans ce contrôle, retirer « IA » de `JARGON_INTERDIT` reviendrait à retirer la garde et à
    la déclarer remplacée. C'est ce test qui rend le remplacement réel.
    """
    pollue = pages["vitrine"].replace("</main>", f"<p>{injection}</p></main>")
    assert _revendication_de_fabrication_par_ia(_texte_visible(pollue)), (
        f"la garde ne voit pas {injection!r} : le mot « IA » a ete libere sans contrepartie")


def test_l_ia_comme_capacite_du_produit_est_permise(pages):
    """L'autre moitié de la règle corrigée : dire « IA » d'une CAPACITÉ doit rester possible.

    Ce test n'est pas décoratif. Le mot est présent sur la Vitrine, dans une phrase validée
    par l'owner ; si un scan le reprenait un jour pour interdit, c'est ici que ça se verrait,
    plutôt qu'au moment où la phrase disparaîtrait de la page sans que personne ne l'ait
    décidé.
    """
    texte = _texte_visible(pages["vitrine"])
    assert re.search(r"\bIA\b", texte), (
        "« IA » a disparu de la Vitrine : la phrase validee par l'owner n'y est plus")
    assert not _jargon_trouve(texte), "le scan de vocabulaire s'est remis a crier sur la Vitrine"
    assert not _revendication_de_fabrication_par_ia(texte)
    # Et la contrepartie de l'argument : la copie dit qui conçoit le code.
    assert "conçu et vérifié par un ingénieur" in re.sub(r"\s+", " ", texte), (
        "l'argument « de l'IA, oui — mais prouvee » a perdu la phrase qui le rend vrai")


def _attribution_de_performance_a_l_ia(texte):
    """Les phrases où l'IA et le RÉSULTAT sont dits dans le même souffle.

    L'unité est la PHRASE et non la page, et c'est le point qui rend la garde utilisable :
    sur la Vitrine, « IA » et le « 9 sur 10 » coexistent légitimement à deux sections d'écart,
    et une garde de page interdirait l'argument au lieu d'interdire l'affirmation. Ce qui est
    faux, c'est une phrase qui donne le résultat à l'IA — pas leur voisinage sur un écran.

    Une phrase qui NIE l'attribution n'en est pas une : `DENEGATIONS_D_ATTRIBUTION` l'exempte.
    Sans cela l'oracle refuserait l'énoncé même de la doctrine (« la performance vient du
    moteur, pas de l'IA »), c'est-à-dire qu'il rebannirait « IA » par le côté honnête.
    """
    plat = re.sub(r"\s+", " ", texte.lower())
    fautives = []
    for phrase in re.split(r"(?<=[.!?])\s+", plat):
        if not re.search(vue.MENTION_D_IA, phrase):
            continue
        if any(re.search(d, phrase) for d in vue.DENEGATIONS_D_ATTRIBUTION):
            continue
        marqueurs = [m for m in vue.MARQUEURS_DE_PERFORMANCE if re.search(m, phrase)]
        if marqueurs:
            fautives.append((phrase.strip()[:160], marqueurs))
    return fautives


@pytest.mark.parametrize("surface", ["vitrine", "salle_des_machines", "bac_a_sable"])
def test_l_ia_n_est_jamais_donnee_comme_la_cause_de_la_performance(pages, surface):
    """TROISIÈME règle de vocabulaire : l'IA est une capacité vendue, jamais la cause du chiffre.

    Les deux premières règles — fabrication interdite, capacité permise — étaient tenues par
    des oracles. La troisième ne l'était par rien : huit phrases d'attribution injectées dans
    la Vitrine traversaient les quatre gardes existantes sans en émouvoir une seule. C'est la
    règle dont la violation coûterait le plus cher, puisqu'elle rendrait la face de vente
    fausse au regard du banc du projet lui-même.

    Le dossier technique est HORS de cette garde, et pas par commodité : sa fonction est de
    publier l'apport MESURÉ de la revue par IA À CÔTÉ des métriques. On ne garde pas contre
    l'honnêteté ; sur les surfaces de vente, où aucune métrique n'a sa place, la co-occurrence
    n'a aucun usage légitime.
    """
    fautives = _attribution_de_performance_a_l_ia(_texte_visible(pages[surface]))
    assert not fautives, (
        f"{surface} fait porter le resultat a l'IA : {fautives}. La performance vient du "
        f"moteur ; l'apport mesure de la revue par IA vaut zero (contribution_llm.json).")


@pytest.mark.parametrize("injection", [
    "Ces 9 doublons sur 10, c'est notre IA qui les trouve.",
    "Grâce à l'IA, le moteur atteint le niveau des meilleurs.",
    "C'est l'intelligence artificielle qui fait la performance.",
    "Notre IA rapproche vos fiches mieux que tout le reste.",
    "L'IA porte 92 % du résultat.",
    "Le moteur doit sa parité à l'intelligence artificielle.",
    "L'IA permet d'atteindre ce niveau des meilleurs outils.",
    # La forme que la copie portait RÉELLEMENT avant cette passe. Sans elle, la garde aurait
    # été écrite pour passer au vert sur la page qu'elle prétend garder.
    "Il s'appuie sur l'intelligence artificielle là où elle fait vraiment la différence.",
    # L'exemption de dénégation ne doit pas devenir une porte : un « sans » posé n'importe où
    # dans la phrase n'annule pas l'attribution qui la précède.
    "L'IA porte 92 % du résultat, sans exception.",
])
def test_controle_positif_une_attribution_de_performance_a_l_ia_serait_vue(pages, injection):
    """CONTRÔLE POSITIF : chacune de ces phrases traversait les QUATRE gardes de vocabulaire."""
    pollue = pages["vitrine"].replace("</main>", f"<p>{injection}</p></main>")
    assert _attribution_de_performance_a_l_ia(_texte_visible(pollue)), (
        f"la garde ne voit pas {injection!r} : la troisieme regle reste declarative")


@pytest.mark.parametrize("licite", [
    # La phrase réelle de la Vitrine après cette passe : elle vend une CAPACITÉ et n'affirme
    # aucun résultat. Si elle rougissait, c'est la garde qui serait fautive.
    "Le moteur est conçu et vérifié par un ingénieur, et il s'appuie sur l'intelligence "
    "artificielle pour ce qu'un calcul ne sait pas faire : lire un document de mauvaise "
    "qualité, trancher un cas ambigu, ou expliquer chaque rapprochement en français clair.",
    "Notre IA lit vos factures, même mal scannées.",
    "L'IA explique chaque rapprochement en français clair.",
    "De l'IA, oui — mais prouvée.",
    # LES CINQ ÉNONCÉS HONNÊTES. Ils sont ici parce qu'une première version de cette garde
    # les refusait tous les cinq : elle interdisait de NIER l'attribution, donc elle
    # rebannissait « IA » de la face de vente par le côté honnête.
    "La performance vient du moteur statistique, pas de l'IA.",
    "L'apport mesuré de l'IA sur ce jeu est nul.",
    "La revue de zone grise par IA n'a modifié ni le résultat ni la parité.",
    "Aucune de ces performances ne vient de l'IA.",
    "Ces chiffres sont obtenus sans intelligence artificielle.",
])
def test_controle_negatif_les_enonces_honnetes_sur_l_ia_restent_permis(licite):
    """CONTRÔLE NÉGATIF : la garde ne doit pas interdire ce que la doctrine exige de dire.

    Une garde qui refuse la dénégation force le rédacteur honnête à se taire ou à la
    désarmer. Les deux issues sont pires que l'absence de garde, parce qu'elles se
    présentent comme une garde.
    """
    assert not _attribution_de_performance_a_l_ia(licite), (
        f"la garde refuse un enonce honnete : {licite!r}. Elle rebannit « IA » par le cote "
        f"honnete au lieu d'interdire l'attribution.")


def test_cc4_controle_positif_le_scan_voit_un_terme_injecte(pages):
    """CONTRÔLE POSITIF : le scan doit voir chaque terme qu'il prétend interdire."""
    for terme in ("Splink", "rappel", "F1", "clustering", "LLM",
                  "machine learning", "OpenAI"):
        pollue = pages["vitrine"].replace(
            "</main>", f"<p>Notre {terme} est excellent.</p></main>")
        assert _jargon_trouve(_texte_visible(pollue)), (
            f"le scan de vocabulaire ne voit pas {terme!r} injecte en Vitrine : il ne garde rien")

    # Le jargon loge aussi dans les attributs : une infobulle se lit, un aria-label s'entend.
    for gabarit in ('<span title="rappel 0,918">ici</span>',
                    '<img alt="schema du clustering">',
                    '<button aria-label="lancer Splink">go</button>',
                    # L'injection portait « Notre IA rapproche vos fiches », qui n'est plus
                    # une faute : c'est la phrase même que la règle corrigée autorise. Un
                    # contrôle positif dont l'injection est devenue licite ne prouve rien.
                    '<meta name="description" content="Un moteur de record linkage.">'):
        pollue = pages["vitrine"].replace("</main>", gabarit + "</main>")
        assert _jargon_trouve(_texte_visible(pollue)), (
            f"le scan de vocabulaire ne voit pas le jargon porte par {gabarit!r} : "
            f"une infobulle EST vue, un aria-label EST lu")


def test_cc4_le_scan_ne_se_declenche_pas_sur_des_mots_francais_courants():
    """Un scan qui crie sur « fiabilité » serait désarmé par son propre bruit."""
    innocent = ("Notre fiabilité et notre spécialisation sont au rendez-vous. "
                "Le rapprochement des fiches, même déformées, reste lisible. "
                "De l'IA, oui — mais prouvée : son apport est mesuré et affiché.")
    assert not _jargon_trouve(innocent), (
        "le scan de vocabulaire se declenche sur du francais ordinaire : "
        "il serait desactive en pratique")


def test_cc4_la_salle_des_machines_porte_les_chiffres(pages):
    """La Salle des machines reste technique : elle publie les métriques, sous leur nom."""
    texte = _texte_visible(pages["salle_des_machines"]).lower()
    for attendu in ("précision", "rappel", "f1"):
        assert attendu in texte, f"la Salle des machines devrait porter {attendu!r}"


def test_cc4_le_dossier_technique_porte_TOUT_le_jargon(pages):
    """Le dossier est la transparence radicale : rien n'y est adouci, tout y est nommé.

    C'est ce qui rend l'écart de positionnement tenable. Si le dossier perdait ces termes,
    l'évaluateur n'aurait plus nulle part où vérifier, et le déplacement deviendrait un
    escamotage.
    """
    texte = _texte_visible(pages["dossier_technique"]).lower()
    for attendu in ("précision", "rappel", "f1", "splink", "mcnemar", "zone grise",
                    "asymétries", "réserves"):
        assert attendu in texte, f"le dossier technique devrait porter {attendu!r}"


#: Marques de concurrents. Bannies des SURFACES DE VENTE — un prospect ne les connaît pas, et
#: les citer ne fait que lui apprendre qu'elles existent. Le dossier technique, lui, DOIT les
#: nommer : une comparaison anonyme ne se reproduit pas.
MARQUES_CONCURRENTES = ("splink", "dedupe", "duckdb", "openrefine", "talend", "informatica")

#: Tournures qui revendiqueraient une SUPÉRIORITÉ. Le garde-fou du tour 2 : la reformulation
#: n'est légitime que parce que la parité est réelle. Prétendre mieux serait faux.
#: Radicaux, et non formes conjuguées : « surpasse » ne voyait pas « surpassons », ce que le
#: contrôle positif a montré du premier coup. Une garde qui ne tient que sur la personne du
#: verbe ne garde rien.
COMPARATIFS_INTERDITS = (
    "meilleur que", "meilleurs que", "meilleure que", "supérieur", "supérieure", "supérieurs",
    "plus performant", "plus performante", "surpass", "surclass", "devanc",
    "bat les", "nous gagnons", "on gagne", "leader du marché", "numéro un", "numéro 1",
)


def _marques_ou_superiorite(texte: str) -> list:
    minuscule = texte.lower()
    trouves = [m for m in MARQUES_CONCURRENTES
               if re.search(r"\b" + re.escape(m) + r"\b", minuscule)]
    trouves += [c for c in COMPARATIFS_INTERDITS if c in minuscule]
    return trouves


@pytest.mark.parametrize("surface", ["vitrine", "salle_des_machines", "bac_a_sable"])
def test_aucune_marque_ni_revendication_de_superiorite_en_vente(pages, surface):
    trouves = _marques_ou_superiorite(_texte_visible(pages[surface]))
    assert not trouves, f"{surface} : marque de concurrent ou comparatif de superiorite {trouves}"


@pytest.mark.parametrize("injection", [
    "Nous faisons mieux que Splink sur tous les points.",
    "Notre moteur est supérieur aux logiciels du marché.",
    "Un rapprochement plus performant que la concurrence.",
    "Nous surpassons les outils spécialisés.",
])
def test_controle_positif_une_revendication_de_superiorite_serait_vue(pages, injection):
    """CONTRÔLE POSITIF : le garde-fou du tour 2 doit voir une revendication de supériorité.

    La reformulation « au niveau des meilleurs » n'est légitime QUE parce que la parité est
    mesurée. Un texte qui glisserait vers « mieux » serait faux, et ce scan est ce qui
    empêche la glissade de passer inaperçue.
    """
    pollue = pages["vitrine"].replace("</main>", f"<p>{injection}</p></main>")
    assert _marques_ou_superiorite(_texte_visible(pollue)), (
        f"le scan ne voit pas {injection!r} : il ne garde rien")


def test_le_scan_de_superiorite_ne_crie_pas_sur_la_formulation_retenue():
    """Il doit rester muet sur la formulation de vente en vigueur, sinon on le désactive.

    L'exemple était « au niveau des meilleurs logiciels du marché » — la formulation voulue
    jusqu'au briefing de clôture, aujourd'hui bannie par `_comparaison_au_marche`. Un test
    qui certifierait le silence du scan sur une phrase que la page n'a plus le droit d'écrire
    documenterait une doctrine périmée.
    """
    assert not _marques_ou_superiorite(
        "Le moteur retrouve automatiquement environ 92 % des doublons. Les cas où il hésite, "
        "c'est vous qui tranchez. Il tourne chez vous, hors ligne, et montre chaque décision.")


#: Les tournures qui POSITIONNENT le moteur par rapport au marché. Bannies des surfaces de
#: VENTE depuis le briefing de clôture (point 1) : la comparaison a quitté la face de vente,
#: pas le dossier. Ce n'est pas la même garde que `COMPARATIFS_INTERDITS` — celle-là
#: interdisait de se dire MEILLEUR, celle-ci interdit de se SITUER, même à parité.
#:
#: Le dossier technique en est exempt, et doit l'être : il nomme, chiffre et compare, et
#: c'est ce qui honore `O5` et la loyauté de la comparaison.
#: Un signalement neutre (« la comparaison chiffrée est
#: publiée dans le dossier technique ») n'est pas une comparaison : il ne situe rien, il
#: indique où regarder — et sans lui le déplacement se lirait comme un escamotage.
COMPARAISONS_AU_MARCHE = (
    "au niveau des meilleurs", "meilleurs outils du marché", "meilleurs logiciels du marché",
    "outils du marché", "logiciels du marché", "solutions du marché",
    "état de l'art", "etat de l'art", "à parité", "a parite",
    "aussi bon que", "aussi bien que", "se valent",
    "univers de comparaison", "meilleure configuration", "la concurrence",
)


def _comparaison_au_marche(texte: str) -> list:
    minuscule = re.sub(r"\s+", " ", texte.lower())
    return [t for t in COMPARAISONS_AU_MARCHE if t in minuscule]


@pytest.mark.parametrize("surface", ["vitrine", "salle_des_machines", "bac_a_sable"])
def test_aucune_comparaison_au_marche_sur_les_surfaces_de_vente(pages, surface):
    """La face de vente publie le résultat du moteur, jamais son classement."""
    trouves = _comparaison_au_marche(_texte_visible(pages[surface]))
    assert not trouves, (
        f"{surface} : la comparaison au marche est revenue sur la face de vente {trouves}. "
        f"Elle vit au dossier technique, et elle y vit entiere.")


def _valeurs_de_comparateurs(modele) -> list:
    """Toute valeur chiffrée du modèle qui appartient à un système AUTRE que le moteur.

    Dérivée du modèle plutôt qu'énumérée à la main. La première écriture recopiait trois clés
    — `splink_defaut`, `splink_reference`, `baseline` — et manquait la QUATRIÈME cellule de
    comparateur : `CELLULE_BASELINE_RAPPEL` (même système, autre point de fonctionnement,
    rappel 0,900), qui n'entre dans le modèle que par `cibles[*].reference_valeur`. Une ligne
    « 0,900 » réintroduite en Salle des machines passait les trois gardes.

    Rendue comme une LISTE de couples et non comme une table indexée par la valeur : deux
    cellules différentes s'écrivent parfois pareil — `splink_reference.f1` et
    `baseline.precision` valent tous deux 0,936 — et une table en perdait une, donc un
    paramètre du contrôle positif devenait introuvable.
    """
    valeurs = []
    for cle in ("splink_defaut", "splink_reference", "baseline"):
        for champ in ("precision", "rappel", "f1"):
            valeurs.append((fmt.nombre(modele[cle][champ]), f"{cle}.{champ}"))
    for cible in modele["cibles"]:
        valeurs.append((fmt.nombre(cible["reference_valeur"]),
                        f"cibles[{cible['code']}].reference_valeur"))
    valeurs.append((fmt.signe(modele["parite"]["ecart_f1"]), "parite.ecart_f1"))
    return valeurs


def _verifie_absence_des_chiffres_des_comparateurs(pages, modele):
    """Le corps de la garde, isolé pour qu'un contrôle positif puisse l'EXERCER.

    Sa première écriture réimplémentait le prédicat (`valeur in texte`) dans le contrôle
    positif au lieu d'appeler la garde : elle n'exerçait ni la boucle sur les surfaces, ni
    l'énumération des cellules. C'est le motif que ce fichier dit chasser, et il s'y était
    laissé prendre une fois de plus.
    """
    valeurs = _valeurs_de_comparateurs(modele)
    for surface in app.SURFACES_DE_VENTE:
        texte = _texte_visible(pages[surface])
        for ecrit, origine in valeurs:
            assert ecrit not in texte, (
                f"{surface} affiche {ecrit} — c'est {origine}, une valeur de comparateur. "
                f"La comparaison a quitte la face de vente.")


def test_les_chiffres_des_comparateurs_ne_sont_sur_aucune_surface_de_vente(pages, modele):
    """Garde STRUCTURELLE, et non de vocabulaire : les métriques des autres systèmes.

    Un tableau comparatif réintroduit sans une ligne de prose passerait le scan de
    vocabulaire sans être vu. Ici, ce sont les VALEURS qui sont interdites : le F1 du
    comparateur et celui des approches simples n'ont rien à faire sur une face de vente.
    """
    _verifie_absence_des_chiffres_des_comparateurs(pages, modele)


@pytest.mark.parametrize("injection", [
    "Notre moteur est au niveau des meilleurs outils du marché.",
    "Nous sommes à parité avec l'état de l'art.",
    "À la résolution de la mesure, les deux se valent.",
])
def test_controle_positif_une_comparaison_reintroduite_serait_vue(pages, injection):
    """CONTRÔLE POSITIF du scan de vocabulaire : chaque tournure de position doit mordre."""
    pollue = pages["salle_des_machines"].replace("</main>", f"<p>{injection}</p></main>")
    assert _comparaison_au_marche(_texte_visible(pollue)), (
        f"le scan ne voit pas {injection!r} : il ne garde rien")


@pytest.mark.parametrize("origine", ["splink_reference.f1", "baseline.rappel",
                                     "cibles[O2].reference_valeur", "parite.ecart_f1"])
def test_controle_positif_un_chiffre_de_comparateur_reintroduit_serait_vu(pages, modele,
                                                                          origine):
    """CONTRÔLE POSITIF de la garde structurelle, qui EXERCE la garde et non une copie.

    `cibles[O2].reference_valeur` est le paramètre qui compte : c'est la quatrième cellule de
    comparateur, celle que l'énumération recopiée à la main ne couvrait pas. Sans ce cas, le
    contrôle certifierait une couverture qui n'existe pas.
    """
    valeur = next(v for v, o in _valeurs_de_comparateurs(modele) if o == origine)
    assert valeur not in _texte_visible(pages["salle_des_machines"]), (
        f"{valeur} est deja sur la page : le controle positif ne distinguerait rien")
    polluees = dict(pages)
    polluees["salle_des_machines"] = pages["salle_des_machines"].replace(
        "</main>", f"<table><tr><td>autre système</td><td>{valeur}</td></tr></table></main>")
    with pytest.raises(AssertionError):
        _verifie_absence_des_chiffres_des_comparateurs(polluees, modele)


def test_le_dossier_technique_garde_la_comparaison_ENTIERE(pages, modele):
    """Le déplacement porte sur l'emplacement, jamais sur le contenu.

    C'est la condition qui rend le retrait tenable : si le dossier perdait la comparaison en
    même temps que la face de vente, `O5` et la loyauté de la comparaison tomberaient et il ne
    resterait qu'un escamotage. On exige donc que chaque valeur retirée de la vente soit AU dossier.
    """
    texte = _texte_visible(pages["dossier_technique"])
    for cle in ("splink_defaut", "splink_reference", "baseline"):
        for champ in ("precision", "rappel", "f1"):
            assert fmt.nombre(modele[cle][champ]) in texte, (
                f"{cle}.{champ} a disparu du dossier technique : la comparaison n'est plus "
                f"nulle part, et le retrait de la face de vente devient un escamotage")
    assert fmt.signe(modele["parite"]["ecart_f1"]) in texte
    assert "splink" in texte.lower(), "le dossier doit NOMMER le comparateur"


def test_la_salle_des_machines_dit_ou_la_comparaison_est_publiee(pages):
    """Retirer sans le dire serait cacher. La page nomme ce qu'elle a déplacé, et où."""
    texte = re.sub(r"\s+", " ", _texte_visible(pages["salle_des_machines"]))
    assert "comparaison chiffrée" in texte, (
        "la Salle des machines ne signale plus que la comparaison existe : le lecteur ne "
        "peut pas savoir qu'elle est au dossier, ni aller la vérifier")
    assert "/dossier-technique" in pages["salle_des_machines"]


# ============ L'encadré commercial, en tête de l'accueil (briefing, point 6) ============

#: Les onze exemples de l'encadré, dans l'ordre. La liste est ici pour une raison précise :
#: le contenu est VALIDÉ par l'owner et ne doit pas être raboté. Une passe d'écriture qui en
#: retirerait deux pour « alléger le premier écran » passerait tous les autres oracles.
TITRES_ENCADRE_COMMERCIAL = (
    "Vos fichiers, tels qu'ils sont",
    "Vos documents lus, triés, rapprochés",
    "Chaque euro payé en double, retrouvé",
    "Tous vos rapprochements",
    "Vos référentiels remis d'aplomb",
    "À votre échelle, à votre rythme",
    "Dans vos outils, pas à côté",
    "Vos équipes gardent la main",
    "De l'IA, oui — mais prouvée",
    # « recompté par un tiers » a été corrigé en « recompté indépendamment du moteur » : la
    # Vitrine écrit trois écrans plus bas « recompté par un programme séparé du moteur », et
    # son commentaire dit pourquoi « tiers indépendant » serait faux. Un titre ne rétablit pas
    # ce que le corps de la page a écarté.
    "Le résultat, recompté indépendamment du moteur",
    "Conforme, et vous pouvez le montrer",
)


def _bloc_encadre(html: str) -> str:
    """Le fragment HTML de l'encadré commercial, de sa balise ouvrante à sa fermeture."""
    debut = html.index('class="surmesure"')
    return html[debut:html.index("</section>", debut)]


def test_l_encadre_commercial_est_la_premiere_chose_vue(pages):
    """« Tout en haut de l'accueil » se vérifie par la POSITION, pas par la présence.

    Le placer sous l'accroche satisferait « présent » et manquerait la décision : c'est la
    première chose vue, avant les boutons qui mènent aux scénarios.
    """
    html = pages["vitrine"]
    assert html.index('class="surmesure"') < html.index('class="hero"'), (
        "l'encadre commercial n'est plus en tete de l'accueil")
    assert html.index('class="surmesure"') < html.index('href="/bac-a-sable"',
                                                        html.index("<main")), (
        "l'encadre commercial passe apres les boutons de parcours")


def test_l_encadre_commercial_est_replie_par_defaut(pages):
    """Titre et sous-titre à découvert, les onze exemples derrière un chevron replié."""
    bloc = _bloc_encadre(pages["vitrine"])
    assert "<details>" in bloc, "l'encadre n'a plus de section depliable"
    assert "<details open" not in bloc, (
        "l'encadre est deplie par defaut : le premier ecran de la Vitrine deborde")
    texte = re.sub(r"\s+", " ", _texte_visible(pages["vitrine"]))
    assert "Exemples de ce que nous pouvons mettre en place" in texte, (
        "le libelle de la section depliable a change : c'est lui qui cadre les onze points "
        "comme des exemples de sur-mesure plutot que comme des capacites livrees")


def test_l_encadre_commercial_porte_ses_onze_exemples_et_sa_cloture(pages):
    """Le contenu validé, entier : les onze points, le sous-titre, les deux lignes de fin."""
    texte = re.sub(r"\s+", " ", _texte_visible(pages["vitrine"]))
    manquants = [t for t in TITRES_ENCADRE_COMMERCIAL if t not in texte]
    assert not manquants, f"exemples rabotes de l'encadre commercial : {manquants}"
    assert "Ce démonstrateur est une version volontairement réduite." in texte, (
        "le sous-titre a disparu : c'est LUI qui dit que les onze points decrivent le "
        "sur-mesure et non ce que la demonstration fait deja")
    for cloture in ("Le même moteur s'applique partout où deux listes doivent se correspondre",
                    "le moteur peut les rapprocher, les dédoublonner, et vous prouver"):
        assert cloture in texte, f"ligne de cloture absente : {cloture!r}"


def test_le_badge_et_le_bouton_de_l_ancien_encadre_ont_disparu(pages):
    """Briefing, point 4 : ils n'ont plus lieu d'être, l'encadré ayant été remplacé."""
    texte = _texte_visible(pages["vitrine"])
    for retire in ("pistes sur mesure", "pas encore construites", "Décrire mon besoin"):
        assert retire not in texte, f"{retire!r} est encore sur la Vitrine"


def _plan_de_titres(html: str) -> list:
    """Les niveaux de titre, dans l'ordre du DOM. C'est ce plan qu'un lecteur d'écran parcourt."""
    return [int(n) for n in re.findall(r"<h([1-6])\b", html, flags=re.I)]


@pytest.mark.parametrize("surface", ["vitrine", "salle_des_machines", "bac_a_sable",
                                     "dossier_technique"])
def test_le_plan_de_titres_commence_par_un_h1_et_ne_saute_aucun_niveau(pages, surface):
    """Un plan de titres est une navigation, pas une décoration.

    Placer l'encadré commercial au-dessus du héros avait mis un `h2` et onze `h3` AVANT le
    `h1` de l'accueil : en navigation par titres — le mode normal d'un lecteur d'écran — la
    page s'ouvrait sur onze exemples avant d'annoncer de quoi elle parle. Le titre de premier
    niveau est donc celui de l'encadré, qui ouvre réellement la page, et l'accroche du héros
    est passée en `h2`.
    """
    plan = _plan_de_titres(pages[surface])
    assert plan, f"{surface} n'a aucun titre"
    assert plan[0] == 1, (
        f"{surface} commence son plan de titres par un h{plan[0]} : le lecteur d'ecran "
        f"entend une sous-section avant de savoir de quoi parle la page")
    assert plan.count(1) == 1, f"{surface} porte {plan.count(1)} titres de niveau 1"
    for precedent, suivant in zip(plan, plan[1:]):
        assert suivant <= precedent + 1, (
            f"{surface} saute du h{precedent} au h{suivant} : un niveau manque")


@pytest.mark.parametrize("plan_fautif", [
    "<h2>Exemples</h2><h1>Le titre</h1>",           # le défaut exact qui a motivé l'oracle
    "<h1>Le titre</h1><h3>Un point</h3>",           # niveau sauté
    "<h1>Un</h1><h2>Deux</h2><h1>Trois</h1>",       # deux titres de premier niveau
])
def test_controle_positif_un_plan_de_titres_fautif_serait_vu(plan_fautif):
    """CONTRÔLE POSITIF : chacune des trois propriétés doit être réellement gardée."""
    plan = _plan_de_titres(plan_fautif)
    faute = (plan[0] != 1 or plan.count(1) != 1
             or any(b > a + 1 for a, b in zip(plan, plan[1:])))
    assert faute, f"l'oracle du plan de titres ne voit pas {plan_fautif!r}"


# ============================ Aucun chiffre en dur ============================

#: Les seuls nombres que les gabarits ont le droit d'écrire, et pourquoi. La liste est courte
#: par construction : tout ce qui mesure quelque chose vient d'un artefact.
NOMBRES_DE_STRUCTURE = {
    "10": "denominateur de la projection « N doublons sur 10 » (regle d'ecriture)",
    "5": "budget annonce a l'utilisateur du bac a sable, en secondes (mandat C4)",
    "3": "nombre de decimales / enumerations de l'interface",
    "1": "articles et enumerations",
    "2": "enumerations",
}


def _valeurs_du_modele(modele: dict):
    """Toutes les chaînes et tous les nombres portés par le modèle d'affichage."""
    chaines, nombres = set(), set()

    def collecte(noeud):
        if isinstance(noeud, dict):
            for valeur in noeud.values():
                collecte(valeur)
        elif isinstance(noeud, list):
            for valeur in noeud:
                collecte(valeur)
        elif isinstance(noeud, str):
            if noeud.strip():
                chaines.add(noeud)
        elif isinstance(noeud, bool):
            pass
        elif isinstance(noeud, (int, float)):
            nombres.add(noeud)

    collecte(modele)
    return chaines, nombres


def _jetons_autorises(nombres) -> set:
    """Les écritures possibles des valeurs mesurées, réduites à leur partie numérique.

    On compare des JETONS ENTIERS, jamais par remplacement de sous-chaînes : effacer du texte
    toutes les écritures possibles reviendrait à y effacer « 9 », « 7 », « 0 »… et donc à
    dissoudre n'importe quel chiffre inventé. Un oracle qui efface avant de regarder ne
    regarde plus rien — c'est exactement ce que son contrôle positif a montré.
    """
    jetons = set()
    for valeur in nombres:
        ecritures = {str(valeur)}
        for decimales in range(0, 5):
            ecritures.add(fmt.nombre(valeur, decimales))
            ecritures.add(fmt.signe(valeur, decimales))
            ecritures.add(fmt.pourcent(valeur, decimales))
        if float(valeur).is_integer():
            ecritures.add(str(int(valeur)))
            ecritures.add(fmt.entier(int(valeur)))
            ecritures.add(str(int(valeur) * 100))
        # Un taux publié « en points » (0,15 -> 15) reste la même mesure, écrite autrement.
        produit = valeur * 100
        if abs(produit) < 1e6:
            for decimales in range(0, 3):
                ecritures.add(fmt.nombre(produit, decimales))
        for ecriture in ecritures:
            for jeton in re.findall(r"\d+(?:[.,]\d+)?", ecriture):
                jetons.add(jeton)
    return jetons


def _nombres_restants(texte: str, modele: dict) -> set:
    """Les jetons numériques du texte qui ne proviennent d'aucune valeur du modèle.

    Les chaînes du modèle (versions, empreintes, graines, énoncés gelés, valeurs
    d'enregistrements) sont retirées d'abord : elles sont longues et spécifiques, donc sûres
    à effacer. Ce qui reste est ensuite comparé jeton par jeton.
    """
    chaines, nombres = _valeurs_du_modele(modele)

    # Les chaînes du modèle, PUIS leurs préfixes. Les gabarits affichent des empreintes
    # tronquées (`empreinte[:16]`, `commit[:12]`) : le résultat n'est plus une chaîne du
    # modèle, mais il en est un préfixe, et ses fragments chiffrés ont donc bien une source.
    #
    # C'est la seule échappatoire, et elle est étroite par construction. La version
    # précédente autorisait tout jeton apparaissant N'IMPORTE OÙ dans la concaténation des
    # chaînes du modèle — soit 8 800 caractères incluant trois empreintes hexadécimales de
    # 40 signes. Résultat : « 42 » était couvert par un SHA de commit, « 99 » par
    # « REC_00099 », et un « 99 % » inventé en Vitrine passait au vert. Dix entiers d'un
    # chiffre sur dix et 84 sur 90 de deux chiffres échappaient à la garde qui porte tout le
    # mandat. Un préfixe est vérifiable ; une sous-chaîne quelconque ne l'est pas.
    fragments = set()
    for chaine in chaines:
        if len(chaine) >= 16 and re.fullmatch(r"[0-9a-fA-F]+", chaine):
            fragments.update(chaine[:k] for k in range(8, len(chaine)))
    for chaine in sorted(chaines | fragments, key=len, reverse=True):
        if len(chaine) < 4:          # trop court pour être effacé sans risque de tout raser
            continue
        texte = texte.replace(chaine, " ").replace(H.unescape(chaine), " ")

    # Le séparateur de milliers ne doit pas couper « 5 932 » en deux jetons.
    texte = re.sub(r"(?<=\d)[   ](?=\d{3}\b)", "", texte)

    autorises = _jetons_autorises(nombres)
    return {jeton for jeton in re.findall(r"\d+(?:[.,]\d+)?", texte)
            if jeton not in autorises}


@pytest.mark.parametrize("surface", ["vitrine", "salle_des_machines", "bac_a_sable"])
def test_aucun_chiffre_affiche_n_est_ecrit_en_dur(pages, modele, surface):
    restants = _nombres_restants(_texte_visible(pages[surface]), modele)
    orphelins = restants - set(NOMBRES_DE_STRUCTURE)
    assert not orphelins, (
        f"{surface} : nombres sans source dans un artefact : {sorted(orphelins)}. "
        f"Chaque valeur affichee doit etre lue du modele, jamais ecrite dans le gabarit.")


@pytest.mark.parametrize("injection", [
    "99,7 %",          # décimale
    "1 284 doublons",  # entier à quatre chiffres, séparateur de milliers
    "0,4242",          # décimale longue
    # `{n}` est remplacé par un entier à deux chiffres CHOISI absent du modèle : c'est la
    # classe qu'une promesse commerciale emploie, et fixer « 99 » ou « 42 » rendait le
    # contrôle dépendant des données — il a cassé deux fois quand un scénario a produit ces
    # nombres. Un contrôle positif qui rougit pour une raison étrangère finit désactivé.
    "{n} %",
    "{n} fichiers",
])
def test_controle_positif_un_chiffre_en_dur_serait_vu(pages, modele, injection):
    """CONTRÔLE POSITIF : l'oracle doit voir un nombre inventé glissé dans une page.

    Ce contrôle a échoué DEUX fois, et chaque échec a révélé une cécité réelle :
    1. la première écriture effaçait du texte toutes les écritures possibles des valeurs
       mesurées — donc « 9 », « 7 », « 0 » — et dissolvait le chiffre injecté ;
    2. la deuxième autorisait tout jeton apparaissant en sous-chaîne des 8 800 caractères de
       chaînes du modèle : « 42 » passait par un SHA de commit, « 99 » par « REC_00099 ».
       Les paramètres n'étaient alors que des décimales et des entiers longs — les seules
       formes que l'oracle savait voir. Il certifiait une couverture qu'il n'avait pas.
    Les petits entiers sont désormais paramétrés : ce sont EUX qu'un « 99 % des doublons »
    emploierait.

    Reste une cécité IRRÉDUCTIBLE, et il vaut mieux la nommer que la laisser croire couverte :
    un entier qui coïncide avec une valeur réelle du modèle (« 95 », « 100 », « 8 ») est
    indistinguable ici — les deux s'écrivent pareil. C'est
    `test_controle_positif_un_litteral_dans_un_gabarit_serait_vu` qui couvre cette classe, en
    regardant la source plutôt que le rendu.

    Les gabarits portant `{n}` reçoivent un entier à deux chiffres absent du modèle.
    """
    if "{n}" in injection:
        _, nombres = _valeurs_du_modele(modele)
        pris = _jetons_autorises(nombres) | set(NOMBRES_DE_STRUCTURE)
        libre = next((str(n) for n in range(10, 100) if str(n) not in pris), None)
        assert libre, "aucun entier a deux chiffres n'est libre : l'oracle ne peut rien prouver"
        injection = injection.replace("{n}", libre)
    pollue = pages["vitrine"].replace(
        "</main>", f"<p>Nous retrouvons {injection} des doublons.</p></main>")
    restants = _nombres_restants(_texte_visible(pollue), modele)
    orphelins = restants - set(NOMBRES_DE_STRUCTURE)
    assert orphelins, (
        f"l'oracle « aucun chiffre en dur » ne voit pas {injection!r} injecte : il ne garde rien")


def _litteraux_de_mesure(source: str) -> list:
    """Les nombres écrits EN TOUTES LETTRES dans le texte d'un gabarit, hors Jinja et balises.

    Deuxième garde, sur la SOURCE, et elle est nécessaire : l'oracle du rendu compare des
    jetons, donc il ne peut pas distinguer un « 95 % » inventé d'un 95 légitimement lu d'un
    artefact — les deux s'écrivent pareil. Ici, la question est différente et décidable : le
    gabarit a-t-il ÉCRIT un nombre, au lieu de le lire ? Les deux gardes se complètent
    exactement là où chacune est aveugle.
    """
    hors_jinja = re.sub(r"\{[\{%#].*?[\}%#]\}", " ", source, flags=re.S)
    hors_commentaires = re.sub(r"<!--.*?-->", " ", hors_jinja, flags=re.S)
    hors_balises = re.sub(r"<[^>]+>", " ", hors_commentaires)
    return [jeton for jeton in re.findall(r"\d+(?:[.,]\d+)?", hors_balises)
            if jeton not in NOMBRES_DE_STRUCTURE]


def test_les_gabarits_ne_contiennent_aucun_litteral_de_mesure():
    """Aucun gabarit n'écrit de nombre — décimale OU entier — hors ceux de structure."""
    dossier = os.path.join(_RACINE, "src", "surfaces", "gabarits")
    for nom in sorted(os.listdir(dossier)):
        if not nom.endswith(".html"):
            continue
        with open(os.path.join(dossier, nom), encoding="utf-8") as fh:
            litteraux = _litteraux_de_mesure(fh.read())
        assert not litteraux, f"{nom} ecrit des nombres en dur : {litteraux}"


@pytest.mark.parametrize("injection", [
    "<p>Nous retrouvons 95 % des doublons.</p>",
    "<p>Fiabilité de 100 % sur vos fichiers.</p>",
    "<p>8 clients sur 9 nous recommandent.</p>",
    "<p>0,919 de justesse.</p>",
    "<p>Plus de 1 284 fusions par jour.</p>",
])
def test_controle_positif_un_litteral_dans_un_gabarit_serait_vu(injection):
    """CONTRÔLE POSITIF de la garde de source : elle doit voir un nombre écrit dans le texte.

    Ce sont exactement les formes que l'oracle du rendu ne peut PAS distinguer (« 95 », « 100 »,
    « 8 » coïncident avec des valeurs réelles du modèle). Si cette garde-ci ne les voyait pas
    non plus, un chiffre commercial inventé n'aurait aucun gardien.
    """
    gabarit = ("{% extends \"base.html\" %}\n{% block contenu %}\n"
               + injection + "\n{% endblock %}\n")
    assert _litteraux_de_mesure(gabarit), (
        f"la garde de source ne voit pas {injection!r} : elle ne garde rien")


def test_la_garde_de_source_ne_crie_pas_sur_les_nombres_de_structure():
    """Elle doit rester silencieuse sur ce qui est déclaré structurel, sinon on la désactive."""
    assert not _litteraux_de_mesure(
        "<p>Plus de {{ v.chiffre_affiche.sur_dix }} doublons sur 10 retrouvés.</p>"
        "<p>Le résultat se recalcule sous cinq secondes.</p>")


# ============================ Déterminisme / C4 — le bac à sable ============================

def test_cc2_le_bac_a_sable_est_deterministe(modele, point):
    records = bac_a_sable.normalise_entree(modele["demonstration"]["extrait"]["records"])
    premier = bac_a_sable.execute(records, point)
    second = bac_a_sable.execute(records, point)
    assert premier["empreinte"] == second["empreinte"]
    assert premier["repartition"] == second["repartition"]


def test_cc2_le_determinisme_tient_d_un_processus_a_l_autre(modele):
    """Même entrée, même sortie — y compris dans un autre interpréteur, `PYTHONHASHSEED` libre.

    Le déterminisme intra-processus ne prouve rien sur un serveur qui redémarre : une seule
    itération sur un `set` suffirait à le rompre entre deux processus sans jamais le rompre
    dans un seul.
    """
    records = modele["demonstration"]["extrait"]["records"]
    programme = (
        "import sys, json; sys.path.insert(0, %r);"
        "from surfaces import bac_a_sable;"
        "from pipeline import point as pt;"
        "records = json.load(sys.stdin);"
        "p = pt.point_depuis_artefact(pt.CHEMIN_DIMS_V2, racine=%r);"
        "r = bac_a_sable.execute(bac_a_sable.normalise_entree(records), p);"
        "print(r['empreinte'])"
        % (os.path.join(_RACINE, "src"), _RACINE)
    )
    empreintes = set()
    for graine in ("0", "1"):
        env = dict(os.environ, PYTHONHASHSEED=graine)
        sortie = subprocess.run([sys.executable, "-c", programme],
                                input=json.dumps(records), capture_output=True,
                                text=True, env=env, cwd=_RACINE, timeout=180)
        assert sortie.returncode == 0, sortie.stderr[-2000:]
        empreintes.add(sortie.stdout.strip())
    assert len(empreintes) == 1, f"empreintes divergentes entre processus : {empreintes}"


def test_c4_le_bac_a_sable_tient_son_budget(modele, point):
    records = bac_a_sable.normalise_entree(modele["demonstration"]["extrait"]["records"])
    depart = time.perf_counter()
    resultat = bac_a_sable.execute(records, point)
    duree = time.perf_counter() - depart
    assert duree < 5.0, f"budget C4 depasse : {duree:.2f} s"
    assert resultat["duree_s"] < 5.0


def _jeu(n, cp_uniques=1, longueur=None):
    """Un jeu d'essai paramétré par les TROIS dimensions du coût : lignes, blocs, longueurs.

    `longueur` rembourre TOUS les attributs textuels, et non le seul nom : le coût est une
    somme sur les attributs comparés, et ne charger qu'un champ sur huit sous-estimait le pire
    cas d'un facteur six. C'est cette sous-estimation qui avait laissé croire que les plafonds
    se suffisaient à eux-mêmes.
    """
    def pad(base, i, suffixe):
        if not longueur:
            return base
        graine = f"{base} {i:04d} {suffixe} "
        return (graine * (longueur // len(graine) + 1))[:longueur]

    return [{
        "record_id": f"R{i:05d}", "source_id": "SRC_%d" % (i % 3),
        "nom": pad(f"Martin{i // 2}", i, "nom"), "prenom": pad("Catherine", i, "pre"),
        "date_naissance": "1980-01-01",
        "adresse": pad(f"{i // 2} rue de la Paix", i, "adr"),
        "code_postal": "%05d" % (75001 + i % cp_uniques), "ville": pad("Paris", i, "vil"),
        "email": pad(f"c.martin{i // 2}@example.fr", i, "ema"),
        "telephone": pad("01 23 45 67 %02d" % (i % 100), i, "tel"),
    } for i in range(n)]


def test_c4_une_entree_trop_lourde_en_paires_est_refusee_et_non_tronquee(point):
    """Le coût suit les paires : 150 lignes d'un même code postal dépassent le plafond."""
    with pytest.raises(bac_a_sable.BudgetDepasse) as capture:
        bac_a_sable.execute(bac_a_sable.normalise_entree(_jeu(150)), point)
    assert "paires" in str(capture.value)


def test_c4_une_valeur_demesuree_est_refusee(point):
    """Deux enregistrements suffisaient à occuper le serveur des minutes : le coût de la
    comparaison de chaînes est quadratique, et ni le nombre de lignes ni le nombre de paires
    ne le voit venir."""
    with pytest.raises(bac_a_sable.BudgetDepasse) as capture:
        bac_a_sable.normalise_entree(_jeu(2, longueur=50000))
    assert "caractères" in str(capture.value)


#: Nombre de mesures du pire régime admis. Une mesure de mur d'horloge date la CHARGE de la
#: machine autant que le coût du calcul : l'ordonnanceur ne peut qu'AJOUTER du temps, jamais en
#: retrancher. Le minimum de plusieurs mesures est donc l'estimateur de ce que la machine sait
#: faire, et le seul qui ne transforme pas une machine occupée en verdict produit. Trois suffit :
#: l'écart mesuré entre trois passages à vide est de 0,15 à 0,21 s, quand la contention observée
#: sous charge lourde ajoutait plus d'une seconde.
REPETITIONS_ETALONNAGE = 3


def test_c4_le_pire_regime_admis_tient_le_budget(point):
    """LA garde du budget : TOUTE entrée acceptée reste sous 5 s, sur les trois dimensions.

    Le coût a trois dimensions, et les éprouver une à une ne prouve rien sur leur produit :
    - les LIGNES, via le nombre de paires après blocking ;
    - la SÉPARABILITÉ, qui décide si l'estimation converge ou tourne jusqu'à sa borne (le
      débit y tombe d'un facteur 5) ;
    - la LONGUEUR des valeurs, qui entre au carré dans la comparaison de chaînes.
    On croise donc les trois. Chaque entrée est soit refusée, soit tenue par le budget : c'est
    la seule formulation qui ferme le trou du produit de plafonds indépendants.

    **Pourquoi le pire régime est re-mesuré.** Ce test a été vu rouge à 5,27 s alors que la
    machine portait douze tâches concurrentes, puis vert à 3,98 s sur la même machine au repos.
    Ce n'était donc pas le produit qui avait changé, mais la charge — et un oracle qui rend son
    verdict sur la charge du moment ne garde plus rien. On mesure le pire cas admis
    `REPETITIONS_ETALONNAGE` fois et l'on retient le MINIMUM. Le seuil de 5 s, lui, ne bouge
    pas : c'est le nombre affiché au visiteur, et le desserrer désadosserait silencieusement une
    promesse publiée.

    La répétition est INCONDITIONNELLE, et ce point est le cœur de l'affaire : re-mesurer
    seulement lorsque le premier passage dépasse serait un ré-essai jusqu'au vert, c'est-à-dire
    exactement la faute que ce dépôt proscrit. On applique un estimateur défini d'avance, dans
    tous les cas, y compris quand le premier passage suffisait.

    Grille mesurée sur la machine de build, au repos, trois passages (min → max) :
        (55, 1, 40) 3,54 → 3,75    (56, 1, 40) 3,71 → 3,90
        (57, 3, 39) 3,79 → 3,98    (57, 5, 39) 3,62 → 3,77
    Le pire régime admis tient donc en ~3,8 s, soit 20 % de marge sur le budget — et non les
    40 % qu'annonçait `src/surfaces/bac_a_sable.py`, dont le chiffre a été corrigé avec ce test.
    """
    pire, pire_cas, pire_records, admises = 0.0, None, None, 0
    cas = (
        (55, 1, None), (55, 5, None), (55, 10, None),   # régime EM lent, valeurs ordinaires
        (55, 1, 40), (35, 1, 60), (28, 1, 80), (11, 1, 200),   # frontière des longueurs
        # Les deux régimes les plus lents trouvés en revue : valeurs longues ET estimation qui
        # tourne jusqu'à sa borne. La grille précédente n'avait que `cp=1` sur les cas longs,
        # et manquait donc le croisement des deux dimensions coûteuses.
        (56, 1, 40), (57, 3, 39), (57, 5, 39),
        (30, 1, 200), (60, 1, 40),                             # au-delà : doivent être refusées
    )
    for n, cp, longueur in cas:
        records = bac_a_sable.normalise_entree(_jeu(n, cp, longueur))
        depart = time.perf_counter()
        try:
            resultat = bac_a_sable.execute(records, point)
        except bac_a_sable.BudgetDepasse:
            continue
        duree = time.perf_counter() - depart
        admises += 1
        assert resultat["n_paires"] <= bac_a_sable.PLAFOND_PAIRES
        assert (bac_a_sable.cout_comparaison(records, resultat["n_paires"])
                <= bac_a_sable.PLAFOND_COUT_COMPARAISON)
        if duree > pire:
            pire, pire_cas, pire_records = duree, (n, cp, longueur), records
    assert admises >= 6, "l'oracle ne prouve rien s'il refuse presque tout"

    # Le pire régime admis, re-mesuré et retenu au MINIMUM (cf. docstring). La première mesure
    # est celle de la grille : on ne la jette pas, on la complète.
    mesures = [pire]
    for _ in range(REPETITIONS_ETALONNAGE - 1):
        depart = time.perf_counter()
        bac_a_sable.execute(pire_records, point)
        mesures.append(time.perf_counter() - depart)
    tenu = min(mesures)
    assert tenu < 5.0, (
        f"le pire regime admis {pire_cas} prend {tenu:.2f} s au mieux de {len(mesures)} mesures "
        f"({', '.join(f'{m:.2f}' for m in mesures)}) : au-dela du budget de 5 s annonce au "
        f"visiteur. Ce n'est pas un alea de charge — le minimum l'a absorbe.")


def test_c4_le_budget_de_cout_est_load_bearing(point, monkeypatch):
    """CONTRÔLE POSITIF du budget de coût : sans lui, les trois autres plafonds laissent
    passer un calcul qui dépasse les cinq secondes.

    L'entrée ci-dessous respecte les TROIS plafonds pris séparément — moins de lignes que
    `PLAFOND_RECORDS`, moins de paires que `PLAFOND_PAIRES`, aucune valeur plus longue que
    `LONGUEUR_MAX_VALEUR`. Elle était donc acceptée, et prenait 5 s et plus. On le vérifie en
    désarmant le seul garde-fou qui la refuse : si le calcul tenait le budget, ce garde-fou
    serait gratuit et cet oracle le dirait.
    """
    brut = _jeu(30, 1, bac_a_sable.LONGUEUR_MAX_VALEUR)
    records = bac_a_sable.normalise_entree(brut)          # les trois plafonds l'acceptent
    assert len(records) <= bac_a_sable.PLAFOND_RECORDS
    assert max(len(v) for r in records for v in r.values() if v) \
        <= bac_a_sable.LONGUEUR_MAX_VALEUR

    with pytest.raises(bac_a_sable.BudgetDepasse) as capture:
        bac_a_sable.execute(records, point)
    assert "caractères" in str(capture.value)

    monkeypatch.setattr(bac_a_sable, "PLAFOND_COUT_COMPARAISON", 10 ** 15)
    depart = time.perf_counter()
    resultat = bac_a_sable.execute(records, point)
    duree = time.perf_counter() - depart
    assert resultat["n_paires"] <= bac_a_sable.PLAFOND_PAIRES     # le plafond de paires passe
    assert duree > 5.0, (
        f"le budget de cout ne prouve rien : desarme, l'entree tient en {duree:.2f} s")


def test_c4_toute_entree_acceptee_reste_sous_le_plafond_de_paires(point):
    """Aucune entrée acceptée ne doit dépasser le plafond : le refus se fait AVANT le calcul."""
    for n, cp in ((80, 1), (100, 5), (150, 10), (200, 20)):
        records = bac_a_sable.normalise_entree(_jeu(n, cp))
        try:
            resultat = bac_a_sable.execute(records, point)
        except bac_a_sable.BudgetDepasse:
            continue
        assert resultat["n_paires"] <= bac_a_sable.PLAFOND_PAIRES


def test_le_bac_a_sable_montre_les_trois_verdicts_et_sa_file_d_attente(modele, point):
    """L'extrait de démonstration doit exhiber un rapprochement, un doute et un rejet."""
    records = bac_a_sable.normalise_entree(modele["demonstration"]["extrait"]["records"])
    resultat = bac_a_sable.execute(records, point)
    assert resultat["repartition"]["MATCH"] >= 1
    assert resultat["repartition"]["ZONE_GRISE"] >= 1
    assert resultat["repartition"]["NON_MATCH"] >= 1
    assert resultat["a_verifier"], "la file « a verifier » doit etre visible"
    assert not resultat["estimation"]["repli"], (
        "l'extrait de demonstration ne doit pas replier : il montrerait des poids non calibres")
    assert any(len(e["membres"]) > 1 for e in resultat["entites"]), "aucune entite consolidee"


def test_le_bac_a_sable_refuse_une_entree_malformee(point):
    with pytest.raises(bac_a_sable.EntreeInvalide):
        bac_a_sable.normalise_entree([{"record_id": "A"}, {"record_id": "A"}])
    with pytest.raises(bac_a_sable.EntreeInvalide):
        bac_a_sable.normalise_entree([{"nom": "sans identifiant"}, {"record_id": "B"}])
    with pytest.raises(bac_a_sable.EntreeInvalide):
        bac_a_sable.normalise_entree([{"record_id": "A"}])


def test_le_bac_a_sable_projette_sur_les_seuls_champs_du_moteur(point):
    """Un champ inconnu ne doit pas laisser croire qu'il entre dans la décision."""
    records = bac_a_sable.normalise_entree([
        {"record_id": "A", "nom": "Durand", "chiffre_affaires": "1000000"},
        {"record_id": "B", "nom": "Durand", "chiffre_affaires": "2000000"},
    ])
    assert all("chiffre_affaires" not in record for record in records)


# ============================ Lecture : les gardes de la porte ============================

def test_une_cellule_s_adresse_par_son_identite_jamais_par_un_index():
    banc = lecture.charge(_RACINE)["banc"]
    cellule = lecture.cellule(banc, *vue.CELLULE_MOTEUR)
    assert cellule["systeme"] == "moteur_maison"
    assert cellule["point"] == "point_2_budget_de_revue_egal"


def test_une_selection_ambigue_est_refusee():
    """CONTRÔLE POSITIF de `cellule()` : deux résultats doivent lever, pas en choisir un."""
    banc = lecture.charge(_RACINE)["banc"]
    with pytest.raises(lecture.LectureImpossible):
        # Sans le bras, le couple (systeme, point) rend DEUX cellules : A et B.
        lecture.cellule(banc, "moteur_maison", "point_2_budget_de_revue_egal", bras=None)
    with pytest.raises(lecture.LectureImpossible):
        lecture.cellule(banc, "systeme_inexistant", "point_2_budget_de_revue_egal")


def test_une_cle_absente_leve_au_lieu_de_valoir_none():
    """`metriques["rappel"]` n'existe pas : un `.get` aurait affiché un tiret plausible."""
    banc = lecture.charge(_RACINE)["banc"]
    cellule = lecture.cellule(banc, *vue.CELLULE_MOTEUR)
    with pytest.raises(lecture.LectureImpossible):
        lecture.valeur(cellule, "metriques.rappel")
    assert lecture.valeur(cellule, "metriques.rappel_bout_en_bout") is not None


def test_la_convention_stricte_est_la_seule_exposee(modele):
    """Le cueillage le plus facile de l'artefact doit être impossible, pas déconseillé."""
    assert modele["moteur"]["convention"] == "stricte"
    assert "toutes_conventions" not in json.dumps(modele), (
        "le modele d'affichage expose toutes_conventions : une surface pourrait y piocher "
        "un F1 de 0,93 au lieu de 0,92 sans que rien ne le signale")


def test_l_artefact_de_demonstration_est_reproductible():
    """L'artefact des sorties moteur se régénère à l'identique — sinon il n'est pas une preuve.

    La comparaison passe par `empreinte_artefact`, la règle PARTAGÉE, et non plus par un retrait
    de champs réécrit ici. C'est exactement ce qui manquait : ce test-ci excluait le seul
    `commit`, quand le sceau publié en excluait déjà davantage — soit deux définitions
    concurrentes de « ce qui ne compte pas », la faute que `tools/empreinte_artefact.py` avait
    été écrit pour supprimer. Il gardait donc `version_python` dans ce qu'il comparait, et
    faisait rougir toute machine dont l'interpréteur n'était pas EXACTEMENT celui du build,
    alors que rien de mesuré n'avait bougé.
    """
    module = _empreinte_artefact()
    chemin = os.path.join(_RACINE, "artifacts", "ui_demonstration.json")
    with open(chemin, encoding="utf-8") as fh:
        publie = json.load(fh)
    sys.path.insert(0, os.path.join(_RACINE, "tools"))
    import produit_artefacts_ui as producteur
    recalcule = producteur.construit(racine=_RACINE)
    assert module.empreinte(publie) == module.empreinte(recalcule), (
        "artifacts/ui_demonstration.json ne se regenere pas a l'identique : relancer "
        "tools/produit_artefacts_ui.py")


def test_le_cas_heros_montre_vraiment_un_rapprochement_malgre_la_graphie(modele):
    """Le héros doit prouver quelque chose : deux fiches identiques ne démontreraient rien."""
    heros = modele["demonstration"]["cas_heros"]["correspondance"]
    assert heros["verdict"] == "MATCH"
    assert heros["champs_ecrits_differemment"], (
        "le cas heros a deux fiches ecrites a l'identique : il ne demontre rien")
    assert len(heros["champs_par_niveau"]["ACCORD_FORT"]) >= 3
    assert not heros["champs_par_niveau"]["DESACCORD"]
    # Et il doit illustrer CE QUE LA PAGE AFFIRME à côté de lui : une orthographe différente
    # sur l'identité. Sans cette exigence, le maximum retombait sur une paire dont seuls le
    # format de la date et l'espacement du téléphone changeaient — vrai, et hors sujet.
    assert any(a in heros["champs_ecrits_differemment"] for a in ("nom", "prenom")), (
        "le cas heros ne montre aucune graphie differente sur le nom ou le prenom : la "
        "carte n'illustre plus la promesse imprimee a trois centimetres d'elle")


def _verite_canonique_du_pack() -> tuple:
    """La vérité terrain, RELUE PAR L'ORACLE — jamais empruntée au programme qu'il juge.

    C'est ce qui distingue une vérification d'une signature : si cette fonction appelait
    `produit_artefacts_ui.verite_canonique`, elle certifierait que le producteur est
    d'accord avec lui-même. Elle relit donc le pack, vérifie son empreinte, et reconstruit la
    lignée pour son compte.
    """
    from benchmark import substrat
    with open(os.path.join(_RACINE, substrat.CHEMIN_FIXTURE), encoding="utf-8") as fh:
        pack = json.load(fh)
    assert substrat.empreinte_pack(pack) == substrat.CONTENT_SHA256_V1_2, (
        "la fixture n'est pas celle du mandat : l'oracle ne peut rien conclure")
    entite_de = {g["record_id"]: g["id_entite_vraie"] for g in pack["ground_truth"]}
    par_id = {r["record_id"]: r for r in pack["records"]}
    canoniques = {}
    for annotation in pack["corruption_annotation"]:
        if annotation.get("record_id_origine") is None:
            canoniques[entite_de[annotation["record_id"]]] = par_id[annotation["record_id"]]
    return canoniques, entite_de


def _valeurs_non_canoniques(dore, membres, champs) -> dict:
    """Les attributs où la fiche de référence s'écarte de la valeur canonique de l'entité."""
    canoniques, entite_de = _verite_canonique_du_pack()
    entites_vraies = {entite_de[record_id] for record_id in membres}
    assert len(entites_vraies) == 1, (
        f"l'entite du cas heros melange {len(entites_vraies)} entites vraies : la fiche de "
        f"reference presentee comme une reussite est une fusion erronee")
    canon = canoniques[next(iter(entites_vraies))]
    return {champ: (dore.get(champ), canon.get(champ))
            for champ in champs if dore.get(champ) != canon.get(champ)}


def test_la_fiche_de_reference_du_heros_ne_porte_aucune_valeur_corrompue(modele):
    """Le défaut fermé par le briefing de clôture : « Aubri » retenu pour « Aubry ».

    La fiche de référence du cas héros est l'écran censé prouver la valeur. Une graphie
    corrompue y suffit à retourner la démonstration contre elle-même — d'autant que le vrai
    nom était lisible, dans l'adresse de courriel affichée juste au-dessus.

    Le critère est déterministe et vérifiable : chaque valeur retenue doit être égale à celle
    de l'enregistrement d'origine de l'entité vraie, celui qu'aucune corruption de doublon
    n'a touché. Ce n'est pas « incontestablement juste » au jugé, c'est une égalité.
    """
    entite = modele["demonstration"]["cas_heros"]["entite"]
    ecarts = _valeurs_non_canoniques(
        entite["enregistrement_dore"], entite["membres"], modele["champs_compares"])
    assert not ecarts, (
        f"la fiche de reference du cas heros retient des valeurs non canoniques : {ecarts} "
        f"(retenu, canonique). C'est le defaut « Aubri / Aubry », revenu.")


@pytest.mark.parametrize("attribut", ["nom", "prenom", "telephone"])
def test_controle_positif_une_valeur_corrompue_en_fiche_de_reference_serait_vue(modele,
                                                                                attribut):
    """CONTRÔLE POSITIF : le détecteur doit voir une graphie corrompue qu'on lui soumet.

    On rejoue le défaut historique — une fusion qui retient la variante fautive plutôt que la
    valeur d'origine — sur trois attributs, et on exige que l'écart soit nommé. Un oracle qui
    ne verrait pas « Aubri » à la place d'« Aubry » certifierait toutes les fiches, y compris
    celle qui a motivé la correction.
    """
    entite = modele["demonstration"]["cas_heros"]["entite"]
    corrompue = dict(entite["enregistrement_dore"])
    assert corrompue.get(attribut), (
        f"le cas heros n'a pas de valeur sur {attribut} : le controle ne prouve rien")
    corrompue[attribut] = str(corrompue[attribut])[:-1] + "z"     # la graphie du doublon
    ecarts = _valeurs_non_canoniques(
        corrompue, entite["membres"], modele["champs_compares"])
    assert attribut in ecarts, (
        f"le detecteur ne voit pas une graphie corrompue sur {attribut} : il ne garde rien")


def _paires_separees_a_tort(correspondances, entite_de) -> list:
    """Les paires que le moteur a déclarées DISTINCTES et qui sont la même entité vraie.

    Isolé pour que le contrôle positif exerce ce prédicat-ci, et non une copie écrite dans
    son propre corps — deux gardes de ce fichier s'étaient déjà laissé prendre à cela.
    """
    return [(c["record_id_a"], c["record_id_b"]) for c in correspondances
            if c["verdict"] == "NON_MATCH"
            and entite_de[c["record_id_a"]] == entite_de[c["record_id_b"]]]


def test_l_extrait_du_bac_a_sable_ne_separe_aucune_paire_de_la_meme_personne(modele):
    """Aucun FAUX NÉGATIF montré comme une séparation correcte.

    Le bac à sable affiche les NON_MATCH de son extrait. Sur une paire qui est en vérité la
    même personne, la surface AFFIRME au visiteur « ce sont deux personnes différentes », et
    c'est faux — une phrase fausse sur un cas précis, pas une statistique optimiste.

    Le défaut s'est produit : en passant le filtre de canonicité du cas héros à
    `choisit_extrait`, l'extrait s'est recomposé et a ramené REC_00167 / REC_00168 — deux
    « Alexandre Lefebvre » nés le 28/02/1990, même entité vraie, séparés à l'écran. Personne
    ne l'avait vu, parce qu'aucun oracle ne regardait la répartition des verdicts de l'extrait.

    Ce n'est pas cacher le taux d'erreur : le rappel mesuré est publié en Vitrine (« plus de 9
    sur 10 ») et en Salle des machines, et c'est LUI qui dit combien de doublons échappent.
    """
    import engine
    from pipeline import point as pt
    sys.path.insert(0, os.path.join(_RACINE, "tools"))
    import produit_artefacts_ui as producteur

    _canoniques, entite_de = _verite_canonique_du_pack()
    records = modele["demonstration"]["extrait"]["records"]
    point_ = pt.point_depuis_artefact(producteur.CHEMIN_DIMS_V2, racine=_RACINE)
    resultat = engine.execute_moteur(records, point_.parametres_moteur())

    separees_a_tort = _paires_separees_a_tort(resultat["correspondances"], entite_de)
    assert not separees_a_tort, (
        f"l'extrait du bac a sable separe des fiches de la MEME personne : {separees_a_tort}. "
        f"La surface prononcerait une phrase fausse sur un cas precis.")
    # Et l'extrait doit toujours montrer les trois verdicts : la garde ci-dessus ne doit pas
    # avoir été satisfaite en vidant la démonstration de son NON_MATCH.
    verdicts = {c["verdict"] for c in resultat["correspondances"]}
    assert verdicts >= {"MATCH", "NON_MATCH", "ZONE_GRISE"}, (
        f"l'extrait ne montre plus les trois verdicts : {sorted(verdicts)}")


def test_controle_positif_un_faux_negatif_dans_l_extrait_serait_vu(modele):
    """CONTRÔLE POSITIF : le détecteur doit voir la paire exacte qui a motivé la garde.

    On lui soumet REC_00167 / REC_00168, l'extrait fautif d'origine, relu du pack. S'il ne la
    voyait pas, la garde ci-dessus serait au vert sur l'extrait qu'elle est censée refuser.
    """
    _canoniques, entite_de = _verite_canonique_du_pack()
    assert entite_de["REC_00167"] == entite_de["REC_00168"], (
        "la paire du controle positif n'est plus une meme entite vraie dans le pack : "
        "le controle ne prouve plus rien")
    historique = [{"record_id_a": "REC_00167", "record_id_b": "REC_00168",
                   "verdict": "NON_MATCH"},
                  {"record_id_a": "REC_00024", "record_id_b": "REC_00025",
                   "verdict": "MATCH"}]
    vues = _paires_separees_a_tort(historique, entite_de)
    assert vues == [("REC_00167", "REC_00168")], (
        f"le predicat de la garde ne voit pas le faux negatif historique : {vues}")


def test_les_reserves_sont_toutes_publiees_au_dossier(modele, pages):
    """Les six limites du banc sont publiées INTÉGRALEMENT — au dossier technique.

    L'écart de positionnement porte sur l'EMPLACEMENT, jamais sur le contenu : c'est la
    condition posée par la décision owner, et c'est ce test qui la tient.
    """
    texte = _texte_visible(pages["dossier_technique"])
    assert len(modele["reserves"]) >= 6
    for limite in modele["reserves"]:
        extrait = (limite if isinstance(limite, str)
                   else (limite.get("quelle") or limite.get("libelle") or ""))
        assert extrait[:40] in texte, f"reserve absente du dossier : {extrait[:60]!r}"


def test_le_verdict_global_est_publie_EN_TETE_du_dossier(modele, pages):
    """`O5` exige le verdict « publié en tête, avant tout détail favorable ». On le vérifie
    par la POSITION, pas seulement par la présence : reléguer le verdict sous le tableau de
    comparaison satisferait « publié » et violerait le critère."""
    texte = _texte_visible(pages["dossier_technique"])
    statut = modele["verdict_global"]["statut"]
    assert statut in texte, "le verdict global n'est pas publie au dossier technique"
    for cible in modele["verdict_global"]["cibles_en_echec"]:
        assert cible in texte, f"cible en echec non publiee : {cible}"

    position_verdict = texte.index(statut)
    for favorable in (fmt.nombre(modele["moteur"]["f1"]),
                      fmt.signe(modele["parite"]["ecart_f1"])):
        assert position_verdict < texte.index(favorable), (
            "le verdict doit precéder tout detail favorable (critere O5)")


def test_la_distinction_obligatoire_est_citee_verbatim(modele, pages):
    """« la chaîne de revue n'a rien produit » n'est pas « un adjudicateur n'a rien trouvé ».

    La distinction est gelée dans l'artefact et doit figurer telle quelle. La Salle des
    machines ne porte plus ce bloc ; le dossier, lui, le doit — sans quoi le déplacement
    aurait effacé la nuance au lieu de la ranger.
    """
    texte = _texte_visible(pages["dossier_technique"])
    distinction = modele["revue"]["distinction"]
    # 60 caracteres ne portaient PAS la nuance : ils s'arretaient avant les deux lectures
    # qu'il faut opposer. On exige la chaine ENTIERE, et explicitement les deux membres.
    assert distinction in texte, "la distinction obligatoire n'est pas citee INTEGRALEMENT"
    for membre in ("chaine de revue n'a rien produit", "adjudicateur"):
        assert membre in texte, f"la distinction perd son membre {membre!r}"


def test_les_enonces_pre_enregistres_des_TROIS_cibles_sont_rendus(modele, pages):
    """La cible ATTEINTE porte le positionnement : perdre son énoncé gelé en silence était le
    plus coûteux des trois oublis possibles."""
    texte = _texte_visible(pages["dossier_technique"])
    for cible in modele["cibles"]:
        assert cible["enonce"], f"cible {cible['code']} sans enonce pre-enregistre"
        assert cible["enonce"][:50] in texte, (
            f"l'enonce gele de {cible['code']} n'est pas rendu au dossier")


def test_le_bac_a_sable_avertit_que_les_seuils_ne_sont_pas_ceux_du_visiteur(pages):
    """Seule page où le visiteur saisit SES lignes et reçoit un verdict : sans cet
    avertissement, il repart en croyant que le moteur a été réglé pour ses données."""
    # Les espaces sont normalisés : le gabarit coupe ses lignes, et une phrase vraie mais
    # coupée ferait rougir un test qui ne cherche pas ce qu'il croit chercher.
    texte = re.sub(r"\s+", " ", _texte_visible(pages["bac_a_sable"]))
    assert "pas sur le vôtre" in texte, "l'avertissement sur les seuils a disparu"
    assert "démonstration du mécanisme" in texte
    assert "réglés sur un jeu de référence" in texte


@pytest.mark.parametrize("surface", ["vitrine", "salle_des_machines"])
def test_les_surfaces_de_vente_pointent_vers_le_dossier(pages, surface):
    """Un dossier sans lien visible serait un dossier caché — la ligne à ne pas franchir.

    La Vitrine a été ajoutée à cette garde : elle n'y menait qu'en DEUX sauts, par la Salle
    des machines, alors que c'est elle qui porte le chiffre d'affiche. Le lecteur qui doute
    d'un chiffre doute au moment où il le lit.

    Le bac à sable en est exclu à dessein : c'est une page où l'on FAIT, pas où l'on lit, et
    elle mène à la Salle des machines, qui mène au dossier. Le jour où on voudrait l'y
    ajouter, c'est cette liste qu'il faut changer, pas la garde.
    """
    assert "/dossier-technique" in pages[surface], (
        f"{surface} doit pointer vers le dossier technique")


def test_le_dossier_ramene_a_la_salle_des_machines(pages):
    """Aucun cul-de-sac : depuis le dossier, on revient."""
    assert "/salle-des-machines" in pages["dossier_technique"]


@pytest.mark.parametrize("surface", ["vitrine", "salle_des_machines", "bac_a_sable",
                                     "dossier_technique"])
def test_chaque_page_ramene_a_l_accueil(pages, surface):
    """La navigation est un outil de vente : jamais d'écran d'où l'on ne sait pas revenir."""
    html = pages[surface]
    assert re.search(r'href="/"', html), f"{surface} n'offre aucun retour a l'accueil"


# ============================ Les scénarios ============================

def test_les_trois_scenarios_montrent_un_vrai_nettoyage(modele):
    """L'écart avant → après doit être franc : c'est le signal « ça a marché »."""
    assert len(modele["scenarios"]) == 3
    for scenario in modele["scenarios"]:
        assert scenario["n_lignes"] > scenario["n_fiches_uniques"], (
            f"{scenario['cle']} : aucun nettoyage visible")
        assert scenario["n_consolidees"] >= 1, f"{scenario['cle']} : aucun groupe consolide"
        assert scenario["n_deja_uniques"] >= 1, f"{scenario['cle']} : aucune fiche deja unique"
        assert scenario["a_confirmer"], f"{scenario['cle']} : aucun doute a soumettre"
        assert scenario["fichiers"], f"{scenario['cle']} : aucun fichier d'entree"
        assert sum(f["n_lignes"] for f in scenario["fichiers"]) == scenario["n_lignes"], (
            f"{scenario['cle']} : les cartes de fichiers ne totalisent pas les lignes")


def test_aucun_vrai_doublon_ne_dort_dans_deja_uniques(modele):
    """La section « déjà uniques » ne doit contenir AUCUN doublon réel.

    C'est la mesure qui autorise à garder cette section : une non-détection présentée comme
    un résultat propre serait une réussite affichée là où il y a un échec. On confronte donc
    la partition du moteur à la vérité terrain — celle du pack du générateur pour les particuliers,
    le SIRET pour les entreprises, où l'identité est connue par construction.

    Le nombre de vraies paires n'est pas écrit dans cette docstring : il y était, faux d'une
    version à l'autre — « 328 » quand le compte reproductible en donnait 325. Un commentaire
    chiffré se périme en silence ; ici, le total est COMPTÉ à l'exécution et gardé par un
    plancher, de sorte qu'un jeu qui rétrécirait sous ce plancher ferait rougir l'oracle au
    lieu de le rendre vide.
    """
    sys.path.insert(0, os.path.join(_RACINE, "tools"))
    import produit_scenarios as producteur
    import generator

    total_vraies_paires = 0
    par_cle = {s["cle"]: s for s in modele["scenarios"]}
    for config in producteur.SCENARIOS:
        scenario = par_cle[config["cle"]]
        if config["genre"] == "entreprises":
            verite = dict(scenario["sirets"])
        else:
            pack = generator.generate_pack(seed=config["graine"],
                                           n_entities=config["n_entites"])
            verite = {g["record_id"]: g["id_entite_vraie"] for g in pack["ground_truth"]}

        # Où chaque enregistrement a été rangé. Restreint aux PRÉSENTS : les entités écartées
        # (personnes morales) ne sont pas dans le scénario, et les compter ferait mesurer une
        # faute qui n'existe pas — le premier jet de cette mesure s'y était laissé prendre.
        place = {}
        for indice, groupe in enumerate(scenario["consolidees"]):
            for record in groupe["records"]:
                place[record["record_id"]] = ("groupe", indice)
        for record in scenario["deja_uniques"]:
            place[record["record_id"]] = ("seul", record["record_id"])

        verite = {rid: e for rid, e in verite.items() if rid in place}
        par_entite = {}
        for rid, entite in verite.items():
            par_entite.setdefault(entite, []).append(rid)

        seules_a_tort = [rid for rid in (r["record_id"] for r in scenario["deja_uniques"])
                         if len(par_entite.get(verite.get(rid), [])) > 1]
        assert not seules_a_tort, (
            f"{config['cle']} : {len(seules_a_tort)} fiches rangees « deja uniques » alors "
            f"qu'elles ont un doublon reel — la section affiche une reussite la ou il y a un "
            f"echec : {seules_a_tort[:5]}")

        vraies_paires = [(membres[i], membres[j]) for membres in par_entite.values()
                         for i in range(len(membres)) for j in range(i + 1, len(membres))]
        total_vraies_paires += len(vraies_paires)
        manquees = sum(1 for a, b in vraies_paires if place[a] != place[b])
        assert manquees == 0, (
            f"{config['cle']} : {manquees} vraies paires non regroupees (entites scindees)")

    # Le plancher, et non le compte exact : le compte est une donnée du jeu, pas une propriété
    # à figer. Ce que l'oracle doit garantir, c'est qu'il a MESURÉ quelque chose — une mesure
    # sur zéro paire passerait au vert en ne prouvant rien.
    assert total_vraies_paires >= 300, (
        f"seulement {total_vraies_paires} vraies paires confrontees a la verite terrain : "
        f"la mesure de non-detection ne porte plus sur assez de matiere pour conclure")


def test_les_scenarios_de_particuliers_ne_contiennent_aucune_societe(modele):
    """Un scénario vendu « le même CLIENT revient plusieurs fois » ne doit montrer que des
    particuliers.

    Le générateur tire environ 15 % de personnes morales — ni prénom, ni ville, mais une
    date de naissance. Non filtrées, elles affichaient « date de naissance : 13/12/2003 » sous
    un nom de SARL, sur la surface dont le seul travail est d'avoir l'air vrai. La correction
    filtre ces entités dans l'outil de scénarios ; rien ne le vérifiait, et un filtre que rien
    ne vérifie se défait au premier remaniement du générateur.

    La signature testée est celle du filtre : pas de prénom ET pas de ville. On la mesure sur
    les enregistrements PUBLIÉS, pas sur le code qui les produit.
    """
    sys.path.insert(0, os.path.join(_RACINE, "tools"))
    import produit_scenarios as producteur

    genres = {config["cle"]: config["genre"] for config in producteur.SCENARIOS}
    assert set(genres.values()) == {"personnes", "entreprises"}, (
        "les deux genres doivent exister : un oracle qui ne compare rien ne prouve rien")

    for scenario in modele["scenarios"]:
        enregistrements = list(scenario["deja_uniques"])
        for groupe in scenario["consolidees"]:
            enregistrements += groupe["records"]
        for doute in scenario["a_confirmer"]:
            enregistrements += [doute["record_a"], doute["record_b"]]

        morales = [r for r in enregistrements
                   if r.get("prenom") is None and r.get("ville") is None]
        if genres[scenario["cle"]] == "personnes":
            assert not morales, (
                f"{scenario['cle']} : {len(morales)} enregistrements sans prenom ni ville — "
                f"des personnes morales dans un scenario de particuliers : "
                f"{[r['record_id'] for r in morales[:5]]}")
            # Et l'inverse : un scénario de particuliers doit VRAIMENT porter des prénoms.
            assert sum(1 for r in enregistrements if r.get("prenom")) > len(enregistrements) // 2
        else:
            # CONTRÔLE POSITIF par contraste : le scénario entreprises, lui, n'a AUCUN prénom.
            # Si la signature testée ne distinguait rien, les deux branches passeraient.
            assert not any(r.get("prenom") for r in enregistrements), (
                f"{scenario['cle']} : un scenario d'entreprises ne porte pas de prenom")
            assert not any(r.get("date_naissance") for r in enregistrements), (
                f"{scenario['cle']} : une societe n'a pas de date de naissance")


def test_le_siret_n_entre_jamais_dans_le_moteur(modele):
    """Le moteur compare huit attributs, et le SIRET n'en fait pas partie.

    La garde est STRUCTURELLE : le SIRET est porté dans une table à part, et aucun
    enregistrement passé au moteur n'en contient. C'est ce qui rend impossible d'écrire un
    jour « le moteur a vu que les SIRET diffèrent » — la donnée n'y est pas.
    """
    champs_moteur = set(modele["champs_compares"]) | {"record_id", "source_id"}
    for scenario in modele["scenarios"]:
        enregistrements = list(scenario["deja_uniques"])
        for groupe in scenario["consolidees"]:
            enregistrements += groupe["records"]
        for doute in scenario["a_confirmer"]:
            enregistrements += [doute["record_a"], doute["record_b"]]
        for record in enregistrements:
            hors = set(record) - champs_moteur
            assert not hors, f"{scenario['cle']} : un enregistrement porte {hors} vers le moteur"
    assert "siret" not in json.dumps(modele["champs_compares"]).lower()


def test_le_scenario_fournisseurs_expose_un_doute_ou_le_siret_tranche(modele):
    """L'argument finance : le moteur hésite sur ce qu'il compare, le SIRET tranche pour
    l'humain. Si aucun cas ne le montre, le scénario ne raconte plus rien."""
    fournisseurs = next(s for s in modele["scenarios"] if s["cle"] == "fournisseurs")
    parlants = [d for d in fournisseurs["a_confirmer"]
                if d["siret_a"] and d["siret_b"] and d["siret_a"] != d["siret_b"]]
    assert parlants, "aucun cas a confirmer ou le SIRET departage"
    assert any("nom" in d["preuve"]["concordent"] for d in parlants), (
        "le doute montre doit etre LISIBLE : deux fiches dont le nom concorde")


def test_aucune_fusion_ne_reunit_deux_siret_differents(modele):
    """Le moteur ne doit pas fusionner deux entreprises distinctes dans la démonstration.

    Une fusion fautive visible détruirait précisément l'argument de confiance du scénario
    fournisseurs. Ce test garde la DONNÉE : si une évolution du jeu réintroduisait une
    coïncidence qui fait fusionner deux SIRET, il rougit.
    """
    fournisseurs = next(s for s in modele["scenarios"] if s["cle"] == "fournisseurs")
    sirets = fournisseurs["sirets"]
    for groupe in fournisseurs["consolidees"]:
        distincts = {sirets.get(r["record_id"]) for r in groupe["records"]
                     if sirets.get(r["record_id"])}
        assert len(distincts) <= 1, (
            f"fusion fautive : {[r['nom'] for r in groupe['records']]} porte {distincts}")


def test_les_scenarios_sont_reproductibles():
    """Même scénario, même résultat : la démonstration ne bouge pas d'une exécution à l'autre.

    Comme pour l'artefact de démonstration, la comparaison passe par la règle partagée plutôt
    que par un retrait de champs recopié ici — un seul endroit dit ce que le sceau couvre.
    """
    module = _empreinte_artefact()
    sys.path.insert(0, os.path.join(_RACINE, "tools"))
    import produit_scenarios as producteur
    publie = json.load(open(os.path.join(_RACINE, "artifacts", "ui_scenarios.json"),
                            encoding="utf-8"))
    recalcule = producteur.construit()
    assert module.empreinte(publie) == module.empreinte(recalcule), (
        "artifacts/ui_scenarios.json ne se regenere pas a l'identique : "
        "relancer tools/produit_scenarios.py")


#: Les deux artefacts d'interface qui publient une `empreinte_contenu`.
ARTEFACTS_SCELLES = ("artifacts/ui_demonstration.json", "artifacts/ui_scenarios.json")


def _empreinte_artefact():
    sys.path.insert(0, os.path.join(_RACINE, "tools"))
    import empreinte_artefact
    return empreinte_artefact


@pytest.mark.parametrize("chemin", ARTEFACTS_SCELLES)
def test_l_empreinte_publiee_correspond_au_contenu_publie(chemin):
    """La garantie d'intégrité doit être VÉRIFIÉE, pas seulement affichée.

    `empreinte_contenu` est présenté dans les deux artefacts comme leur sceau : un lecteur
    doit pouvoir le recalculer depuis le fichier qu'il tient. Personne ne le recalculait —
    ni ici, ni ailleurs. Un champ produit, publié, présenté comme garantie, et que rien ne
    vérifie, n'est pas une garantie faible : c'est une affirmation.
    """
    module = _empreinte_artefact()
    with open(os.path.join(_RACINE, chemin), encoding="utf-8") as fh:
        contenu = json.load(fh)
    assert contenu.get("empreinte_contenu"), f"{chemin} ne publie pas d'empreinte"
    assert module.verifie(contenu), (
        f"{chemin} : l'empreinte publiee ne correspond pas a son contenu "
        f"(publiee {contenu['empreinte_contenu'][:16]}, recalculee "
        f"{module.empreinte(contenu)[:16]}). Relancer le producteur.")
    assert contenu.get("_note_empreinte") == module.NOTE, (
        f"{chemin} : la note qui dit ce que l'empreinte couvre doit accompagner l'empreinte")


@pytest.mark.parametrize("chemin", ARTEFACTS_SCELLES)
def test_controle_positif_une_valeur_modifiee_casserait_l_empreinte(chemin):
    """CONTRÔLE POSITIF : le sceau doit se briser si l'on touche à ce qu'il scelle.

    On modifie une valeur affichée — la première chaîne rencontrée en profondeur — et on
    exige que l'empreinte ne suive plus. Sans ce contrôle, une empreinte calculée sur un
    sous-ensemble vide passerait toutes les vérifications du monde.
    """
    module = _empreinte_artefact()
    with open(os.path.join(_RACINE, chemin), encoding="utf-8") as fh:
        contenu = json.load(fh)

    def altere(noeud):
        """Modifie la première chaîne non technique trouvée. Rend True si quelque chose a bougé."""
        if isinstance(noeud, dict):
            for cle, valeur in noeud.items():
                if cle in ("empreinte_contenu", "_note_empreinte", "commit",
                           "version_python", "duree_calcul_build_s"):
                    continue
                if isinstance(valeur, str) and valeur:
                    noeud[cle] = valeur + "!"
                    return True
                if altere(valeur):
                    return True
        elif isinstance(noeud, list):
            for element in noeud:
                if altere(element):
                    return True
        return False

    assert altere(contenu), "rien a alterer dans l'artefact : le controle ne prouverait rien"
    assert not module.verifie(contenu), (
        f"{chemin} : une valeur modifiee ne casse pas l'empreinte — elle ne scelle rien")


@pytest.mark.parametrize("chemin", ARTEFACTS_SCELLES)
def test_l_empreinte_ignore_la_provenance_et_la_duree_de_build(chemin):
    """Ce que l'empreinte EXCLUT doit être exclu des deux côtés, et pour la même raison.

    La règle divergeait entre les deux producteurs : `ui_scenarios.json` excluait le commit,
    `ui_demonstration.json` le hachait. La même promesse couvrait donc deux comportements —
    l'un reproductible d'un commit à l'autre, l'autre non.

    `version_python` a rejoint la liste, et pour un motif MESURÉ, non par symétrie : tant qu'il
    était scellé, les deux artefacts ne se régénéraient à l'identique que sur l'interpréteur
    exact du build. Rejoués sur Python 3.12.7 (numpy 1.26) et sur Python 3.14.3 (sans numpy,
    tables Unicode 16.0) contre le build en 3.12.14 (numpy 2.5, Unicode 15.0), ils sortaient
    identiques partout ailleurs — le sceau attestait donc l'environnement, pas la matière.
    C'est la règle qu'applique déjà `tools/banc_ub6.py`, qui exclut tout son bloc `provenance`.
    """
    module = _empreinte_artefact()
    with open(os.path.join(_RACINE, chemin), encoding="utf-8") as fh:
        contenu = json.load(fh)
    reference = module.empreinte(contenu)

    contenu["provenance"]["commit"] = "0" * 40
    contenu["provenance"]["version_python"] = "0.0.0"
    for scenario in contenu.get("scenarios", []):
        scenario["duree_calcul_build_s"] = 999.0
    assert module.empreinte(contenu) == reference, (
        f"{chemin} : l'empreinte suit le commit, la version de Python ou la duree de build — "
        f"elle change alors que rien d'affiche ne change, et un lecteur qui n'a pas exactement "
        f"l'environnement du build ne peut plus la reproduire")
    # Et les champs exclus restent PUBLIÉS : exclure du sceau n'est pas retirer du fichier.
    assert "commit" in contenu["provenance"]
    assert "version_python" in contenu["provenance"]


#: Le fichier de logique PURE du client, celui que le navigateur charge et que Node exécute.
CHEMIN_LOGIQUE_JS = os.path.join(_RACINE, "src", "surfaces", "statique", "logique.js")
CHEMIN_BAC_JS = os.path.join(_RACINE, "src", "surfaces", "statique", "bac.js")


def _source_bac_js() -> str:
    with open(CHEMIN_BAC_JS, encoding="utf-8") as fh:
        return fh.read()


def _exports_de_logique_js() -> set:
    """Ce que `module.exports` expose RÉELLEMENT — la liste que Node charge.

    Lire les déclarations `function` à la place donnait un sur-ensemble : une fonction
    déclarée mais absente de l'export aurait été servie au navigateur sans qu'aucun oracle
    puisse l'atteindre, et la liste aurait paru complète.
    """
    with open(CHEMIN_LOGIQUE_JS, encoding="utf-8") as fh:
        source = fh.read()
    bloc = re.search(r"module\.exports\s*=\s*\{(.*?)\}", source, re.S)
    assert bloc, "logique.js n'expose plus rien : les oracles ne peuvent plus rien charger"
    return set(re.findall(r"\b(\w+)\b", bloc.group(1)))


def _node_disponible() -> bool:
    try:
        return subprocess.run(["node", "--version"], capture_output=True,
                              timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


#: Résolu une fois : chaque appel relançait `node --version`, six fois par exécution.
_NODE_PRESENT = _node_disponible()

_MOTIF_SANS_NODE = (
    "Node absent : les oracles du client ne peuvent pas executer logique.js. "
    "Node est une dependance de TEST declaree (ENV_SETUP_README.md, section « Node.js ») ; "
    "sans lui, la prose et l'arithmetique du navigateur ne sont pas gardees.")

#: Le nom de la variable, écrit UNE fois. `tools/job_ci.py` la pose, ce fichier la lit, et un
#: oracle vérifie que les deux parlent du même nom ET de la même valeur : une faute de frappe
#: d'un seul côté désarmerait la garde sans rien casser d'autre.
NOM_VAR_NODE_EXIGE = "MR_NODE_REQUIS"

#: Posée par `tools/job_ci.py`. Elle dit : ici, l'absence de Node n'est
#: pas une circonstance, c'est une panne. Sans elle, un job qui installe Node, le rate en
#: silence et voit ces oracles sauter rend un code 0 — vert, et n'ayant rien exécuté. Un
#: `skipped` est un résultat parfaitement honnête sur un poste ; dans un job dont la raison
#: d'être est d'exécuter ces oracles-là, c'est un vert qui ne porte sur rien.
_NODE_EXIGE = os.environ.get(NOM_VAR_NODE_EXIGE) == "1"

_MOTIF_NODE_EXIGE = (
    "Node est EXIGE (MR_NODE_REQUIS=1) et absent : les oracles du client n'ont pas tourne. "
    "Le job les compte comme executes ; les laisser sauter rendrait un vert qui ne porte sur "
    "rien. Remede : installer Node (ENV_SETUP_README.md, section « Node.js ») ou, hors job, "
    "ne pas poser MR_NODE_REQUIS.")


def _conduite_sans_node(node_present, node_exige):
    """Que faire quand Node manque ? Fonction PURE, pour que ses quatre cas soient éprouvés.

    Écrire la décision en ligne, dans le décorateur ET dans le point de passage, la rendrait
    intestable : on ne peut pas, depuis cette suite, relancer pytest sans Node — le lancement
    de sous-processus y est réservé à trois fonctions nommées (`_LANCEURS_AUTORISES`), et un
    oracle le vérifie. La décision sort donc ici, où un contrôle positif l'appelle directement
    sur ses quatre entrées.
    """
    if node_present:
        return "executer"
    return "echouer" if node_exige else "sauter"


#: Marqueur informatif, pour que le rapport de collecte dise pourquoi ces oracles sautent.
#: Il n'est PAS le garde-fou : la garantie est `_execute_fichier_logique` ci-dessous, qui
#: saute quoi qu'il arrive. La revue a trouvé ce marqueur posé sur 2 tests appelant Node
#: sur 6 — un garde-fou qu'il faut penser à recopier n'en est pas un.
#: Sous `MR_NODE_REQUIS`, il ne saute plus : le test part, atteint le point de passage, et y
#: échoue — un rouge nommé plutôt qu'un vert silencieux.
_SANS_NODE = pytest.mark.skipif(
    _conduite_sans_node(_NODE_PRESENT, _NODE_EXIGE) == "sauter", reason=_MOTIF_SANS_NODE)


def _execute_fichier_logique(chemin_js, appels):
    """Le POINT DE PASSAGE UNIQUE vers Node. Saute proprement si Node est absent.

    Deux choses tenaient ici par convention, et la revue a montré qu'aucune ne tenait :
    - la garde d'absence de Node reposait sur un décorateur à recopier sur chaque test ; il
      manquait sur quatre des six, qui tombaient en `FileNotFoundError` — un échec qui se lit
      comme une régression du produit alors qu'il ne dit que « Node n'est pas installé » ;
    - le contrôle positif de mutation refaisait son propre appel à `node`, hors de tout garde.
    Les deux passent désormais par ici, et la garde est structurelle : on ne peut plus appeler
    Node depuis cette suite sans être gardé.
    """
    conduite = _conduite_sans_node(_NODE_PRESENT, _NODE_EXIGE)
    if conduite == "echouer":
        pytest.fail(_MOTIF_NODE_EXIGE)
    if conduite == "sauter":
        pytest.skip(_MOTIF_SANS_NODE)
    # Avec `node -e`, les arguments de l'utilisateur commencent à argv[1] : il n'y a pas de
    # chemin de script à la position 1 comme lors d'un `node fichier.js`.
    driver = (
        "const L = require(process.argv[1]);"
        "const appels = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));"
        "const sorties = appels.map(a => L[a.fn].apply(null, a.args));"
        "process.stdout.write(JSON.stringify(sorties));"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8",
                                     delete=False) as fh:
        json.dump(appels, fh, ensure_ascii=False)
        chemin_args = fh.name
    try:
        sortie = subprocess.run(
            ["node", "-e", driver, str(chemin_js), chemin_args],
            capture_output=True, text=True, encoding="utf-8", timeout=180)
        assert sortie.returncode == 0, f"node a echoue : {sortie.stderr[-2000:]}"
        return json.loads(sortie.stdout)
    finally:
        os.unlink(chemin_args)


#: Les seules fonctions autorisées à lancer un sous-processus dans cette suite, et pourquoi.
#: Toute addition à cette table est une décision, pas une formalité : elle doit dire quel
#: exécutable est lancé et ce qui se passe s'il manque.
_LANCEURS_AUTORISES = {
    "_node_disponible": "détecte la présence de Node ; tolère son absence par construction",
    "_execute_fichier_logique": "LE point de passage vers Node ; saute si Node est absent",
    "test_cc2_le_determinisme_tient_d_un_processus_a_l_autre":
        "relance `sys.executable` — l'interpréteur qui fait tourner la suite, donc présent",
}


def _lanceurs_de_sous_processus(source: str) -> dict:
    """Où, dans ce source, un sous-processus est lancé — par fonction porteuse.

    On lit l'ARBRE, pas les lignes : un scan textuel se voyait lui-même dans son propre
    message d'erreur, et signalait n'importe quel commentaire citant `node`.

    La première écriture ne regardait que le premier élément d'une liste littérale, à
    l'intérieur d'une `FunctionDef`. Elle laissait passer trois contournements, chacun
    suffisant à rouvrir le trou : un lancement au niveau MODULE (jamais visité), un binaire
    porté par une VARIABLE (`[NODE, ...]`), et une commande en CHAÎNE (`shell=True`). On ne
    cherche donc plus « node » : on repère TOUT lancement de sous-processus, et on exige qu'il
    vive dans une fonction nommément autorisée. Un garde-fou doit être plus large que la faute
    qu'il connaît.
    """
    arbre = ast.parse(source)
    porteur_de = {}
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for interne in ast.walk(noeud):
                porteur_de.setdefault(id(interne), noeud.name)

    lancements = {}
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        cible = noeud.func
        lance = (isinstance(cible, ast.Attribute)
                 and isinstance(cible.value, ast.Name) and cible.value.id == "subprocess"
                 and cible.attr in ("run", "Popen", "call", "check_call", "check_output"))
        if not lance:
            continue
        # « <module> » quand le lancement est au niveau module : il ne porte alors AUCUN nom
        # de fonction, donc aucune autorisation possible — ce qui est le comportement voulu.
        lancements.setdefault(porteur_de.get(id(noeud), "<module>"), []).append(noeud.lineno)
    return lancements


def test_aucun_oracle_ne_lance_de_sous_processus_hors_des_points_de_passage():
    """La garde d'absence de Node doit rester STRUCTURELLE, pas conventionnelle.

    C'est l'un des rares endroits où un scan de source est le bon outil : la propriété gardée
    porte sur la suite de tests elle-même — « personne ne contourne le point de passage » — et
    aucune exécution ne l'observe. Sans elle, la prochaine addition qui relance `node` de son
    côté rouvre le trou que la revue a trouvé : quatre tests sur six tombant en
    `FileNotFoundError` sur une machine sans Node.
    """
    with open(__file__, encoding="utf-8") as fh:
        lancements = _lanceurs_de_sous_processus(fh.read())
    intrus = {nom: lignes for nom, lignes in lancements.items()
              if nom not in _LANCEURS_AUTORISES}
    assert not intrus, (
        f"sous-processus lance hors des points de passage : {intrus}. Tout passage par Node "
        f"doit traverser _execute_fichier_logique, qui saute proprement quand Node est absent.")
    assert set(lancements) == set(_LANCEURS_AUTORISES), (
        f"les lancements legitimes ont disparu ou change de forme ({sorted(lancements)}) : "
        f"cet oracle ne garde plus rien, il faut le remettre en face du code")


@pytest.mark.parametrize("contournement,description", [
    ('import subprocess\nsubprocess.run(["node", "-e", "1"])\n',
     "lancement au niveau module, jamais visite par une collecte par fonction"),
    ('import subprocess\nNODE = "node"\n'
     'def test_x():\n    subprocess.run([NODE, "-e", "1"])\n',
     "binaire porte par une variable, invisible a une recherche du litteral « node »"),
    ('import subprocess\ndef test_x():\n    subprocess.run("node -e 1", shell=True)\n',
     "commande en chaine, sans liste d'arguments a inspecter"),
    ('import subprocess\ndef test_x():\n    subprocess.Popen(["node"])\n',
     "Popen au lieu de run"),
])
def test_controle_positif_un_contournement_du_point_de_passage_serait_vu(contournement,
                                                                        description):
    """CONTRÔLE POSITIF de la garde ci-dessus, sur les quatre contournements connus.

    La version précédente n'en voyait aucun des trois premiers, et n'avait aucun contrôle
    positif — elle certifiait une couverture qu'elle n'avait pas. C'est exactement le motif
    que la règle transverse du mandat interdit.
    """
    lancements = _lanceurs_de_sous_processus(contournement)
    intrus = {nom: lignes for nom, lignes in lancements.items()
              if nom not in _LANCEURS_AUTORISES}
    assert intrus, f"contournement non vu ({description}) : la garde ne garde rien"


def test_controle_positif_un_lancement_legitime_reste_accepte():
    """L'autre bord : la garde ne doit pas condamner le point de passage lui-même."""
    legitime = ('import subprocess\n'
                'def _execute_fichier_logique(c, a):\n'
                '    return subprocess.run(["node", "-e", "1"])\n')
    lancements = _lanceurs_de_sous_processus(legitime)
    assert set(lancements) == {"_execute_fichier_logique"}
    assert not {n: l for n, l in lancements.items() if n not in _LANCEURS_AUTORISES}


@pytest.mark.parametrize("present,exige,attendu", [
    (True, False, "executer"),
    (True, True, "executer"),
    (False, False, "sauter"),
    (False, True, "echouer"),
])
def test_controle_positif_la_conduite_sans_node_couvre_ses_quatre_cas(present, exige, attendu):
    """Les quatre entrées, dont la seule qui porte le job : absent ET exigé -> échec.

    Sans ce contrôle, `MR_NODE_REQUIS` pourrait n'être qu'une variable lue et jetée : le job
    resterait vert à vide, ce que la variable est précisément là pour empêcher.
    """
    assert _conduite_sans_node(present, exige) == attendu


def test_le_job_pose_bien_la_variable_que_ce_fichier_lit():
    """ANTI-VACUITÉ DU CÂBLAGE : le job et ce fichier parlent du même nom ET de la même valeur.

    L'oracle n'inspecte pas la source de l'outil à la recherche d'un littéral : ce contrôle-là
    ne regarderait qu'un seul côté, et resterait vert si c'était CE fichier qui avait la faute
    de frappe — c'est-à-dire dans la moitié des cas qu'il prétend fermer. Il resterait vert
    aussi si le job posait `"true"` au lieu de `"1"`, ce qui désarmerait la garde en silence.

    On interroge donc l'outil : on lui demande l'environnement qu'il poserait, et on vérifie
    que cet environnement-là produit bien la conduite « echouer » quand Node manque. Renommer
    d'un côté, ou changer la valeur, fait rougir.
    """
    chemin = os.path.join(_RACINE, "tools", "job_ci.py")
    garde = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("job_ci_sous_test", chemin)
        job_ci = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(job_ci)
    finally:
        sys.dont_write_bytecode = garde

    pose = job_ci.environnement_du_job()
    assert NOM_VAR_NODE_EXIGE in pose, (
        f"tools/job_ci.py ne pose plus {NOM_VAR_NODE_EXIGE} : la garde anti-saut est desarmee")
    exige = pose[NOM_VAR_NODE_EXIGE] == "1"
    assert _conduite_sans_node(False, exige) == "echouer", (
        f"le job pose {NOM_VAR_NODE_EXIGE}={pose[NOM_VAR_NODE_EXIGE]!r}, que ce fichier ne lit "
        f"pas comme une exigence : sous le job, Node absent rendrait un vert a vide")


def _execute_logique(appels):
    """Exécute le VRAI `logique.js` sous Node et rend ses résultats.

    C'est le point entier de ce montage. Une première version RÉPLIQUAIT ces fonctions en
    Python : les oracles éprouvaient alors la réplique, jamais le code servi, et le seul lien
    entre les deux était une recherche de sous-chaînes qui survivait à n'importe quelle
    réécriture. La revue l'a dit sans détour — la garde annoncée n'existait pas. Ici, le
    fichier chargé par le navigateur est le fichier exécuté par le test : une régression de
    la prose ou de l'arithmétique fait rougir la suite, par construction.

    `appels` : liste de {"fn": nom, "args": [...]}. Rend la liste des retours.
    """
    return _execute_fichier_logique(CHEMIN_LOGIQUE_JS, appels)


def _compteurs_js(scenario, arbitrages):
    return _execute_logique([{"fn": "compteurs", "args": [scenario, arbitrages]}])[0]


def _toutes_combinaisons(doutes):
    """Tous les arbitrages possibles sur les doutes montrés — l'espace complet, pas un cas."""
    choix = ("fusionner", "separer", "inconnu", None)
    combinaisons = [{}]
    for doute in doutes:
        suivantes = []
        for partielle in combinaisons:
            for c in choix:
                nouvelle = dict(partielle)
                if c:
                    nouvelle[doute["a"] + "|" + doute["b"]] = c
                suivantes.append(nouvelle)
        combinaisons = suivantes
    return combinaisons


@_SANS_NODE
def test_les_compteurs_du_doute_restent_coherents_sur_TOUS_les_arbitrages(modele):
    """`consolidées + déjà uniques` doit toujours totaliser les fiches affichées.

    Éprouvé sur l'espace COMPLET des arbitrages possibles de chaque scénario — pas sur un
    scénario de clic heureux. C'est l'invariant que le prospect vérifie sans y penser : le
    grand chiffre en tête et la décomposition juste dessous décrivent le même ensemble.
    """
    for scenario in modele["scenarios"]:
        combinaisons = _toutes_combinaisons(scenario["a_confirmer"])
        resultats = _execute_logique(
            [{"fn": "compteurs", "args": [scenario, a]} for a in combinaisons])
        for arbitrages, c in zip(combinaisons, resultats):
            assert c["consolidees"] + c["deja_uniques"] == c["fiches"], (
                f"{scenario['cle']} : {c['consolidees']} + {c['deja_uniques']} != "
                f"{c['fiches']} pour {arbitrages}")
            assert c["a_confirmer"] >= 0, f"{scenario['cle']} : doutes negatifs"
            assert c["consolidees"] >= 0 and c["deja_uniques"] >= 0, (
                f"{scenario['cle']} : compteur negatif pour {arbitrages}")


@_SANS_NODE
def test_seule_la_fusion_change_les_compteurs(modele):
    """« Non, à garder séparées » confirme ce que le moteur a déjà fait : rien ne doit bouger.

    L'ancienne version ajoutait +2 aux déjà uniques — le bouton déplaçait un chiffre au lieu
    de refléter une décision, ce qui est le pire signal possible sur une surface de vente.
    """
    for scenario in modele["scenarios"]:
        depart = _compteurs_js(scenario, {})
        for doute in scenario["a_confirmer"]:
            for neutre in ("separer", "inconnu"):
                apres = _compteurs_js(scenario, {doute["a"] + "|" + doute["b"]: neutre})
                assert apres["consolidees"] == depart["consolidees"]
                assert apres["deja_uniques"] == depart["deja_uniques"]
                assert apres["fiches"] == depart["fiches"], (
                    f"{scenario['cle']} : « {neutre} » a modifie le resultat")
                # « Je ne sais pas » ne RÉSOUT rien : le doute reste en attente. Le décompter
                # faisait afficher zéro cas restant au-dessus de trois cas déclarés ouverts.
                attendu = depart["a_confirmer"] - (0 if neutre == "inconnu" else 1)
                assert apres["a_confirmer"] == attendu, (
                    f"{scenario['cle']} : « {neutre} » compte mal les doutes restants")


@_SANS_NODE
def test_controle_positif_un_je_ne_sais_pas_qui_viderait_la_file_serait_vu(modele):
    """CONTRÔLE POSITIF : si « Je ne sais pas » décomptait, la file tomberait sous le nombre
    de cas réellement en attente — et c'est cela qu'il faut voir."""
    scenario = modele["scenarios"][0]
    tous_inconnus = {d["a"] + "|" + d["b"]: "inconnu" for d in scenario["a_confirmer"]}
    apres = _compteurs_js(scenario, tous_inconnus)
    assert apres["a_confirmer"] == scenario["n_a_confirmer"], (
        "repondre « je ne sais pas » a tout ne doit RIEN resoudre : la file reste entiere")
    assert apres["a_confirmer"] > 0


def test_controle_positif_l_ancienne_arithmetique_serait_vue(modele):
    """CONTRÔLE POSITIF : la formule fautive d'origine DOIT violer l'invariant.

    Sans lui, rien ne dirait que le test ci-dessus attrape quoi que ce soit.
    """
    def ancienne(scenario, arbitrages):
        fusionnes = sum(1 for v in arbitrages.values() if v == "fusionner")
        separes = sum(1 for v in arbitrages.values() if v == "separer")
        return {"consolidees": scenario["n_consolidees"] + fusionnes,
                "deja_uniques": scenario["n_deja_uniques"] + separes * 2,
                "fiches": scenario["n_fiches_uniques"] - fusionnes}

    fautes = 0
    for scenario in modele["scenarios"]:
        for arbitrages in _toutes_combinaisons(scenario["a_confirmer"]):
            c = ancienne(scenario, arbitrages)
            if c["consolidees"] + c["deja_uniques"] != c["fiches"]:
                fautes += 1
    assert fautes, "l'invariant ne distingue pas l'ancienne formule : il ne garde rien"


@_SANS_NODE
def test_la_logique_eprouvee_est_bien_celle_qui_est_servie(pages):
    """Les oracles doivent porter sur le FICHIER SERVI, pas sur une paraphrase.

    Une version précédente répliquait `compteurs` et `phraseDeProuve` en Python, et prouvait
    l'alignement par une recherche de six sous-chaînes dans `bac.js` : n'importe quelle
    réécriture sémantique passait. La revue l'a dit sans détour — la garde annoncée
    n'existait pas. Trois conditions la rendent réelle :
      1. la page charge `logique.js` AVANT `bac.js` ;
      2. `bac.js` ne redéfinit ni `compteurs` ni `phraseDeProuve`, sans quoi il masquerait
         la version éprouvée ;
      3. Node charge `logique.js` et y trouve les deux fonctions.
    """
    html = pages["bac_a_sable"]
    assert "/statique/logique.js" in html, "la page ne charge pas la logique eprouvee"
    assert html.index("/statique/logique.js") < html.index("/statique/bac.js"), (
        "logique.js doit etre charge AVANT bac.js")

    source_bac = _source_bac_js()
    # La liste vient de `module.exports` — ce que Node charge réellement — et non des
    # déclarations `function`, qui n'en sont qu'un sur-ensemble : une fonction déclarée mais
    # oubliée de l'export serait absente des tests tout en étant servie au navigateur.
    exportes = _exports_de_logique_js()
    assert len(exportes) >= 8, f"exports de logique.js introuvables : {sorted(exportes)}"
    for nom in exportes:
        # Trois formes de masquage, pas une : `function f(`, `const f =`, `f = function`.
        # La version précédente ne cherchait que la première, et une redéfinition écrite en
        # fonction fléchée serait passée sans rien faire rougir.
        masquages = [motif for motif in (rf"\bfunction\s+{nom}\s*\(",
                                         rf"\b(?:const|let|var)\s+{nom}\s*=",
                                         rf"^\s*{nom}\s*=\s*(?:function|\()")
                     if re.search(motif, source_bac, re.M)]
        assert not masquages, (
            f"bac.js redefinit {nom} ({masquages}) : il masquerait la version eprouvee")

    exporte = _execute_logique([{"fn": "accord", "args": [1, "fiche"]},
                                {"fn": "accord", "args": [2, "fiche"]}])
    assert exporte == ["1 fiche", "2 fiches"], (
        "logique.js n'expose pas ses fonctions a Node : les oracles ne s'executent pas")


#: Les fonctions de `logique.js` dont l'absence d'appel dans `bac.js` RETIRE du texte de la
#: page, en silence. Chacune a été introduite pour combler un manque que la revue avait
#: trouvé ; supprimer l'appel rouvre le manque sans que la fonction, elle, cesse d'être
#: éprouvée par ses propres oracles — c'est le trou que cette table ferme.
APPELS_DE_PROSE_REQUIS = {
    "noteDuPoint": "sans elle, le résultat s'affiche sous les seuils d'un AUTRE mode",
    "annonceTroncature": "sans elle, la file de doutes est montrée tronquée sans le dire",
    "phraseValeursEcartees": "sans elle, la valeur écartée n'est plus expliquée",
    "phraseDeProuve": "sans elle, un rapprochement s'affiche sans sa preuve",
    "compteurs": "sans elle, les compteurs ne suivent plus les arbitrages",
    "accord": "sans elle, « 1 fiches uniques » revient",
}


def _appels_dans(source: str) -> set:
    """Les identifiants APPELÉS dans un source JavaScript (`nom(` en position d'appel)."""
    return set(re.findall(r"(?<![\w.])(\w+)\s*\(", source))


def test_chaque_regle_de_prose_est_reellement_appelee_par_la_page():
    """Une règle sortie dans `logique.js` doit rester BRANCHÉE dans `bac.js`.

    Déplacer une règle de rendu vers le fichier éprouvé la met à l'abri des réécritures — et
    crée un trou nouveau : ses oracles la testent en isolation, si bien que supprimer les deux
    lignes qui l'appellent fait disparaître le texte de la page sans faire rougir la suite.
    C'est le défaut d'origine (« le lecteur croit voir toute la zone grise ») redevenu
    possible par la correction elle-même.

    C'est un scan de source, et il faut dire sa limite : il prouve que l'appel EXISTE, pas
    qu'il est atteint. Il n'y a pas de DOM dans cet environnement verrouillé, donc pas de
    rendu à observer. Il ferme la régression par suppression, qui est celle qui s'est produite.
    """
    source_bac = _source_bac_js()
    appeles = _appels_dans(source_bac)
    manquants = {nom: raison for nom, raison in APPELS_DE_PROSE_REQUIS.items()
                 if nom not in appeles}
    assert not manquants, (
        f"regles de prose definies mais jamais appelees par bac.js : {manquants}")
    # Et la table doit rester en face du fichier : une fonction de prose ajoutée à
    # `logique.js` sans entrée ici retomberait dans l'angle mort.
    assert set(APPELS_DE_PROSE_REQUIS) <= _exports_de_logique_js()


@pytest.mark.parametrize("regle", sorted(APPELS_DE_PROSE_REQUIS))
def test_controle_positif_une_regle_de_prose_debranchee_serait_vue(regle):
    """CONTRÔLE POSITIF : retirer l'appel du source doit faire rougir le scan ci-dessus."""
    ampute = re.sub(rf"(?<![\w.]){regle}\s*\(", "neantAppele(", _source_bac_js())
    assert regle not in _appels_dans(ampute), "l'amputation n'a rien retire"
    manquants = {nom for nom in APPELS_DE_PROSE_REQUIS if nom not in _appels_dans(ampute)}
    assert regle in manquants, f"debrancher {regle} ne serait pas vu"


@_SANS_NODE
def test_le_total_des_doutes_est_publie_et_non_seulement_l_echantillon(modele):
    """Annoncer « 3 à confirmer » quand le moteur en a laissé 4 sous-déclare le doute — et le
    sous-déclare dans le sens qui flatte.

    L'oracle EXÉCUTE la règle d'annonce. Sa version précédente cherchait la sous-chaîne
    `"c.total > c.montres"` dans le source de `bac.js` : elle rougissait sur une réécriture
    équivalente et restait verte si l'annonce disparaissait autour de la ligne. C'est le motif
    d'oracle inerte que ce projet a déjà corrigé trois fois ailleurs.
    """
    for scenario in modele["scenarios"]:
        assert scenario["n_a_confirmer"] >= len(scenario["a_confirmer"])
        assert scenario["n_a_confirmer_montres"] == len(scenario["a_confirmer"])

    tronques = [s for s in modele["scenarios"]
                if s["n_a_confirmer"] > s["n_a_confirmer_montres"]]
    assert tronques, "aucun scenario tronque : l'oracle ne prouverait rien"

    # Les compteurs sont ceux que `compteurs()` PRODUIT, pas un dictionnaire fabriqué ici.
    # Fabriqués, ils laissaient passer un renommage de clé : `annonceTroncature` recevait un
    # objet sans `montres`, rendait la chaîne vide, et l'annonce disparaissait de la page sans
    # qu'aucun test ne rougisse. Les deux fonctions sont maintenant chaînées, comme sur la page.
    compteurs = _execute_logique([{"fn": "compteurs", "args": [s, {}]} for s in tronques])
    appels = [{"fn": "annonceTroncature", "args": [c]} for c in compteurs]
    # CONTRÔLE POSITIF, dans le même appel : file entière montrée -> aucune annonce ; un seul
    # cas caché -> annonce. Sans ces deux bornes, une fonction qui annonce TOUJOURS, ou
    # JAMAIS, passerait.
    appels.append({"fn": "annonceTroncature", "args": [{"total": 7, "montres": 7}]})
    appels.append({"fn": "annonceTroncature", "args": [{"total": 8, "montres": 7}]})
    # Et la branche du SINGULIER, que les données livrées n'atteignent pas : elle n'est
    # inatteignable aujourd'hui que parce qu'une constante d'un AUTRE fichier
    # (`N_DOUTES_PUBLIES`) vaut trois. C'est une coïncidence de configuration, pas une garde —
    # et elle écrivait « 1 cas détaillés ci-dessous ».
    appels.append({"fn": "annonceTroncature", "args": [{"total": 2, "montres": 1}]})
    rendus = _execute_logique(appels)

    for scenario, rendu in zip(tronques, rendus):
        assert str(scenario["n_a_confirmer"]) in rendu and \
               str(scenario["n_a_confirmer_montres"]) in rendu, (
            f"{scenario['cle']} : l'annonce ne porte pas les deux comptes ({rendu!r})")
    assert rendus[-3] == "", "une file entierement montree ne doit rien annoncer"
    assert rendus[-2], "un seul cas cache doit etre annonce"
    # `annonceTroncature` est de la PROSE : elle passe au même scan que le reste. C'était la
    # seule phrase du fichier qui ne le traversait pas, et elle était fautive.
    fautives = [(r, _fautes(r)) for r in rendus if r and _fautes(r)]
    assert not fautives, f"annonce de troncature fautive : {fautives}"


def test_un_meme_doute_n_est_pas_pose_deux_fois(modele):
    """Un doute porte sur deux ENTITÉS : le poser une fois par membre du groupe faisait
    répéter la même question, et rien n'empêchait d'y répondre « oui » puis « non »."""
    for scenario in modele["scenarios"]:
        couples = [frozenset((d["entite_a"], d["entite_b"])) for d in scenario["a_confirmer"]]
        assert len(couples) == len(set(couples)), (
            f"{scenario['cle']} : deux doutes portent sur le meme couple d'entites")


# ============ La prose composée par le JavaScript ============
#
# La moitié du texte que lit le prospect n'est pas dans les gabarits : `bac.js` l'assemble à
# l'exécution. Rien ne l'inspectait, et c'est ce trou qui a laissé passer « mêmes adresse »
# au-dessus de deux adresses différentes, « Seul téléphone diffère » sans article, et
# « 1 fiches uniques » — jusqu'à la revue adversariale. Un scan qui ne regarde que les
# gabarits certifie une qualité d'écriture qu'il n'a pas vérifiée.
#
# Ces oracles EXÉCUTENT `logique.js` sous Node, sur les données réelles des scénarios, et
# éprouvent les phrases obtenues. Le paragraphe qui tenait ici décrivait le dispositif
# PRÉCÉDENT — une réplique Python des mêmes règles, tenue alignée par un
# `test_la_replique_de_phrase_suit_le_javascript` qui n'existe plus. Ce commentaire a survécu
# à la suppression de ce qu'il décrivait, et affirmait donc une garde inexistante à qui le
# lisait. Un commentaire périmé sur un dispositif de garde est pire qu'aucun commentaire :
# il dispense d'aller voir.


def _libelles_du_javascript():
    """La table de libellés, LUE dans `logique.js` plutôt que recopiée ici.

    La recopier créait une seconde source de vérité, qui ne rougissait pas quand le fichier
    servi changeait : c'est le motif même que ce bloc a corrigé pour les fonctions. On la lit
    donc à l'exécution, du fichier lui-même.
    """
    return _execute_logique([{"fn": "libelle", "args": [champ]}
                             for champ in CHAMPS_ATTENDUS])


#: Les champs dont la prose peut parler : les huit comparés, plus les deux clés techniques.
CHAMPS_ATTENDUS = ("record_id", "source_id", "nom", "prenom", "date_naissance", "adresse",
                   "code_postal", "ville", "email", "telephone")


def _appels_de_phrase(modele):
    """Les appels que la page fera réellement à `phraseDeProuve`, avec leur contexte."""
    appels, contextes = [], []
    for scenario in modele["scenarios"]:
        for groupe in scenario["consolidees"]:
            par_id = {r["record_id"]: r for r in groupe["records"]}
            for paire in groupe["paires"]:
                ra, rb = par_id.get(paire["a"]), par_id.get(paire["b"])
                appels.append({"fn": "phraseDeProuve", "args": [
                    paire["preuve"], f"{paire['a']} et {paire['b']} sont la même entité",
                    ra, rb]})
                contextes.append((scenario["cle"], paire["preuve"], ra, rb))
        for doute in scenario["a_confirmer"]:
            appels.append({"fn": "phraseDeProuve", "args": [
                doute["preuve"], "Le moteur hésite", doute["record_a"], doute["record_b"]]})
            contextes.append((scenario["cle"], doute["preuve"],
                              doute["record_a"], doute["record_b"]))
    return appels, contextes


def _phrases_composees(modele):
    """Toutes les phrases que le JavaScript produit sur les données livrées — EXÉCUTÉES.

    Plus de réplique : c'est `logique.js` lui-même qui compose, sous Node.
    """
    appels, _ = _appels_de_phrase(modele)
    return _execute_logique(appels)


#: Fautes que la prose composée ne doit jamais produire. Chacune a été RÉELLEMENT observée
#: sur les surfaces livrées avant la revue.
FAUTES_DE_COMPOSITION = (
    # « mêmes » ne doit précéder qu'une énumération. La virgule et « et » sont exclus DANS le
    # motif : la version précédente ne les niait qu'après la correspondance, et signalait
    # fautive « mêmes nom et adresse », qui est juste.
    (r"\bmêmes (?:(?! et )[^;.,])+[.;]", "« mêmes » suivi d'un seul champ"),
    # `[a-zéèêà]` attrapait le « l » de « le » : il fallait exclure explicitement l'article,
    # sans quoi « Seul le prénom diffère » — la phrase VOULUE — était signalée fautive.
    (r"\bSeule?s? (?!l[ea'’]|l')[a-zéèêà]", "« Seul » sans article"),
    # `Seuls?` acceptait « Seuls » : le motif du singulier ne doit pas matcher le pluriel.
    (r"\bSeule? l[ea'][^.]*? diffèrent\b", "« Seul » singulier avec verbe pluriel"),
    (r"\bSeuls l[ea'][^.]*? diffère\b", "« Seuls » pluriel avec verbe singulier"),
    # L'accord en GENRE : « Seul la ville » passait sous les motifs précédents, qui ne
    # regardaient que l'article et le nombre. Une mutation de la branche féminine restait
    # donc invisible — le contrôle positif l'a montré.
    (r"\bSeul la\b", "« Seul » masculin devant un nom féminin"),
    (r"\bSeule le\b", "« Seule » féminin devant un nom masculin"),
    # Les noms INVARIABLES en -s sont exclus : « 1 cas détaillé » est juste, et le motif nu le
    # signalait fautif. Un scan qui rougit sur une phrase correcte finit par être désarmé —
    # c'est le sort qu'ont connu deux contrôles positifs de ce fichier.
    (r"\b1 (?!(?:cas|pas|temps|fois|prix|choix|corps|univers|français)\b)[a-zéèêà]+s\b",
     "accord de nombre : « 1 » suivi d'un pluriel"),
    (r"\s:\s*\.", "phrase vide après deux-points"),
    (r"\s{2,}", "espaces doubles"),
    # En typographie française, l'espace AVANT « ; » et « : » est obligatoire : ne sont
    # fautifs que le point et la virgule précédés d'une espace.
    (r"\s+[.,]", "espace avant un point ou une virgule"),
)


def _fautes(phrase):
    return [motif for expression, motif in FAUTES_DE_COMPOSITION
            if re.search(expression, phrase)]


#: Les motifs de `FAUTES_DE_COMPOSITION` qui gardent leur sens sur du texte EXTRAIT d'un
#: rendu HTML. Les deux motifs d'espacement en sont exclus, et pas par commodité :
#: `_texte_visible` remplace chaque balise par une espace, si bien que le HTML parfaitement
#: correct « <b>téléphone</b>. » devient « téléphone . » à l'extraction. Les treize
#: occurrences relevées sur les quatre pages étaient toutes de cette forme — zéro faute
#: réelle. Un oracle qui rougit sur du texte juste finit désarmé, et c'est la garde entière
#: qu'on perd alors, pas seulement le motif bruyant.
#:
#: L'espacement du rendu n'est donc pas gardé ici. Il l'est là où il est décidable : sur les
#: phrases composées par `logique.js`, qui sont du texte pur.
FAUTES_DE_PROSE_RENDUE = tuple(
    (expression, motif) for expression, motif in FAUTES_DE_COMPOSITION
    if motif not in ("espaces doubles", "espace avant un point ou une virgule"))


def _fautes_de_prose_rendue(texte: str) -> list:
    normalise = re.sub(r"\s+", " ", texte)
    return [motif for expression, motif in FAUTES_DE_PROSE_RENDUE
            if re.search(expression, normalise)]


@pytest.mark.parametrize("surface", ["vitrine", "salle_des_machines", "bac_a_sable",
                                     "dossier_technique"])
def test_la_prose_des_gabarits_ne_porte_aucune_faute_de_composition(pages, surface):
    """La table de fautes ci-dessus ne portait QUE sur la prose du navigateur.

    Aucun oracle ne lisait le texte rendu des gabarits : la seule chose qu'on y regardait
    était les littéraux numériques. La passe de clôture y a ajouté environ neuf cents mots —
    l'encadré commercial, la phrase de lecture simple, les explications du tableau — et rien
    n'aurait vu un « Seul la ville » ni un « la ville n'est renseigné ».
    """
    fautes = _fautes_de_prose_rendue(_texte_visible(pages[surface]))
    assert not fautes, f"{surface} : faute de composition dans la prose rendue — {fautes}"


@pytest.mark.parametrize("injection", [
    "<p>Seul la ville concorde.</p>",
    "<p>Seule le nom concorde.</p>",
    "<p>Seul le nom diffèrent.</p>",
    "<p>Les mêmes adresse.</p>",
    "<p>1 informations concordent.</p>",
])
def test_controle_positif_une_faute_de_prose_dans_un_gabarit_serait_vue(pages, injection):
    """CONTRÔLE POSITIF : les cinq classes que la table retenue prétend voir, sur un rendu."""
    pollue = pages["vitrine"].replace("</main>", injection + "</main>")
    assert _fautes_de_prose_rendue(_texte_visible(pollue)), (
        f"le scan de prose ne voit pas {injection!r} sur une page rendue : il ne garde rien")


@_SANS_NODE
def test_la_note_des_valeurs_ecartees_accorde_ses_deux_nombres(modele):
    """Deux accords indépendants, et la phrase n'en tenait aucun.

    Le nombre de CHAMPS en désaccord commande « la valeur retenue » / « les valeurs
    retenues » ; le nombre de VALEURS écartées commande « l'autre » / « les autres ». La
    version livrée écrivait « l'autre entre parenthèses » au singulier devant trois champs et
    deux graphies concurrentes — sous la carte même qui promet la fiche propre.
    """
    # Cas synthétiques : les quatre combinaisons des deux accords, dont deux que les données
    # livrées n'exercent pas. Un oracle qui ne teste que ce qui se présente ne garde rien.
    synthetiques = [
        ({"nom": ["Aubry"]}, "la valeur retenue est indiquée", "l'autre entre"),
        ({"nom": ["Aubry", "Aubrit"]}, "la valeur retenue est indiquée", "les autres entre"),
        ({"nom": ["Aubry"], "adresse": ["3 r. de la Gare"]},
         "les valeurs retenues sont indiquées", "les autres entre"),
        ({}, None, None),                       # rien d'écarté : aucune phrase
    ]
    appels = [{"fn": "phraseValeursEcartees", "args": [ecartees]}
              for ecartees, _, _ in synthetiques]
    reels = [groupe["valeurs_ecartees"] for scenario in modele["scenarios"]
             for groupe in scenario["consolidees"] if groupe.get("valeurs_ecartees")]
    assert reels, "aucun groupe a valeurs ecartees : l'oracle ne porterait que du synthetique"
    appels += [{"fn": "phraseValeursEcartees", "args": [e]} for e in reels]

    rendus = _execute_logique(appels)
    for (ecartees, retenue, autres), rendu in zip(synthetiques, rendus):
        if retenue is None:
            assert rendu == "", f"{ecartees} ne devrait produire aucune phrase, or {rendu!r}"
            continue
        assert retenue in rendu and autres in rendu, f"accord manque dans {rendu!r}"

    for ecartees, rendu in zip(reels, rendus[len(synthetiques):]):
        n_champs = len(ecartees)
        n_valeurs = sum(len(v) for v in ecartees.values())
        attendu_retenue = ("les valeurs retenues sont indiquées" if n_champs > 1
                           else "la valeur retenue est indiquée")
        attendu_autres = "les autres entre" if n_valeurs > 1 else "l'autre entre"
        assert attendu_retenue in rendu and attendu_autres in rendu, (
            f"{n_champs} champ(s), {n_valeurs} valeur(s) ecartee(s) : accord faux "
            f"dans {rendu!r}")
        # « divergeaient sur nom et adresse » est du télégramme : l'article est obligatoire.
        assert "divergeaient sur le" in rendu or "divergeaient sur la" in rendu \
            or "divergeaient sur l'" in rendu, f"article manquant dans {rendu!r}"
    assert not [r for r in rendus if r and _fautes(r)], "faute de composition dans la note"


@_SANS_NODE
def test_chaque_scenario_affiche_les_seuils_qui_l_ont_reellement_produit(modele):
    """Un résultat ne doit pas s'afficher sous les seuils d'un autre mode.

    La page ne publiait qu'un couple de seuils — celui de la saisie manuelle, DIMS-v2 — alors
    que les trois scénarios ont re-dérivé le leur sur leurs propres données : Tμ vaut +2,650
    en manuel et −8,325 pour les clients. Le lecteur attribuait donc aux résultats qu'il
    regardait des seuils qui ne les avaient pas produits.

    L'oracle exige aussi que le BUDGET de revue soit dit : c'est lui qui rend la file courte,
    et le taire laisse prendre pour une propriété du moteur ce qui est un réglage de
    démonstration.
    """
    points = [s["point"] for s in modele["scenarios"]]
    assert len({p["t_mu"] for p in points}) > 1, (
        "les scenarios partagent un seul point : l'oracle ne distinguerait rien")

    notes = _execute_logique([{"fn": "noteDuPoint", "args": [s]}
                              for s in modele["scenarios"]])
    for scenario, note in zip(modele["scenarios"], notes):
        point = scenario["point"]
        for seuil in (point["t_mu"], point["t_lambda"]):
            attendu = f"{seuil:.3f}".replace(".", ",").replace("-", "−")
            # Le signe moins typographique ou le trait d'union : on accepte les deux formes,
            # c'est la VALEUR qui est gardée ici.
            assert attendu in note or attendu.replace("−", "-") in note, (
                f"{scenario['cle']} : la note n'annonce pas {seuil} ({note!r})")
        budget = point["provenance"]["budget_vise"]
        assert str(budget) in note, (
            f"{scenario['cle']} : le budget de revue qui rend la file courte n'est pas dit")
    assert not [(n, _fautes(n)) for n in notes if _fautes(n)], (
        f"note de point fautive : {[(n, _fautes(n)) for n in notes if _fautes(n)]}")


@_SANS_NODE
def test_controle_positif_la_note_du_point_refuse_un_scenario_sans_seuils():
    """CONTRÔLE POSITIF : sans point de fonctionnement, la note doit LEVER, pas se taire.

    Un repli silencieux ferait disparaître les seuils de la page — exactement le défaut que
    cette note est là pour fermer — sans que rien ne rougisse.
    """
    with pytest.raises(AssertionError):
        _execute_logique([{"fn": "noteDuPoint", "args": [{"cle": "sans_point"}]}])


@_SANS_NODE
def test_la_prose_composee_par_le_javascript_est_correcte(modele):
    """Chaque phrase que le JavaScript produira sur les données livrées est bien formée."""
    phrases = _phrases_composees(modele)
    assert len(phrases) > 50, "trop peu de phrases eprouvees : le scan ne garde presque rien"
    fautives = [(p, _fautes(p)) for p in phrases if _fautes(p)]
    assert not fautives, f"prose composee fautive : {fautives[:5]}"


@_SANS_NODE
def test_la_prose_composee_ne_contredit_jamais_les_valeurs_affichees(modele):
    """« mêmes adresse » ne doit JAMAIS surmonter deux adresses différentes.

    C'est la faute qui a survécu jusqu'à la revue : le moteur compare des valeurs normalisées
    et déclare un accord fort entre « 3 rue de la Gare » et « 3 r. de la Gare ». Écrire
    « mêmes adresse » au-dessus des deux valeurs brutes faisait mentir la preuve devant le
    lecteur, sur la carte la plus argumentative de la démonstration.
    """
    appels, contextes = _appels_de_phrase(modele)
    # Les libellés sont LUS du fichier servi, jamais recopiés ici : une seconde table aurait
    # divergé sans rien faire rougir, et c'est elle que l'oracle aurait cru garder.
    libelles = dict(zip(CHAMPS_ATTENDUS, _libelles_du_javascript()))
    phrases = _execute_logique(appels)
    for phrase, (cle, preuve, ra, rb) in zip(phrases, contextes):
        # Le segment qui énumère ce qui est IDENTIQUE : « même(s) … » jusqu'au prochain
        # « ; » ou « . ». C'est lui, et lui seul, qui affirme l'égalité des valeurs.
        segment = re.search(r"mêmes? ([^;.]+)", phrase)
        # Découpé en libellés EXACTS : « nom » est une sous-chaîne de « prénom », et une
        # recherche par inclusion signalait fautive la phrase juste.
        enumeres = set()
        if segment:
            for morceau in re.split(r",\s*|\s+et\s+", segment.group(1)):
                enumeres.add(morceau.strip())
        # Et le segment qui affirme « la même chose écrite différemment » : il ne vaut que
        # pour les champs que la NORMALISATION rend égaux. Un accord fort obtenu par simple
        # similarité — deux numéros de rue voisins — n'est pas deux graphies d'une chose.
        segment_ecriture = re.search(r"([^;.]+) concorden?t? malgré une écriture différente",
                                     phrase)
        annonces_equivalentes = set()
        if segment_ecriture:
            for morceau in re.split(r",\s*|\s+et\s+", segment_ecriture.group(1)):
                annonces_equivalentes.add(morceau.strip().lstrip("Xx: ").strip())
        normalisees_egales = set(preuve.get("identiques_apres_normalisation", []))

        # Les deux enregistrements DOIVENT être là. Les exempter par un `continue` rendait
        # l'oracle aveugle à la régression même qu'il garde : si les enregistrements cessaient
        # d'arriver à la composition, toutes les paires étaient exemptées et la suite restait
        # verte pendant que la page affirmait « mêmes adresse » sur des valeurs différentes.
        assert ra and rb, (
            f"{cle} : une paire est composee sans ses enregistrements — la phrase de preuve "
            f"ne peut plus distinguer l'egalite de la ressemblance")
        for champ in preuve["concordent"]:
            a, b = ra.get(champ), rb.get(champ)
            if a is None or b is None or str(a) == str(b):
                continue
            assert libelles[champ] not in enumeres, (
                f"{cle} : « {phrase} » annonce {champ} identique alors que les valeurs "
                f"affichees sont {a!r} et {b!r}")
            if champ not in normalisees_egales:
                assert not any(libelles[champ] in m for m in annonces_equivalentes), (
                    f"{cle} : « {phrase} » presente {champ} comme deux ecritures d'une meme "
                    f"valeur, alors que la normalisation ne les rend pas egales "
                    f"({a!r} / {b!r}) — c'est un accord par SIMILARITE, pas une graphie")


@pytest.mark.parametrize("phrase,attendu", [
    ("X : mêmes adresse.", "« mêmes » suivi d'un seul champ"),
    ("X. Seul téléphone diffère.", "« Seul » sans article"),
    ("X. Seul le nom diffèrent.", "« Seul » singulier avec verbe pluriel"),
    ("X. Seuls le nom diffère.", "« Seuls » pluriel avec verbe singulier"),
    ("Résultat : 1 fiches uniques.", "accord de nombre : « 1 » suivi d'un pluriel"),
    ("X : .", "phrase vide après deux-points"),
    ("X  Y.", "espaces doubles"),
    ("X ; mêmes nom .", "espace avant un point ou une virgule"),
    ("X. Seul la ville diffère.", "« Seul » masculin devant un nom féminin"),
    ("X. Seule le nom diffère.", "« Seule » féminin devant un nom masculin"),
])
def test_controle_positif_le_scan_de_prose_voit_chaque_faute(phrase, attendu):
    """CONTRÔLE POSITIF : chaque faute que le scan prétend interdire doit être vue.

    Les huit exemples ci-dessous sont ceux réellement produits par la version fautive.
    """
    assert attendu in _fautes(phrase), f"le scan ne voit pas {attendu!r} dans {phrase!r}"


def test_le_scan_de_prose_ne_crie_pas_sur_les_phrases_correctes():
    """Un scan qui rougit sur la prose voulue serait retiré au premier faux positif."""
    for correcte in (
        "FOU_0011 et FOU_0012 sont la même entité : mêmes adresse, code postal et ville ; "
        "le nom concorde malgré une écriture différente.",
        "Le moteur hésite : même nom. Seuls le code postal et la ville diffèrent.",
        "Le moteur hésite : même nom ; l'adresse concorde malgré une écriture différente. "
        "Seule la ville diffère.",
        "34 fiches consolidées · 101 déjà uniques · 3 à confirmer",
        "1 fiche unique",
        # Noms invariables en -s : le motif d'accord de nombre les signalait fautifs.
        "1 cas détaillé ci-dessous, sur 2 que le moteur a laissés en attente.",
        "1 fois sur 2",
    ):
        assert not _fautes(correcte), f"faux positif sur {correcte!r} : {_fautes(correcte)}"


@_SANS_NODE
@pytest.mark.parametrize("mutation,attendu", [
    ('(identiques.length > 1 ? "mêmes " : "même ")', '"mêmes "',
     ),
    ('(pluriel ? " diffèrent." : " diffère.")', '" diffèrent."'),
    ('(GENRES[preuve.divergent[0]] === "f" ? "Seule " : "Seul ")', '"Seul "'),
])
def test_controle_positif_une_regression_du_FICHIER_SERVI_serait_vue(modele, mutation,
                                                                     attendu, tmp_path):
    """CONTRÔLE POSITIF : casser l'accord DANS `logique.js` doit faire rougir le scan.

    C'est ce contrôle-là qui donne sa valeur à tout le montage : on mute le fichier
    réellement servi — pas une copie Python — et on exige que la prose devienne fautive. Si
    une mutation de l'accord passait inaperçue, l'oracle ne garderait rien.
    """
    with open(CHEMIN_LOGIQUE_JS, encoding="utf-8") as fh:
        source = fh.read()
    assert mutation in source, f"le code a change : {mutation!r} n'est plus present"
    mute = tmp_path / "logique_mutee.js"
    mute.write_text(source.replace(mutation, attendu), encoding="utf-8")

    # Les données livrées n'exercent pas toutes les branches grammaticales — aucun de leurs
    # cas ne présente un seul champ FÉMININ divergent, par exemple. Un contrôle positif qui
    # ne repose que sur elles laisse passer les mutations des branches non couvertes : on
    # ajoute donc des cas synthétiques qui exercent chaque branche.
    def cas(concordent, divergent):
        return {"fn": "phraseDeProuve", "args": [
            {"concordent": concordent, "concordent_partiellement": [],
             "divergent": divergent, "non_renseignes": [],
             "identiques_apres_normalisation": concordent},
            "Le moteur hésite",
            {c: "x" for c in concordent + divergent},
            {c: "x" for c in concordent + divergent}]}

    appels = [
        cas(["nom"], ["ville"]),            # un seul champ, un seul divergent FÉMININ
        cas(["nom", "adresse"], ["ville"]),
        cas(["nom"], ["ville", "email"]),   # divergents au pluriel
        cas(["adresse"], ["nom"]),          # un seul divergent MASCULIN
    ]
    appels += _appels_de_phrase(modele)[0]
    # Même point de passage que les oracles positifs : on mute le FICHIER, pas le driver.
    phrases = _execute_fichier_logique(mute, appels)
    fautives = [p for p in phrases if _fautes(p)]
    assert fautives, (
        f"muter {mutation!r} en {attendu!r} dans le fichier SERVI ne produit aucune faute "
        f"detectee : le scan de prose ne garde rien")


def test_aucun_texte_visible_du_javascript_ne_porte_de_jargon_ni_de_marque(modele):
    """Le scan de vocabulaire ne voyait que le squelette rendu au serveur : toute la prose du
    résultat riche — accroches, bénéfices, explications, libellés de section — lui échappait."""
    with open(os.path.join(_RACINE, "src", "surfaces", "statique", "bac.js"),
              encoding="utf-8") as fh:
        source = fh.read()
    # Le filtre `" " in c` écartait toute chaîne d'un seul mot : « Splink » y passait sans
    # être vu. Un scan qui ne regarde que les phrases laisse entrer précisément ce qui
    # s'écrit en un mot — une marque.
    chaines = re.findall(r'"((?:[^"\\]|\\.)*)"', source) + \
        re.findall(r"`((?:[^`\\]|\\.)*)`", source) + \
        re.findall(r"'((?:[^'\\]|\\.)*)'", source)
    texte_js = " ".join(c for c in chaines if len(c) > 2)
    # `_revendication_de_fabrication_par_ia` est joint aux deux autres scans : c'est LUI qui a
    # remplacé le bannissement du mot « IA », et il ne portait que sur les quatre pages
    # rendues. La prose du navigateur et celle des scénarios étaient donc passées de « gardées
    # par un scan du mot » à « gardées par rien du tout ».
    trouves = (_jargon_trouve(texte_js) + _marques_ou_superiorite(texte_js)
               + _revendication_de_fabrication_par_ia(texte_js))
    assert not trouves, f"bac.js compose du jargon ou une marque : {trouves}"

    for chemin in _fichiers_statiques():
        if not chemin.endswith(".js"):
            continue
        with open(chemin, encoding="utf-8") as fh:
            contenu = fh.read()
        mots = re.findall(r'["\'`]((?:[^"\'`\\]|\\.)*)["\'`]', contenu)
        blob = " ".join(m for m in mots if len(m) > 2)
        fautifs = (_jargon_trouve(blob) + _marques_ou_superiorite(blob)
                   + _revendication_de_fabrication_par_ia(blob))
        assert not fautifs, f"{os.path.basename(chemin)} compose {fautifs}"

    # Et le texte que les scénarios apportent depuis l'artefact.
    depuis_artefact = " ".join(
        [s["titre"] + " " + s["accroche"] + " " + s["benefice"] for s in modele["scenarios"]])
    trouves = (_jargon_trouve(depuis_artefact) + _marques_ou_superiorite(depuis_artefact)
               + _revendication_de_fabrication_par_ia(depuis_artefact))
    assert not trouves, f"un scenario apporte du jargon ou une marque : {trouves}"


@pytest.mark.parametrize("injection", ['const marque = "Splink";',
                                       'const x = "clustering";',
                                       # L'injection etait `'notre IA'`, qui n'est plus une
                                       # faute : la regle corrigee autorise le mot. On garde
                                       # la propriete que ce controle visait — un mot SEUL —
                                       # avec un terme encore proscrit.
                                       "const y = 'mcnemar';",
                                       # Et le relais doit mordre ICI aussi, pas seulement
                                       # sur les pages rendues au serveur.
                                       "const z = 'ce module est genere par IA';"])
def test_controle_positif_une_marque_dans_le_javascript_serait_vue(injection):
    """CONTRÔLE POSITIF : le scan doit voir un mot SEUL, pas seulement une phrase.

    Le filtre précédent n'examinait que les chaînes contenant un espace — donc jamais une
    marque, qui s'écrit en un mot.
    """
    mots = re.findall(r'["\'`]((?:[^"\'`\\]|\\.)*)["\'`]', injection)
    blob = " ".join(m for m in mots if len(m) > 2)
    assert (_jargon_trouve(blob) + _marques_ou_superiorite(blob)
            + _revendication_de_fabrication_par_ia(blob)), (
        f"le scan ne voit pas {injection!r} : il ne garde rien")


def test_le_bac_a_sable_dit_ce_qui_est_calcule_et_ce_qui_est_prepare(pages):
    """La honnêteté du tour 4 : la page ne doit pas laisser croire à un calcul en direct des
    scénarios, ni à une lecture de vos fichiers."""
    texte = _texte_visible(pages["bac_a_sable"]).lower()
    assert "calculé à l'avance" in texte or "préparé à l'avance" in texte, (
        "la page doit dire que les scenarios sont pre-calcules")
    assert "ne lit pas vos fichiers" in texte, (
        "la page doit dire qu'elle n'analyse pas les fichiers de l'utilisateur")
    assert "sur mesure" in texte, (
        "la limite doit etre tournee en promesse : c'est ce qu'on construit avec vous")


def test_aucune_ressource_distante_dans_les_pages(pages):
    """Le produit tourne hors ligne : une seule URL externe ferait mentir la Vitrine."""
    for surface, html in pages.items():
        externes = re.findall(r"(?:src|href)\s*=\s*[\"'](https?://[^\"']+)", html)
        assert not externes, f"{surface} charge des ressources distantes : {externes}"


#: Ce qu'un fichier statique ne doit contenir sous aucune forme. Les pages rendues étaient
#: scannées, pas les fichiers SERVIS : `bac.js` rend la totalité du résultat dans le
#: navigateur et `surfaces.css` est chargé par chaque page — une fonte tierce ou un appel
#: sortant y passait inaperçu, sous une Vitrine qui promet « aucune donnée ne sort ».
MOTIFS_SORTANTS = (
    r"https?://",
    r"@import\s+url\(\s*[\"']?https?:",
    r"\bXMLHttpRequest\b",
    r"\bWebSocket\b",
    r"\bnavigator\.sendBeacon\b",
    r"\bimportScripts\b",
)


#: Le navigateur n'AGIT que sur la feuille de style et le script. Un `.woff2` est un binaire
#: inerte, un `.json` ou un `.txt` posés là ne déclenchent aucune requête. C'est donc sur les
#: fichiers exécutables que porte la garde — et le manifeste des fontes, lui, DOIT contenir
#: les URL d'origine : c'est sa raison d'être, un binaire sans provenance n'étant pas auditable.
EXTENSIONS_EXECUTEES = (".css", ".js")


def _fichiers_statiques() -> list:
    """Les fichiers servis, y compris sous `fontes/`, tous niveaux confondus."""
    racine = os.path.join(_RACINE, "src", "surfaces", "statique")
    trouves = []
    for dossier, _, fichiers in os.walk(racine):
        trouves += [os.path.join(dossier, f) for f in sorted(fichiers)]
    return sorted(trouves)


def _sorties_reseau(source: str) -> list:
    trouves = [motif for motif in MOTIFS_SORTANTS if re.search(motif, source)]
    # `fetch` est légitime vers une route RELATIVE (le bac à sable appelle son propre serveur) ;
    # il ne l'est pas vers un hôte.
    if re.search(r"fetch\(\s*[\"'`]\s*(?:https?:)?//", source):
        trouves.append("fetch vers un hote")
    return trouves


def test_aucun_appel_sortant_dans_les_fichiers_statiques():
    executes = [c for c in _fichiers_statiques() if c.endswith(EXTENSIONS_EXECUTEES)]
    assert executes, "aucun fichier executable trouve : le scan ne garderait rien"
    for chemin in executes:
        with open(chemin, encoding="utf-8") as fh:
            trouves = _sorties_reseau(fh.read())
        assert not trouves, f"{os.path.basename(chemin)} sort du reseau : {trouves}"


#: Modules par lesquels un socket s'ouvre. `tests/test_llm_review.py` pose le même interdit
#: sur `tools/` — la zone de mesure ; celui-ci le pose sur `src/`, le code LIVRÉ.
MODULES_RESEAU = {"requests", "urllib", "urllib3", "http", "socket", "websockets",
                  "httpx", "aiohttp", "ftplib", "smtplib", "telnetlib", "webbrowser"}


def _imports_recursifs(racine: str) -> dict:
    importes = {}
    for dossier, _, fichiers in os.walk(racine):
        if "__pycache__" in dossier:
            continue
        for nom in sorted(f for f in fichiers if f.endswith(".py")):
            chemin = os.path.join(dossier, nom)
            importes[os.path.relpath(chemin, _RACINE)] = _imports_du_module(chemin)
    return importes


def test_le_produit_livre_n_ouvre_jamais_de_socket():
    """`C7` : le code livré ne contient aucun moyen d'ouvrir une connexion.

    La Vitrine promet « aucune donnée ne sort, aucun service distant ». Ce n'est pas une
    intention : `src/` n'importe littéralement rien qui puisse ouvrir un socket, et un
    évaluateur peut le vérifier par analyse d'imports sans lire une ligne de logique.

    Les fontes auto-hébergées ne changent rien à cette propriété — elles la renforcent : le
    programme qui les récupère vit dans `deploiement/`, hors du produit et hors de la zone de
    mesure, et n'entre pas dans l'image.
    """
    fautifs = {fichier: sorted(modules & MODULES_RESEAU)
               for fichier, modules in _imports_recursifs(
                   os.path.join(_RACINE, "src")).items()
               if modules & MODULES_RESEAU}
    assert not fautifs, f"le code livre peut ouvrir un socket : {fautifs}"


def test_controle_positif_un_import_reseau_dans_le_produit_serait_vu(tmp_path):
    """CONTRÔLE POSITIF : le détecteur doit voir un import réseau glissé dans le produit."""
    faux = tmp_path / "src"
    (faux / "surfaces").mkdir(parents=True)
    (faux / "surfaces" / "fuite.py").write_text(
        "import json\nimport urllib.request\n", encoding="utf-8")
    modules = set()
    for chemin in (faux / "surfaces" / "fuite.py",):
        modules |= _imports_du_module(str(chemin))
    assert modules & MODULES_RESEAU, (
        "le detecteur ne voit pas `import urllib.request` : il ne garde rien")


def test_le_recuperateur_de_fontes_est_hors_de_la_zone_de_mesure():
    """L'interdit de `tools/` est inviolable — on ne l'a pas percé, on s'est rangé dessous.

    `tools/` est la zone de mesure : un artefact qui dépendrait d'un serveur distant ne se
    régénérerait plus à l'octet. Le récupérateur de fontes ouvre un socket ; il n'y a donc pas
    sa place, et il vit dans `deploiement/`, avec le Dockerfile et les requirements, où le
    réseau est le régime normal. Ce test empêche qu'il y revienne par inadvertance.
    """
    recuperateur = os.path.join(_RACINE, "deploiement", "recupere_fontes.py")
    assert os.path.exists(recuperateur), (
        "le recuperateur de fontes a disparu : les fontes du depot n'ont plus de provenance")
    assert _imports_du_module(recuperateur) & MODULES_RESEAU, (
        "ce test protege un interdit qui ne s'applique plus : si le recuperateur n'ouvre "
        "plus de socket, il peut rentrer dans tools/ et ce test doit disparaitre")

    outils = _imports_recursifs(os.path.join(_RACINE, "tools"))
    fautifs = {f: sorted(m & MODULES_RESEAU) for f, m in outils.items() if m & MODULES_RESEAU}
    assert not fautifs, f"la zone de mesure a ete percee : {fautifs}"


# ============================ Les fontes auto-hébergées ============================

def _manifeste_fontes() -> dict:
    chemin = os.path.join(_RACINE, "src", "surfaces", "statique", "fontes", "manifeste.json")
    with open(chemin, encoding="utf-8") as fh:
        return json.load(fh)


def test_les_fontes_sont_dans_le_depot_et_conformes_a_leur_empreinte():
    """Chaque fonte servie est celle qui a été téléchargée — sinon la provenance ne vaut rien."""
    manifeste = _manifeste_fontes()
    assert manifeste["fontes"], "aucune fonte declaree"
    for entree in manifeste["fontes"]:
        chemin = os.path.join(_RACINE, entree["chemin"].replace("/", os.sep))
        assert os.path.exists(chemin), f"fonte declaree mais absente : {entree['chemin']}"
        with open(chemin, "rb") as fh:
            donnees = fh.read()
        assert len(donnees) == entree["octets"], f"{entree['chemin']} : taille divergente"
        assert hashlib.sha256(donnees).hexdigest() == entree["sha256"], (
            f"{entree['chemin']} : empreinte divergente de celle du manifeste")


def test_chaque_famille_porte_sa_licence():
    """L'OFL autorise la redistribution À CONDITION que la licence accompagne les fichiers.
    L'embarquer n'est pas une politesse : c'est la seule condition que ces auteurs posent."""
    manifeste = _manifeste_fontes()
    familles_servies = {e["famille"] for e in manifeste["fontes"]}
    familles_licenciees = {l["famille"] for l in manifeste["licences"]}
    assert familles_servies <= familles_licenciees, (
        f"familles sans licence embarquee : {familles_servies - familles_licenciees}")
    for licence in manifeste["licences"]:
        chemin = os.path.join(_RACINE, licence["chemin"].replace("/", os.sep))
        with open(chemin, encoding="utf-8") as fh:
            texte = fh.read()
        assert os.path.exists(chemin) and len(texte) > 1000, f"licence vide : {licence['chemin']}"
        assert "SIL OPEN FONT LICENSE" in texte.upper(), (
            f"{licence['chemin']} ne ressemble pas a l'OFL")


def test_la_feuille_des_fontes_ne_designe_que_des_chemins_locaux():
    """Le point entier de l'auto-hébergement : plus une seule URL de tiers."""
    chemin = os.path.join(_RACINE, "src", "surfaces", "statique", "fontes.css")
    with open(chemin, encoding="utf-8") as fh:
        source = fh.read()
    sources = re.findall(r"src:\s*url\('([^']+)'\)", source)
    assert sources, "aucune @font-face : la feuille ne sert a rien"
    for url in sources:
        assert url.startswith("/statique/fontes/"), f"chemin non local dans fontes.css : {url}"
    assert not _sorties_reseau(source)


def test_chaque_fonte_designee_par_la_feuille_existe():
    """Une `@font-face` qui pointe dans le vide fait retomber la page sur la pile système
    sans le dire — le rendu diverge du modèle et rien ne le signale."""
    dossier = os.path.join(_RACINE, "src", "surfaces", "statique")
    with open(os.path.join(dossier, "fontes.css"), encoding="utf-8") as fh:
        sources = re.findall(r"src:\s*url\('/statique/([^']+)'\)", fh.read())
    for relatif in set(sources):
        assert os.path.exists(os.path.join(dossier, relatif.replace("/", os.sep))), (
            f"fonte designee mais absente du depot : {relatif}")


def test_les_trois_familles_de_la_maquette_sont_servies(pages):
    """La maquette fait autorité sur la typographie : les trois familles doivent être là,
    déclarées dans la feuille ET employées par les jetons de `surfaces.css`."""
    dossier = os.path.join(_RACINE, "src", "surfaces", "statique")
    with open(os.path.join(dossier, "fontes.css"), encoding="utf-8") as fh:
        fontes_css = fh.read()
    with open(os.path.join(dossier, "surfaces.css"), encoding="utf-8") as fh:
        surfaces_css = fh.read()
    for famille in ("Space Grotesk", "Inter", "JetBrains Mono"):
        assert f"font-family: '{famille}'" in fontes_css, f"{famille} non declaree"
        assert famille in surfaces_css, f"{famille} declaree mais jamais employee"
    # Et la feuille est bien reliée depuis le gabarit de base, sinon rien ne s'applique.
    assert "/statique/fontes.css" in pages["vitrine"]


@pytest.mark.parametrize("injection", [
    "const r = await fetch('https://exemple.fr/collecte', {method:'POST'});",
    "@import url(https://fonts.googleapis.com/css2?family=Inter);",
    "new WebSocket('wss://telemetrie.exemple.fr');",
    "navigator.sendBeacon('/x', d);",
])
def test_controle_positif_un_appel_sortant_serait_vu(injection):
    """CONTRÔLE POSITIF : le scan doit voir chaque forme de sortie réseau qu'il prétend interdire."""
    assert _sorties_reseau(injection), (
        f"le scan des fichiers statiques ne voit pas {injection!r} : il ne garde rien")


def test_le_scan_statique_laisse_passer_un_appel_relatif_legitime():
    """Le bac à sable appelle sa propre route : un scan qui l'interdirait serait retiré."""
    assert not _sorties_reseau('const r = await fetch("/api/rapprocher", {method:"POST"});')
