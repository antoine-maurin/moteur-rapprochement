"""Clustering — clôture transitive de la relation de liaison.

    CORRESPONDENCE (verdicts du moteur)  ->  arêtes liantes  ->  partition en entités

Si A~B et B~C sont des liens, alors A, B et C forment une seule entité. C'est une
**clôture transitive** : le calcul des composantes connexes du graphe dont les sommets sont
les `record_id` et les arêtes les paires jugées liantes.

## Ce que la clôture ajoute
La décision du moteur porte sur une paire à la fois. Deux enregistrements peuvent appartenir
à la même entité sans qu'aucune paire ne les relie directement : le lien passe par un
troisième. `couverture_transitive` compte exactement ces paires-là — celles qu'implique la
partition et que la décision par paire n'a pas produites.

Ce décompte se calcule intégralement à partir des verdicts du moteur et des identifiants
d'enregistrements ; aucune étiquette de référence n'y entre, donc il ne peut par
construction rien dire de la **justesse** des liens. Il répond à « combien de paires la
clôture ajoute-t-elle aux liens directs », jamais à « combien de liens sont bons » — cette
seconde question appartient au scoreur, indépendant par construction.

## Doctrine d'erreur (énoncée une fois, elle dérive toute la table des refus)
On **tolère la redondance** — une même arête reçue deux fois, ou reçue en `(b, a)` : une
relation est un ENSEMBLE d'arêtes, la dédupliquer n'est pas réparer une faute. On **refuse
l'incohérence référentielle** — identifiant hors univers, doublon, arête réflexive : la
réparer exigerait de deviner. Tous les refus lèvent `ValueError` (ou `TypeError` pour un
typage), **jamais** `assert` : `python -O` supprime les `assert`, et un invariant qui
disparaît sous une option d'exécution est exactement le mode de défaillance combattu ici.

## Déterminisme
Aucun parcours d'ensemble non trié, aucun `hash()`, aucun aléa. Les `record_id` sont des
identifiants **opaques** : ils ne sont jamais normalisés (sinon « A » et « a » fusionneraient
en silence) et l'ordre est lexicographique par point de code, donc indépendant de la locale.
La racine du union-find n'est jamais exposée — elle dépend de l'ordre des unions ; le
représentant d'un groupe est son plus petit membre, fonction pure de l'ensemble.

## Frontière de non-circularité
La signature de `cloture_transitive` ne reçoit que des verdicts et des identifiants : aucune
annotation de référence ne peut y entrer, même par accident. La partition dérive des
décisions du moteur, jamais d'étiquettes.
"""
from __future__ import annotations

import math

from .decide import MATCH

#: Jeton de promotion rendu par la revue du doute, RE-DÉCLARÉ ici plutôt qu'importé.
#:
#: `llm_client` n'est pas dans la liste blanche d'imports du clustering (`.decide`, `.normalize`,
#: `__future__`, `math`), et l'y ajouter attacherait la clôture transitive à la revue : la
#: partition doit rester calculable sans que la revue existe. Le prix d'une re-déclaration
#: est le risque de dérive silencieuse ; il est payé par un oracle qui compare les deux
#: constantes — `tests/test_clustering.py::test_le_jeton_de_promotion_ne_derive_pas_de_u_b3`
#: échoue si `llm_client.MATCH_APRES_REVUE` change sans que cette ligne suive.
MATCH_APRES_REVUE = "MATCH_APRES_REVUE"

#: Ce qui fait d'une correspondance revue une ARÊTE. N-uplet, donc appartenance par
#: ÉGALITÉ : `NON_MATCH_APRES_REVUE` contient `MATCH_APRES_REVUE` comme sous-chaîne, et un
#: test de sous-chaîne retournerait donc le sens d'un refus.
JETONS_LIANTS = (MATCH, MATCH_APRES_REVUE)

#: Les deux constantes ci-dessus ne figurent PAS dans `__all__`, et c'est délibéré : la revue a
#: gelé la proposition « la revue n'entre pas dans la surface du paquet `engine` », et le
#: paquet réexporte exactement ce que chaque module déclare ici. Y inscrire un nom portant
#: `MATCH_APRES_REVUE` ferait entrer la revue dans cette surface par la bande — au prix
#: d'un affaiblissement de la garde gelée. Elles restent lisibles sur le module lui-même,
#: qui est la façon dont la chaîne de bout en bout les consomme.
__all__ = ["cle_paire", "est_liante", "aretes_liantes", "univers_depuis_records",
           "cloture_transitive", "couverture_transitive"]


def _exige_collection(valeur, role: str) -> None:
    """Refuse une chaîne là où une collection d'identifiants est attendue.

    Une `str` est itérable de `str` : passée comme univers ou comme groupe, chacun de ses
    caractères devient un sommet à part entière, sans erreur ni trace, et la sortie reste
    une partition parfaitement bien formée. C'est le miroir exact du défaut que
    `_exige_identifiant` empêche — là trois identifiants devenaient un sommet, ici un
    identifiant en devient plusieurs. Le déclencheur réaliste est l'appel à un seul
    enregistrement, écrit `cloture_transitive(corrs, rid)` au lieu de `(corrs, [rid])`.
    """
    if isinstance(valeur, (str, bytes)):
        raise TypeError(f"{role} : une collection d'identifiants est attendue, pas "
                        f"{type(valeur).__name__} ({valeur!r} serait eclate caractere "
                        f"par caractere)")


def _exige_identifiant(valeur) -> None:
    """Refuse tout ce qui ne peut pas servir d'identifiant d'enregistrement.

    Le typage `str` n'est pas une coquetterie : `{1: x, True: y, 1.0: z}` s'effondre en UNE
    seule clé de dict, si bien que trois identifiants distincts deviendraient un seul sommet
    AVANT que la clôture ne commence, sans erreur ni trace. La chaîne vide est refusée pour
    la raison symétrique : elle est falsy, donc toute garde écrite `if rid:` la ferait
    disparaître silencieusement.
    """
    if not isinstance(valeur, str):
        raise TypeError(f"record_id doit etre une chaine : {valeur!r} "
                        f"est de type {type(valeur).__name__}")
    if not valeur:
        raise ValueError("record_id vide : identification impossible")


def cle_paire(a, b) -> tuple:
    """Clé canonique `(min, max)` d'une paire non ordonnée.

    Re-déclarée ici plutôt qu'importée d'une unité de mesure : la duplication est le prix
    documenté de l'indépendance. Elle ne **présume pas** l'invariant `record_id_a <
    record_id_b` que `blocking.py` garantit aujourd'hui — les jeux d'essai sont écrits à la
    main et le blocking est retouché par une unité voisine.

    L'auto-paire lève : `blocking.py` la rend structurellement impossible, donc sa présence
    signifie que l'entrée ne vient pas du moteur. L'absorber masquerait une régression du
    producteur, et son dégât serait entièrement dans le décompte, où elle rendrait le nombre
    de paires récupérées négatif sur un singleton.
    """
    _exige_identifiant(a)
    _exige_identifiant(b)
    if a == b:
        raise ValueError(f"paire reflexive : {a!r} avec lui-meme")
    return (a, b) if a < b else (b, a)


def est_liante(correspondance: dict) -> bool:
    """Une CORRESPONDENCE établit-elle un lien pour la clôture ?

    Deux cas, et **deux seulement** (mandat §2, « MATCH ∪ MATCH_APRÈS_REVUE ») : le verdict
    du moteur est MATCH ; ou la revue de zone grise a rendu une décision MATCH.

    Publique parce que c'est ici que vit la catastrophe silencieuse. Le dict de revue
    `{"statut": "en_attente", "decision": None, ...}` est **truthy** : une garde écrite
    `or correspondance["revue_zone_grise"]` ferait entrer TOUTE la zone grise dans la
    clôture et produirait un groupe géant qui n'a l'air anormal nulle part. La comparaison
    est une égalité, jamais un `in` — un test de sous-chaîne accepterait « NON_MATCH ».

    La seconde branche ne pouvait PAS s'animer avant la chaîne bout-en-bout, et pas pour la raison
    qu'on croyait. Elle comparait `decision` au jeton `MATCH` du moteur — un jeton que la revue
    n'émet jamais : son énumération fermée (`llm_client.DECISIONS`) ne connaît que
    `MATCH_APRES_REVUE`, `NON_MATCH_APRES_REVUE` et `NON_TRANCHE`. La branche était donc
    structurellement inatteignable, et non « morte en attendant que la revue conclue » :
    une paire promue par la revue n'aurait pas produit d'arête, en silence, alors que la
    docstring de `aretes_liantes` annonce précisément l'union `MATCH ∪ MATCH_APRÈS_REVUE`.
    La chaîne bout-en-bout la rend atteignable ; c'est la condition pour qu'elle ait un
    étage de revue qui serve à quelque chose.

    L'appartenance se fait par ÉGALITÉ sur un n-uplet, jamais par sous-chaîne : le jeton de
    rejet `NON_MATCH_APRES_REVUE` CONTIENT le jeton de promotion, si bien qu'un `in` sur la
    chaîne retournerait le sens d'un refus.
    """
    if correspondance.get("verdict") == MATCH:
        return True
    revue = correspondance.get("revue_zone_grise")
    return isinstance(revue, dict) and revue.get("decision") in JETONS_LIANTS


def aretes_liantes(correspondances) -> list:
    """Arêtes liantes canoniques, dédupliquées, triées.

    La déduplication est silencieuse **et documentée** : le cas réaliste n'est pas la faute
    de frappe mais l'union `MATCH ∪ MATCH_APRÈS_REVUE` portant la même paire des deux côtés.
    Compter une arête deux fois fausserait le décompte de couverture, pas la partition.
    """
    retenues = {}
    for correspondance in correspondances:
        if not est_liante(correspondance):
            continue
        cle = cle_paire(correspondance["record_id_a"], correspondance["record_id_b"])
        retenues[cle] = True
    return sorted(retenues)


def univers_depuis_records(records) -> list:
    """Projection DÉFENSIVE d'une collection d'enregistrements sur ses seuls identifiants.

    Commodité qui ferme un risque réel : l'univers est obligatoire dans `cloture_transitive`,
    mais rien n'empêcherait un appelant de le construire depuis les seules paires observées —
    ce qui ferait disparaître tous les singletons. Cette fonction le construit correctement
    sans jamais laisser une valeur d'attribut approcher la clôture : seul `record_id` est lu.
    """
    vus = {}
    for record in records:
        rid = record.get("record_id")
        if rid is None:
            raise ValueError("enregistrement sans record_id : identification impossible")
        _exige_identifiant(rid)
        if rid in vus:
            raise ValueError(f"record_id duplique : {rid!r}")
        vus[rid] = True
    return sorted(vus)


def _univers_canonique(univers) -> list:
    """Univers validé et trié. Les doublons lèvent : ils fausseraient les tailles d'union."""
    _exige_collection(univers, "univers")
    vus = {}
    for rid in univers:
        _exige_identifiant(rid)
        if rid in vus:
            raise ValueError(f"identifiant duplique dans l'univers : {rid!r}")
        vus[rid] = True
    return sorted(vus)


def _racine(parent: dict, sommet: str) -> str:
    """Racine du sommet, avec compression de chemin — en boucle, jamais en récursion.

    Une chaîne de plusieurs milliers d'enregistrements ferait déborder la pile d'appels, et
    un jeu d'essai de quelques dizaines de records ne le verrait jamais.
    """
    racine = sommet
    while parent[racine] != racine:
        racine = parent[racine]
    while parent[sommet] != racine:
        parent[sommet], sommet = racine, parent[sommet]
    return racine


def _unit(parent: dict, taille: dict, a: str, b: str) -> None:
    """Union par taille, départagée par identifiant.

    La clé de comparaison est `(taille, identifiant)` et non `taille` seule : le départage
    par identifiant rend chaque union INDIVIDUELLE indépendante de l'ordre de ses deux
    arguments `(a, b)`.

    Elle ne rend PAS la racine finale indépendante de l'ordre d'ARRIVÉE des arêtes — les
    tailles évoluent différemment selon cet ordre, si bien qu'un même ensemble d'arêtes
    présenté dans trois ordres donne trois racines. Cette indépendance-là est obtenue en
    amont, par le tri de `aretes_liantes` ; et c'est précisément pourquoi la racine n'est
    jamais exposée, le représentant d'un groupe restant son plus petit membre.
    """
    ra, rb = _racine(parent, a), _racine(parent, b)
    if ra == rb:
        return
    if (taille[ra], ra) < (taille[rb], rb):
        ra, rb = rb, ra
    parent[rb] = ra
    taille[ra] += taille[rb]


def cloture_transitive(correspondances, univers) -> list:
    """Partition de `univers` en entités par clôture transitive des arêtes liantes.

    Retourne `list[list[str]]` — rien d'autre : ni identifiant de groupe, ni compteur, ni
    trace. Une sortie nue est une sortie qu'un test peut confronter à une partition écrite
    à la main.

    `univers` est **obligatoire et positionnel**, et c'est le point le plus important de
    cette signature. Un univers déduit des seules arêtes ferait disparaître tout
    enregistrement sans correspondance — donc tous les singletons, et tous les records perdus
    au blocking — et la sortie resterait une partition parfaitement bien formée : l'erreur
    serait rigoureusement invisible.

    Ordre canonique, deux règles : les membres d'un groupe sont triés ; les groupes sont
    triés entre eux sur leur liste de membres, donc par plus petit membre. Aucun ex aequo
    n'est possible, les groupes étant disjoints. Le tri par TAILLE est délibérément écarté :
    il ferait dépendre l'ordre de sortie d'une grandeur que tout recalibrage des seuils fait
    bouger, produisant une agitation d'ordre à chaque réglage.

    Deux paramètres, dont aucun ne peut porter une étiquette de référence. La partition
    dérive exclusivement des verdicts du moteur et des identifiants.
    """
    ordonnes = _univers_canonique(univers)
    parent = {rid: rid for rid in ordonnes}
    taille = {rid: 1 for rid in ordonnes}

    inconnus = {}
    aretes = aretes_liantes(correspondances)
    for a, b in aretes:
        for extremite in (a, b):
            if extremite not in parent:
                inconnus[extremite] = True
    if inconnus:
        raise ValueError(
            "arete liante hors univers : " + ", ".join(sorted(inconnus)) +
            " (ignorer tronquerait la partition en silence ; adopter inventerait un "
            "enregistrement dont on ne sait rien)")
    for a, b in aretes:
        _unit(parent, taille, a, b)

    groupes = {}
    for rid in ordonnes:                     # itération d'une séquence TRIÉE
        groupes.setdefault(_racine(parent, rid), []).append(rid)
    # Le tri externe est REDONDANT par construction, et c'est délibéré : `ordonnes` étant
    # trié, les groupes s'insèrent déjà par plus petit membre croissant, et une mutation qui
    # le retirerait serait aujourd'hui équivalente. Il est conservé parce qu'il est le seul
    # endroit où la canonicité se prouve LOCALEMENT — sans dépendre d'un raisonnement établi
    # trente lignes plus haut, qu'une refonte casserait en silence.
    return sorted(sorted(membres) for membres in groupes.values())


def couverture_transitive(partition, correspondances) -> dict:
    """Ce que la clôture ajoute aux liens directs (mandat §4, objectif O3).

    Un groupe de `n` membres implique `C(n, 2)` paires internes. Si la décision par paire
    n'en a produit que `k`, les `C(n, 2) - k` autres sont **récupérées par transitivité**.

    Retourne des CARDINAUX, et rien d'autre :

        {"n_paires_internes", "n_paires_directes", "n_paires_recuperees",
         "par_entite": [{"membres", "n_paires_internes", "n_paires_directes",
                         "n_paires_recuperees"}, ...]}

    Toutes les valeurs sont des `int` : un flottant serait le premier symptôme d'un taux, et
    ce module n'en produit aucun — il ne contient aucune division.

    **Le total est la somme par groupe**, jamais un calcul global. Sur `{A,B,C,D}` avec les
    liens `{(A,B), (C,D)}` : 1 + 1 = 2 paires internes et 0 récupérée. Un `C(N, 2)` sur
    l'univers entier donnerait 6 et 4 — et le nombre faux est ici le plus gros, donc le plus
    flatteur, donc le plus dangereux.

    DEUX gardes SYMÉTRIQUES de cohérence, et il faut bien les deux. Une arête liante qui
    TRAVERSE deux groupes signale une partition plus fine que les correspondances ; un
    groupe que les arêtes reçues ne CONNECTENT pas signale l'exact inverse. Ne garder que la
    première laisserait passer le seul des deux sens qui GONFLE `n_paires_recuperees` — le
    `C(n, 2)` d'un groupe surfusionné explose pendant que le compte direct stagne, et le
    maximum est atteint quand la liste de correspondances est vide ou déjà épuisée. Le
    nombre faux serait, là encore, le plus flatteur.

    Ensemble, elles font de `n_paires_recuperees >= 0` un THÉORÈME (dans une composante
    connexe, `n - 1 <= |E| <= C(n, 2)`) plutôt qu'une garde défensive.
    """
    groupe_de = {}
    for rang, membres in enumerate(partition):
        # Le contrôle de TYPE précède celui de l'ordre : sur un conteneur non ordonné, le
        # contrôle d'ordre serait lui-même non déterministe. La garde est celle que la
        # consolidation applique déjà — la même partition ne peut pas être refusée par
        # l'une et propagée en silence par l'autre.
        _exige_collection(membres, f"groupe de rang {rang}")
        if not isinstance(membres, (list, tuple)):
            raise TypeError(f"groupe de rang {rang} non ordonne : list ou tuple attendu, "
                            f"recu {type(membres).__name__} (un conteneur non ordonne "
                            f"rendrait `membres` dependant de la graine de hachage)")
        for rid in membres:
            _exige_identifiant(rid)
            if rid in groupe_de:
                raise ValueError(f"partition invalide : {rid!r} apparait dans deux groupes")
            groupe_de[rid] = rang
        if list(membres) != sorted(membres):
            raise ValueError(f"groupe non canonique : membres non tries {list(membres)}")

    aretes = aretes_liantes(correspondances)
    directes = [0] * len(partition)
    hors_partition = {}
    for a, b in aretes:
        if a not in groupe_de or b not in groupe_de:
            for extremite in (a, b):
                if extremite not in groupe_de:
                    hors_partition[extremite] = True
            continue
        if groupe_de[a] != groupe_de[b]:
            raise ValueError(
                f"partition incoherente avec les correspondances : l'arete liante "
                f"({a!r}, {b!r}) relie deux groupes distincts")
        directes[groupe_de[a]] += 1
    if hors_partition:
        raise ValueError("arete liante hors partition : " + ", ".join(sorted(hors_partition)))

    # Garde symétrique : chaque groupe doit être CONNEXE pour les arêtes liantes reçues.
    # Elle attrape le sens que la garde précédente ne voit pas, y compris le cas réaliste
    # d'un itérateur de correspondances déjà consommé par la clôture.
    parent = {rid: rid for rid in sorted(groupe_de)}
    taille = {rid: 1 for rid in parent}
    for a, b in aretes:
        _unit(parent, taille, a, b)
    for membres in partition:
        tete = None
        for rid in membres:
            racine = _racine(parent, rid)
            if tete is None:
                tete = racine
            elif racine != tete:
                raise ValueError(
                    f"partition incoherente avec les correspondances : le groupe "
                    f"{sorted(membres)} n'est pas connexe pour les aretes liantes recues "
                    f"(partition et correspondances issues d'executions differentes, ou "
                    f"correspondances deja consommees)")

    # Les totaux sont accumulés au fil des groupes plutôt que re-lus dans `par_entite` :
    # ce module ne relit AUCUNE clé qu'il n'a pas reçue en entrée, ce qui rend la garde
    # de non-circularité « clés lues closes » vérifiable par simple lecture de l'arbre syntaxique.
    par_entite = []
    total_internes = 0
    total_directes = 0
    for rang, membres in enumerate(partition):
        internes = math.comb(len(membres), 2)
        total_internes += internes
        total_directes += directes[rang]
        par_entite.append({
            "membres": list(membres),
            "n_paires_internes": internes,
            "n_paires_directes": directes[rang],
            "n_paires_recuperees": internes - directes[rang],
        })
    return {
        "n_paires_internes": total_internes,
        "n_paires_directes": total_directes,
        "n_paires_recuperees": total_internes - total_directes,
        "par_entite": par_entite,
    }
