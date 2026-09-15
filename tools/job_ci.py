#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""LES ÉTAPES du job d'oracles. Une seule fois, pour deux appelants.

## Pourquoi ce fichier existe plutôt qu'un YAML qui saurait tout

Ce dépôt n'a **aucun remote** (`git remote -v` ne rend rien). Un `.github/workflows/*.yml`
n'y sera donc jamais exécuté, et écrire « CI verte » à côté d'un fichier que rien ne lance
serait exactement l'affirmation non vérifiée que ce projet traque partout ailleurs — la même
classe de faute que « 289 tests verts » (qui en valait 288), ou qu'une empreinte publiée que
personne ne recalcule.

La sortie retenue : **les étapes vivent ici**, en Python de bibliothèque standard, exécutable
aujourd'hui sur cette machine. Le YAML provisionne l'environnement puis appelle ce script ;
`lancer_ci.bat` l'appelle aussi. Il n'existe nulle part ailleurs où écrire une étape, donc les
deux voies ne peuvent pas diverger. Ce qui est vert et **constatable** est ce que ce fichier
rend ; le YAML est une déclaration portable, prête à mordre le jour où un remote existe, et
son en-tête le dit sans détour.

## Un profil : la suite entière

Les packs de fixtures sont embarqués dans `fixtures/FIXTURE_PACK_GT_V1_*.json` : tout checkout
les contient, et `tests/` s'exécute en entier.

- `complet` : `tests/` en entier. Refuse de partir si un pack manque.

## Ce qui rend le vert non vide

Sans Node, les oracles de prose du navigateur sautent **proprement** et la suite est verte :
un job qui les installerait mal rendrait donc 0 sans avoir rien exécuté. Ce fichier pose
`MR_NODE_REQUIS=1`, que `tests/test_surfaces.py` lit à son point de passage unique vers Node
pour transformer ce saut en échec nommé. La variable est posée **ici** et non dans le YAML :
on ne peut pas désarmer la garde en éditant le workflow.

## Système

`windows-latest` : c'est le seul système où cette suite est observée verte, c'est celui du
lanceur local, et c'est la cible documentée du démonstrateur. Linux — qui est pourtant l'OS
qui *sert* le démonstrateur — est un **item ouvert nommé** dans `ENV_SETUP_README.md`, pas
une promesse déguisée en matrice `continue-on-error`.

Usage : `python tools/job_ci.py [--profil complet] [--repetition]`
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

__all__ = ["environnement_du_job", "main"]

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Les packs attendus par le profil `complet`, relativement à la racine du dépôt.
PACKS = ("fixtures/FIXTURE_PACK_GT_V1_1.json",
         "fixtures/FIXTURE_PACK_GT_V1_2.json")


class Echec(Exception):
    """Une étape a échoué. Le message porte la cause ET le remède."""


def environnement_du_job():
    """L'environnement que le job pose au-dessus du sien.

    Public et sans effet de bord : `tests/test_surfaces.py` l'interroge pour vérifier que le
    nom ET la valeur posés ici sont bien ceux qu'il lit. Un contrôle qui se contenterait de
    chercher un littéral dans cette source ne regarderait qu'un seul côté du câblage.
    """
    return {
        "MR_NODE_REQUIS": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
    }


def _dit(etape, message):
    print(f"[{etape}] {message}", flush=True)


# ─────────────────────────────────────── étapes ───────────────────────────────────────

def verifie_python(racine):
    if sys.version_info[:2] != (3, 12):
        raise Echec(f"Python 3.12 attendu, {sys.version.split()[0]} trouve. Remede : lancer "
                    f"le job avec l'interpreteur du .venv (install.bat), ou installer 3.12.")
    _dit("python", sys.version.split()[0])


def verifie_node(racine):
    """Un message clair au lieu de onze rouges — mais ce n'est PAS la garde.

    La garde est `MR_NODE_REQUIS`, lue au point de passage vers Node : si Node disparaît
    APRÈS cette vérification, les oracles partent quand même et échouent là-bas. Contrôler la
    précondition sans contrôler le résultat serait précisément l'affirmation que rien
    n'observe.
    """
    if not shutil.which("node"):
        raise Echec("node introuvable sur le PATH. Les oracles de prose du navigateur "
                    "executent src/surfaces/statique/logique.js sous Node ; sans lui ils ne "
                    "gardent rien. Remede : ENV_SETUP_README.md, section « Node.js ».")
    sortie = subprocess.run(["node", "--version"], capture_output=True, text=True)
    _dit("node", (sortie.stdout or sortie.stderr).strip())


def verifie_fixtures_hors_depot(racine):
    manquants = [p for p in PACKS if not os.path.isfile(os.path.join(racine, p))]
    if manquants:
        raise Echec("packs de fixtures absents : " + ", ".join(manquants) +
                    ". Le profil `complet` les exige ; ils font partie du depot (fixtures/).")
    _dit("fixtures", f"{len(PACKS)} packs presents")


def lance_pytest(racine, env, arguments):
    cmd = [sys.executable, "-m", "pytest", *arguments,
           "-q", "-rs", "--strict-markers", "-p", "no:cacheprovider"]
    _dit("pytest", " ".join(cmd[2:]))
    if subprocess.run(cmd, cwd=racine, env=env).returncode != 0:
        raise Echec("la suite est rouge")
    _dit("pytest", "vert")


# ─────────────────────────────────────── profils ──────────────────────────────────────

def joue(profil, racine):
    env = dict(os.environ, **environnement_du_job())
    verifie_python(racine)
    verifie_fixtures_hors_depot(racine)
    verifie_node(racine)
    lance_pytest(racine, env, ["tests/"])


def repetition(racine, profil):
    """Rejoue le profil sur un CHECKOUT NU, hors du dépôt.

    On extrait l'arbre de `HEAD` dans un dossier temporaire et on y rejoue.

    `git archive` archive le commit, pas l'arbre de travail : la répétition ne dit donc rien
    des modifications non committées, et elle le dit. C'est pour cela que `lancer_ci.bat`
    expose aussi le mode sur place.
    """
    tete = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=racine,
                          capture_output=True, text=True).stdout.strip()
    sale = subprocess.run(["git", "status", "--porcelain"], cwd=racine,
                          capture_output=True, text=True).stdout.strip()
    _dit("repetition", f"checkout nu du commit {tete}")
    if sale:
        _dit("repetition", "ATTENTION : l'arbre de travail porte des modifications NON "
                           "committees ; elles ne sont PAS dans cette repetition.")
    dossier = tempfile.mkdtemp(prefix="mr_ci_")
    archive = os.path.join(dossier, "tete.zip")
    if subprocess.run(["git", "archive", "--format=zip", "-o", archive, "HEAD"],
                      cwd=racine).returncode != 0:
        raise Echec("git archive a echoue")
    cible = os.path.join(dossier, "arbre")
    with zipfile.ZipFile(archive) as z:
        z.extractall(cible)
    _dit("repetition", cible)
    try:
        joue(profil, cible)
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def main(argv=None):
    analyseur = argparse.ArgumentParser(description="Job d'oracles — moteur-rapprochement")
    analyseur.add_argument("--profil", choices=("complet",), default="complet")
    analyseur.add_argument("--repetition", action="store_true",
                           help="rejouer sur un checkout nu de HEAD, hors du depot")
    args = analyseur.parse_args(argv)
    try:
        if args.repetition:
            repetition(_RACINE, args.profil)
        else:
            joue(args.profil, _RACINE)
    except Echec as erreur:
        print(f"[ECHEC] {erreur}", file=sys.stderr)
        return 2
    print(f"[OK] profil {args.profil}"
          + (" (repetition sur checkout nu)" if args.repetition else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
