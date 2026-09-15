# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Produit les SCÉNARIOS de démonstration et leurs résultats figés.

    .venv\\Scripts\\python tools/produit_scenarios.py

## Pourquoi les résultats sont figés, et pourquoi ce n'est pas de la triche
Un scénario riche — celui qui montre un vrai nettoyage — pèse des centaines de fiches. Mesuré :
400 lignes font 79 800 paires et **57 secondes**. Le budget de la surface est de 5. Les
scénarios sont donc **calculés ici, au build**, et la surface AFFICHE le résultat déjà produit.

C'est exactement le régime du reste de la démo (non-circularité : la surface affiche, ne recompte
jamais), et c'est le seul honnête : promettre un calcul en direct sur 400 lignes serait une
promesse intenable. Le bac à sable garde un mode de **saisie manuelle** qui, lui, fait tourner
le moteur pour de vrai sous les 5 secondes — c'est là que la démonstration « le moteur tourne »
se tient, et la surface dit lequel est lequel.

## Le générateur n'est pas touché
`src/generator/` est une unité **close, verdictée et gelée par empreinte** : `regression_check`
bloque toute écriture qui la modifierait. Ce programme l'APPELLE par son interface publique
(`generate_pack`) et compose par-dessus ce qu'elle ne produit pas — l'habillage de source et
les personnes morales. Rien n'est écrit dans `src/generator/`.

## Les seuils sont RE-DÉRIVÉS sur chaque scénario
Transplanter le point DIMS-v2, dimensionné sur FX_001, découperait sur une autre population
une bande grise sans rapport avec le budget de revue visé — c'est la « dette §12.1 » que
`pipeline.point` combat. Chaque scénario re-dérive donc son point sur SA population, par
`point_depuis_records`, qui embarque les empreintes permettant à `verifie_provenance` de
confirmer la liaison. Le budget de revue est fixé bas pour que la file « à confirmer » reste
lisible : montrer trois doutes instruits vaut mieux que trente.

## Le SIRET n'entre JAMAIS dans le moteur
Le moteur compare huit attributs, et le SIRET n'en fait pas partie. Il est donc porté **à
côté** des enregistrements, dans une table séparée, et n'est jamais passé à `execute_moteur`.
Ce n'est pas une précaution de style : c'est ce qui rend structurellement impossible d'écrire
un jour « le moteur a vu que les SIRET diffèrent ». Le moteur hésite sur ce qu'il compare ;
le SIRET aide l'humain à trancher, et la surface le dit dans ces termes.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
import time

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RACINE, "src"))

import engine                                            # noqa: E402
import generator                                         # noqa: E402
from pipeline import point as pt                         # noqa: E402
# Une seule définition de « ce que la normalisation rend égal », partagée par l'outil et par
# le bac à sable : deux copies auraient divergé, et la phrase de preuve aurait dit une chose
# sur les scénarios et une autre en direct.
from surfaces import bac_a_sable                          # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Une seule règle d'empreinte pour les deux artefacts d'interface : elle divergeait entre les
# deux producteurs, et la même promesse d'intégrité couvrait deux comportements différents.
import empreinte_artefact                                 # noqa: E402

CHEMIN_ARTEFACT = "artifacts/ui_scenarios.json"

#: Budget de revue par scénario : le nombre de paires que le dimensionnement cherche à laisser
#: en zone grise. Bas volontairement — la file « à confirmer » doit s'instruire d'un coup d'œil.
BUDGET_REVUE_SCENARIO = 4

#: Nombre de cas douteux publiés au plus, et de groupes consolidés détaillés.
N_DOUTES_PUBLIES = 3


def _canon(objet) -> str:
    return json.dumps(objet, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))


def _commit() -> str:
    try:
        sortie = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_RACINE,
                                capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "indisponible"
    return sortie.stdout.strip() if sortie.returncode == 0 else "indisponible"


# --- Composition des personnes morales (hors du générateur, qui ne produit que des personnes) -----

_FORMES = ("SARL", "SAS", "EURL", "SA", "SASU")
_ACTIVITES = ("BTP", "Menuiserie", "Transports", "Conseil", "Plomberie", "Electricite",
              "Peinture", "Maconnerie", "Espaces Verts", "Nettoyage", "Informatique",
              "Metallerie", "Couverture", "Carrelage", "Terrassement")
_PATRONYMES = ("Martin", "Bernard", "Dubois", "Leroy", "Moreau", "Girard", "Lefevre",
               "Roux", "Fournier", "Morel", "Garnier", "Chevalier", "Robin", "Masson")
#: Couples de villes VOISINES : c'est le décor des cas à confirmer — deux entreprises
#: différentes que seule leur commune sépare.
_VILLES_PROCHES = (("Lille", "59000", "Roubaix", "59100"),
                   ("Lyon", "69003", "Villeurbanne", "69100"),
                   ("Nantes", "44000", "Saint-Herblain", "44800"),
                   ("Toulouse", "31000", "Blagnac", "31700"),
                   ("Bordeaux", "33000", "Merignac", "33700"))

#: Villes ordinaires, en nombre : sans elles, 130 entreprises se partageaient dix communes et
#: sept voies, et le moteur — qui ne dispose que de six attributs sur huit pour une personne
#: morale (ni prénom, ni date de naissance) — les rapprochait toutes de proche en proche. La
#: clôture transitive faisait le reste : 172 lignes s'effondraient en 9 fiches. Une population
#: de démonstration doit être aussi DISCRIMINANTE qu'un vrai fichier fournisseurs.
#: Villes et codes postaux RÉELS. Un gabarit du genre « 210%02d » fabriquait des « 21005 »
#: pour Dijon, qui est 21000 : un prospect français repère un code postal inventé au premier
#: coup d'œil, et la démonstration se signale comme fabriquée sur son propre argument de
#: crédibilité. Les villes à arrondissements portent une plage réelle ; les autres, leur code.
_VILLES = (("Paris", tuple(f"750{n:02d}" for n in range(1, 21))),
           ("Lyon", tuple(f"6900{n}" for n in range(1, 10))),
           ("Marseille", tuple(f"130{n:02d}" for n in range(1, 17))),
           ("Toulouse", ("31000", "31100", "31200", "31300", "31400", "31500")),
           ("Nantes", ("44000", "44100", "44200", "44300")),
           ("Lille", ("59000", "59160", "59260", "59777")),
           ("Bordeaux", ("33000", "33100", "33200", "33300", "33800")),
           ("Nice", ("06000", "06100", "06200", "06300")),
           ("Rennes", ("35000", "35200", "35700")),
           ("Strasbourg", ("67000", "67100", "67200")),
           ("Montpellier", ("34000", "34070", "34080", "34090")),
           ("Rouen", ("76000", "76100")),
           ("Dijon", ("21000",)),
           ("Angers", ("49000", "49100")),
           ("Reims", ("51100",)),
           ("Grenoble", ("38000", "38100")),
           ("Le Mans", ("72000", "72100")),
           ("Clermont-Ferrand", ("63000", "63100")))
_VOIES = ("rue de la Gare", "avenue Jean Jaures", "boulevard Victor Hugo",
          "rue des Acacias", "route de Paris", "rue du Commerce", "allee des Chenes",
          "rue Pasteur", "avenue de la Liberte", "impasse des Vignes", "quai de Seine",
          "rue Gambetta", "boulevard Foch", "rue des Ecoles", "avenue du General Leclerc",
          "rue Saint-Michel", "place du Marche", "chemin des Sources")


def _siret(rng: random.Random) -> str:
    return " ".join("".join(str(rng.randint(0, 9)) for _ in range(n)) for n in (3, 3, 3, 5))


def _variantes_raison_sociale(forme: str, activite: str, patronyme: str) -> list:
    """Les façons dont une même entreprise s'écrit d'un fichier à l'autre.

    Ce ne sont pas des fautes de frappe inventées : c'est ce qu'un fichier fournisseurs
    contient réellement après une migration — la forme juridique déplacée, abrégée, ponctuée
    ou absente.
    """
    return [
        f"{forme} {patronyme} {activite}",
        f"{patronyme} {activite}",
        f"{patronyme} {activite} {forme}",
        f"{forme} {patronyme.upper()} {activite.upper()}",
        f"{patronyme} {'.'.join(activite[:3].upper())}.",
    ]


def _entreprises(graine: str, n_entites: int, sources: tuple) -> tuple:
    """Des fiches fournisseurs déterministes, plus la table SIRET tenue À PART.

    Deux populations sont fabriquées ensemble :
      - des entreprises **réelles en double**, écrites différemment d'un fichier à l'autre :
        le moteur doit les rapprocher ;
      - des entreprises **distinctes qui se ressemblent** — même patronyme, même voie, villes
        voisines — dont les SIRET diffèrent : le moteur doit HÉSITER sur ses huit attributs,
        et c'est l'humain qui tranchera avec le SIRET.
    """
    rng = random.Random(int(hashlib.sha256(graine.encode("utf-8")).hexdigest()[:12], 16))
    records, sirets, homonymes, n = [], {}, set(), 0

    def ajoute(nom, adresse, cp, ville, email, tel, source, siret):
        nonlocal n
        n += 1
        rid = f"FOU_{n:04d}"
        records.append({"record_id": rid, "source_id": source, "nom": nom, "prenom": None,
                        "date_naissance": None, "adresse": adresse, "code_postal": cp,
                        "ville": ville, "email": email, "telephone": tel})
        sirets[rid] = siret
        return rid

    # Les HOMONYMES : deux entreprises DIFFÉRENTES portant la même raison sociale, avec des
    # SIRET distincts. Leur ressemblance est GRADUÉE — de « même voie, même numéro » à « voie
    # différente » — et c'est délibéré : la bande grise que le dimensionnement découpe est
    # étroite, et sa position dépend de la distribution entière. Placer tous les homonymes au
    # même degré de ressemblance revenait à parier sur cette position ; le premier essai l'a
    # perdu, et le moteur a FUSIONNÉ les paires conçues pour être douteuses — une démonstration
    # qui montrait précisément la faute qu'on veut lui voir éviter. Étalés, il s'en trouve
    # toujours dans la bande, où qu'elle tombe, et le moteur les signale pour de bon.
    # Un homonyme par couple de villes voisines, pas davantage : au-delà, deux homonymes
    # retombaient sur la même commune et se rapprochaient l'un l'autre par la ville, ce qui
    # ajoutait des fusions fautives au lieu de doutes lisibles.
    # Les homonymes ne sont plus tassés en tête : sinon ils occupaient les dix premières
    # puces de « déjà uniques », et la section censée prouver que le moteur ne sur-fusionne
    # pas s'ouvrait sur cinq paires de noms identiques. On les répartit sur toute la plage.
    n_pieges = len(_VILLES_PROCHES)
    pas_piege = max(1, n_entites // (n_pieges + 1))
    indices_pieges = {(k + 1) * pas_piege for k in range(n_pieges)}
    for i in range(n_entites):
        # Patronyme et activité DÉCORRÉLÉS : indexer le patronyme sur `i // len(_ACTIVITES)`
        # donnait le même à quinze entreprises d'affilée — et à TOUS les homonymes, qui
        # tombent en tête de boucle. Résultat : « Martin BTP » et « Martin Électricité » se
        # rapprochaient, la clôture transitive les enchaînait, et neuf groupes sur trente-neuf
        # fusionnaient des SIRET différents. Un fichier fournisseurs réel ne concentre pas ses
        # raisons sociales ainsi, et la démonstration montrait une faute que le moteur ne
        # commet pas sur de la donnée normale.
        forme = _FORMES[i % len(_FORMES)]
        patronyme = _PATRONYMES[i % len(_PATRONYMES)]
        activite = _ACTIVITES[(i * 7) % len(_ACTIVITES)]
        # Chaque entreprise porte une identité PROPRE : numéro de voie unique, courriel et
        # téléphone dérivés de son index. Deux fournisseurs différents ne doivent pas se
        # ressembler par accident, sinon le moteur les enchaîne et la démonstration montre
        # un moteur qui fusionne tout.
        voie = _VOIES[i % len(_VOIES)]
        numero = 3 + (i * 7) % 190
        adresse = f"{numero} {voie}"
        # Le domaine ne porte PAS l'indice de génération : « contact@robinnettoyage12.fr »
        # signalait la fabrication à l'écran. L'unicité vient du couple patronyme × activité,
        # qui ne se répète pas avant 210 entreprises — au-delà des 130 produites ici.
        base = f"{patronyme}{activite}".lower().replace(" ", "").replace("-", "")
        courriel = f"contact@{base}.fr"
        tel = "0%d %02d %02d %02d %02d" % (1 + i % 5, (i * 13) % 100, (i * 29) % 100,
                                           (i * 7) % 100, (i * 3) % 100)
        siret = _siret(rng)
        variantes = _variantes_raison_sociale(forme, activite, patronyme)

        if i in indices_pieges:
            rang = sorted(indices_pieges).index(i)
            ville, cp, ville2, cp2 = _VILLES_PROCHES[rang % len(_VILLES_PROCHES)]
            degre = rang % 3       # 0 = très ressemblant, 2 = nettement moins
            adresse_jumelle = {
                0: adresse,                                   # même voie, même numéro
                1: f"{numero + 2} {voie}",                    # même voie, numéro voisin
                2: f"{numero} {_VOIES[(i + 5) % len(_VOIES)]}",   # voie différente
            }[degre]
            ajoute(variantes[0], adresse, cp, ville, courriel, tel,
                   sources[0], siret)
            homonyme = ajoute(variantes[0], adresse_jumelle, cp2, ville2,
                              None if degre else courriel.replace("contact", "accueil"),
                              None, sources[1], _siret(rng))
            homonymes.add(homonyme)
            continue

        # La ville est indexée sur `i // len(_PATRONYMES)` : deux entreprises qui partagent un
        # patronyme (donc `i` congrus modulo le nombre de patronymes) tombent alors forcément
        # dans des communes différentes. Sans cela, « Bernard Maçonnerie » et « Bernard
        # Plomberie » se retrouvaient à Lyon toutes les deux, et le moteur les fusionnait —
        # une coïncidence que J'AI introduite dans la donnée, pas un défaut du moteur.
        # Indexer sur le seul quotient rangeait les quatorze premières entreprises dans la
        # même commune, et les premiers groupes affichés étaient tous parisiens : un fichier
        # fournisseurs ne ressemble pas à ça, et la démonstration paraissait fabriquée. En
        # ajoutant le reste, les villes défilent d'une entreprise à l'autre — tout en gardant
        # la propriété qui compte : deux entreprises de même patronyme (mêmes `i` modulo le
        # nombre de patronymes) restent dans des communes différentes.
        ville, codes = _VILLES[(i // len(_PATRONYMES) + i % len(_PATRONYMES)) % len(_VILLES)]
        cp = codes[i % len(codes)]
        ajoute(variantes[0], adresse, cp, ville, courriel, tel,
               sources[0], siret)
        if rng.random() < 0.32:
            # La MÊME entreprise, réécrite par le nouveau logiciel : même SIRET, même adresse,
            # raison sociale sous une autre forme, contacts parfois perdus à la migration.
            ajoute(variantes[1 + (i % (len(variantes) - 1))], adresse, cp, ville,
                   courriel if rng.random() < 0.6 else None,
                   tel.replace(" ", "") if rng.random() < 0.7 else None,
                   sources[1], siret)
    return records, sirets, homonymes


def _est_personne_morale(pivot: dict) -> bool:
    """Le pivot d'une entité décrit-il une société plutôt qu'un particulier ?

    `generator._clean_entity` tire environ 15 % de personnes morales, et leur donne ni prénom
    ni ville. La signature est structurelle — on ne va pas lire la liste privée des raisons
    sociales du générateur, qui pourrait changer sans prévenir. Le pivot suffit : c'est le
    seul enregistrement d'une entité que la corruption n'a pas touché.
    """
    return pivot.get("prenom") is None and pivot.get("ville") is None


def _personnes(graine: str, n_entites: int, sources: tuple) -> list:
    """Des fiches de PARTICULIERS issues du générateur, ré-étiquetées par source de scénario.

    `generate_pack` produit exactement ce qu'il faut : des entités réparties sur trois
    sources, un même client écrit différemment d'une source à l'autre, des champs manquants —
    et tout cela reproductible depuis la graine. On ne réécrit pas ce qui existe.

    ## Pourquoi on écarte les personnes morales
    Le générateur en tire environ 15 %, sans prénom ni ville, et avec une date de naissance.
    Sur un scénario vendu « le même CLIENT revient plusieurs fois », le prospect lisait
    « date de naissance : 13/12/2003 » sous un nom de SARL. On filtre ici, dans l'outil de
    scénarios — le générateur est clos et gelé, et de toute façon ces entités-là ont leur propre
    scénario, celui des fournisseurs, où elles sont construites pour ce qu'elles sont.
    """
    pack = generator.generate_pack(seed=graine, n_entities=n_entites)
    correspondance_sources = dict(zip(generator.generator.SOURCES, sources))

    entite_de = {g["record_id"]: g["id_entite_vraie"] for g in pack["ground_truth"]}
    par_entite = {}
    for record in pack["records"]:
        par_entite.setdefault(entite_de[record["record_id"]], []).append(record)

    records = []
    for entite in sorted(par_entite):
        membres = sorted(par_entite[entite], key=lambda r: r["record_id"])
        if _est_personne_morale(membres[0]):
            continue
        for record in membres:
            projete = {cle: record.get(cle) for cle in
                       ("record_id", "source_id") + engine.ATTRIBUTS_COMPARE}
            projete["source_id"] = correspondance_sources.get(record["source_id"],
                                                              record["source_id"])
            records.append(projete)
    records.sort(key=lambda r: r["record_id"])
    return records


# --- Les scénarios -------------------------------------------------------------------------

SCENARIOS = (
    {
        "cle": "clients",
        "titre": "Réunir vos clients éparpillés dans plusieurs fichiers",
        "accroche": (
            "Vos clients vivent dans plusieurs listes — un export de votre CRM, les contacts "
            "d'un salon, la liste d'une campagne — et le même client y revient plusieurs fois, "
            "écrit différemment. Vous relancez deux fois la même personne, et vous payez pour "
            "des fiches en double."),
        "benefice": "Trois fichiers, deux formats, une seule base propre.",
        "graine": "SCENARIO::clients::seed-0001",
        # Environ 15 % des entités tirées sont des personnes morales et sont écartées :
        # on en demande davantage pour retrouver le volume visé.
        "n_entites": 355,
        "genre": "personnes",
        "sources": ("clients_crm.csv", "contacts_salon.xlsx", "campagne_email.csv"),
        "formats": ("csv", "xlsx", "csv"),
    },
    {
        "cle": "fournisseurs",
        "titre": "Dédoublonner votre fichier fournisseurs après un changement de logiciel",
        "accroche": (
            "Après une migration de logiciel, votre fichier fournisseurs a gonflé : le même "
            "fournisseur revient sous plusieurs orthographes. Résultat : des paiements en "
            "double et une comptabilité impossible à réconcilier."),
        "benefice": "Deux fichiers, deux formats, un fichier fournisseurs assaini.",
        "graine": "SCENARIO::fournisseurs::seed-0001",
        "n_entites": 130,
        "genre": "entreprises",
        "sources": ("fournisseurs_ancien.csv", "fournisseurs_migration.pdf"),
        "formats": ("csv", "pdf"),
    },
    {
        "cle": "contacts",
        "titre": "Unifier une base de contacts venue de plusieurs outils",
        "accroche": (
            "Newsletter, formulaires du site, ancien tableur : vos contacts se sont accumulés "
            "dans plusieurs outils, souvent en double. Vos envois partent plusieurs fois à la "
            "même personne."),
        "benefice": "Trois outils, une seule liste de contacts.",
        "graine": "SCENARIO::contacts::seed-0002",
        "n_entites": 225,
        "genre": "personnes",
        "sources": ("newsletter.csv", "formulaires_site.csv", "ancien_fichier.xlsx"),
        "formats": ("csv", "csv", "xlsx"),
    },
)


def _preuve(correspondance, record_a, record_b) -> dict:
    composantes = correspondance["composantes"]
    par_niveau = {niveau: [] for niveau in engine.NIVEAUX}
    for attribut in engine.ATTRIBUTS_COMPARE:
        par_niveau[composantes["accord_" + attribut]].append(attribut)
    return {
        "concordent": par_niveau[engine.ACCORD_FORT],
        "concordent_partiellement": par_niveau[engine.ACCORD_PARTIEL],
        "divergent": par_niveau[engine.DESACCORD],
        "non_renseignes": par_niveau[engine.INDETERMINE_MANQUANT],
        # Ce que la NORMALISATION rend égal — à distinguer d'un accord fort obtenu par
        # simple similarité. La surface ne peut dire « la même chose écrite différemment »
        # que du premier cas.
        "identiques_apres_normalisation": bac_a_sable.champs_egaux_apres_normalisation(
            record_a, record_b),
    }


def _construit_scenario(scenario: dict) -> dict:
    if scenario["genre"] == "entreprises":
        records, sirets, _homonymes = _entreprises(
            scenario["graine"], scenario["n_entites"], scenario["sources"])
    else:
        records = _personnes(scenario["graine"], scenario["n_entites"], scenario["sources"])
        sirets = {}

    depart = time.perf_counter()
    # Les seuils sont re-dérivés SUR CETTE population : le point porte alors ses empreintes,
    # et `verifie_provenance` peut confirmer la liaison au lieu de la supposer.
    point, _ = pt.point_depuis_records(records, budget_revue=BUDGET_REVUE_SCENARIO,
                                       nom=f"scenario-{scenario['cle']}")
    resultat = engine.execute_moteur(records, point.parametres_moteur())
    correspondances = resultat["correspondances"]
    partition = engine.cloture_transitive(
        correspondances, engine.univers_depuis_records(records))
    dores = engine.consolide_partition(partition, records)
    duree = time.perf_counter() - depart

    index = {record["record_id"]: record for record in records}
    consolidees, deja_uniques = [], []
    for groupe, dore in zip(partition, dores):
        if len(groupe) == 1:
            deja_uniques.append(index[groupe[0]])
            continue
        internes = [c for c in correspondances
                    if c["record_id_a"] in groupe and c["record_id_b"] in groupe
                    and c["verdict"] == engine.MATCH]
        # Les champs sur lesquels les sources ne disaient PAS la même chose. La règle vit dans
        # `bac_a_sable`, partagée avec le mode manuel : définie ici, elle ne servait que les
        # scénarios, et l'écran où le prospect voit le moteur tourner sur SES lignes affichait
        # la graphie corrompue comme fiche propre — le défaut que cette correction ferme.
        concurrentes = bac_a_sable.valeurs_ecartees([index[rid] for rid in groupe], dore)

        consolidees.append({
            "membres": list(groupe),
            "records": [index[rid] for rid in groupe],
            "enregistrement_dore": dore,
            "valeurs_ecartees": concurrentes,
            "paires": [{"a": c["record_id_a"], "b": c["record_id_b"],
                        "preuve": _preuve(c, index[c["record_id_a"]],
                                          index[c["record_id_b"]])} for c in internes],
        })

    grises = [c for c in correspondances if c["verdict"] == engine.ZONE_GRISE]

    def merite_d_etre_montre(correspondance) -> tuple:
        """Ordre de présentation des doutes. Tri STABLE : l'ordre du moteur départage.

        Un doute ne vaut d'être montré que s'il se COMPREND. La zone grise est une bande de
        budget : la première paire venue oppose deux fiches qui ne partagent que la ville, et
        un lecteur y voit un moteur qui hésite sans raison. On présente donc d'abord celles
        dont le NOM concorde — le doute y est lisible sans commentaire — puis, parmi elles,
        celles dont le SIRET diffère, qui portent l'argument. On choisit une ILLUSTRATION ;
        le verdict, lui, n'est pas choisi, et le total est publié à côté.
        """
        nom_concorde = correspondance["composantes"]["accord_nom"] == engine.ACCORD_FORT
        siret_a, siret_b = (sirets.get(correspondance["record_id_a"]),
                            sirets.get(correspondance["record_id_b"]))
        siret_parle = bool(siret_a and siret_b and siret_a != siret_b)
        return (0 if nom_concorde else 1, 0 if siret_parle else 1)

    grises.sort(key=merite_d_etre_montre)

    # Un doute porte sur DEUX ENTITÉS, pas sur deux lignes. Sans cette déduplication, le
    # scénario clients posait deux fois la même question — « REC_0417 est-il l'entité
    # {REC_0029, REC_0030} ? » — une fois par membre du groupe, et rien n'empêchait d'y
    # répondre « oui » puis « non ». On garde un doute par couple d'entités.
    entite_de = {rid: n for n, groupe in enumerate(partition) for rid in groupe}
    a_confirmer, couples_vus = [], set()
    for c in grises:
        couple = frozenset((entite_de[c["record_id_a"]], entite_de[c["record_id_b"]]))
        if couple in couples_vus:
            continue
        couples_vus.add(couple)
        if len(a_confirmer) >= N_DOUTES_PUBLIES:
            continue
        a_confirmer.append({
            "a": c["record_id_a"], "b": c["record_id_b"],
            "record_a": index[c["record_id_a"]], "record_b": index[c["record_id_b"]],
            "preuve": _preuve(c, index[c["record_id_a"]], index[c["record_id_b"]]),
            "siret_a": sirets.get(c["record_id_a"]),
            "siret_b": sirets.get(c["record_id_b"]),
            # De quoi que la surface compte JUSTE après un arbitrage : fusionner deux fiches
            # seules ne fait pas le même effet que rattacher une fiche à un groupe existant.
            "entite_a": entite_de[c["record_id_a"]],
            "entite_b": entite_de[c["record_id_b"]],
            "taille_entite_a": len(partition[entite_de[c["record_id_a"]]]),
            "taille_entite_b": len(partition[entite_de[c["record_id_b"]]]),
        })

    n_par_source = {}
    for record in records:
        n_par_source[record["source_id"]] = n_par_source.get(record["source_id"], 0) + 1

    return {
        "cle": scenario["cle"],
        "titre": scenario["titre"],
        "accroche": scenario["accroche"],
        "benefice": scenario["benefice"],
        "fichiers": [{"nom": nom, "format": fmt, "n_lignes": n_par_source.get(nom, 0)}
                     for nom, fmt in zip(scenario["sources"], scenario["formats"])],
        "n_lignes": len(records),
        "n_fiches_uniques": len(partition),
        "n_consolidees": len(consolidees),
        "n_deja_uniques": len(deja_uniques),
        # Le TOTAL des doutes distincts que le moteur a produits, et le nombre montré. La
        # surface doit afficher le total : annoncer « 3 à confirmer » quand le moteur en a
        # laissé 4 sous-déclare le doute, et le sous-déclare dans le sens qui flatte.
        "n_a_confirmer": len(couples_vus),
        "n_a_confirmer_montres": len(a_confirmer),
        "n_paires_grises": len(grises),
        "consolidees": consolidees,
        "deja_uniques": deja_uniques,
        "a_confirmer": a_confirmer,
        "sirets": sirets,
        "regle_des_doutes": (
            "parmi les paires que le moteur a mises en zone grise : d'abord celles dont le nom "
            "concorde (le doute y est lisible), puis celles dont le SIRET diffère ; à égalité, "
            "l'ordre canonique du moteur. Le total est publié à côté de l'échantillon, et le "
            "verdict de chaque paire vient du moteur, jamais de ce tri."),
        "point": point.en_dict(),
        "duree_calcul_build_s": duree,
        "empreinte_sortie": hashlib.sha256(
            engine.sortie_canonique(resultat).encode("utf-8")).hexdigest(),
    }


def construit() -> dict:
    contenu = {
        "_lisez_moi": (
            "SCÉNARIOS de démonstration et leurs résultats, CALCULÉS AU BUILD. "
            "Un scénario riche prend de 14 à 57 secondes : la surface AFFICHE ce résultat, "
            "elle ne le recalcule pas. Le mode saisie manuelle du bac à sable, lui, fait "
            "tourner le moteur en direct. Ce fichier ne contient AUCUNE métrique de qualité : "
            "il porte des décisions, pas des notes."),
        "provenance": {
            "commit": _commit(),
            "version_python": ".".join(str(n) for n in sys.version_info[:3]),
            "version_generateur": generator.GENERATOR_VERSION,
            "graine_em": engine.GRAINE_EM_SCELLEE,
            "champs_compares": list(engine.ATTRIBUTS_COMPARE),
            "budget_revue": BUDGET_REVUE_SCENARIO,
            "note_siret": (
                "le SIRET est porté HORS des enregistrements et n'est jamais passé au moteur : "
                "il ne fait pas partie des huit attributs comparés. Le moteur hésite sur ce "
                "qu'il compare ; le SIRET aide l'humain à trancher."),
        },
        "scenarios": [_construit_scenario(s) for s in SCENARIOS],
    }
    # L'empreinte porte sur le CONTENU, jamais sur le temps qu'il a fallu pour le produire ni
    # sur le commit qui l'a produit. La règle vit dans `empreinte_artefact`, partagée avec
    # l'autre producteur : elle divergeait entre les deux, et la même promesse couvrait deux
    # comportements — l'un reproductible, l'autre non.
    contenu["empreinte_contenu"] = empreinte_artefact.empreinte(contenu)
    contenu["_note_empreinte"] = empreinte_artefact.NOTE
    return contenu


def main() -> int:
    contenu = construit()
    chemin = os.path.join(_RACINE, CHEMIN_ARTEFACT)
    with open(chemin, "w", encoding="utf-8") as fh:
        json.dump(contenu, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"ecrit {CHEMIN_ARTEFACT}")
    for s in contenu["scenarios"]:
        print(f"  {s['cle']:14s} {s['n_lignes']:4d} lignes -> {s['n_fiches_uniques']:4d} fiches"
              f" | {s['n_consolidees']:3d} consolidees, {s['n_deja_uniques']:4d} deja uniques,"
              f" {s['n_a_confirmer']:2d} a confirmer | build {s['duree_calcul_build_s']:.1f}s")
    print(f"  empreinte_contenu : {contenu['empreinte_contenu']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
