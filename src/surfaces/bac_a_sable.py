# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Le bac à sable : le moteur, en direct, sur l'entrée de l'utilisateur (O3).

Seul module des surfaces à importer `engine`, et c'est sa raison d'être : il **exécute
réellement** la chaîne (normalisation → blocking → comparaison → décision → clôture → fusion).
Rien n'est simulé, rien n'est rejoué depuis un artefact.

Ce qu'il ne fait pas, en revanche : **noter**. Il n'importe pas `scorer`, ne connaît aucune
vérité terrain, et ne produit ni précision, ni rappel, ni F1. Sa sortie est une DÉCISION
accompagnée de sa preuve — quelles informations concordent, lesquelles divergent — jamais une
note. C'est la même frontière de non-circularité que partout ailleurs dans le projet, à ceci près
qu'ici elle sépare deux choses qu'un démonstrateur aurait toutes les raisons de confondre.

## Trois honnêtetés que ce module doit à l'utilisateur
1. **Le repli de l'estimation.** Sous `MIN_PAIRES_EM` paires, ou sur un mélange dégénéré,
   l'estimation ne converge pas et les poids retombent sur des a priori NON CALIBRÉS. Le
   moteur le dit dans sa trace ; la surface doit le relayer, sans quoi l'utilisateur croirait
   voir le moteur mesuré alors qu'il voit son repli.
2. **Les seuils ne sont pas les siens.** Le point DIMS-v2 a été dimensionné sur FX_001 V1.2.
   Appliqué à un autre jeu, il découpe une bande grise qui n'a plus de rapport avec le budget
   de revue visé — c'est la « dette §12.1 » que `pipeline.point` combat. On l'affiche.
3. **Le coût suit le PRODUIT « paires × longueurs² », pas les lignes.** Cent enregistrements
   d'un même code postal coûtent vingt-sept fois plus que cent enregistrements répartis, et
   les mêmes paires coûtent trente-cinq fois plus si les valeurs sont longues. Trois plafonds
   INDÉPENDANTS ne bornent pas leur produit : 55 lignes de valeurs à 200 caractères passaient
   les trois et demandaient 18,6 s sous une page qui promet cinq secondes. Le budget est donc
   posé sur le coût estimé lui-même, après blocking et avant comparaison.
"""
from __future__ import annotations

import hashlib
import time

import engine
from engine import blocking as blk
from engine import decide as dec

__all__ = [
    "PLAFOND_PAIRES", "PLAFOND_RECORDS", "LONGUEUR_MAX_VALEUR", "PLAFOND_COUT_COMPARAISON",
    "CHAMPS_RECORD", "CHAMPS_OBLIGATOIRES",
    "EntreeInvalide", "BudgetDepasse", "cout_comparaison", "valeurs_ecartees",
    "champs_egaux_apres_normalisation", "normalise_entree", "execute",
]

#: Plafond de paires, calibré sur le débit du PIRE régime mesuré — pas sur le meilleur.
#:
#: Le coût par paire varie d'un facteur 5,5 selon la séparabilité de l'entrée, parce que le
#: coût réel n'est pas la comparaison mais les itérations de l'estimation EM. Mesures sur la
#: machine de build (médianes, `.venv` Python 3.12) :
#:
#:     100 lignes / 1 code postal   4 950 paires    7 itérations    1,6 s   3 015 paires/s
#:     100 lignes / 5 codes postaux 4 950 paires  200 itérations    7,1 s     695 paires/s
#:     120 lignes / 5 codes postaux 7 140 paires  200 itérations   10,7 s     670 paires/s
#:
#: Une entrée dont les classes ne se séparent pas fait tourner l'EM jusqu'à sa borne, et le
#: débit tombe à ~660 paires/s. Un plafond calibré sur le régime rapide laissait donc passer
#: des calculs de 10 s sous une page qui promet cinq secondes. 1 600 paires tiennent dans
#: 2,4 s au pire régime observé ici.
#:
#: Borner les itérations EM aurait permis un plafond plus généreux, et aurait fait démontrer
#: au bac à sable un moteur qui n'est pas celui qu'on mesure ailleurs. On borne l'entrée.
PLAFOND_PAIRES = 1600

#: Plafond de lignes, qui borne le blocking lui-même. Il ne remplace pas le plafond de paires :
#: 57 lignes d'un même code postal suffisent à saturer celui-ci.
PLAFOND_RECORDS = 200

#: Plafond de longueur d'une valeur. Sans lui, deux enregistrements suffisent à occuper le
#: serveur plusieurs minutes : les comparateurs de chaînes sont quadratiques, et rien dans le
#: nombre de lignes ni dans le nombre de paires ne voit venir un pavé de 100 000 caractères
#: collé dans une cellule. Deux cents caractères passent largement tout nom ou adresse réels.
#:
#: Il ne suffit PAS à lui seul : c'est une borne par valeur, pas un budget. Le budget est
#: `PLAFOND_COUT_COMPARAISON` ci-dessous, qui croise les deux dimensions.
LONGUEUR_MAX_VALEUR = 200

#: Budget de comparaison, en « paires × Σ longueur² ». C'est LE plafond qui tient la promesse
#: des cinq secondes ; les trois précédents ne sont que des bornes bon marché sur chaque
#: dimension prise isolément.
#:
#: Trois plafonds indépendants ne bornent pas leur produit. Mesures sur la machine de build,
#: à 1 485 paires, valeurs de longueur uniforme :
#:
#:      40 caractères   Σ longueur² =   9 600   coût 1,4·10⁷    1,2 s
#:      80 caractères   Σ longueur² =  38 400   coût 5,7·10⁷    3,8 s
#:     200 caractères   Σ longueur² = 240 000   coût 3,6·10⁸   18,6 s   ← les 3 plafonds passent
#:
#: Le débit observé va de 1,7 à 2,2·10⁷ unités/s selon la longueur ; on retient la borne basse
#: 1,5·10⁷ et on s'accorde ~1,2 s de comparaison, en plus de ce que le plafond de paires
#: autorise déjà au pire régime d'estimation.
#:
#: **Ce qui est mesuré, et ce qui ne l'est pas.** Le pire cas ADMIS, cherché en croisant les
#: trois dimensions, coûte ~3,8 s sur la machine de build — la promesse de cinq secondes y
#: tient avec 20 % de marge. Une version antérieure de ce commentaire annonçait « ~3,0 s […]
#: 40 % de marge » : la re-mesure de ce jour, au repos et sur trois passages par cas, donne
#: 3,54 à 3,98 s selon le régime. Le chiffre est corrigé plutôt que conservé, et la marge
#: réelle — 20 %, non 40 % — est remontée telle quelle : c'est un arbitrage produit, pas une
#: variable d'ajustement du commentaire. Une version encore antérieure concluait « un facteur 2
#: pour une machine plus lente — le Space CPU l'est » : rien de tel n'a été mesuré, et le calcul
#: ne le donne pas. L'affirmation avait été retirée plutôt que corrigée à la baisse, parce
#: qu'aucun chiffre ne la remplaçait ; elle ne revient pas ici.
#:
#: La garde réelle est ailleurs, et elle est suffisante : `test_c4_le_pire_regime_admis_tient
#: _le_budget` mesure sur LA MACHINE QUI EXÉCUTE LA SUITE et exige `< 5 s`. Déployer sur une
#: machine trop lente fait donc rougir la suite sur cette machine-là — c'est le bon endroit
#: pour l'apprendre, et cela ne demande aucune extrapolation. Cette garde retient le MINIMUM de
#: trois mesures du pire régime : l'ordonnanceur ne peut qu'ajouter du temps, et une mesure
#: unique faisait rendre à l'oracle un verdict sur la charge de la machine — vu rouge à 5,27 s
#: sous douze tâches concurrentes, vert à 3,98 s au repos, sans qu'une ligne du produit ait
#: changé. Le seuil de 5 s, lui, n'a pas bougé : c'est le nombre affiché au visiteur.
#:
#: Sur des données réelles il ne se déclenche jamais : une fiche client dont l'adresse fait
#: 60 caractères et l'e-mail 40 pèse Σ longueur² ≈ 7 500, soit plus de 2 000 paires
#: autorisées — c'est le plafond de paires qui borne le premier. Il ne mord que sur ce que le
#: nombre de lignes ne voit pas venir.
PLAFOND_COUT_COMPARAISON = 15_000_000

#: Les attributs que le moteur compare, plus les deux clés techniques. L'ordre est celui de
#: l'affichage.
CHAMPS_RECORD = ("record_id", "source_id") + engine.ATTRIBUTS_COMPARE

#: Sans identifiant, le moteur ne peut rien indexer — et deux identifiants égaux le font lever.
CHAMPS_OBLIGATOIRES = ("record_id",)


class EntreeInvalide(ValueError):
    """L'entrée de l'utilisateur ne forme pas une collection d'enregistrements exploitable."""


class BudgetDepasse(ValueError):
    """L'entrée dépasse le plafond. Refusée explicitement, jamais tronquée en silence."""


def normalise_entree(brut) -> list:
    """Valide et projette l'entrée sur les seuls champs du moteur.

    Projeter n'est pas une politesse : accepter un champ inconnu laisserait croire qu'il entre
    dans la décision, alors que le moteur ne compare que `ATTRIBUTS_COMPARE`. Une chaîne vide
    devient `None` — « non renseigné » et « renseigné à vide » sont la même chose pour une
    fiche client, et le moteur a un niveau d'accord dédié pour ça.
    """
    if not isinstance(brut, list):
        raise EntreeInvalide("L'entrée doit être une liste d'enregistrements.")
    if len(brut) < 2:
        raise EntreeInvalide(
            "Il faut au moins deux enregistrements pour qu'il y ait quelque chose à rapprocher.")
    if len(brut) > PLAFOND_RECORDS:
        raise BudgetDepasse(
            f"{len(brut)} enregistrements : le bac à sable en accepte {PLAFOND_RECORDS} au plus.")

    records, vus = [], set()
    for rang, ligne in enumerate(brut, start=1):
        if not isinstance(ligne, dict):
            raise EntreeInvalide(f"Ligne {rang} : un enregistrement doit être un objet.")
        record = {}
        for champ in CHAMPS_RECORD:
            valeur = ligne.get(champ)
            if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
                valeur = str(valeur)          # un code postal saisi en nombre reste une valeur
            if valeur is not None and not isinstance(valeur, str):
                raise EntreeInvalide(
                    f"Ligne {rang}, champ « {champ} » : une valeur doit être du texte.")
            if isinstance(valeur, str):
                if len(valeur) > LONGUEUR_MAX_VALEUR:
                    raise BudgetDepasse(
                        f"Ligne {rang}, champ « {champ} » : {len(valeur)} caractères, au-delà "
                        f"des {LONGUEUR_MAX_VALEUR} acceptés. La comparaison de chaînes est "
                        f"quadratique — un pavé de texte dans une cellule occuperait le "
                        f"serveur plusieurs minutes sans jamais approcher les autres plafonds.")
                valeur = valeur.strip() or None
            record[champ] = valeur
        identifiant = record.get("record_id")
        if not identifiant:
            raise EntreeInvalide(f"Ligne {rang} : identifiant manquant.")
        if identifiant in vus:
            raise EntreeInvalide(f"Ligne {rang} : identifiant en double ({identifiant}).")
        vus.add(identifiant)
        records.append(record)
    return records


def _estime_paires(records, parametres) -> int:
    """Compte les paires candidates AVANT de payer la comparaison.

    Le blocking est la partie bon marché de la chaîne ; c'est la comparaison et l'estimation
    qui coûtent. Compter d'abord permet de refuser un calcul trop gros sans l'avoir commencé.
    """
    normalises = engine.normalise_records(records)
    bloc = blk.genere_paires_candidates(
        normalises, passes=parametres.passes_blocking,
        longueur_prefixe=parametres.longueur_prefixe,
        taille_bloc_max=parametres.taille_bloc_max)
    return len(bloc["paires"])


def cout_comparaison(records, n_paires: int) -> int:
    """Le coût de la phase de comparaison, dans l'unité de `PLAFOND_COUT_COMPARAISON`.

    Les comparateurs de chaînes sont quadratiques en la longueur : comparer une paire coûte,
    à peu près, la somme sur les attributs du produit des deux longueurs. On majore ce produit
    par le carré de la plus longue valeur rencontrée sur l'attribut — une borne supérieure, ce
    qui est le sens correct pour un garde-fou : il peut refuser un calcul qui serait passé, il
    ne peut pas laisser passer un calcul qui explose.

    Le modèle n'a pas besoin d'être exact, il a besoin d'être MONOTONE dans les deux
    dimensions que les plafonds séparés ne croisaient pas. Il l'est.
    """
    longueurs = {}
    for record in records:
        for attribut in engine.ATTRIBUTS_COMPARE:
            valeur = record.get(attribut)
            if valeur:
                longueurs[attribut] = max(longueurs.get(attribut, 0), len(valeur))
    return n_paires * sum(longueur * longueur for longueur in longueurs.values())


def valeurs_ecartees(records, enregistrement_dore: dict) -> dict:
    """Les valeurs concurrentes que la fusion n'a PAS retenues, par attribut.

    Avec deux fiches et deux graphies (« Aubry » / « Aubri »), aucune ne fait majorité : la
    règle de fusion en retient une, et la carte affichait la graphie corrompue comme fiche
    propre, sans un mot, sur la section même qui promet le nettoyage. Publier la valeur
    concurrente rend l'arbitrage lisible — c'est la promesse d'auditabilité du produit.

    Cette fonction vit ICI, et non dans l'outil de scénarios où elle est née, parce qu'elle
    doit servir les DEUX modes du bac à sable. Elle n'était appelée que par les scénarios : le
    mode manuel — le seul écran où le prospect voit le moteur tourner sur SES lignes — gardait
    le défaut que la surface déclarait fermé.
    """
    concurrentes = {}
    for attribut in engine.ATTRIBUTS_COMPARE:
        valeurs = []
        for record in records:
            valeur = record.get(attribut)
            if valeur and valeur not in valeurs:
                valeurs.append(valeur)
        if len(valeurs) > 1:
            concurrentes[attribut] = [v for v in valeurs
                                      if v != enregistrement_dore.get(attribut)]
    return concurrentes


def champs_egaux_apres_normalisation(record_a: dict, record_b: dict) -> list:
    """Les attributs que la NORMALISATION rend identiques, formes brutes mises à part.

    `ACCORD_FORT` n'est pas une égalité : c'est une similarité au-dessus de 0,90. Deux
    numéros de rue voisins peuvent la franchir sans être deux graphies de la même adresse.
    Dire « concorde malgré une écriture différente » d'un tel couple serait affirmer, sur la
    carte la plus argumentative de la démonstration, quelque chose que le lecteur voit être
    faux. Cette liste sépare les deux cas, et elle se calcule — elle ne se devine pas.
    """
    na, nb = engine.normalise_record(record_a), engine.normalise_record(record_b)
    return [attribut for attribut in engine.ATTRIBUTS_COMPARE
            if na.get(attribut) is not None and na.get(attribut) == nb.get(attribut)]


def _preuve(correspondance, record_a=None, record_b=None) -> dict:
    """Le « pourquoi » d'une paire : ce qui concorde, ce qui diverge, ce qui manque."""
    composantes = correspondance["composantes"]
    par_niveau = {niveau: [] for niveau in engine.NIVEAUX}
    for attribut in engine.ATTRIBUTS_COMPARE:
        par_niveau[composantes["accord_" + attribut]].append(attribut)
    preuve = {
        "concordent": par_niveau[engine.ACCORD_FORT],
        "concordent_partiellement": par_niveau[engine.ACCORD_PARTIEL],
        "divergent": par_niveau[engine.DESACCORD],
        "non_renseignes": par_niveau[engine.INDETERMINE_MANQUANT],
        "poids_par_champ": correspondance["poids_par_champ"],
    }
    if record_a is not None and record_b is not None:
        preuve["identiques_apres_normalisation"] = champs_egaux_apres_normalisation(
            record_a, record_b)
    return preuve


def execute(records, point) -> dict:
    """Exécute la chaîne complète et rend de quoi l'afficher. Déterministe.

    `point` est un `pipeline.point.PointDeFonctionnement` : les seuils viennent de l'artefact
    DIMS-v2, jamais d'un flottant écrit ici. Le module de point refuse par construction qu'un
    seuil soit recopié à la main, et cette surface n'a aucune raison d'être l'exception.
    """
    parametres = point.parametres_moteur()

    n_paires = _estime_paires(records, parametres)
    if n_paires > PLAFOND_PAIRES:
        raise BudgetDepasse(
            f"{len(records)} enregistrements produisent {n_paires} paires à comparer, au-delà "
            f"du plafond de {PLAFOND_PAIRES}. Le coût suit les paires, pas les lignes : des "
            f"enregistrements qui partagent tous le même code postal se comparent tous entre "
            f"eux. Retirez des lignes, ou diversifiez les codes postaux.")

    cout = cout_comparaison(records, n_paires)
    if cout > PLAFOND_COUT_COMPARAISON:
        plus_longue = max(
            (len(record[attribut]) for record in records
             for attribut in engine.ATTRIBUTS_COMPARE if record.get(attribut)),
            default=0)
        raise BudgetDepasse(
            f"{n_paires} paires de valeurs allant jusqu'à {plus_longue} caractères : le coût "
            f"de la comparaison dépasse le budget des cinq secondes. Comparer deux textes "
            f"coûte le produit de leurs longueurs — doubler la longueur des valeurs quadruple "
            f"le calcul, à nombre de paires égal. Raccourcissez les valeurs, ou retirez des "
            f"lignes.")

    depart = time.perf_counter()
    resultat = engine.execute_moteur(records, parametres)
    correspondances = resultat["correspondances"]
    partition = engine.cloture_transitive(
        correspondances, engine.univers_depuis_records(records))
    dores = engine.consolide_partition(partition, records)
    couverture = engine.couverture_transitive(partition, correspondances)
    duree = time.perf_counter() - depart

    index = {record["record_id"]: record for record in records}
    repartition = {verdict: 0 for verdict in engine.VERDICTS}
    for correspondance in correspondances:
        repartition[correspondance["verdict"]] += 1

    entites = []
    for groupe, dore in zip(partition, dores):
        # Les paires INTERNES au groupe : c'est d'elles que le groupe est fait.
        internes = [c for c in correspondances
                    if c["record_id_a"] in groupe and c["record_id_b"] in groupe]
        entites.append({
            "membres": list(groupe),
            "records": [index[rid] for rid in groupe],
            "enregistrement_dore": dore,
            "valeurs_ecartees": valeurs_ecartees([index[rid] for rid in groupe], dore),
            "paires": [{
                "a": c["record_id_a"], "b": c["record_id_b"],
                "verdict": c["verdict"], "poids_match": c["poids_match"],
                "preuve": _preuve(c, index[c["record_id_a"]], index[c["record_id_b"]]),
            } for c in internes],
        })

    # La file « à vérifier » : le moteur s'abstient plutôt que de deviner. On teste le verdict
    # par EGALITE — `revue_zone_grise` est un dict truthy même quand rien n'a été décidé, et
    # un `if correspondance["revue_zone_grise"]` ferait passer toute la zone grise pour revue.
    a_verifier = [{
        "a": c["record_id_a"], "b": c["record_id_b"],
        "record_a": index[c["record_id_a"]], "record_b": index[c["record_id_b"]],
        "poids_match": c["poids_match"],
        "preuve": _preuve(c, index[c["record_id_a"]], index[c["record_id_b"]]),
    } for c in correspondances if c["verdict"] == engine.ZONE_GRISE]

    estimation = resultat["rapport"]["estimation"]
    return {
        "n_records": len(records),
        "n_paires": len(correspondances),
        "repartition": repartition,
        "entites": entites,
        "n_entites": len(partition),
        "a_verifier": a_verifier,
        "couverture": couverture,
        "duree_s": duree,
        "empreinte": hashlib.sha256(
            engine.sortie_canonique(resultat).encode("utf-8")).hexdigest(),
        "estimation": {
            "repli": estimation.get("repli"),
            "motif_repli": estimation.get("motif_repli"),
            "convergence": estimation.get("convergence"),
            "iterations": estimation.get("iterations"),
            "min_paires_em": dec.MIN_PAIRES_EM,
        },
        "point": {
            "t_mu": point.t_mu,
            "t_lambda": point.t_lambda,
            "nom": point.nom,
            "provisoire": point.provenance.get("provisoire"),
            # Les seuils viennent d'une AUTRE population. Le dire ici est la seule façon
            # d'empêcher que la démonstration se lise comme un étalonnage.
            "dimensionne_sur": point.provenance.get("fixture"),
        },
    }
