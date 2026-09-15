#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""L'IDENTITÉ FORMELLE du produit livré : quels fichiers, quels octets, quelle tête.

## Ce que ce fichier existe pour supprimer

Le registre de promotion était vide et le rapport de build final un squelette, alors que la
chaîne est close. Il n'existait donc aucune réponse opposable à « qu'est-ce qui est livré,
exactement ? » — et une chaîne close sans identité formelle est une chaîne dont on doit croire
le résumé sur parole.

## Le périmètre n'est pas choisi ici : il est LU dans le Dockerfile

Un manifeste dont le périmètre serait une liste écrite à la main dériverait du produit réel au
premier `COPY` ajouté, en silence. Le périmètre est donc défini par le seul document qui dit
déjà ce qui part en production — `deploiement/Dockerfile` — et un oracle vérifie l'égalité
(`tests/test_manifeste.py`). Le Dockerfile porte **six** `COPY`, pas cinq :

- **anneau 1**, le PRODUIT (l. 35-39) : `src/engine/`, `src/pipeline/`, `src/surfaces/`,
  `artifacts/`, `serveur.py`. C'est ce qui tourne.
- **anneau 2**, les RECETTES : `deploiement/requirements-surfaces.txt` (l. 30 — copié dans
  l'image puis consommé au build par le `pip install` de la l. 31 ; son contenu ne tourne pas,
  ses paquets oui), plus `deploiement/Dockerfile`, `.dockerignore` et `requirements.lock`, qui
  ne partent pas mais DÉFINISSENT ce qui part. Les distinguer n'est pas un raffinement : c'est
  la différence entre « ce que j'exécute » et « ce qui a produit ce que j'exécute », et le
  sixième `COPY` tombe précisément entre les deux. On le nomme plutôt que de l'omettre.

## Ce que le manifeste hache, et pourquoi c'est l'octet brut

Les octets du fichier, tels quels. Un lecteur doit pouvoir recalculer le chiffre à partir du
fichier qu'il tient, sur Windows comme ailleurs : normaliser les fins de ligne avant de hacher
donnerait un nombre que `sha256sum` ne retrouve pas. `.gitattributes` (`* -text`) interdit à
git de traduire quoi que ce soit au checkout, sans quoi le manifeste deviendrait faux sans
qu'aucun commit n'ait eu lieu. Le `blob_git` est publié à côté, pour qu'on puisse vérifier par
les deux voies.

## CORPS et EMPREINTE DE TÊTE : la séparation qui rend la promesse tenable

`empreinte_de_tete` (commit, arbre, nombre de commits) est DATÉE par construction : le
manifeste est calculé, puis committé, donc le commit qu'il porte est le parent de celui qui le
contient, et toute régénération ultérieure en écrit un autre. Si le sceau publié couvrait ce
bloc, il serait périmé au commit suivant — exactement le défaut que `tools/empreinte_artefact.py`
raconte avoir corrigé sur `ui_demonstration.json`, et qu'il serait absurde de réintroduire dans
le document dont c'est le sujet.

Le sceau publié porte donc sur le **CORPS** seul : périmètre, fichiers, empreintes, règles. Le corps ne dépend
d'aucun état de tête ; il est byte-identique d'une exécution à l'autre tant que le contenu ne
bouge pas, et c'est ce que l'oracle vérifie. L'empreinte de tête est publiée à côté, non
scellée, et gardée par son propre oracle (le commit existe et est ancêtre de `HEAD`).

Usage :
    python tools/manifeste_produit.py            # écrit MANIFESTE_PRODUIT.json
    python tools/manifeste_produit.py --verifie  # recalcule et compare, exit 2 si divergence
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

__all__ = ["NOM_MANIFESTE", "ANNEAU_1", "ANNEAU_2", "COPY_HORS_ANNEAU_1",
           "copies_du_dockerfile", "construis_corps", "empreinte_de_tete", "sceau",
           "fichiers_suivis", "divergences", "main"]

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NOM_MANIFESTE = "MANIFESTE_PRODUIT.json"

#: Le produit qui TOURNE — les cinq `COPY` de contenu (`deploiement/Dockerfile` l. 35-39).
ANNEAU_1 = ("src/engine", "src/pipeline", "src/surfaces", "artifacts", "serveur.py")

#: Les RECETTES : elles définissent le produit sans être le produit.
ANNEAU_2 = ("deploiement/Dockerfile", "deploiement/requirements-surfaces.txt",
            ".dockerignore", ".gitattributes", "requirements.lock", "requirements.txt")

#: Le sixième `COPY`. Il entre bien dans l'image (build mono-étage, aucun `--from`), mais son
#: contenu ne s'exécute pas : la l. 31 le consomme en `pip install`. Il est haché en anneau 2,
#: et il est nommé ici pour que l'oracle de périmètre le connaisse — sans cette constante,
#: l'égalité `COPY == anneau 1` serait fausse et l'oracle rougirait sans rien signaler de vrai.
COPY_HORS_ANNEAU_1 = ("deploiement/requirements-surfaces.txt",)

#: Le fichier qui réduit le contexte de build aux seuls fichiers suivis. Sans lui, l'égalité
#: « ce que ce manifeste hache » = « ce qui part dans l'image » est FAUSSE.
NOM_DOCKERIGNORE = ".dockerignore"


def _git(racine, *args):
    res = subprocess.run(["git", *args], cwd=racine, capture_output=True, text=True)
    return res.stdout.strip() if res.returncode == 0 else ""


def fichiers_suivis(racine, prefixes):
    """Les fichiers suivis par git sous ces préfixes, en chemins POSIX triés.

    `git ls-files` plutôt qu'un parcours du disque : c'est l'ensemble reproductible. Le
    parcours, lui, dépend de ce que la machine a laissé traîner — et c'est justement l'écart
    que `.dockerignore` referme et qu'un oracle mesure.
    """
    sortie = _git(racine, "ls-files", "-z", *prefixes)
    return sorted(c.replace("\\", "/") for c in sortie.split("\0") if c)


def copies_du_dockerfile(racine):
    """Les sources des `COPY` de `deploiement/Dockerfile`, sans le `--chown`."""
    chemin = os.path.join(racine, "deploiement", "Dockerfile")
    with open(chemin, encoding="utf-8") as fh:
        contenu = fh.read()
    sources = set()
    for ligne in re.findall(r"^\s*COPY\s+(.*)$", contenu, re.M):
        mots = [m for m in ligne.split() if not m.startswith("--")]
        if len(mots) >= 2:
            sources.add(mots[0].rstrip("/").replace("\\", "/"))
    return sources


def _empreinte_fichier(racine, chemin):
    absolu = os.path.join(racine, chemin)
    with open(absolu, "rb") as fh:
        octets = fh.read()
    # `blob_git` : le sha1 de l'objet blob, publié pour qu'on puisse vérifier par les deux
    # voies — `sha256sum` d'un côté, `git rev-parse HEAD:<chemin>` de l'autre.
    entete = b"blob " + str(len(octets)).encode() + b"\0"
    return {
        "chemin": chemin,
        "octets": len(octets),
        "sha256": hashlib.sha256(octets).hexdigest(),
        "blob_git": hashlib.sha1(entete + octets).hexdigest(),
    }


def _lot(racine, prefixes, chemins=None):
    """Un lot de fichiers haches, enumere par git ou par une liste explicite.

    La liste explicite sert au produit PROMU : une fois extrait, il n'a plus de `.git`, donc
    `git ls-files` n'y rend rien. C'est le manifeste lui-meme qui porte alors le perimetre —
    ce qui est la bonne source, puisque c'est justement ce que la promotion doit reproduire
    a l'identique.
    """
    chemins = fichiers_suivis(racine, prefixes) if chemins is None else sorted(chemins)
    fichiers = [_empreinte_fichier(racine, c) for c in chemins]
    # Le sceau du lot : sha256 des couples (chemin, sha256) triés. Il change si un fichier
    # change, disparaît ou apparaît — les trois, et pas seulement le premier.
    matiere = "\n".join(f"{f['chemin']} {f['sha256']}" for f in fichiers)
    return {
        "n_fichiers": len(fichiers),
        "octets": sum(f["octets"] for f in fichiers),
        "sceau": hashlib.sha256(matiere.encode("utf-8")).hexdigest(),
        "fichiers": fichiers,
    }


def construis_corps(racine=None, listes=None):
    """Le CORPS : strictement déterministe, ne dépend d'aucun état de tête.

    `listes` — un dict `{"anneau_1": [...], "anneau_2": [...]}` — remplace l'enumeration par
    git. La structure produite est EXACTEMENT la meme, ce qui est le point : le corps du
    produit extrait se compare alors au corps du build, et l'egalite des sceaux prouve que
    l'extraction n'a rien change, a l'octet.
    """
    racine = racine or _RACINE
    listes = listes or {}
    return {
        "produit": "moteur-rapprochement",
        "perimetre": {
            "definition": (
                "les six COPY de deploiement/Dockerfile (l. 30, 35-39) : cinq forment "
                "l'anneau 1, le produit qui tourne ; la sixieme "
                "(deploiement/requirements-surfaces.txt) entre dans l'image mais est "
                "consommee au build par le pip install de la l. 31, et est donc hachee en "
                "anneau 2 comme recette."),
            "ensemble": (
                "les fichiers SUIVIS par git sous ces prefixes. Le contexte de build est "
                "reduit au meme ensemble par .dockerignore, sans quoi les __pycache__/ "
                "presents sur le poste entreraient dans l'image et ce manifeste attesterait "
                "un autre objet que celui qui part."),
            "anneau_1": list(ANNEAU_1),
            "anneau_2": list(ANNEAU_2),
            "copy_hors_anneau_1": list(COPY_HORS_ANNEAU_1),
        },
        "regles": {
            "hachage": ("sha256 des OCTETS BRUTS du fichier, sans normalisation des fins de "
                        "ligne : un lecteur doit retrouver le chiffre avec sha256sum. "
                        ".gitattributes (* -text) interdit a git de traduire au checkout."),
            "blob_git": "sha1('blob <n>\\0' + octets) — verifiable par git rev-parse HEAD:<chemin>",
            "sceau_de_lot": "sha256 des lignes '<chemin> <sha256>' triees, jointes par \\n",
            "sceau_du_corps": ("sha256 de json.dumps(corps, sort_keys=True, "
                               "ensure_ascii=False, separators=(',', ':')) en UTF-8. C'est LUI "
                               "le sceau publie : il ne couvre PAS "
                               "l'empreinte de tete, qui est datee par construction et "
                               "perimerait le sceau au commit suivant."),
        },
        "anneau_1": _lot(racine, ANNEAU_1, listes.get("anneau_1")),
        "anneau_2": _lot(racine, ANNEAU_2, listes.get("anneau_2")),
    }


def sceau(corps):
    """Le sceau du corps — la valeur publiée au registre de promotion."""
    canonique = json.dumps(corps, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonique.encode("utf-8")).hexdigest()


def empreinte_de_tete(racine=None):
    """L'état de tête, publié À CÔTÉ du corps et jamais scellé avec lui.

    `commit` est le `HEAD` au moment du calcul ; comme le manifeste est committé ensuite, le
    commit inscrit est normalement le PARENT du commit qui porte le fichier. On ne l'exige pas
    (une régénération sans commit derrière est légitime) : l'oracle vérifie que le commit
    existe et qu'il est ancêtre de `HEAD`, ce qui est vrai dans les deux cas.
    """
    racine = racine or _RACINE
    return {
        "commit": _git(racine, "rev-parse", "HEAD"),
        "arbre": _git(racine, "rev-parse", "HEAD^{tree}"),
        "n_commits": int(_git(racine, "rev-list", "--count", "HEAD") or 0),
        "branche": _git(racine, "rev-parse", "--abbrev-ref", "HEAD"),
        "note": ("etat de tete au moment du calcul. NON couvert par sceau_du_corps : il "
                 "change a chaque commit sans qu'aucun contenu produit ne change, et un "
                 "sceau irreproductible ne prouve rien (cf. tools/empreinte_artefact.py)."),
    }


def construis(racine=None):
    racine = racine or _RACINE
    corps = construis_corps(racine)
    return {
        "_lisez_moi": (
            "Identite formelle du produit livre. Regenerable : "
            "`python tools/manifeste_produit.py --verifie` recalcule tout et sort 2 en cas de "
            "divergence. Le CORPS est deterministe et son sceau est la valeur citee au "
            "registre de promotion ; l'empreinte de tete est datee et publiee non scellee."),
        "sceau_du_corps": sceau(corps),
        "empreinte_de_tete": empreinte_de_tete(racine),
        "corps": corps,
    }


def _serialise(manifeste):
    return json.dumps(manifeste, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def divergences(racine=None):
    """Ce qui sépare le manifeste publié de l'état réel. Liste vide = tout concorde."""
    racine = racine or _RACINE
    chemin = os.path.join(racine, NOM_MANIFESTE)
    if not os.path.isfile(chemin):
        return [f"{NOM_MANIFESTE} absent"]
    with open(chemin, encoding="utf-8") as fh:
        publie = json.load(fh)
    ecarts = []

    frais = construis_corps(racine)
    if sceau(frais) != publie.get("sceau_du_corps"):
        ecarts.append("sceau_du_corps : publie %s, recalcule %s"
                      % (publie.get("sceau_du_corps"), sceau(frais)))
    anciens = {f["chemin"]: f for f in publie.get("corps", {}).get("anneau_1", {}).get("fichiers", [])}
    nouveaux = {f["chemin"]: f for f in frais["anneau_1"]["fichiers"]}
    for disparu in sorted(set(anciens) - set(nouveaux)):
        ecarts.append("fichier disparu de l'anneau 1 : " + disparu)
    for apparu in sorted(set(nouveaux) - set(anciens)):
        ecarts.append("fichier apparu dans l'anneau 1 : " + apparu)
    for commun in sorted(set(anciens) & set(nouveaux)):
        if anciens[commun]["sha256"] != nouveaux[commun]["sha256"]:
            ecarts.append("contenu modifie : " + commun)

    # L'empreinte de tête n'est pas scellée, mais elle doit rester VRAIE : sans ce contrôle,
    # `--verifie` pourrait sortir 0 pendant qu'elle désigne un commit inexistant.
    tete = publie.get("empreinte_de_tete", {})
    commit = tete.get("commit", "")
    if not commit or not _git(racine, "cat-file", "-t", commit) == "commit":
        ecarts.append("empreinte de tete : commit inconnu (%r)" % commit)
    elif subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"],
                        cwd=racine).returncode != 0:
        ecarts.append("empreinte de tete : %s n'est pas un ancetre de HEAD" % commit[:12])
    return ecarts


def main(argv=None):
    analyseur = argparse.ArgumentParser(description="Manifeste du produit livre")
    analyseur.add_argument("--verifie", action="store_true",
                           help="recalcule et compare, sans rien ecrire")
    args = analyseur.parse_args(argv)
    chemin = os.path.join(_RACINE, NOM_MANIFESTE)

    if args.verifie:
        ecarts = divergences(_RACINE)
        if ecarts:
            print("[DIVERGENCE]\n  " + "\n  ".join(ecarts), file=sys.stderr)
            return 2
        print("[OK] le manifeste concorde avec l'etat du depot")
        return 0

    manifeste = construis(_RACINE)
    with open(chemin, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(_serialise(manifeste))
    corps = manifeste["corps"]
    print(f"[OK] {NOM_MANIFESTE}")
    print(f"  anneau 1 : {corps['anneau_1']['n_fichiers']} fichiers, "
          f"{corps['anneau_1']['octets']} octets, sceau {corps['anneau_1']['sceau'][:16]}")
    print(f"  anneau 2 : {corps['anneau_2']['n_fichiers']} fichiers, "
          f"{corps['anneau_2']['octets']} octets, sceau {corps['anneau_2']['sceau'][:16]}")
    print(f"  sceau du corps : {manifeste['sceau_du_corps']}")
    print(f"  tete : {manifeste['empreinte_de_tete']['commit'][:12]} "
          f"({manifeste['empreinte_de_tete']['n_commits']} commits)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
