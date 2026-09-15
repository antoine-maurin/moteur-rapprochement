# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Produit `fixtures/llm_review/vecteurs_de_test.json` (O1).

    .venv\\Scripts\\python tools/enregistre_vecteurs_revue.py

## Ce que ce fichier produit, et ce qu'il ne produit PAS
Il produit des **vecteurs de test fabriqués** : des paires d'enregistrements INVENTÉS pour
la DoD, accompagnés de la réponse que l'on veut voir rejouée. Ce n'est **pas** une
transcription de modèle de langue, et l'artefact le déclare en toutes lettres dans son
en-tête de provenance (`est_une_transcription_de_modele: false`).

La distinction est le cœur de l'honnêteté de cette unité. Aucun runtime de modèle local
n'est déclaré dans `requirements.txt` (l'absence y est documentée comme une décision, pas
un oubli), et le runtime est hors ligne strict : **aucune réponse de modèle ne peut être
enregistrée dans ce build**. Prétendre le contraire — en nommant « transcription » un
fichier écrit à la main — serait la seule faute que ce mandat ne pardonne pas.

## Pourquoi des enregistrements INVENTÉS plutôt que des paires de la population
Choisir des paires réelles de la zone grise, puis décider de leur réponse, reviendrait à
choisir les réponses en sachant lesquelles sont bonnes. Les vecteurs sont donc synthétiques
et lisibles : ils éprouvent le **mécanisme** (les trois décisions, le piège de sous-chaîne,
le raté de rejeu), jamais la justesse d'une adjudication sur les données de démonstration.

## Ce que ces vecteurs éprouvent
- les trois décisions de l'énumération fermée ;
- le **piège de sous-chaîne** : `"NON_MATCH_APRES_REVUE"` contient `"MATCH_APRES_REVUE"`,
  et une réponse portant les deux jetons doit s'abstenir, pas promouvoir ;
- une paire volontairement **absente** de la table, pour que le raté de rejeu soit éprouvé
  comme un défaut tracé et non comme une abstention.
"""
from __future__ import annotations

import json
import os
import sys

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RACINE, "src"))

from engine import llm_client as clt                   # noqa: E402
from engine import normalize as nrm                    # noqa: E402

CHEMIN_FIXTURE = os.path.join(_RACINE, "fixtures", "llm_review", "vecteurs_de_test.json")

#: Chemin publié dans l'artefact : littéral POSIX en dur. Dérivé d'un `os.path.join`, il
#: rendrait une barre oblique inverse sous Windows et une barre ailleurs.
CHEMIN_PUBLIE = "fixtures/llm_review/vecteurs_de_test.json"

#: Paires INVENTÉES. `attendu` documente l'intention du vecteur ; c'est `texte` qui est
#: rejoué, et c'est l'analyseur qui tranche — un vecteur dont l'un ne suit pas l'autre est
#: précisément ce que la DoD doit attraper.
VECTEURS = [
    {
        "cas": "identifiant_et_nom_concordants",
        "attendu": clt.MATCH_APRES_REVUE,
        "a": {"record_id": "SYN_A1", "source_id": "SRC_A", "nom": "Duval",
              "prenom": "Camille", "date_naissance": "1988-04-12",
              "adresse": "12 rue des Lilas", "code_postal": "75011", "ville": "Paris",
              "email": "c.duval@example.fr", "telephone": "0612345678"},
        "b": {"record_id": "SYN_B1", "source_id": "SRC_B", "nom": "Duval",
              "prenom": "Camille", "date_naissance": None,
              "adresse": "12 r. des Lilas", "code_postal": "75011", "ville": "Paris",
              "email": "c.duval@example.fr", "telephone": None},
        "texte": ("DECISION: MATCH_APRES_REVUE\n"
                  "JUSTIFICATION: courriel identique et nom identique, adresse concordante "
                  "apres expansion de l'abreviation de voie."),
    },
    {
        "cas": "meme_adresse_personnes_differentes",
        "attendu": clt.NON_MATCH_APRES_REVUE,
        "a": {"record_id": "SYN_A2", "source_id": "SRC_A", "nom": "Bernard",
              "prenom": "Luc", "date_naissance": "1975-02-03",
              "adresse": "8 avenue Victor Hugo", "code_postal": "69003", "ville": "Lyon",
              "email": "l.bernard@example.fr", "telephone": "0700000001"},
        "b": {"record_id": "SYN_B2", "source_id": "SRC_B", "nom": "Fontaine",
              "prenom": "Sarah", "date_naissance": "1980-11-27",
              "adresse": "8 avenue Victor Hugo", "code_postal": "69003", "ville": "Lyon",
              "email": "s.fontaine@example.fr", "telephone": "0700000002"},
        "texte": ("DECISION: NON_MATCH_APRES_REVUE\n"
                  "JUSTIFICATION: meme adresse mais noms, prenoms, dates de naissance et "
                  "courriels tous distincts : co-residence, pas identite."),
    },
    {
        "cas": "preuve_trop_maigre",
        "attendu": clt.NON_TRANCHE,
        "a": {"record_id": "SYN_A3", "source_id": "SRC_A", "nom": "Martin",
              "prenom": None, "date_naissance": None, "adresse": None,
              "code_postal": "33000", "ville": "Bordeaux", "email": None,
              "telephone": None},
        "b": {"record_id": "SYN_B3", "source_id": "SRC_B", "nom": "Martin",
              "prenom": None, "date_naissance": None, "adresse": None,
              "code_postal": "33000", "ville": "Bordeaux", "email": None,
              "telephone": None},
        "texte": ("DECISION: NON_TRANCHE\n"
                  "JUSTIFICATION: un patronyme frequent et une commune ne suffisent pas ; "
                  "aucun attribut discriminant n'est renseigne des deux cotes."),
    },
    {
        "cas": "reponse_ambigue_deux_jetons",
        # Le texte porte les DEUX jetons : l'analyseur doit s'abstenir. C'est le piege de
        # sous-chaine, eprouve de bout en bout et pas seulement sur l'analyseur isole.
        "attendu": clt.NON_TRANCHE,
        "a": {"record_id": "SYN_A4", "source_id": "SRC_A", "nom": "Roux",
              "prenom": "Emma", "date_naissance": "1992-06-06",
              "adresse": "3 place du Marche", "code_postal": "44000", "ville": "Nantes",
              "email": "e.roux@example.fr", "telephone": "0755555555"},
        "b": {"record_id": "SYN_B4", "source_id": "SRC_B", "nom": "Roux",
              "prenom": "Emma", "date_naissance": "1992-06-06",
              "adresse": "3 place du Marche", "code_postal": "44000", "ville": "Nantes",
              "email": "emma.roux@example.fr", "telephone": "0755555555"},
        "texte": ("DECISION: MATCH_APRES_REVUE\n"
                  "DECISION: NON_MATCH_APRES_REVUE\n"
                  "JUSTIFICATION: reponse contradictoire, volontairement ambigue."),
    },
]

#: Paire volontairement NON enregistrée : elle éprouve le raté de rejeu.
VECTEUR_SANS_REPONSE = {
    "cas": "absente_de_la_table",
    "a": {"record_id": "SYN_A5", "source_id": "SRC_A", "nom": "Girard",
          "prenom": "Hugo", "date_naissance": "1969-01-30",
          "adresse": "77 boulevard Nationale", "code_postal": "59000", "ville": "Lille",
          "email": "h.girard@example.fr", "telephone": "0788888888"},
    "b": {"record_id": "SYN_B5", "source_id": "SRC_B", "nom": "Girard",
          "prenom": "Hugo", "date_naissance": "1969-01-30",
          "adresse": "77 bd Nationale", "code_postal": "59000", "ville": "Lille",
          "email": "h.girard@example.fr", "telephone": "0788888888"},
}


def _normalise(paire: dict) -> tuple:
    """Normalise les deux enregistrements d'un vecteur (comme le ferait le moteur)."""
    return nrm.normalise_record(paire["a"]), nrm.normalise_record(paire["b"])


def construis_transcription() -> dict:
    """Assemble la transcription rejouable : en-tête de verrou + table de réponses."""
    reponses = {}
    for vecteur in VECTEURS:
        a, b = _normalise(vecteur)
        cle = clt.cle_de_charge(clt.charge_de_revue(a, b))
        if cle in reponses:
            raise AssertionError(f"deux vecteurs posent la meme question : {vecteur['cas']}")
        reponses[cle] = {"texte": vecteur["texte"], "cas": vecteur["cas"]}
    return {
        "_lisez_moi": (
            "VECTEURS DE TEST FABRIQUES a la main pour la DoD de la revue de zone grise. Ce fichier "
            "n'est PAS une transcription de modele de langue : aucun runtime de modele "
            "local n'est declare dans requirements.txt et le runtime est hors ligne "
            "strict, donc aucune reponse de modele ne peut etre enregistree dans ce build. "
            "Les enregistrements sont INVENTES, jamais tires de la population de "
            "demonstration : ces vecteurs eprouvent le MECANISME de revue (les trois "
            "decisions, le piege de sous-chaine, le rate de rejeu), jamais la justesse "
            "d'une adjudication."),
        "provenance": {
            "nature": "VECTEURS_DE_TEST_FABRIQUES",
            "est_une_transcription_de_modele": False,
            "modele": None,
            "outil_producteur": "tools/enregistre_vecteurs_revue.py",
        },
        "entete": clt.entete_de_projection(),
        "reponses": reponses,
    }


def ecris_fixture(transcription: dict, chemin: str = CHEMIN_FIXTURE) -> str:
    """Écrit la fixture en JSON canonique (clés triées) : régénérable à l'identique."""
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(transcription, fh, sort_keys=True, ensure_ascii=False, indent=2)
        fh.write("\n")
    return chemin


def refuse_doublon(paires):
    """`object_pairs_hook` qui LÈVE sur clé dupliquée.

    `json.load` écraserait sinon un enregistrement par un autre, en silence : la réponse
    retenue dépendrait de l'ordre d'écriture du fichier. Fonction de module, et non close
    dans `charge_fixture`, pour être éprouvable directement.
    """
    vues = {}
    for cle, valeur in paires:
        if cle in vues:
            raise ValueError(f"cle dupliquee dans la transcription : {cle!r}")
        vues[cle] = valeur
    return vues


def charge_fixture(chemin: str = CHEMIN_FIXTURE) -> dict:
    """Charge une transcription depuis le disque — l'entrée/sortie vit ICI, pas au moteur."""
    with open(chemin, encoding="utf-8") as fh:
        return json.load(fh, object_pairs_hook=refuse_doublon)


def main() -> int:
    transcription = construis_transcription()
    chemin = ecris_fixture(transcription)
    sys.stdout.buffer.write(
        (f"fixture ecrite : {CHEMIN_PUBLIE}\n"
         f"  reponses enregistrees : {len(transcription['reponses'])}\n"
         f"  nature : {transcription['provenance']['nature']} "
         f"(transcription de modele : "
         f"{transcription['provenance']['est_une_transcription_de_modele']})\n"
         ).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
