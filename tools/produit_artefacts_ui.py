# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Matérialise les SORTIES DU MOTEUR dont les surfaces ont besoin (O2).

    .venv\\Scripts\\python tools/produit_artefacts_ui.py

## Pourquoi ce fichier existe
Les cinq artefacts de `artifacts/` ne portent que des **mesures agrégées** : pas une seule
CORRESPONDENCE, pas une entité, pas un enregistrement doré. Or la Vitrine doit montrer un
vrai moment de rapprochement, et le bac à sable doit partir d'un extrait réel.

Deux façons de le faire, et une seule est acceptable :

1. faire tourner le moteur **dans la surface** au chargement de la page — la surface
   calculerait alors ce qu'elle affiche, et il faudrait embarquer la fixture, qui vit dans
   `fixtures/`, hors du paquet déployé, dans le démonstrateur ;
2. figer les sorties **ici**, à l'avance, dans un artefact que la surface se contente de
   lire — ce que fait ce programme.

La seconde préserve la non-circularité au sens fort : la surface **affiche, ne recompte jamais**,
et elle n'a besoin ni du moteur ni de la fixture pour rendre la Vitrine et la Salle des machines.
Le bac à sable, lui, exécute réellement le moteur : c'est sa raison d'être, et il le fait sur
l'entrée de l'utilisateur, jamais pour recalculer un chiffre affiché ailleurs.

## Rien n'est choisi à la main
Le cas héros et l'extrait de démonstration ne sont **pas** des identifiants recopiés : ce sont
les résultats de **règles de sélection déterministes**, écrites ci-dessous et rejouées à chaque
exécution. L'artefact publie la règle à côté de son résultat, de sorte qu'un lecteur puisse
contester le choix plutôt que d'avoir à le croire. Recopier `REC_00163` aurait produit la même
donnée sans la propriété qui compte : la reproductibilité du choix.

## Ce programme LIT la vérité terrain, et il faut dire pourquoi
Depuis le briefing de clôture (point 3), le cas héros doit être un cas dont la **fiche de
référence ne retient aucune valeur corrompue**. Le défaut était visible : la fusion retenait
« Aubri » là où le vrai nom, lisible dans l'adresse de courriel, était « Aubry ». Une fiche de
référence qui porte un nom faux, sur l'écran censé prouver la valeur, se retourne contre elle.

Trancher demande de savoir quelle valeur est la vraie — donc de lire le pack. `verite_canonique`
le fait, une fois, et **uniquement pour écarter des candidats**. Ce qui suit est la frontière,
et elle est étroite par construction :

  - la vérité terrain **filtre** l'ensemble des cas éligibles, elle n'entre dans **aucun**
    verdict : les décisions publiées restent celles de `engine.execute_moteur`, prises sans
    elle, sur les mêmes paramètres qu'ailleurs ;
  - elle n'atteint **pas** l'artefact : aucune valeur canonique, aucun identifiant d'entité
    vraie n'est écrit dans `ui_demonstration.json`. Ce qui y est publié, c'est la **règle** ;
  - la règle est **re-vérifiée** par un oracle indépendant de ce programme, qui relit le pack
    lui-même (`tests/test_surfaces.py`). L'affirmation n'est pas auto-certifiée ici.

Choisir une ILLUSTRATION par une règle publiée est le régime déjà retenu pour l'extrait de
démonstration et pour la file de doutes des scénarios. Ce qui change, c'est que la règle
consulte maintenant la vérité terrain — et ce paragraphe existe pour que personne n'ait à le
découvrir en lisant le code.

## Non-circularité — aucune métrique n'est produite ici
Il importe `engine` et `pipeline`, **jamais `scorer`** : `tests/test_surfaces.py` l'éprouve
par analyse des imports de ce fichier, contrôle positif à l'appui. Aucune métrique (précision,
rappel, F1) n'est calculée ni recopiée dans sa sortie — ces chiffres-là vivent dans
`banc_ub6.json`, produits par un scoreur séparé du moteur.

Une précision sur la portée de la garde, parce que la version précédente de ce paragraphe
promettait plus : l'oracle qui interdit de **recomposer** une métrique (analyse de l'AST des
opérations) porte sur les modules d'affichage, pas sur ce fichier. Ce qui est vérifié ici,
c'est l'absence d'import de `scorer` — ce qui suffit à rendre le recomptage impossible, faute
d'avoir de quoi le faire.

C'est cela que la non-circularité interdit : **noter sa propre copie**. Lire la vérité terrain
pour écarter un exemple trompeur ne note rien, et le moteur ne la voit toujours pas.

`benchmark.substrat` est importé pour l'ouverture vérifiée de la fixture. **Et il faut être
exact sur ce qu'il fait de la vérité terrain** : `empreinte_pack` la LIT, parce que le
`content_sha256` du pack se calcule sur `records`, `ground_truth` et `corruption_annotation`
ensemble — c'est la définition du manifest, pas un choix d'ici. Ce qu'il ne fait pas, c'est
la RENDRE : `charge()` retourne un `Substrat` qui ne porte que les records, les normalisés,
l'empreinte et l'ensemble candidat. La vérité terrain n'entre donc pas dans ce programme **par
cette porte** ; elle y entre par `verite_canonique`, qui la relit pour son compte et dont
l'usage est borné ci-dessus.

Écrire « il ne lit pas la vérité terrain » aurait été plus simple, et faux. Sur un fichier
dont la raison d'être est de rendre la non-circularité auditable, une justification approximative
vaut moins que pas de justification du tout : elle se démonte, et emporte le reste avec elle.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RACINE, "src"))

import engine                                            # noqa: E402
from benchmark import substrat                           # noqa: E402
from pipeline import point as pt                         # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Une seule règle d'empreinte pour les deux artefacts d'interface. Celle-ci hachait le commit :
# l'empreinte changeait donc à chaque commit sans qu'aucun contenu affiché ne change, et un
# lecteur qui la recalculait ne retombait jamais dessus.
import empreinte_artefact                                 # noqa: E402

#: Chemins POSIX relatifs à la racine du repo (aucun chemin absolu OS-spécifique).
CHEMIN_ARTEFACT = "artifacts/ui_demonstration.json"
CHEMIN_DIMS_V2 = "artifacts/dimensions.json"

#: Nombre de paires de la file « à vérifier » publiées dans l'artefact. La zone grise réelle
#: en compte 301 : les publier toutes gonflerait l'artefact sans rien ajouter à la
#: démonstration. Le total reste publié à côté de l'échantillon, jamais remplacé par lui.
N_FILE_A_VERIFIER = 8

#: Taille maximale de l'extrait de démonstration du bac à sable. Au-delà, l'extrait cesse
#: d'être lisible d'un coup d'œil, ce qui est sa seule fonction.
TAILLE_MAX_EXTRAIT = 8

#: Ce qu'une annotation de corruption peut porter sur un enregistrement D'ORIGINE. Le
#: générateur du pack n'applique variantes phonétiques, fautes de frappe, transpositions et
#: déménagements qu'aux DOUBLONS ; l'origine ne peut, au plus, qu'avoir des champs absents.
#: La garde le vérifie plutôt que de le supposer : si un pack futur corrompait ses origines,
#: la notion de « valeur canonique » perdrait son sens, et il vaut mieux que le programme
#: s'arrête que de continuer à décorer un cas héros d'une propriété qu'il n'a plus.
CATEGORIES_TOLEREES_SUR_L_ORIGINE = frozenset({"MANQUANT"})

#: La règle publiée à côté du cas héros, dans l'artefact. Nommée plutôt qu'écrite en ligne :
#: elle fait dix lignes, et enfouie dans le littéral de `construit()` personne ne la relit.
REGLE_CAS_HEROS = (
    "parmi les MATCH dont l'entité a une FICHE DE RÉFÉRENCE CANONIQUE (chaque valeur retenue "
    "par la fusion est égale à la valeur de l'enregistrement d'origine de l'entité vraie du "
    "pack, celui qu'aucune corruption de doublon n'a touché ; aucune graphie corrompue ne "
    "peut donc figurer en fiche de référence) : d'abord ceux dont le nom ou le prénom est "
    "écrit différemment des deux côtés, puis maximum d'accords (forts + partiels), puis "
    "minimum de désaccords, puis maximum de champs écrits différemment ; départage par "
    "identifiants. Le résultat est rejoué à chaque exécution, jamais recopié, et la règle est "
    "re-vérifiée par un oracle qui relit le pack pour son compte.")


def _canon(objet) -> str:
    """Forme canonique du projet : triée, non échappée, séparateurs fixés."""
    return json.dumps(objet, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))


def _commit_courant() -> str:
    """SHA du commit courant, ou une marque explicite si git n'a rien à dire."""
    try:
        sortie = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_RACINE,
                                capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "indisponible"
    return sortie.stdout.strip() if sortie.returncode == 0 else "indisponible"


# --- Règles de sélection ---------------------------------------------------------------

def _profil_accords(correspondance) -> dict:
    """Répartition des huit composantes d'accord d'une CORRESPONDENCE, par niveau."""
    composantes = correspondance["composantes"]
    profil = {niveau: [] for niveau in engine.NIVEAUX}
    for attribut in engine.ATTRIBUTS_COMPARE:
        profil[composantes["accord_" + attribut]].append(attribut)
    return profil


def _champs_ecrits_differemment(record_a, record_b) -> list:
    """Attributs présents des deux côtés mais dont la FORME BRUTE diffère.

    C'est la matière du « pourquoi » de la Vitrine : ce sont ces champs-là qui montrent que le
    moteur a rapproché malgré la graphie, et non parce que les deux fiches étaient identiques.
    """
    return [attribut for attribut in engine.ATTRIBUTS_COMPARE
            if record_a.get(attribut) and record_b.get(attribut)
            and str(record_a[attribut]) != str(record_b[attribut])]


#: Les attributs dont une graphie divergente PROUVE l'argument de la Vitrine. La page promet,
#: à trois centimètres de la carte, de retrouver « les orthographes différentes d'un même
#: nom » : un cas héros où seuls la date et le téléphone changent de FORMAT illustre la
#: tolérance aux formats, pas la tolérance aux fautes de saisie sur l'identité.
ATTRIBUTS_D_IDENTITE = ("nom", "prenom")


def _cle_heros(correspondance, index) -> tuple:
    """Ordre de mérite d'un cas héros. Le maximum de cette clé EST la règle de sélection.

    Dans l'ordre, on veut :

    1. un cas où le NOM ou le PRÉNOM est écrit différemment des deux côtés — c'est
       l'affirmation que la page fait juste à côté de la carte, et une carte qui ne
       l'illustre pas laisse l'affirmation seule ;
    2. le plus d'accords (forts ou partiels) ;
    3. le moins de désaccords ;
    4. le plus de champs écrits différemment — un rapprochement entre deux fiches identiques
       ne prouve rien.

    Le premier critère a été ajouté avec le filtre de canonicité (briefing de clôture, point
    3) : sans lui, le maximum retombait sur une paire dont seuls le format de la date et
    l'espacement du téléphone différaient. Choisir une ILLUSTRATION par une règle publiée est
    le régime de tout ce fichier ; le verdict, lui, reste celui du moteur, et cette clé ne le
    touche pas. Le couple d'identifiants ferme la clé pour que le maximum soit unique quoi
    qu'il arrive.
    """
    profil = _profil_accords(correspondance)
    record_a = index[correspondance["record_id_a"]]
    record_b = index[correspondance["record_id_b"]]
    ecrits_differemment = _champs_ecrits_differemment(record_a, record_b)
    return (
        1 if any(a in ecrits_differemment for a in ATTRIBUTS_D_IDENTITE) else 0,
        len(profil[engine.ACCORD_FORT]) + len(profil[engine.ACCORD_PARTIEL]),
        -len(profil[engine.DESACCORD]),
        len(ecrits_differemment),
        # Départage stable et sans préférence : l'ordre lexicographique inverse des
        # identifiants. Il n'a aucun sens métier, et c'est exactement ce qu'on lui demande.
        correspondance["record_id_a"],
        correspondance["record_id_b"],
    )


def verite_canonique(chemin_fixture: str = None) -> tuple:
    """`({id_entite_vraie: enregistrement canonique}, {record_id: id_entite_vraie})`, LUS du pack.

    Le pack ne publie pas de table de valeurs canoniques — il publie une **lignée** :
    `corruption_annotation[*].record_id_origine`. L'enregistrement d'origine d'une entité,
    celui dont l'origine est nulle, est celui que le générateur a écrit AVANT toute corruption
    de doublon. Ce sont donc SES valeurs qui définissent « la valeur canonique » de l'entité.

    Deux invariants sont vérifiés, et non supposés : l'origine est unique par entité, et son
    annotation ne porte rien d'autre que ce que `CATEGORIES_TOLEREES_SUR_L_ORIGINE` autorise.
    Sur le pack V1.2, les deux tiennent — 320 entités, une origine chacune, annotations
    réduites à `MANQUANT`. Un pack qui les romprait fait lever, plutôt que d'affaiblir en
    silence la propriété que la fiche de référence du cas héros est censée porter.

    L'empreinte du pack est revérifiée ici : ce programme ouvre la fixture une seconde fois
    (`substrat.charge` ne rend pas le pack), et une lecture non vérifiée serait une porte
    dérobée dans le seul contrôle d'intégrité de la chaîne.
    """
    chemin = chemin_fixture or os.path.join(_RACINE, substrat.CHEMIN_FIXTURE)
    with open(chemin, encoding="utf-8") as fh:
        pack = json.load(fh)
    obtenue = substrat.empreinte_pack(pack)
    if obtenue != substrat.CONTENT_SHA256_V1_2:
        raise ValueError(
            f"empreinte de pack divergente : attendu {substrat.CONTENT_SHA256_V1_2}, "
            f"obtenu {obtenue}. La fixture n'est pas celle que le mandat designe.")

    entite_de = {g["record_id"]: g["id_entite_vraie"] for g in pack["ground_truth"]}
    par_id = {r["record_id"]: r for r in pack["records"]}
    canoniques = {}
    for annotation in pack["corruption_annotation"]:
        if annotation.get("record_id_origine") is not None:
            continue
        record_id = annotation["record_id"]
        categories = set(annotation.get("categories_appliquees") or ())
        if not categories <= CATEGORIES_TOLEREES_SUR_L_ORIGINE:
            raise ValueError(
                f"l'enregistrement d'origine {record_id} porte {sorted(categories)} : la "
                f"notion de valeur canonique ne tient plus sur ce pack")
        entite = entite_de[record_id]
        if entite in canoniques:
            raise ValueError(
                f"l'entite {entite} a deux enregistrements d'origine : la valeur canonique "
                f"n'y est pas definie")
        canoniques[entite] = par_id[record_id]
    return canoniques, entite_de


def entites_a_fiche_de_reference_canonique(partition, dores, canoniques, entite_de) -> set:
    """Les `record_id` des entités dont la fiche de référence ne retient QUE du canonique.

    Deux conditions, et la première n'est pas un détail : le groupe doit correspondre à **une
    seule** entité vraie. Un groupe qui en mêle deux est une fusion erronée ; l'exposer comme
    fiche de référence serait montrer un défaut en croyant montrer une réussite, et la notion
    de « valeur canonique de l'entité » n'y aurait de toute façon pas de sens.

    Ensuite, égalité STRICTE sur les huit attributs comparés, absences comprises : une valeur
    retenue là où l'origine n'avait rien vient nécessairement d'un doublon, et un doublon
    porte parfois un autre téléphone ou une autre adresse — donc une valeur qu'aucune vérité
    terrain ne soutient. La complétion reste montrée là où elle se raconte avec son
    arbitrage (les scénarios, le bac à sable, qui affichent la valeur écartée à côté de la
    valeur retenue) ; la fiche de référence du cas héros, elle, ne doit rien laisser à
    contester.
    """
    eligibles = set()
    for groupe, dore in zip(partition, dores):
        entites_vraies = {entite_de[record_id] for record_id in groupe}
        if len(entites_vraies) != 1:
            continue
        canon = canoniques[next(iter(entites_vraies))]
        if all(dore.get(attribut) == canon.get(attribut)
               for attribut in engine.ATTRIBUTS_COMPARE):
            eligibles.update(groupe)
    return eligibles


def choisit_cas_heros(correspondances, index, eligibles=None) -> dict:
    """La CORRESPONDENCE qui démontre le mieux « retrouve, même déformé ». Déterministe.

    `eligibles`, quand il est fourni, restreint le choix aux enregistrements dont l'entité a
    une fiche de référence canonique (voir `entites_a_fiche_de_reference_canonique`). Les
    DEUX fiches de la paire doivent en faire partie : la Vitrine les montre côte à côte, et
    le bac à sable rend la fiche consolidée de leur entité.
    """
    matches = [c for c in correspondances if c["verdict"] == engine.MATCH]
    if eligibles is not None:
        matches = [c for c in matches
                   if c["record_id_a"] in eligibles and c["record_id_b"] in eligibles]
    if not matches:
        raise ValueError(
            "aucun MATCH eligible : pas de cas heros possible. "
            + ("Aucune entite n'a de fiche de reference canonique — le critere du briefing "
               "ne peut pas etre satisfait sur ce jeu." if eligibles is not None
               else "Il n'y a aucun MATCH dans les correspondances."))
    return max(matches, key=lambda c: _cle_heros(c, index))


def choisit_extrait(correspondances, partition, index, point, eligibles=None,
                    entite_de=None) -> dict:
    """Le plus petit extrait qui montre les TROIS verdicts, l'estimation ayant convergé.

    La contrainte de convergence n'est pas cosmétique : sous `MIN_PAIRES_EM` paires, ou sur un
    mélange dégénéré, l'estimation **se replie** sur des a priori non calibrés. Un extrait qui
    replierait ferait la démonstration d'un moteur qui n'est pas celui qu'on mesure ailleurs.

    On balaie les paires en zone grise et on retient la PREMIÈRE qui, jointe à l'entité héros
    et à une paire de MATCH extérieure, satisfait le contrat.

    ## Un ordre de passage, et pourquoi il n'est pas l'ordre canonique
    La zone grise est une **bande de budget**, pas une liste de cas sémantiquement douteux :
    la première paire grise venue est, le plus souvent, deux personnes manifestement
    différentes dont seuls le code postal et la ville concordent. Elle est parfaitement
    représentative de ce que la bande contient, et parfaitement inutile à montrer — un lecteur
    y verrait un moteur qui hésite sans raison, là où le propos est « il s'abstient plutôt que
    de deviner ».

    On passe donc d'abord les paires dont le NOM est en accord fort : le doute y est lisible
    sans commentaire. Ce n'est pas un cueillage de résultat — le verdict, lui, n'est pas
    choisi, et la file « à vérifier » publiée dans le même artefact reste dans l'ordre
    canonique, non filtrée, avec son total de 301. On choisit une ILLUSTRATION, et la règle
    qui la choisit est publiée à côté d'elle.
    """
    heros = choisit_cas_heros(correspondances, index, eligibles)
    entite_heros = next((groupe for groupe in partition
                         if heros["record_id_a"] in groupe), [heros["record_id_a"]])

    def doute_lisible(correspondance) -> int:
        """0 si le nom concorde (doute lisible), 1 sinon. Tri STABLE : l'ordre canonique
        du moteur départage à l'intérieur de chaque classe."""
        return 0 if correspondance["composantes"]["accord_nom"] == engine.ACCORD_FORT else 1

    grises = sorted((c for c in correspondances if c["verdict"] == engine.ZONE_GRISE),
                    key=doute_lisible)
    matches_exterieurs = [c for c in correspondances
                          if c["verdict"] == engine.MATCH
                          and c["record_id_a"] not in entite_heros
                          and c["record_id_b"] not in entite_heros]

    for grise in grises:
        for match in matches_exterieurs:
            identifiants = sorted(set(list(entite_heros)
                                      + [grise["record_id_a"], grise["record_id_b"]]
                                      + [match["record_id_a"], match["record_id_b"]]))
            if len(identifiants) > TAILLE_MAX_EXTRAIT:
                continue
            records = [index[rid] for rid in identifiants]
            resultat = engine.execute_moteur(records, point.parametres_moteur())
            verdicts = {c["verdict"] for c in resultat["correspondances"]}
            if resultat["rapport"]["estimation"].get("repli"):
                continue
            # Aucun FAUX NÉGATIF montré comme une séparation correcte. Le bac à sable affiche
            # les NON_MATCH de cet extrait ; sur une paire qui est en vérité la même personne,
            # la surface AFFIRME au visiteur « ce sont deux personnes différentes », et c'est
            # faux. Le premier extrait produit sous le filtre de canonicité en contenait un :
            # deux « Alexandre Lefebvre » nés le même jour, séparés à l'écran.
            #
            # Ce n'est pas cacher le taux d'erreur : le rappel mesuré est publié en Vitrine et
            # en Salle des machines, et c'est LUI qui dit combien de doublons échappent. Ce
            # qu'on refuse, c'est qu'une surface prononce une phrase fausse sur un cas précis.
            if entite_de is not None and any(
                    c["verdict"] == engine.NON_MATCH
                    and entite_de[c["record_id_a"]] == entite_de[c["record_id_b"]]
                    for c in resultat["correspondances"]):
                continue
            if verdicts >= {engine.MATCH, engine.NON_MATCH, engine.ZONE_GRISE}:
                # Les verdicts DE L'EXTRAIT, et non ceux du run complet. L'estimation EM est
                # re-menée sur les seules paires de l'extrait : la paire qui y tombe en zone
                # grise n'est pas nécessairement celle qui y tombait sur 537 enregistrements.
                # Publier la seconde ferait annoncer à la surface un cas que le bac à sable ne
                # montrerait jamais.
                repartition = {v: 0 for v in engine.VERDICTS}
                for c in resultat["correspondances"]:
                    repartition[c["verdict"]] += 1
                return {
                    "record_ids": identifiants,
                    "verdicts_de_l_extrait": repartition,
                    "paires_zone_grise_dans_l_extrait": [
                        [c["record_id_a"], c["record_id_b"]]
                        for c in resultat["correspondances"]
                        if c["verdict"] == engine.ZONE_GRISE],
                    "regle": ("entité du cas héros, plus la première paire en zone grise DONT "
                              "LE NOM CONCORDE (le doute y est lisible ; à défaut, l'ordre "
                              "canonique) et la première paire de MATCH extérieure, qui "
                              "donnent ensemble les trois verdicts sans repli de l'estimation "
                              "ET SANS QU'AUCUN NON_MATCH DE L'EXTRAIT NE SÉPARE DEUX FICHES "
                              "DE LA MÊME ENTITÉ VRAIE — une surface qui affiche « ce sont "
                              "deux personnes différentes » ne doit pas le dire de la même "
                              "personne ; le taux d'erreur, lui, reste publié en Vitrine et "
                              "en Salle des machines. La file « à vérifier » du même artefact "
                              "reste, elle, dans l'ordre canonique et non filtrée."),
                    "paire_zone_grise_au_run_complet": [grise["record_id_a"],
                                                       grise["record_id_b"]],
                    "entite_heros": list(entite_heros),
                }
    raise ValueError("aucun extrait ne satisfait le contrat des trois verdicts sans repli")


# --- Construction de l'artefact --------------------------------------------------------

def _vue_correspondance(correspondance, index) -> dict:
    """Une CORRESPONDENCE et ses deux fiches, dans la forme que la surface affiche.

    Les formes BRUTES des enregistrements sont conservées : c'est la donnée que l'utilisateur
    reconnaît. Montrer la forme normalisée (« marche » pour « Marché ») afficherait une donnée
    appauvrie que personne n'a jamais saisie.
    """
    record_a = index[correspondance["record_id_a"]]
    record_b = index[correspondance["record_id_b"]]
    profil = _profil_accords(correspondance)
    return {
        "record_a": record_a,
        "record_b": record_b,
        "verdict": correspondance["verdict"],
        "poids_match": correspondance["poids_match"],
        "composantes": correspondance["composantes"],
        "poids_par_champ": correspondance["poids_par_champ"],
        "n_composantes_informatives": correspondance["n_composantes_informatives"],
        "champs_par_niveau": {niveau: profil[niveau] for niveau in engine.NIVEAUX},
        "champs_ecrits_differemment": _champs_ecrits_differemment(record_a, record_b),
    }


def construit(racine: str = ".") -> dict:
    """Produit le contenu de l'artefact. Ne l'écrit pas : la décision d'écrire est ailleurs."""
    sub = substrat.charge()
    point = pt.point_depuis_artefact(CHEMIN_DIMS_V2, racine=racine)
    index = {record["record_id"]: record for record in sub.records}

    resultat = engine.execute_moteur(sub.records, point.parametres_moteur())
    correspondances = resultat["correspondances"]
    partition = engine.cloture_transitive(correspondances, engine.univers_depuis_records(sub.records))
    dores = engine.consolide_partition(partition, sub.records)

    repartition = {verdict: 0 for verdict in engine.VERDICTS}
    for correspondance in correspondances:
        repartition[correspondance["verdict"]] += 1

    # La vérité terrain n'entre ici que pour ÉCARTER : elle restreint les cas héros
    # candidats à ceux dont la fiche de référence ne retient aucune valeur corrompue. Aucun
    # verdict ne la voit, et rien de ce qu'elle contient n'atteint l'artefact — voir le
    # docstring du module, section « Ce programme LIT la vérité terrain ».
    canoniques, entite_de = verite_canonique()
    eligibles = entites_a_fiche_de_reference_canonique(partition, dores, canoniques, entite_de)

    heros = choisit_cas_heros(correspondances, index, eligibles)
    entite_heros = next(groupe for groupe in partition if heros["record_id_a"] in groupe)
    dore_heros = dores[partition.index(entite_heros)]

    extrait = choisit_extrait(correspondances, partition, index, point, eligibles, entite_de)
    grises = [c for c in correspondances if c["verdict"] == engine.ZONE_GRISE]

    contenu = {
        "_lisez_moi": (
            "SORTIES DU MOTEUR figées pour les surfaces de démonstration. "
            "Produit par tools/produit_artefacts_ui.py sur FX_001 V1.2, au point DIMS-v2. "
            "Ce fichier ne contient AUCUNE métrique de qualité : précision, rappel et F1 sont "
            "mesurés par un scoreur independant et publies dans banc_ub6.json. Ici, on ne "
            "publie que ce que le moteur a DÉCIDÉ, jamais ce que vaut sa décision."),
        "provenance": {
            "fixture": {
                "chemin_relatif_repo": substrat.CHEMIN_FIXTURE,
                "content_sha256": sub.empreinte_fixture,
            },
            "commit": _commit_courant(),
            "version_python": ".".join(str(n) for n in sys.version_info[:3]),
            "graine_em": engine.GRAINE_EM_SCELLEE,
            # Publié pour que la surface puisse afficher les champs comparés DANS L'ORDRE du
            # moteur sans importer `engine` : `vue` et `lecture` ne connaissent que du JSON,
            # et c'est cette ignorance qui rend la non-circularité vérifiable par analyse d'imports.
            "champs_compares": list(engine.ATTRIBUTS_COMPARE),
            "point_de_fonctionnement": point.en_dict(),
            "passes_blocking": list(engine.PASSES_DEFAUT),
        },
        "population": {
            "n_records": len(sub.records),
            "n_paires_candidates": len(correspondances),
            "n_entites": len(partition),
            "repartition_verdicts": repartition,
            "estimation": resultat["rapport"]["estimation"],
        },
        "cas_heros": {
            "regle_de_selection": REGLE_CAS_HEROS,
            "correspondance": _vue_correspondance(heros, index),
            "entite": {
                "membres": list(entite_heros),
                "records": [index[rid] for rid in entite_heros],
                "enregistrement_dore": dore_heros,
            },
        },
        "extrait_demonstration": {
            "regle_de_selection": extrait["regle"],
            "record_ids": extrait["record_ids"],
            "records": [index[rid] for rid in extrait["record_ids"]],
            "verdicts_de_l_extrait": extrait["verdicts_de_l_extrait"],
            "paires_zone_grise_dans_l_extrait": extrait["paires_zone_grise_dans_l_extrait"],
            "paire_zone_grise_au_run_complet": extrait["paire_zone_grise_au_run_complet"],
        },
        "file_a_verifier": {
            "_lisez_moi": (
                "Échantillon de la file « à vérifier » : les paires sur lesquelles le moteur "
                "s'abstient. Le TOTAL est publié à côté ; l'échantillon ne le remplace pas."),
            "n_total": len(grises),
            "n_publiees": min(N_FILE_A_VERIFIER, len(grises)),
            "paires": [_vue_correspondance(c, index) for c in grises[:N_FILE_A_VERIFIER]],
        },
    }
    contenu["empreinte_contenu"] = empreinte_artefact.empreinte(contenu)
    contenu["_note_empreinte"] = empreinte_artefact.NOTE
    return contenu


def main() -> int:
    contenu = construit()
    chemin = os.path.join(_RACINE, CHEMIN_ARTEFACT)
    with open(chemin, "w", encoding="utf-8") as fh:
        json.dump(contenu, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    heros = contenu["cas_heros"]["correspondance"]
    print(f"ecrit {CHEMIN_ARTEFACT}")
    print(f"  population        : {contenu['population']['n_records']} records, "
          f"{contenu['population']['n_paires_candidates']} paires candidates")
    print(f"  repartition       : {contenu['population']['repartition_verdicts']}")
    print(f"  cas heros         : {heros['record_a']['record_id']} / "
          f"{heros['record_b']['record_id']}  R={heros['poids_match']}")
    print(f"  extrait bac a sable : {contenu['extrait_demonstration']['record_ids']}")
    print(f"  file a verifier   : {contenu['file_a_verifier']['n_total']} paires")
    print(f"  empreinte_contenu : {contenu['empreinte_contenu']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
