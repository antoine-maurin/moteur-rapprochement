"""Critères de lecture PRÉ-ENREGISTRÉS de la contribution de la revue du doute (U-B7, O1).

Ce fichier est **gelé** et committé SEUL, AVANT le moindre chiffre neuf : git rend
l'antériorité vérifiable par un tiers (`git merge-base --is-ancestor <gel> <mesure>`), et
`sha256_criteres_contribution()` la rend citable dans l'artefact. Aucun seuil ci-dessous
n'est révisable après avoir vu un résultat. Si l'un se révèle mal posé, on publie la mesure
ET la critique du critère ; on ne réécrit pas le critère.

## La question, posée avant de connaître la réponse
« Le substitut `1b` de revue apporte-t-il quelque chose sur la zone grise DIMS-v2 réelle ? »

Cette question est plus exposée au biais que la comparaison U-B6, et pour une raison
précise : la matière est **mince**. Quand la zone grise ne contient qu'une poignée de paires
réellement liées, une seule paire restituée déplace le rappel de plusieurs points. Un
lecteur pressé lira « +N points » ; un lecteur averti demandera « sur combien ? ». Toute la
grille ci-dessous existe pour que la seconde question ait sa réponse dans l'artefact, à côté
du chiffre, et non dans la tête de celui qui l'a produit.

## Déclaration d'antériorité — ce qui était connu au moment du gel
**Aucun chiffre de contribution du substitut `1b` sur la zone grise DIMS-v2 n'a été consulté
pour poser ces seuils : aucun n'existait.** Ce qui ÉTAIT connu est déclaré ici, intégralement,
pour que le lecteur juge lui-même d'une éventuelle contamination au lieu de devoir la supposer.

  (a) **Le mandat lui-même annonce la minceur de la matière** : « zone grise DIMS-v2 réelle
      (298 paires, 6 vraies) », et il ordonne de publier le résultat « même si ~1 pt » (O-S1).
      La barre basse est donc posée par l'ÉMETTEUR, pas choisie ici. C'est le point le plus
      important de cette déclaration : le risque classique du pré-enregistrement — placer la
      barre à la hauteur qu'on sait pouvoir franchir — est structurellement absent, et il
      l'est dans le sens défavorable, puisque le mandat exige la publication d'un gain nul.

  (b) **U-B3 a déjà publié, sur SA population de démonstration (générée, 400 entités, pas
      celle-ci), que sa zone grise ne contenait qu'UNE paire réellement liée**, et que cette
      paire s'y trouvait parce que le dimensionnement avait posé `t_mu` exactement sur son
      agrégat. J'ai vu cette valeur avant de geler : elle est apparue dans la sortie du test
      de régénération d'artefact pendant le merge U-B3 (zone grise de 360 paires sur l'arbre
      fusionné, 1 seule liée). Elle porte sur une AUTRE population que celle mesurée ici,
      mais je la déclare parce qu'elle m'informait sur l'ORDRE DE GRANDEUR du plafond, donc
      potentiellement sur ma façon de poser les seuils.

      Conséquence assumée et vérifiable : aucun seuil de ce fichier n'est placé au voisinage
      d'une valeur connue. `TOLERANCE_PRECISION_STABLE` et `DECIMALES_TAUX` sont des
      grandeurs de lecture, pas des barres de succès ; et la grille ne comporte
      **délibérément aucun seuil de gain minimal** — parce qu'un tel seuil serait exactement
      l'endroit où l'on tricherait. Le gain est publié quel qu'il soit ; ce qui est jugé,
      c'est la LOYAUTÉ de sa lecture.

  (c) Des grandeurs mécaniques, mesurables sans vérité terrain : `artifacts/dims_v2.json`
      annonce une zone grise de 301 paires (le mandat en annonce 298 — l'écart est un fait à
      publier, pas à arbitrer ici : cf. `C9_POPULATION_DECLAREE`), un budget visé de 300, et
      des seuils marqués `provisoire`/`GAP-A`.

## Ce que « contribution » veut dire, posé AVANT la mesure
Une contribution est un **gain de rappel à précision stable**, lu **contre son plafond**.
Trois clauses, toutes nécessaires :

  1. *gain de rappel* : des paires réellement liées, laissées indéterminées par le moteur,
     que la revue promeut. Pas « des paires promues » : des paires promues **et vraies**.
  2. *à précision stable* : promouvoir agressivement gagne toujours du rappel. Un gain acheté
     par une chute de précision n'est pas une contribution, c'est un déplacement de seuil —
     que le moteur sait faire seul, sans revue.
  3. *contre son plafond* : le plafond est le nombre de paires vraies PRÉSENTES dans la zone
     grise. Aucune revue, si parfaite soit-elle, ne peut en restituer davantage. Un gain de
     `k` paires sur un plafond de `p` se lit `k/p`, jamais `k/0`.

`CONTRIBUTION_NULLE` n'est pas un échec de la mesure : c'est un résultat, et sa phrase est
rédigée avec le même soin que celle du succès (§ ÉNONCÉS). Elle nomme d'avance les
échappatoires qu'elle s'interdit.

## R-20 — le doute non tranché reste gris
`NON_TRANCHE` ne devient JAMAIS un lien. Une paire que la revue ne sait pas trancher sort de
la revue exactement comme elle y est entrée. C'est éprouvé structurellement (`C2`), et non
seulement affirmé.

## Ce qui est mesuré n'est pas « une IA »
Le client de revue est un **substitut déterministe déclaré** (rejeu de vecteurs enregistrés).
Il ne doit être décrit nulle part comme un modèle de langue, et l'artefact doit le nommer
pour ce qu'il est (`C7`). Un substitut ne prouve rien sur ce qu'un adjudicateur réel ferait :
il prouve ce que la CHAÎNE fait quand un adjudicateur répond, ce qui est une autre question,
et l'artefact doit dire laquelle des deux il traite.
"""
from __future__ import annotations

import hashlib
import os
from typing import Optional

__all__ = [
    "SATISFAIT", "ECHEC", "NON_EVALUABLE", "ISSUES",
    "CONTRIBUTION_MESUREE", "CONTRIBUTION_NULLE", "NOT_CONCLUSIVE", "VERDICTS_CONTRIBUTION",
    "TOLERANCE_PRECISION_STABLE", "DECIMALES_TAUX", "NIVEAU_DE_CONFIANCE",
    "CRITERES_CONTRIBUTION", "ENONCES_CONTRIBUTION",
    "sha256_criteres_contribution", "evalue_criteres_contribution",
    "intervalle_wilson", "lis_verdict_contribution",
]

# ============================ issues et verdicts (énumérations FERMÉES) ================
SATISFAIT = "SATISFAIT"
ECHEC = "ECHEC"
#: Un critère qu'on ne peut pas évaluer n'est JAMAIS satisfait par défaut.
NON_EVALUABLE = "NON_EVALUABLE"
ISSUES = (SATISFAIT, ECHEC, NON_EVALUABLE)

CONTRIBUTION_MESUREE = "CONTRIBUTION_MESUREE"
CONTRIBUTION_NULLE = "CONTRIBUTION_NULLE"
#: Grille cassée : on ne conclut pas. Une mesure défaillante ne mesure rien — et surtout
#: pas l'absence de contribution.
NOT_CONCLUSIVE = "NOT_CONCLUSIVE"
VERDICTS_CONTRIBUTION = (CONTRIBUTION_MESUREE, CONTRIBUTION_NULLE, NOT_CONCLUSIVE)

# ============================ grandeurs de lecture, gelées ============================
#: Chute de précision TOLÉRÉE pour qu'un gain de rappel soit encore dit « à précision
#: stable », en points absolus. Une valeur ronde, choisie comme grandeur de lecture et non
#: comme barre de succès : à ce niveau de matière, une seule fausse promotion sur ~300
#: paires candidates déplace déjà la précision de plus que cela, donc le critère MORD.
TOLERANCE_PRECISION_STABLE = 0.01

#: Arrondi des taux publiés. Le contenu porteur reste ENTIER (numérateurs, dénominateurs,
#: effectifs) : un taux est une commodité de lecture, jamais la donnée.
DECIMALES_TAUX = 5

#: Niveau de l'intervalle de confiance publié à côté de tout taux issu d'un petit effectif.
NIVEAU_DE_CONFIANCE = 0.95
#: z pour 95 %, en dur : `statistics.NormalDist` n'est pas garanti bit-à-bit d'une version
#: à l'autre, et cette constante entre dans un artefact qui doit se régénérer à l'octet.
_Z_95 = 1.959963984540054

# ============================ la grille, critère par critère ==========================
CRITERES_CONTRIBUTION = {
    # ---- PÉRIMÈTRE ET PRUDENCE (ce que la revue n'a pas le droit de faire) -----------
    "C1_PERIMETRE_ZONE_GRISE": {
        "enonce_du_critere": "la revue n'a-t-elle instruit QUE des paires en zone grise ?",
        "seuil": "aucune paire deja tranchee (MATCH ou NON_MATCH) instruite ni modifiee",
        "famille": "perimetre"},
    "C2_R20_NON_TRANCHE_RESTE_GRIS": {
        "enonce_du_critere": "le doute non tranche reste-t-il gris ?",
        "seuil": "aucune paire NON_TRANCHE, ni non revue, promue en lien",
        "famille": "prudence"},
    "C3_ENTREE_NON_MUTEE": {
        "enonce_du_critere": "la revue rend-elle une liste NEUVE sans muter la sortie moteur ?",
        "seuil": "la liste d'entree est identique avant et apres la revue",
        "famille": "perimetre"},

    # ---- HONNÊTETÉ DE LA LECTURE (le cœur de ce gel) --------------------------------
    "C4_PLAFOND_PUBLIE": {
        "enonce_du_critere": "le plafond de la contribution est-il publie a cote du gain ?",
        "seuil": "n_vraies_en_zone_grise present, et gain_en_paires <= plafond",
        "famille": "honnetete"},
    "C5_PRECISION_STABLE": {
        "enonce_du_critere": "le gain de rappel est-il obtenu a precision stable ?",
        "seuil": {"chute_toleree": TOLERANCE_PRECISION_STABLE},
        "famille": "honnetete"},
    "C6_INTERVALLE_PUBLIE": {
        "enonce_du_critere": "l'incertitude est-elle publiee a cote de chaque taux ?",
        "seuil": {"niveau": NIVEAU_DE_CONFIANCE,
                  "regle": "intervalle de Wilson sur tout taux issu d'un effectif < 100"},
        "famille": "honnetete"},
    "C7_SUBSTITUT_DECLARE": {
        "enonce_du_critere": "le substitut est-il nomme pour ce qu'il est ?",
        "seuil": ("le client est declare substitut deterministe ; les mots 'IA', "
                  "'intelligence artificielle', 'modele de langue', 'LLM' sont ABSENTS "
                  "de l'artefact publie"),
        "famille": "honnetete"},
    "C8_COUT_PUBLIE": {
        "enonce_du_critere": "le volume revu et le cout sont-ils publies ?",
        "seuil": "n_paires_instruites, budget et cout declare presents",
        "famille": "honnetete"},
    "C9_POPULATION_DECLAREE": {
        "enonce_du_critere": "la population mesuree est-elle identifiee sans ambiguite ?",
        "seuil": ("fixture, content_sha256, point de fonctionnement et taille de zone "
                  "grise OBSERVEE publies ; tout ecart a une taille annoncee ailleurs "
                  "est publie comme fait, jamais arbitre en silence"),
        "famille": "honnetete"},

    # ---- MÉCANIQUE (sans quoi rien de ce qui précède n'est lisible) -----------------
    "C10_DETERMINISME": {
        "enonce_du_critere": "deux mesures identiques rendent-elles le meme artefact ?",
        "seuil": "serialisation canonique identique entre deux constructions",
        "famille": "plomberie"},
    "C11_ANTERIORITE_DU_GEL": {
        "enonce_du_critere": "un tiers peut-il verifier que les criteres precedent la mesure ?",
        "seuil": ("un seul commit sur ce fichier ; commit de gel ancetre du commit de "
                  "mesure ; sha256 du fichier cite dans l'artefact"),
        "famille": "honnetete"},
}

# ============================ les phrases, écrites AVANT ==============================
#: Une phrase par issue, gabarit compris. Écrire d'avance la phrase DÉFAVORABLE est le seul
#: dispositif qui empêche de la rédiger, le moment venu, avec moins de soin que l'autre.
ENONCES_CONTRIBUTION = {
    "C1_PERIMETRE_ZONE_GRISE_SAT": (
        "Perimetre respecte : {n_instruites} paires instruites, toutes en zone grise. "
        "Aucune paire deja tranchee n'a ete relue ni modifiee."),
    "C1_PERIMETRE_ZONE_GRISE_NON_SAT": (
        "PERIMETRE ROMPU : {n_hors_perimetre} paire(s) hors zone grise ont ete touchees. "
        "La revue a rejuge ce que le moteur avait decide ; la mesure ne porte plus sur "
        "la contribution d'une revue du doute et n'est pas publiable comme telle."),

    "C2_R20_NON_TRANCHE_RESTE_GRIS_SAT": (
        "R-20 tenu : {n_non_tranche} paire(s) NON_TRANCHE et {n_non_revue} non revue(s) "
        "sont restees indeterminees. Aucune promotion sans decision."),
    "C2_R20_NON_TRANCHE_RESTE_GRIS_NON_SAT": (
        "R-20 VIOLE : {n_promues_sans_decision} paire(s) ont ete promues sans decision de "
        "revue. Le doute non tranche est devenu un lien, ce qui est exactement la "
        "defaillance que la regle interdit."),

    "C3_ENTREE_NON_MUTEE_SAT": (
        "La sortie du moteur est intacte apres la revue : la revue enrichit une copie."),
    "C3_ENTREE_NON_MUTEE_NON_SAT": (
        "La revue a MUTE la sortie du moteur. Le point de comparaison 'avant' n'existe "
        "plus, donc aucun ecart mesure ici n'est interpretable."),

    "C4_PLAFOND_PUBLIE_SAT": (
        "Plafond publie : la zone grise contient {plafond} paire(s) reellement liee(s) sur "
        "{n_zone_grise} paires. Aucune revue ne peut en restituer davantage. Le gain "
        "constate est de {gain_en_paires} paire(s), soit {part_du_plafond} du plafond."),
    "C4_PLAFOND_PUBLIE_NON_SAT": (
        "PLAFOND NON PUBLIE OU DEPASSE (gain {gain_en_paires} pour un plafond {plafond}). "
        "Un gain qui excede le nombre de paires vraies presentes signale un defaut de "
        "comptage, pas une performance."),

    "C5_PRECISION_STABLE_SAT": (
        "Precision stable : {precision_avant} -> {precision_apres} (variation "
        "{delta_precision}, tolerance {tolerance}). Le gain de rappel n'est pas achete par "
        "des promotions fausses."),
    "C5_PRECISION_STABLE_NON_SAT": (
        "PRECISION NON STABLE : {precision_avant} -> {precision_apres} (chute "
        "{delta_precision} > {tolerance}). Le rappel gagne l'a ete au prix de promotions "
        "fausses : ce n'est pas une contribution de la revue, c'est un deplacement de "
        "seuil, que le moteur sait produire seul et sans cout."),

    "C6_INTERVALLE_PUBLIE_SAT": (
        "Incertitude publiee : rappel {rappel_apres}, intervalle de Wilson a "
        "{niveau} = [{borne_basse} ; {borne_haute}]. Sur {plafond} paire(s) vraie(s) en "
        "zone grise, UNE paire vaut {valeur_d_une_paire} de rappel : l'intervalle est "
        "large, et c'est la matiere qui le veut, pas la mesure qui faiblit."),
    "C6_INTERVALLE_PUBLIE_NON_SAT": (
        "INTERVALLE ABSENT : un taux issu d'un petit effectif est publie sans son "
        "incertitude. Le chiffre serait lu comme s'il etait precis ; il ne l'est pas."),

    "C7_SUBSTITUT_DECLARE_SAT": (
        "Le client de revue est declare pour ce qu'il est : {nom_client}, substitut "
        "deterministe par rejeu. Ce qui est mesure ici est le comportement de la CHAINE "
        "quand un adjudicateur repond, et non ce qu'un adjudicateur reel deciderait."),
    "C7_SUBSTITUT_DECLARE_NON_SAT": (
        "SUBSTITUT MAL DECLARE : l'artefact emploie un vocabulaire qui laisse croire a un "
        "modele de langue ({termes_trouves}), ou n'identifie pas son client. La mesure "
        "serait lue comme portant sur une capacite qu'elle n'a pas eprouvee."),

    "C8_COUT_PUBLIE_SAT": (
        "Cout publie : {n_instruites} paires instruites pour un budget de {budget}, cout "
        "declare {cout}."),
    "C8_COUT_PUBLIE_NON_SAT": (
        "COUT NON PUBLIE : un gain sans son cout n'est pas un resultat exploitable."),

    "C9_POPULATION_DECLAREE_SAT": (
        "Population identifiee : {fixture}, content_sha256 {sha_fixture}, au point "
        "{point}. Zone grise OBSERVEE : {n_zone_grise} paires. {note_ecart}"),
    "C9_POPULATION_DECLAREE_NON_SAT": (
        "POPULATION MAL IDENTIFIEE : sans fixture, empreinte et point de fonctionnement, "
        "le chiffre n'est rattachable a rien et n'est pas reproductible par un tiers."),

    "C10_DETERMINISME_SAT": (
        "Deux constructions rendent la meme serialisation canonique."),
    "C10_DETERMINISME_NON_SAT": (
        "NON DETERMINISME : deux constructions divergent. L'artefact ne se regenere pas, "
        "donc aucune valeur qu'il porte n'est verifiable par un tiers."),

    "C11_ANTERIORITE_DU_GEL_SAT": (
        "Anteriorite verifiable par un tiers qui n'a que le depot : criteres geles au "
        "commit {commit_gel} (sha256 {sha_fichier}), ancetre du commit de mesure "
        "{commit_mesure}."),
    "C11_ANTERIORITE_DU_GEL_NON_SAT": (
        "ANTERIORITE NON ETABLIE : {motif}. Les criteres ne sont pas demontrablement "
        "anterieurs a la mesure, donc le pre-enregistrement ne vaut rien ici."),

    # ---- LES DEUX VERDICTS D'ENSEMBLE, ÉCRITS AVEC LE MÊME SOIN --------------------
    "VERDICT_CONTRIBUTION_MESUREE": (
        "CONTRIBUTION MESUREE. Sur la zone grise de {n_zone_grise} paires du point {point}, "
        "qui contient {plafond} paire(s) reellement liee(s), la revue en restitue "
        "{gain_en_paires}. Rappel {rappel_avant} -> {rappel_apres} (delta "
        "{delta_rappel}), F1 {f1_avant} -> {f1_apres} (delta {delta_f1}), a precision "
        "stable ({delta_precision}). Ce gain est petit en valeur absolue, et il DOIT etre "
        "lu contre son plafond : {part_du_plafond} de ce qui etait atteignable. "
        "L'intervalle de confiance a {niveau} est [{borne_basse} ; {borne_haute}] ; sur un "
        "effectif de cette taille, une seule paire vaut {valeur_d_une_paire} de rappel. "
        "Ce resultat ne dit rien de ce qu'un adjudicateur reel ferait : le client est un "
        "substitut deterministe."),
    "VERDICT_CONTRIBUTION_NULLE": (
        "CONTRIBUTION NULLE. Sur la zone grise de {n_zone_grise} paires du point {point}, "
        "qui contient {plafond} paire(s) reellement liee(s), la revue n'en restitue "
        "AUCUNE. Rappel et F1 sont inchanges. C'est un resultat, publie tel quel, et il ne "
        "sera requalifie ni en 'zone grise defavorable', ni en 'substitut a remplacer', ni "
        "en 'budget trop court', ni en 'mesure a refaire sur une autre population' : ces "
        "quatre echappatoires sont nommees ici, avant la mesure, precisement pour qu'aucune "
        "ne puisse etre invoquee apres. Si la revue doit apporter quelque chose, elle le "
        "montrera sur une zone grise qui contient de quoi le montrer ; ce qui est etabli "
        "ici, c'est que sur CETTE zone grise, au point DIMS-v2, elle n'apporte rien de "
        "mesurable."),
    "VERDICT_NOT_CONCLUSIVE": (
        "NOT_CONCLUSIVE : {motif}. La grille est cassee ; on ne conclut pas. Une mesure "
        "defaillante ne mesure rien, et surtout pas l'absence de contribution."),
}


# ============================ helpers, sans dépendance externe ========================
def sha256_criteres_contribution(chemin: Optional[str] = None) -> str:
    """sha256 de CE fichier : ce qui rend le gel citable dans l'artefact."""
    with open(chemin or os.path.abspath(__file__), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _fini(x) -> bool:
    """Vrai si `x` est un nombre exploitable (ni None, ni bool, ni NaN, ni infini)."""
    if x is None or isinstance(x, bool):
        return False
    if not isinstance(x, (int, float)):
        return False
    return x == x and x not in (float("inf"), float("-inf"))


class _Defaut(dict):
    """Substitution tolérante : une valeur absente devient `n/d` au lieu de lever.

    Une phrase de verdict ne doit jamais faire échouer la mesure qui la motive. Le GABARIT
    reste intact et comparable à `ENONCES_CONTRIBUTION` — c'est lui, et non la phrase
    rendue, qui atteste le pré-enregistrement.
    """

    def __missing__(self, cle):
        return "n/d"


def intervalle_wilson(succes: int, effectif: int, z: float = _Z_95):
    """Intervalle de Wilson — celui qui convient aux TRÈS petits effectifs.

    Wilson plutôt que Wald, et le choix est gelé ici plutôt que laissé au moment de la
    mesure : sur 1 succès parmi 6, l'intervalle de Wald donne des bornes absurdes (il peut
    sortir de [0, 1], et il se réduit à un point quand le taux vaut 0 ou 1), ce qui
    laisserait publier une fausse précision exactement là où l'incertitude est maximale.
    """
    if effectif <= 0:
        return None
    p = succes / effectif
    d = 1.0 + z * z / effectif
    centre = (p + z * z / (2 * effectif)) / d
    demi = (z / d) * ((p * (1 - p) / effectif + z * z / (4 * effectif * effectif)) ** 0.5)
    return (round(max(0.0, centre - demi), DECIMALES_TAUX),
            round(min(1.0, centre + demi), DECIMALES_TAUX))


def _issue(condition: Optional[bool]) -> str:
    """`None` (indéterminé) ne devient jamais un succès : il devient NON_EVALUABLE."""
    if condition is None:
        return NON_EVALUABLE
    return SATISFAIT if condition else ECHEC


def _critere(code: str, valeur_observee, issue: str,
             valeurs: Optional[dict] = None) -> dict:
    """Une entrée de verdict : le critère, son seuil, ce qui a été observé, l'issue.

    `enonce_retenu` porte le GABARIT verbatim (comparable à `ENONCES_CONTRIBUTION`),
    `enonce_rendu` la phrase avec ses valeurs substituées. Les séparer est ce qui rend le
    pré-enregistrement vérifiable : le gabarit n'a pas pu être réécrit après coup.
    """
    cle_enonce = code + ("_SAT" if issue == SATISFAIT else "_NON_SAT")
    gabarit = ENONCES_CONTRIBUTION[cle_enonce]
    return {
        "code": code,
        "enonce_du_critere": CRITERES_CONTRIBUTION[code]["enonce_du_critere"],
        "famille": CRITERES_CONTRIBUTION[code]["famille"],
        "seuil": CRITERES_CONTRIBUTION[code]["seuil"],
        "valeur_observee": valeur_observee,
        "issue": issue,
        "cle_enonce": cle_enonce,
        "enonce_retenu": gabarit,
        "enonce_rendu": gabarit.format_map(_Defaut(valeurs or {})),
    }


def evalue_criteres_contribution(mesures: dict) -> list:
    """Applique les critères gelés aux mesures. Une entrée PAR critère déclaré.

    `mesures` est le bloc brut produit par l'outil de mesure ; ce module ne calcule aucune
    métrique et n'en recompte aucune — il LIT. La séparation est la même qu'en U-B6 : le
    banc mesure, les critères jugent, et le juge ne remesure pas.
    """
    per = mesures.get("perimetre") or {}
    pru = mesures.get("prudence") or {}
    pla = mesures.get("plafond") or {}
    eff = mesures.get("effets") or {}
    inc = mesures.get("incertitude") or {}
    cli = mesures.get("client") or {}
    cou = mesures.get("cout") or {}
    pop = mesures.get("population") or {}
    det = mesures.get("determinisme") or {}
    ant = mesures.get("anteriorite") or {}

    entrees = []

    n_hors = per.get("n_hors_perimetre")
    entrees.append(_critere(
        "C1_PERIMETRE_ZONE_GRISE", n_hors,
        _issue(None if n_hors is None else n_hors == 0),
        {"n_instruites": per.get("n_instruites"), "n_hors_perimetre": n_hors}))

    n_sans = pru.get("n_promues_sans_decision")
    entrees.append(_critere(
        "C2_R20_NON_TRANCHE_RESTE_GRIS", n_sans,
        _issue(None if n_sans is None else n_sans == 0),
        {"n_non_tranche": pru.get("n_non_tranche"),
         "n_non_revue": pru.get("n_non_revue"),
         "n_promues_sans_decision": n_sans}))

    intacte = per.get("entree_intacte")
    entrees.append(_critere(
        "C3_ENTREE_NON_MUTEE", intacte,
        _issue(None if intacte is None else bool(intacte)), {}))

    plafond, gain = pla.get("n_vraies_en_zone_grise"), pla.get("gain_en_paires")
    ok_plafond = (None if not (isinstance(plafond, int) and isinstance(gain, int))
                  else 0 <= gain <= plafond)
    entrees.append(_critere(
        "C4_PLAFOND_PUBLIE", {"plafond": plafond, "gain_en_paires": gain},
        _issue(ok_plafond),
        {"plafond": plafond, "gain_en_paires": gain,
         "n_zone_grise": pla.get("n_zone_grise"),
         "part_du_plafond": pla.get("part_du_plafond")}))

    dp = eff.get("delta_precision")
    ok_prec = None if not _fini(dp) else dp >= -TOLERANCE_PRECISION_STABLE
    entrees.append(_critere(
        "C5_PRECISION_STABLE", dp, _issue(ok_prec),
        {"precision_avant": eff.get("precision_avant"),
         "precision_apres": eff.get("precision_apres"),
         "delta_precision": dp, "tolerance": TOLERANCE_PRECISION_STABLE}))

    bornes = inc.get("intervalle_rappel_apres")
    ok_int = None if bornes is None else (isinstance(bornes, (list, tuple))
                                          and len(bornes) == 2)
    entrees.append(_critere(
        "C6_INTERVALLE_PUBLIE", bornes, _issue(ok_int),
        {"rappel_apres": eff.get("rappel_apres"), "niveau": NIVEAU_DE_CONFIANCE,
         "borne_basse": (bornes or ["n/d", "n/d"])[0],
         "borne_haute": (bornes or ["n/d", "n/d"])[1],
         "plafond": plafond,
         "valeur_d_une_paire": inc.get("valeur_d_une_paire_en_rappel")}))

    termes = cli.get("termes_interdits_trouves")
    ok_cli = (None if termes is None or not cli.get("nom")
              else len(termes) == 0 and bool(cli.get("est_substitut_declare")))
    entrees.append(_critere(
        "C7_SUBSTITUT_DECLARE", {"nom": cli.get("nom"), "termes_trouves": termes},
        _issue(ok_cli),
        {"nom_client": cli.get("nom"), "termes_trouves": termes}))

    ok_cout = all(cou.get(k) is not None for k in ("n_instruites", "budget", "cout_declare"))
    entrees.append(_critere(
        "C8_COUT_PUBLIE", cou, _issue(ok_cout),
        {"n_instruites": cou.get("n_instruites"), "budget": cou.get("budget"),
         "cout": cou.get("cout_declare")}))

    ok_pop = all(pop.get(k) is not None
                 for k in ("fixture", "content_sha256", "point", "n_zone_grise"))
    entrees.append(_critere(
        "C9_POPULATION_DECLAREE", pop, _issue(ok_pop),
        {"fixture": pop.get("fixture"), "sha_fixture": pop.get("content_sha256"),
         "point": pop.get("point"), "n_zone_grise": pop.get("n_zone_grise"),
         "note_ecart": pop.get("note_ecart") or ""}))

    ident = det.get("identique")
    entrees.append(_critere(
        "C10_DETERMINISME", ident,
        _issue(None if ident is None else bool(ident)), {}))

    entrees.append(_critere(
        "C11_ANTERIORITE_DU_GEL", ant,
        _issue(None if ant.get("ok") is None else bool(ant.get("ok"))),
        {"commit_gel": ant.get("commit_gel"), "sha_fichier": ant.get("sha_fichier"),
         "commit_mesure": ant.get("commit_mesure"),
         "motif": ant.get("motif") or "clause non satisfaite"}))

    return entrees


def lis_verdict_contribution(mesures: dict) -> dict:
    """Le verdict d'ensemble, rendu par la grille GELÉE et par elle seule.

    La règle, posée d'avance :
      - un critère de PLOMBERIE, de PÉRIMÈTRE ou de PRUDENCE en échec (ou non évaluable)
        rend `NOT_CONCLUSIVE` — la mesure n'est pas lisible, donc on ne lit pas ;
      - sinon, `CONTRIBUTION_MESUREE` si et seulement si au moins une paire vraie a été
        restituée ET que les critères d'honnêteté sont satisfaits ;
      - sinon `CONTRIBUTION_NULLE`.

    Noter ce que cette règle NE fait PAS : elle ne compare le gain à aucun seuil minimal.
    Un gain d'une seule paire est une contribution mesurée, et sa petitesse est dite par la
    phrase (plafond, intervalle, valeur d'une paire), jamais par une requalification en
    « négligeable ». C'est le sens de O-S1.
    """
    criteres = evalue_criteres_contribution(mesures)
    bloquants = [c for c in criteres
                 if c["famille"] in ("plomberie", "perimetre", "prudence")
                 and c["issue"] != SATISFAIT]
    honnetete_en_echec = [c for c in criteres
                          if c["famille"] == "honnetete" and c["issue"] != SATISFAIT]

    pla = mesures.get("plafond") or {}
    eff = mesures.get("effets") or {}
    inc = mesures.get("incertitude") or {}
    pop = mesures.get("population") or {}
    gain = pla.get("gain_en_paires")
    bornes = inc.get("intervalle_rappel_apres") or ["n/d", "n/d"]

    valeurs = {
        "n_zone_grise": pla.get("n_zone_grise"), "plafond": pla.get("n_vraies_en_zone_grise"),
        "gain_en_paires": gain, "part_du_plafond": pla.get("part_du_plafond"),
        "point": pop.get("point"),
        "rappel_avant": eff.get("rappel_avant"), "rappel_apres": eff.get("rappel_apres"),
        "delta_rappel": eff.get("delta_rappel"),
        "f1_avant": eff.get("f1_avant"), "f1_apres": eff.get("f1_apres"),
        "delta_f1": eff.get("delta_f1"), "delta_precision": eff.get("delta_precision"),
        "niveau": NIVEAU_DE_CONFIANCE, "borne_basse": bornes[0], "borne_haute": bornes[1],
        "valeur_d_une_paire": inc.get("valeur_d_une_paire_en_rappel"),
    }

    if bloquants:
        statut = NOT_CONCLUSIVE
        cle = "VERDICT_NOT_CONCLUSIVE"
        valeurs = dict(valeurs, motif="; ".join(
            f"{c['code']}={c['issue']}" for c in bloquants))
    elif honnetete_en_echec:
        statut = NOT_CONCLUSIVE
        cle = "VERDICT_NOT_CONCLUSIVE"
        valeurs = dict(valeurs, motif="criteres d'honnetete non satisfaits : " + "; ".join(
            f"{c['code']}={c['issue']}" for c in honnetete_en_echec))
    elif isinstance(gain, int) and gain > 0:
        statut, cle = CONTRIBUTION_MESUREE, "VERDICT_CONTRIBUTION_MESUREE"
    else:
        statut, cle = CONTRIBUTION_NULLE, "VERDICT_CONTRIBUTION_NULLE"

    gabarit = ENONCES_CONTRIBUTION[cle]
    return {
        "statut": statut,
        "cle_enonce": cle,
        "enonce_retenu": gabarit,
        "enonce_rendu": gabarit.format_map(_Defaut(valeurs)),
        "criteres": criteres,
        "criteres_en_echec": sorted(c["code"] for c in criteres
                                    if c["issue"] != SATISFAIT),
        "sha256_criteres": sha256_criteres_contribution(),
    }
