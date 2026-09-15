"""Consolidation d'une entité en un enregistrement doré.

    groupe de record_id  +  enregistrements bruts  ->  UN enregistrement doré

Pour chacun des 8 attributs comparés, la valeur retenue est choisie par une **cascade de
règles déterministe et documentée**. Un conflit est tranché de façon reproductible ; la
même entrée rend toujours la même sortie.

## La cascade — MAJORITÉ, puis COMPLÉTUDE, puis SOURCE PRIORITAIRE, puis ORDRE CANONIQUE
Le mandat énonce l'ordre deux fois et pas dans le même sens (§0 place la majorité en tête,
§3 la complétude). L'ordre retenu par défaut place la **majorité** d'abord, et le paramètre
`politique` transforme l'ambiguïté résiduelle en donnée déclarée plutôt qu'en choix caché.

Contre-exemple qui sépare les deux ordres : trois sources portant « Dupont », « Dupont » et
« Dupont Xk ». Majorité d'abord retient « Dupont » ; complétude d'abord retient « Dupont Xk ».
« Dupont » est la bonne valeur — deux sources indépendantes concordent, la troisième porte
un suffixe qu'aucune autre ne confirme. Trois arguments, aucun de goût :

1. **Asymétrie des modes de défaillance.** Pour que la majorité se trompe, il faut DEUX
   enregistrements altérés coïncidant sur la MÊME valeur fausse. Pour que la complétude se
   trompe, il suffit d'UN enregistrement allongé : elle vote mécaniquement pour toute
   altération qui rallonge.
2. **Monotonie.** Ajouter un enregistrement propre qui corrobore renforce la majorité et ne
   change RIEN sous complétude-d'abord. Une règle qu'aucune preuve supplémentaire ne peut
   corriger doit être en bas de cascade.
3. **Auditabilité.** La majorité a une marge reportable (`ecart_majorite`) ; « le plus long »
   n'en a pas — d'où la publication de `ecart_completude` quand c'est elle qui tranche.

Le désaccord entre les deux ordres n'existe qu'à partir de 3 membres : sur un groupe de 2,
la majorité est toujours à égalité 1–1 et n'élimine personne.

**Coût assumé**, écrit ici plutôt que découvert plus tard : un téléphone tronqué chez DEUX
sources bat un numéro complet chez une seule. C'est réel, c'est plus improbable que le
défaut inverse pour la raison 1, et ce n'est pas corrigeable à l'intérieur de la règle.

« Plus complet » = longueur de la forme NORMALISÉE, c'est-à-dire de la clé de vote
elle-même. La longueur BRUTE est écartée (elle classerait trois écritures d'un même numéro
par densité de ponctuation) ; le nombre de TOKENS aussi (aveugle à la troncature à
l'intérieur d'un token, donc en échec exactement sur le cas pour lequel la règle existe).

## Le vote porte sur les FORMES NORMALISÉES
« Jean-Pierre », « JEAN PIERRE » et « jean pierre » sont une seule et même valeur. Sans
regroupement par forme normalisée, la majorité ne serait pas affaiblie mais INVERSÉE : trois
écritures d'un même prénom feraient une voix chacune, et une quatrième valeur à deux voix
gagnerait. La normalisation est celle de `normalize.py` — une seule frontière du vide
traverse le moteur.

Le poids d'un groupe est le nombre de **sources distinctes**, non de records : deux
enregistrements d'une même source dans une même entité ne peuvent venir que d'un
sur-regroupement, et compter leurs voix séparément laisserait une erreur d'appariement
piloter le contenu du produit. `n_records` est publié à côté, pour que la lecture inverse
reste re-dérivable par qui la préfère.

## Ce qui n'est PAS lu
Le poids agrégé produit par la décision n'entre jamais dans la consolidation : c'est une
propriété d'une PAIRE, pas d'un enregistrement ; le projeter sur un membre exigerait une
agrégation sans réponse de principe, et rendrait le produit dépendant de seuils non calibrés.

## Invariant de non-invention
Pour tout attribut, la valeur retenue est `None` ou appartient à l'ensemble des valeurs
BRUTES des membres. La consolidation **sélectionne**, elle ne synthétise pas. Composer entre
attributs (le nom de l'un, l'adresse de l'autre) est le principe même du produit ; composer
À L'INTÉRIEUR d'un attribut (concaténer deux adresses, compléter un numéro tronqué) est
interdit en V1 — une valeur synthétisée n'a aucun enregistrement d'origine, et `origines`
cesserait de pouvoir désigner quoi que ce soit.

## Paramètres NON CALIBRÉS
`politique` et `priorite_sources` sont des paramétrages déclarés, pas des valeurs ajustées.
`priorite_sources` est VIDE par défaut : livrer un classement de sources codé en dur serait
livrer une calibration déguisée. Table vide, la règle n'élimine personne — elle n'invente
pas un ordre alphabétique, qui serait une décision métier non déclarée sous couvert de
déterminisme.
"""
from __future__ import annotations

from .normalize import ATTRIBUTS_COMPARE, NORMALISEURS

# --- Registre FERMÉ des règles de sélection ------------------------------------------
MAJORITE = "MAJORITE"
COMPLETUDE = "COMPLETUDE"
SOURCE_PRIORITAIRE = "SOURCE_PRIORITAIRE"
ORDRE_CANONIQUE = "ORDRE_CANONIQUE"
REGLES = (MAJORITE, COMPLETUDE, SOURCE_PRIORITAIRE, ORDRE_CANONIQUE)

#: Seule règle TOTALE : elle départage toujours, donc toute cascade doit finir par elle.
REGLE_TERMINALE = ORDRE_CANONIQUE

#: États qui ne sont pas des règles : aucun arbitrage n'a eu lieu.
AUCUN_CANDIDAT = "AUCUN_CANDIDAT"
CANDIDAT_UNIQUE = "CANDIDAT_UNIQUE"
MOTIFS = (AUCUN_CANDIDAT, CANDIDAT_UNIQUE)

#: Énumération fermée du champ `regle` d'un arbitrage.
CODES_SELECTION = MOTIFS + REGLES

POLITIQUE_DEFAUT = REGLES
#: L'autre lecture du mandat (§3), fournie pour que le choix soit éprouvable, pas subi.
POLITIQUE_COMPLETUDE_DABORD = (COMPLETUDE, MAJORITE, SOURCE_PRIORITAIRE, ORDRE_CANONIQUE)

PARAMETRES_NON_CALIBRES = ("politique", "priorite_sources")

__all__ = ["MAJORITE", "COMPLETUDE", "SOURCE_PRIORITAIRE", "ORDRE_CANONIQUE", "REGLES",
           "REGLE_TERMINALE", "AUCUN_CANDIDAT", "CANDIDAT_UNIQUE", "MOTIFS",
           "CODES_SELECTION", "POLITIQUE_DEFAUT", "POLITIQUE_COMPLETUDE_DABORD",
           "PARAMETRES_NON_CALIBRES",
           "valide_politique", "valeurs_candidates", "regle_majorite", "regle_completude",
           "regle_source_prioritaire", "regle_ordre_canonique", "forme_retenue",
           "arbitre_attribut", "trace_selection", "consolide_entite", "consolide_partition"]


def _exige_identifiant(valeur) -> None:
    """Même frontière que dans la clôture : un identifiant est une chaîne non vide."""
    if not isinstance(valeur, str):
        raise TypeError(f"record_id doit etre une chaine : {valeur!r} "
                        f"est de type {type(valeur).__name__}")
    if not valeur:
        raise ValueError("record_id vide : identification impossible")


def valide_politique(politique, priorite_sources=()) -> tuple:
    """Refuse un paramétrage impossible à l'ENTRÉE, et rend les formes MATÉRIALISÉES.

    Une cascade qui ne finit pas par la règle totale peut se terminer sur plusieurs
    survivants ; l'arbitrage lèverait alors au beau milieu d'une consolidation, une fois la
    moitié des attributs déjà tranchés.

    Retourne `(politique, priorite_sources)` sous forme de tuples, et **tout appelant doit
    travailler sur ces valeurs-là**, jamais sur ses paramètres d'origine. Valider consomme :
    un itérable à usage unique — `iter(...)`, `reversed(...)`, un générateur, `map` — se
    viderait dans la validation et arriverait VIDE au calcul. Une table de priorité perdue
    de cette façon ne lève pas : tous les rangs deviennent égaux, la règle de source
    s'abstient, et la cascade retombe sur l'ordre canonique en rendant un produit
    différent, sans un mot.

    L'inventaire des règles inconnues est une LISTE de `repr`, jamais un ensemble trié :
    trier un ensemble hétérogène lève un `TypeError` dont le message nomme les opérandes
    dans l'ordre d'itération de l'ensemble, donc dans un ordre qui varie d'un processus à
    l'autre. Une erreur au message irreproductible est indiagnosticable — et le `repr`
    distingue au passage `1` de `"1"`.
    """
    noms = tuple(politique)
    if not noms:
        raise ValueError("politique vide : aucune regle de selection")
    inconnues = [repr(n) for n in noms if n not in REGLES]
    if inconnues:
        raise ValueError(f"regles inconnues dans la politique : {inconnues}")
    if len(set(noms)) != len(noms):
        raise ValueError(f"regle repetee dans la politique : {list(noms)}")
    if noms[-1] != REGLE_TERMINALE:
        raise ValueError(f"politique non terminale : la derniere regle doit etre "
                         f"{REGLE_TERMINALE}, recu {noms[-1]!r}")
    sources = tuple(priorite_sources)
    for source in sources:
        if not isinstance(source, str) or not source:
            raise ValueError(f"priorite_sources : {source!r} n'est pas une source valide")
    if len(sources) != len({s for s in sources}):
        raise ValueError(f"source repetee dans priorite_sources : {list(sources)}")
    return noms, sources


def _rang_de_source(source, priorite_sources) -> int:
    """Rang d'une source dans la table de priorité ; DERNIER rang si elle n'y est pas.

    Le dernier rang est `len(priorite_sources)`, jamais `-1` ni `0` : l'un et l'autre
    feraient de toute source absente, vide ou inconnue la source la PLUS prioritaire du
    groupe — un trou de schéma renverserait silencieusement une politique déclarée.
    """
    if isinstance(source, str) and source:
        for rang, connue in enumerate(priorite_sources):
            if connue == source:
                return rang
    return len(priorite_sources)


def valeurs_candidates(membres_bruts, attribut: str, priorite_sources=()) -> dict:
    """Le BULLETIN d'un attribut : les valeurs en lice, groupées par forme normalisée.

    Un membre est candidat si et seulement si la forme normalisée de sa valeur n'est pas
    `None`. C'est la convention de manquant DÉJÀ déclarée par `normalize.py`, réutilisée
    telle quelle. Jamais de test de vérité booléenne : `if valeur` ferait disparaître un
    code postal réduit à « 0 », et un test sur la seule valeur brute ferait de la chaîne
    vide un candidat légitime, élu à l'unanimité d'une voix.

    C'est ICI, et nulle part ailleurs, que le tri des groupes a lieu : c'est l'unique point
    où l'invariance par permutation des membres est établie, tout l'aval étant une fonction
    pure d'une liste déjà triée.

    Le bulletin est **auto-suffisant** : il porte tout ce dont l'arbitrage a besoin. C'est ce
    qui rend la décision rejouable par un tiers qui n'aurait que la trace.

    Il porte en outre cinq champs de LECTURE, destinés à l'auditeur et délibérément non
    consommés par la cascade : `record_ids`, `source_ids`, `source_inconnue` et `n_records`
    au niveau du groupe, `n_membres` au niveau du bulletin. Ils sont nommés ici plutôt que
    laissés à la découverte, parce que la distinction porte une conséquence : les retirer ne
    changerait aucune décision, donc le contrôle négatif du rejeu ne peut pas les dénoncer.
    C'est le test qui ferme le SCHÉMA du groupe qui les tient, pas celui qui mutile la trace.
    `n_records` en particulier existe pour que la lecture « par enregistrements » du vote
    reste re-dérivable par qui la préfère à la lecture « par sources » qui est appliquée.
    """
    if attribut not in ATTRIBUTS_COMPARE:
        raise ValueError(f"attribut hors du schema compare : {attribut!r} "
                         f"(attendus : {list(ATTRIBUTS_COMPARE)})")
    normaliseur = NORMALISEURS[attribut]
    priorite = tuple(priorite_sources)

    seaux = {}
    n_membres = 0
    n_candidats = 0
    for record in membres_bruts:
        n_membres += 1
        rid = record.get("record_id")
        _exige_identifiant(rid)
        brut = record.get(attribut)
        if brut is not None and not isinstance(brut, str):
            raise ValueError(f"valeur d'attribut ni None ni chaine : {attribut}="
                             f"{brut!r} sur {rid!r}")
        cle = normaliseur(brut)
        if cle is None:
            continue
        n_candidats += 1
        seau = seaux.setdefault(cle, {"formes": {}, "record_ids": [],
                                      "sources": {}, "rangs": []})
        seau["formes"].setdefault(brut, []).append(rid)
        seau["record_ids"].append(rid)
        source = record.get("source_id")
        if isinstance(source, str) and source:
            seau["sources"][source] = True
        else:
            # Source absente, nulle ou vide : un seau unique, qui pèse UNE voix. Les
            # confondre avec les sources nommées gonflerait le poids d'un groupe.
            seau["sources"][None] = True
        seau["rangs"].append(_rang_de_source(source, priorite))

    groupes = []
    for cle in sorted(seaux):                       # itération d'une séquence TRIÉE
        seau = seaux[cle]
        formes = [{"forme": forme,
                   "n_records": len(seau["formes"][forme]),
                   "record_id_min": min(seau["formes"][forme])}
                  for forme in sorted(seau["formes"])]
        nommees = sorted(s for s in seau["sources"] if s is not None)
        groupes.append({
            "valeur_normalisee": cle,
            "longueur_normalisee": len(cle),
            "formes_brutes": formes,
            "record_ids": sorted(seau["record_ids"]),
            "source_ids": nommees,
            "source_inconnue": None in seau["sources"],
            "n_records": len(seau["record_ids"]),
            "n_sources": len(seau["sources"]),
            "rang_source": min(seau["rangs"]),
        })
        # Pas de `record_id_min` au niveau du groupe : il serait strictement redondant avec
        # `record_ids[0]`, la liste étant triée, et c'est le `record_id_min` de chaque
        # ÉCRITURE que `forme_retenue` consomme. Redondance, et non « champ décoratif » :
        # les champs de lecture ci-dessus n'entrent pas non plus dans la décision, et ce
        # n'est pas ce qui les condamnerait.
    return {"attribut": attribut, "n_membres": n_membres, "n_candidats": n_candidats,
            "n_groupes": len(groupes), "groupes": groupes}


# ============ Les quatre règles sont des FILTRES PURS `list -> list` ==================
# S'abstenir, c'est rendre la liste INCHANGÉE — donc observable. Aucune règle ne
# sélectionne d'élément : c'est ce qui élimine structurellement `max(..., key=...)`, dont
# la réponse à égalité de clé dépend de l'ordre de rencontre.
def regle_majorite(survivants) -> list:
    """Garde les groupes dont le nombre de SOURCES distinctes est maximal."""
    if not survivants:
        return list(survivants)
    sommet = max(g["n_sources"] for g in survivants)
    return [g for g in survivants if g["n_sources"] == sommet]


def regle_completude(survivants) -> list:
    """Garde les groupes dont la forme normalisée est la plus longue.

    Une égalité de longueur normalisée tombe d'un cran dans la cascade : jamais de
    départage par la longueur BRUTE, qui trierait par densité de ponctuation.
    """
    if not survivants:
        return list(survivants)
    sommet = max(g["longueur_normalisee"] for g in survivants)
    return [g for g in survivants if g["longueur_normalisee"] == sommet]


def regle_source_prioritaire(survivants) -> list:
    """Garde les groupes portés par la source la mieux classée.

    Table de priorité vide : tous les rangs valent 0, la règle n'élimine personne et
    s'abstient — sans jamais inventer d'ordre sur les identifiants de source.
    """
    if not survivants:
        return list(survivants)
    meilleur = min(g["rang_source"] for g in survivants)
    return [g for g in survivants if g["rang_source"] == meilleur]


def regle_ordre_canonique(survivants) -> list:
    """Garde le groupe de plus petite forme normalisée. TOTALE par construction.

    Les clés de vote d'un même bulletin sont distinctes deux à deux : cette règle rend donc
    toujours exactement un groupe, et c'est pour cela qu'elle clôt la cascade.
    """
    if not survivants:
        return list(survivants)
    return [sorted(survivants, key=lambda g: g["valeur_normalisee"])[0]]


_FILTRES = {MAJORITE: regle_majorite, COMPLETUDE: regle_completude,
            SOURCE_PRIORITAIRE: regle_source_prioritaire,
            ORDRE_CANONIQUE: regle_ordre_canonique}


def forme_retenue(groupe: dict) -> tuple:
    """Écriture brute émise pour un groupe, et l'enregistrement d'où elle vient.

    Nécessaire parce que la normalisation replie les diacritiques et la casse : « Marché » et
    « Marche » vivent dans le MÊME groupe, il faut donc encore choisir laquelle émettre.
    Deux étages : l'écriture la plus fréquente, puis le plus petit `record_id` qui la porte.
    La provenance en sort gratuitement.

    La clé de tri se termine par l'écriture elle-même, de sorte qu'elle soit TOTALE sans
    rien présumer de l'entrée. Sur un groupe bien formé, un enregistrement ne porte qu'une
    écriture et les `record_id_min` suffiraient déjà à départager ; mais `valeurs_candidates`
    et `trace_selection` acceptent, eux, un identifiant répété — seule `consolide_entite` le
    refuse. Faire reposer la totalité de l'ordre sur une garde qui vit ailleurs serait la
    perdre partout où cette garde ne s'applique pas.
    """
    ordonnees = sorted(groupe["formes_brutes"],
                       key=lambda f: (-f["n_records"], f["record_id_min"], f["forme"]))
    retenue = ordonnees[0]
    return retenue["forme"], retenue["record_id_min"]


def _ecart_de_tete(valeurs) -> int:
    """Écart entre la plus grande valeur et la suivante. `0` quand il n'y a pas de suivante."""
    ordonnees = sorted(valeurs, reverse=True)
    if len(ordonnees) < 2:
        return 0
    return ordonnees[0] - ordonnees[1]


def arbitre_attribut(bulletin: dict, politique=POLITIQUE_DEFAUT) -> dict:
    """Applique la cascade au SEUL bulletin, et rend la décision motivée.

    Sa signature EST la preuve de rejouabilité : elle ne reçoit pas les enregistrements,
    donc rien qui ne soit publié dans le bulletin ne peut peser sur la décision. Un tiers
    qui n'a que la trace retrouve exactement la même valeur.

    Le dénominateur est le nombre de CANDIDATS, jamais le nombre de membres : une valeur
    manquante n'est pas un vote contre. Sinon un attribut présent chez un seul membre sur
    trois serait « non résolu », et la consolidation détruirait la seule information dont
    l'entité dispose.
    """
    politique, _ = valide_politique(politique)
    groupes = list(bulletin["groupes"])
    ecart_majorite = _ecart_de_tete([g["n_sources"] for g in groupes])

    def decision(groupe, regle, rang_regle, abstenues, ecart_completude=None) -> dict:
        valeur, origine = (None, None) if groupe is None else forme_retenue(groupe)
        return {
            "attribut": bulletin["attribut"],
            "valeur": valeur,
            "valeur_normalisee": None if groupe is None else groupe["valeur_normalisee"],
            "origine": origine,
            "regle": regle,
            "rang_regle": rang_regle,
            "regles_abstenues": abstenues,
            "n_candidats": bulletin["n_candidats"],
            "n_groupes": bulletin["n_groupes"],
            "ecart_majorite": ecart_majorite,
            "ecart_completude": ecart_completude,
        }

    # Deux états qui ne sont pas des arbitrages : `rang_regle` reste None parce qu'aucune
    # règle n'est créditée. « 1 sur 1 » n'est pas un consensus, c'est une absence de
    # contradiction — un auditeur doit pouvoir lire la différence.
    if not groupes:
        return decision(None, AUCUN_CANDIDAT, None, [])
    if len(groupes) == 1:
        return decision(groupes[0], CANDIDAT_UNIQUE, None, [])

    survivants = groupes
    abstenues = []
    for rang, nom_regle in enumerate(politique):
        avant = survivants
        survivants = _FILTRES[nom_regle](avant)
        if len(survivants) == len(avant):
            abstenues.append(nom_regle)
            continue
        if len(survivants) == 1:
            ecart = (_ecart_de_tete([g["longueur_normalisee"] for g in avant])
                     if nom_regle == COMPLETUDE else None)
            return decision(survivants[0], nom_regle, rang, abstenues, ecart)
    raise ValueError(
        f"cascade non terminale : {len(survivants)} survivants apres {list(politique)}")


def trace_selection(membres_bruts, attribut: str, politique=POLITIQUE_DEFAUT,
                    priorite_sources=()) -> dict:
    """Le bulletin complet d'UN attribut et sa décision, À LA DEMANDE.

    Retourne `{"bulletin": ..., "decision": ...}`. Délègue au MÊME arbitre que
    `consolide_entite` : la trace ne PEUT PAS diverger du produit, et un test l'atteste.

    C'est le pivot de la conception : l'information d'audit est DISPONIBLE sans être PORTÉE
    par chaque enregistrement produit.
    """
    politique, priorite = valide_politique(politique, priorite_sources)
    bulletin = valeurs_candidates(membres_bruts, attribut, priorite)
    return {"bulletin": bulletin, "decision": arbitre_attribut(bulletin, politique)}


def consolide_entite(membres_bruts, politique=POLITIQUE_DEFAUT,
                     priorite_sources=()) -> dict:
    """Une entité -> UN enregistrement doré, aux 10 clés CONSTANTES sur tous les chemins.

        {"record_ids_sources": [...],            # exigence de traçabilité du mandat
         "nom": ..., "prenom": ..., ... ,        # les 8 attributs, À PLAT, en forme BRUTE
         "origines": {"nom": "REC_0001", ...}}   # d'où vient CHAQUE valeur

    Singleton, groupe en désaccord total, groupe dont les 8 attributs sont absents partout :
    toujours ces 10 clés. Un contrat qui change de forme selon la branche est un contrat
    qu'aucun appelant ne peut consommer sans condition.

    Les valeurs sont BRUTES : un enregistrement doré doit se lire exactement comme un
    enregistrement source. La normalisation est un dispositif de COMPARAISON, pas un
    produit — l'émettre détruirait une information qu'aucune étape en aval ne peut restaurer.

    `origines` est le seul champ au-delà du littéral du mandat, et il le mérite : la liste
    des sources répond « quels enregistrements ont été réunis », pas « d'où vient CETTE
    valeur ». Or un enregistrement doré est une chimère par construction — le nom de l'un,
    l'adresse de l'autre. Sans `origines`, la traçabilité s'arrête exactement là où elle
    devient utile. Le biconditionnel `origines[a] is None` ⟺ `valeur[a] is None` en donne
    un oracle bon marché.

    Refuse un groupe dont les membres ne sont pas triés et distincts : le déterminisme de la
    consolidation est CONDITIONNÉ par la canonicité d'ordre de la clôture. Accepter un
    groupe désordonné rendrait silencieusement le produit dépendant de l'ordre d'entrée.
    """
    politique, priorite = valide_politique(politique, priorite_sources)
    membres = list(membres_bruts)
    if not membres:
        raise ValueError("groupe vide : aucun enregistrement a consolider")
    identifiants = []
    for record in membres:
        rid = record.get("record_id")
        _exige_identifiant(rid)
        identifiants.append(rid)
    if len(set(identifiants)) != len(identifiants):
        raise ValueError(f"record_id duplique dans le groupe : {sorted(identifiants)}")
    if identifiants != sorted(identifiants):
        raise ValueError(f"groupe non canonique : membres non tries {identifiants}")

    dore = {"record_ids_sources": identifiants}
    origines = {}
    for attribut in ATTRIBUTS_COMPARE:      # projection défensive : le tuple FERMÉ, jamais
        bulletin = valeurs_candidates(membres, attribut, priorite)           # record.keys()
        arbitrage = arbitre_attribut(bulletin, politique)
        dore[attribut] = arbitrage["valeur"]
        origines[attribut] = arbitrage["origine"]
    dore["origines"] = origines
    return dore


def consolide_partition(partition, records, politique=POLITIQUE_DEFAUT,
                        priorite_sources=()) -> list:
    """Une partition -> un enregistrement doré par entité, dans l'ordre de la partition.

    `len(sortie) == len(partition)` est le contrat de cardinalité du mandat, vérifiable en
    une assertion. Aucune enveloppe, aucun rapport d'exécution : la politique est celle que
    l'appelant a passée, il n'a pas besoin qu'on la lui renvoie.
    """
    politique, priorite = valide_politique(politique, priorite_sources)
    index = {}
    for record in records:
        rid = record.get("record_id")
        if rid is None:
            raise ValueError("enregistrement sans record_id : identification impossible")
        _exige_identifiant(rid)
        if rid in index:
            raise ValueError(f"record_id duplique : {rid!r}")
        index[rid] = record

    sortie = []
    for membres in partition:
        absents = sorted(rid for rid in membres if rid not in index)
        if absents:
            raise ValueError(f"membres sans enregistrement : {absents}")
        sortie.append(consolide_entite([index[rid] for rid in membres],
                                       politique, priorite))
    return sortie
