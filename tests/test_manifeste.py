# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Les oracles de l'identité formelle du produit — `MANIFESTE_PRODUIT.json`.

Un manifeste que rien ne vérifie n'est pas une garantie faible : c'est une affirmation. Le
projet a déjà payé cette leçon sur `empreinte_contenu`, publié comme preuve d'intégrité et
que personne ne recalculait jamais (`tools/empreinte_artefact.py`). Ce fichier interdit que ça
recommence sur le document dont c'est précisément le sujet.

Quatre propriétés, et chacune ferme un défaut qui a été TROUVÉ, pas imaginé :

1. **Le périmètre est celui du Dockerfile**, pas une liste écrite à la main — sinon il dérive
   au premier `COPY` ajouté. Le Dockerfile en porte **six**, et la revue a montré qu'une
   lecture à cinq rendait l'oracle rouge et le manifeste faux sur son objet central.
2. **Le corps se régénère à l'octet**, et lui seul : le sceau publié ne couvre pas l'empreinte
   de tête, qui est datée par construction. Sceller les deux ensemble rendait le sceau périmé
   au commit suivant — le défaut exact que `empreinte_artefact.py` raconte avoir corrigé.
3. **Les empreintes sont vraies** : recalculées depuis les fichiers, par les deux voies.
4. **Ce qui est haché est ce qui part** : sans `.dockerignore`, `COPY src/engine/` embarquait
   les `__pycache__/` du poste — 40 fichiers non déclarés, machine-dépendants, dont du
   bytecode d'un interpréteur que l'image n'exécute même pas.
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import pytest

_RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def _charge_outil():
    garde = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(
            "manifeste_sous_test", os.path.join(_RACINE, "tools", "manifeste_produit.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = garde


mp = _charge_outil()


@pytest.fixture(scope="module")
def publie():
    chemin = os.path.join(_RACINE, mp.NOM_MANIFESTE)
    assert os.path.isfile(chemin), (
        f"{mp.NOM_MANIFESTE} absent : le produit n'a pas d'identite formelle. "
        f"Remede : python tools/manifeste_produit.py")
    with open(chemin, encoding="utf-8") as fh:
        return json.load(fh)


def test_le_perimetre_du_manifeste_est_celui_des_copy_du_dockerfile():
    """Le périmètre est LU dans le Dockerfile, jamais recopié à côté.

    Le Dockerfile porte SIX `COPY` : les cinq de contenu (l. 35-39) et
    `deploiement/requirements-surfaces.txt` (l. 30), qui entre bien dans l'image — le build
    est mono-étage — mais dont le contenu ne s'exécute pas. Il est déclaré dans
    `COPY_HORS_ANNEAU_1` plutôt que passé sous silence : un septième `COPY` ajouté un jour
    fera rougir cet oracle, ce qui est exactement ce qu'on veut.
    """
    attendu = set(mp.ANNEAU_1) | set(mp.COPY_HORS_ANNEAU_1)
    assert mp.copies_du_dockerfile(_RACINE) == attendu, (
        "le perimetre du manifeste ne correspond plus aux COPY du Dockerfile : le produit "
        "livre a change sans que son identite suive")


def test_controle_positif_un_copy_ajoute_serait_vu(tmp_path):
    """CONTRÔLE POSITIF de l'oracle ci-dessus : il doit VOIR un `COPY` de plus.

    Sans ce contrôle, un lecteur de `COPY` qui ne trouverait plus rien du tout rendrait
    l'égalité vraie par le vide, et le périmètre ne serait plus gardé par personne.
    """
    faux = tmp_path / "deploiement"
    faux.mkdir()
    (faux / "Dockerfile").write_text(
        "FROM x\nCOPY src/engine/ ./src/engine/\nCOPY src/scorer/ ./src/scorer/\n",
        encoding="utf-8")
    sources = mp.copies_du_dockerfile(str(tmp_path))
    assert sources == {"src/engine", "src/scorer"}, (
        "le lecteur de COPY ne voit plus ce qu'il lit : l'oracle de perimetre serait vide")


def test_le_corps_se_regenere_a_l_octet(publie):
    """Le CORPS est déterministe : deux calculs sur le même contenu donnent les mêmes octets.

    C'est la promesse vendue par le document. Elle porte sur le corps SEUL, et pas sur le
    fichier entier : `empreinte_de_tete` change à chaque commit sans qu'aucun contenu produit
    ne bouge, et exiger l'identité du fichier complet serait une exigence qu'aucun état du
    dépôt ne peut satisfaire — l'oracle serait rouge dès le commit suivant sa propre pose.
    """
    frais = mp.construis_corps(_RACINE)
    assert mp.sceau(frais) == publie["sceau_du_corps"], (
        "le corps du manifeste ne correspond plus au depot. Remede : "
        "python tools/manifeste_produit.py --verifie pour voir ce qui a bouge")
    canon_a = json.dumps(frais, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    canon_b = json.dumps(mp.construis_corps(_RACINE), sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"))
    assert canon_a == canon_b, "deux calculs successifs divergent : le corps n'est pas stable"


def test_chaque_empreinte_publiee_est_recalculable(publie):
    """Un lecteur doit retrouver chaque chiffre depuis le fichier qu'il tient."""
    fichiers = publie["corps"]["anneau_1"]["fichiers"] + publie["corps"]["anneau_2"]["fichiers"]
    assert fichiers, "le manifeste ne hache aucun fichier"
    for entree in fichiers:
        absolu = os.path.join(_RACINE, entree["chemin"])
        assert os.path.isfile(absolu), f"{entree['chemin']} est au manifeste mais pas au depot"
        with open(absolu, "rb") as fh:
            octets = fh.read()
        assert len(octets) == entree["octets"], f"taille divergente : {entree['chemin']}"
        assert hashlib.sha256(octets).hexdigest() == entree["sha256"], (
            f"sha256 divergent : {entree['chemin']}")
        entete = b"blob " + str(len(octets)).encode() + b"\0"
        assert hashlib.sha1(entete + octets).hexdigest() == entree["blob_git"], (
            f"blob git divergent : {entree['chemin']}")


def test_l_anneau_1_couvre_exactement_les_fichiers_suivis(publie):
    """Ni oubli ni fichier fantôme : l'exhaustivité est une propriété, pas une intention."""
    au_manifeste = {f["chemin"] for f in publie["corps"]["anneau_1"]["fichiers"]}
    au_depot = set(mp.fichiers_suivis(_RACINE, mp.ANNEAU_1))
    assert au_manifeste == au_depot, (
        f"manquants : {sorted(au_depot - au_manifeste)} ; en trop : "
        f"{sorted(au_manifeste - au_depot)}")


def test_aucune_recette_declaree_ne_manque_au_manifeste(publie):
    """Un fichier de l'anneau 2 present sur le disque doit etre suivi ET hache.

    Ce contrôle existe parce que le défaut s'est produit : `.dockerignore` et `.gitattributes`
    ont d'abord été écrits sans être ajoutés à l'index, et le manifeste — qui énumère par
    `git ls-files` — a publié quatre recettes au lieu de six sans que rien ne s'en aperçoive.
    Les autres oracles restaient verts, puisqu'ils vérifient la cohérence de ce qui EST là et
    non l'absence de ce qui devrait y être. Un manifeste amputé en silence est exactement ce
    qu'un document d'identité ne peut pas se permettre.
    """
    au_manifeste = {f["chemin"] for f in publie["corps"]["anneau_2"]["fichiers"]}
    for declare in mp.ANNEAU_2:
        if os.path.isfile(os.path.join(_RACINE, declare)):
            assert declare in au_manifeste, (
                f"{declare} est declare a l'anneau 2 et present sur le disque, mais absent du "
                f"manifeste : il n'est pas suivi par git (`git add {declare}`)")


def test_l_empreinte_de_tete_designe_un_commit_reel_et_ancetre(publie):
    """L'empreinte de tête n'est pas scellée, mais elle doit rester vraie.

    On n'exige PAS l'inégalité avec `HEAD` : le manifeste est normalement calculé puis
    committé, donc son commit est le parent — mais une régénération sans commit derrière est
    légitime, et un oracle qui l'interdirait rendrait l'outil inutilisable hors cérémonie.
    Ce qui doit tenir dans les deux cas, c'est l'ancestralité.
    """
    commit = publie["empreinte_de_tete"]["commit"]
    assert commit, "aucun commit inscrit"
    typ = subprocess.run(["git", "cat-file", "-t", commit], cwd=_RACINE,
                         capture_output=True, text=True)
    assert typ.stdout.strip() == "commit", f"{commit} n'est pas un commit de ce depot"
    assert subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"],
                          cwd=_RACINE).returncode == 0, (
        f"{commit[:12]} n'est pas un ancetre de HEAD : le manifeste date d'une autre ligne")


def test_ce_qui_est_hache_est_ce_qui_part_dans_l_image():
    """LE contrôle qui rend vraie la phrase « le manifeste atteste ce qui part ».

    `COPY src/engine/ ./src/engine/` copie le CONTENU DU RÉPERTOIRE du contexte de build, pas
    ce que git suit. Sans `.dockerignore`, les `__pycache__/` du poste entraient donc dans
    l'image — mesuré à l'écriture de cet oracle : 40 fichiers et ~500 Ko non déclarés, dont
    19 `.pyc` compilés par un interpréteur 3.14 que l'image (`python:3.12-slim`) n'exécute
    même pas, et tous absents chez un autre opérateur. Le manifeste aurait attesté l'arbre
    suivi en le présentant comme l'image.

    L'oracle ne simule pas Docker : il vérifie que tout fichier présent sous les préfixes
    livrés et NON suivi par git est bien couvert par un motif de `.dockerignore`.
    """
    chemin = os.path.join(_RACINE, mp.NOM_DOCKERIGNORE)
    assert os.path.isfile(chemin), (
        ".dockerignore absent : le contexte de build n'est pas reduit aux fichiers suivis, "
        "et le manifeste atteste alors un autre objet que ce qui part dans l'image")
    with open(chemin, encoding="utf-8") as fh:
        motifs = [l.strip().rstrip("/") for l in fh
                  if l.strip() and not l.strip().startswith("#")]

    suivis = set(mp.fichiers_suivis(_RACINE, mp.ANNEAU_1))
    intrus = []
    for prefixe in mp.ANNEAU_1:
        base = os.path.join(_RACINE, prefixe)
        if not os.path.isdir(base):
            continue
        for dossier, _, noms in os.walk(base):
            for nom in noms:
                absolu = os.path.join(dossier, nom)
                relatif = os.path.relpath(absolu, _RACINE).replace("\\", "/")
                if relatif in suivis:
                    continue
                segments = relatif.split("/")
                import fnmatch
                couvert = any(
                    any(fnmatch.fnmatch(s, motif) for s in segments)
                    or fnmatch.fnmatch(relatif, motif)
                    for motif in motifs)
                if not couvert:
                    intrus.append(relatif)
    assert not intrus, (
        f"ces fichiers ne sont ni suivis par git ni exclus par .dockerignore : ils entreraient "
        f"dans l'image sans figurer au manifeste — {sorted(intrus)[:10]}")


def test_le_manifeste_publie_concorde_avec_le_depot():
    """`--verifie` et la suite ne peuvent pas rendre des réponses différentes.

    Deux gardes du même document qui divergent, c'est une garde de moins et une fausse
    assurance de plus.
    """
    assert mp.divergences(_RACINE) == []
