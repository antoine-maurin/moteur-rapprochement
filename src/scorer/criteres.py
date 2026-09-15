"""Critères de lecture PRÉ-ENREGISTRÉS du verdict de discrimination (U-B5, mandat DISP-UB5-01 §4).

Ce fichier est **gelé** et committé SEUL, AVANT le commit qui exécute la moindre mesure :
git rend l'antériorité vérifiable par un tiers, et `sha256_criteres()` la rend citable dans
l'artefact. Aucun seuil ci-dessous n'est révisable après avoir vu un résultat. Si l'un se
révèle mal posé, on publie la mesure ET la critique du critère ; on ne réécrit pas le critère.

## Pourquoi pré-enregistrer
La question posée — « la donnée V1.2 exerce-t-elle réellement la décision 3 zones ? » — se
prête au plus banal des biais : regarder les chiffres, puis choisir la grille de lecture qui
en fait une belle histoire. Le seul remède est de fixer la grille d'abord. Le split
calibration/évaluation (`split.py`) protège du sur-ajustement d'un PARAMÈTRE ; il ne protège
pas du choix d'un CRITÈRE après coup. Les deux dispositifs couvrent des risques différents.

## Déclaration d'antériorité
Aucune mesure sur V1.2 n'a été consultée pour poser ces seuils. Une seule quantité mesurée
était exposée par le code gelé : `threshold_sizing` note dans sa docstring que, sous les
placeholders ±8 bits, la bande centrale contenait 2 paires sur 21 781 — sur la POPULATION DE
DÉMONSTRATION du générateur (400 entités), **pas** sur V1.2. Elle est déclarée ici pour que le
lecteur juge lui-même d'une éventuelle contamination ; aucun seuil ci-dessous n'en dérive.

## Anti-circularité (contrainte ARCHI, non négociable)
« Je mesure, le concepteur de données conçoit à l'aveugle. » La donnée n'est **jamais** ajustée
sur le résultat. Le corollaire est écrit ici AVANT la mesure, et c'est le dispositif
anti-circularité le plus fort du dispositif : **l'issue « le moteur est excellent » a déjà son
étiquette et sa phrase**, si bien qu'elle ne peut plus être requalifiée en défaut à corriger.

## Frontière CC1
Ce module n'importe rien de `src/engine/` ni de `src/generator/` — il ne connaît que des
nombres. Bibliothèque standard seulement (C7, offline strict).
"""
from __future__ import annotations

import hashlib
import os
from typing import Optional

__all__ = [
    "CRITERES", "ENONCES", "JUSTIFICATIONS", "SOCLE_DE_RESOLUTION",
    "sha256_criteres", "evalue_criteres", "lis_verdict",
]

# ===================================================================================
# SOCLE DE RÉSOLUTION — ce qu'un écart peut signifier, compte tenu de la taille du jeu
# ===================================================================================
#: Ce socle est commun à TOUS les seuils : aucun critère ne s'appuie sur un écart plus fin
#: que ce que le dénominateur permet de distinguer. Les valeurs viennent de la fixture telle
#: qu'elle se DÉCLARE (manifest), pas d'une mesure : 537 records, 271 vraies paires.
SOCLE_DE_RESOLUTION = {
    "n_vraies_paires_annonce": 271,
    "poids_d_une_vraie_paire_en_rappel": 1.0 / 271.0,     # ≈ 0,369 point
    "demi_largeur_wilson_95_a_0_97_sur_271": 0.020,
    "demi_largeur_wilson_95_a_0_995_sur_271": 0.008,
    "demi_largeur_wilson_95_sur_30": 0.18,
    "n_paires_possibles": 537 * 536 // 2,                 # 143 916
    "prevalence_absolue_approx": 271.0 / (537 * 536 / 2),  # ≈ 0,188 %
    "ancre_structurelle_empruntee": (
        "le manifest du pack annonce 7 vraies paires perdues au blocking DE SYNTH "
        "(plafond 264/271 ~ 0,9742). C'est le seul ordre de grandeur de paires "
        "structurellement dures disponible avant mesure ; il porte sur un AUTRE blocking "
        "que celui du moteur, et sert de repere, JAMAIS d'attendu"),
}

# ===================================================================================
# P0 — PRÉALABLE BLOQUANT
# ===================================================================================
#: Un Fellegi-Sunter non supervisé qui laisse passer plus d'une vraie paire sur deux sur une
#: fixture réaliste est plus probablement branché sur un espace d'identifiants décalé que
#: réellement mauvais. Le contrôle est DIAGNOSTIQUE (revalider la jointure), et non une
#: attente de performance : si la plomberie est saine, un chiffre bas est publié tel quel.
SEUIL_RAPPEL_PLOMBERIE = 0.50

# ===================================================================================
# (a) LE RAPPEL < 1,0 EST-IL CRÉDIBLE ?
# ===================================================================================
#: Une seule paire manquée sur 271 n'est pas un régime d'erreur mais un cas singulier : sa
#: disparition ne changerait pas le verdict, et sous 2 paires manquées on ne caractérise rien.
SEUIL_RAPPEL_SATURE = 0.995
#: 9 paires manquées, soit STRICTEMENT PLUS que les 7 que le manifest déclare structurellement
#: perdues au blocking de SYNTH : c'est le point à partir duquel le déficit ne s'explique plus
#: par la seule cause structurelle déjà connue et annoncée. C'est aussi le point où l'IC de
#: Wilson (±2 points) exclut confortablement 1,0. Deux contraintes indépendantes concordent —
#: ce n'est pas un chiffre rond choisi pour sa rondeur.
SEUIL_RAPPEL_EXERCE = 0.970

#: Plancher d'inspectabilité : 5 cas se lisent et se typent un à un, et c'est le plus petit
#: effectif dont une borne de Wilson inférieure exclut nettement zéro.
MIN_PAIRES_INSPECTABLES = 5
#: Point où l'une des deux causes de perte (blocking / décision) devient majoritaire. Règle
#: d'ATTRIBUTION, pas objectif : les deux causes restent rapportées séparément.
SEUIL_PART_BLOCKING = 0.50
#: Au-delà, le résidu inexpliqué (≤ 1 FN sur 10) relève du cas particulier et non d'un motif
#: de règle. Arbitraire assumé : sa vertu n'est pas d'être juste, c'est d'être FIXÉ d'avance.
SEUIL_FN_EXPLIQUES = 0.90
#: Au-delà, des paires FACILES sont manquées : anomalie de DÉCISION à instruire.
SEUIL_FN_FACILES = 0.20

#: Gardes anti-dégénérescence : un rappel élevé est trivial si l'on déclare tout MATCH, ou si
#: les vraies paires sont des doublons quasi exacts. Posées MAINTENANT, précisément pour
#: empêcher de célébrer plus tard un moteur qui dit oui à tout.
PRECISION_MIN_NON_DEGENERESCENCE = 0.50
TAUX_MATCH_MAX_NON_DEGENERESCENCE = 0.50
SEUIL_PART_VRAIES_CORROMPUES = 0.50

#: Critères compagnons sur la précision (contrôle de santé, non critère de verdict).
SEUIL_PRECISION_SATUREE = 0.99
SEUIL_PRECISION_EXERCEE = 0.95

# ===================================================================================
# (b) LA ZONE GRISE EST-ELLE NON TRIVIALE ?
# ===================================================================================
#: Sous 30, aucune proportion mesurée dans la bande n'a une demi-largeur de Wilson sous
#: ~18 points : la bande ne peut porter aucun énoncé quantitatif. 30 = un dixième du budget de
#: revue ; en deçà, le modèle de capacité qui fonde le budget perd son sens.
MIN_VOLUME_GRIS = 30
MIN_PART_GRIS = 0.001
#: Une bande contenant 0 ou 1 vraie paire ne porte pas de doute à instruire : un relecteur y
#: tamponnerait NON_MATCH. 2 % sépare « mixte » de « quelques traînards » — et non 5 %, qui
#: déclarerait TRIVIALE une bande de 300 contenant 10 vraies paires, soit 3,7 points de rappel.
MIN_EFFECTIF_MINORITAIRE = 5
MIN_PART_MINORITAIRE = 0.02
#: SEULE condition qui réponde LITTÉRALEMENT à la question posée. Si chaque valeur distincte
#: de R dans la bande est pure, un meilleur SEUIL — et non un humain, et non un LLM — résout
#: la bande : le doute est un artefact de PLACEMENT, pas un doute réel.
MIN_PART_PAIRES_MIXTES = 0.20
MIN_PLANCHER_BAYES_BANDE = 5
#: Résoudre parfaitement la bande doit déplacer le rappel d'au moins 2 points (l'ordre de
#: grandeur de l'IC de Wilson à ce dénominateur) et le F1 d'au moins 1 point (~ trois vraies
#: paires reclassées). En deçà, l'issue de la revue est opérationnellement indiscernable de
#: l'absence de revue : la bande est décorative QUELLE QUE SOIT sa taille.
MIN_RAPPEL_EN_JEU = 0.02
MIN_LARGEUR_F1 = 0.01
#: Sous 5 vraies paires dans la bande, l'erreur d'échantillonnage domine : rendre un nombre
#: ferait passer du bruit pour une mesure.
MIN_VRAIES_ZG_EVALUABLE = 5
#: Qualificateurs (non bloquants) de la NATURE du doute, lus sur l'AUC interne à la bande.
BORNES_DOUTE_IRREDUCTIBLE = (0.45, 0.55)
SEUIL_DOUTE_ORDONNE = 0.70

# ===================================================================================
# (c) SÉPARATION GLOBALE DES DISTRIBUTIONS
# ===================================================================================
#: Unité de lecture : `e = (1 - auc) * |M|` = nombre de vraies paires ÉQUIVALENTES entièrement
#: mal classées. Une vraie paire classée sous TOUTES les fausses coûte exactement 1/|M| d'AUC :
#: la conversion est EXACTE, pas analogique. C'est la seule forme dans laquelle « 0,999 » veut
#: dire quelque chose.
MAX_EQUIV_MAL_CLASSEES_SEPAREES = 0.5        # auc >= 0,9982 sur 271 vraies paires
MIN_EQUIV_MAL_CLASSEES_RECOUVREMENT = 3.0    # auc <= 0,9889 sur 271 vraies paires
OVL_SEPARE = 0.01
OVL_RECOUVREMENT = 0.05
PART_PLANCHER_BAYES_SEPARE = 0.005           # du nombre de paires candidates
PART_PLANCHER_BAYES_RECOUVREMENT = 0.02
AP_SATURE = 0.99

# ===================================================================================
# (d) ISSUE « MOTEUR EXCELLENT » — écrite AVANT la mesure
# ===================================================================================
#: Seuil de LISIBILITÉ, pas objectif : au-delà de 0,99 de F1 les erreurs résiduelles se
#: comptent sur les doigts et la conclusion opératoire ne change plus.
SEUIL_F1_EXCELLENT = 0.99

# ===================================================================================
# (e) DIAGNOSTIC SUPERVISÉ — seul chiffre contaminé, confiné au split
# ===================================================================================
#: Deux points de F1 : l'écart en deçà duquel préférer un seuil supervisé ne vaut pas la perte
#: d'indépendance qu'il coûte.
REGRET_MAX = 0.02

# ===================================================================================
# ÉNONCÉS PRÉ-ÉCRITS, VERBATIM ET SYMÉTRIQUES
# ===================================================================================
#: Chaque issue possible a SA phrase, écrite avant la mesure. Un test vérifie que tout
#: `enonce_retenu` d'un verdict appartient à `ENONCES.values()` : il est donc IMPOSSIBLE de
#: reformuler la lecture après avoir vu les chiffres. Les valeurs mesurées sont substituées
#: dans un champ SÉPARÉ (`enonce_rendu`), de sorte que le gabarit reste comparable au verbatim.
ENONCES = {
    # ---- (a) rappel -------------------------------------------------------------------
    "RAPPEL_EXERCE": (
        "Le moteur manque {n_manquees} vraies paires sur {n_vraies}, soit un rappel bout en "
        "bout de {rappel} (IC95 [{ic_bas}, {ic_haut}]). {n_perdues_blocking} sont perdues au "
        "blocking (plafond {plafond}), {n_manquees_decision} survivent au blocking sans etre "
        "declarees MATCH. Le rappel < 1,0 est credible et mesurable sur V1.2 ; la donnee "
        "exerce {ce_qui_est_exerce}."),
    "RAPPEL_SATURE": (
        "Le moteur retrouve toutes (ou toutes sauf une) les {n_vraies} vraies paires de V1.2, "
        "rappel bout en bout {rappel} (IC95 [{ic_bas}, {ic_haut}]), sur une population dont "
        "{part_corrompues} des vraies paires portent au moins une corruption. C'EST UN "
        "RESULTAT VRAI, PUBLIE TEL QUEL, ET NON UN DEFAUT A CORRIGER. Reserve, dans le meme "
        "paragraphe : un rappel sature signifie aussi que cette donnee n'exerce pas la borne "
        "haute du rappel ; c'est un enonce sur la DONNEE, qui borne ce que cette fixture peut "
        "demontrer. Aucune modification de la fixture n'est demandee ni suggeree ; la donnee "
        "n'est jamais ajustee sur le resultat."),
    "RAPPEL_NON_EVALUABLE": (
        "Le rappel n'est pas evaluable : {motif}. Aucune lecture n'est publiee sur cet axe."),
    "PLOMBERIE_SUSPECTE": (
        "Prealable P0 en echec : {motif}. Aucune lecture n'est publiee avant enquete — un "
        "chiffre issu d'une jointure douteuse n'est pas une mesure degradee, c'est un artefact."),
    "FN_EXPLIQUES": (
        "{part} des faux negatifs portent une cause materielle identifiee (perte au blocking, "
        "garde R-20, desaccords, champs absents, corruption annotee) : le rappel < 1 est "
        "imputable a la DONNEE, pas a la regle de decision. Aucune modification de la donnee "
        "n'en decoule."),
    "FN_INEXPLIQUES": (
        "Seuls {part} des faux negatifs portent une cause materielle identifiee : plus d'un "
        "sur dix reste INEXPLIQUE. Soupcon de defaut de MESURE (derivation des vraies paires, "
        "cle de paire, jointure) AVANT d'incriminer le moteur."),
    "FN_FACILES": (
        "{part} des faux negatifs se situent au-dessus de la mediane de R des vraies paires : "
        "des paires FACILES sont manquees, anomalie de DECISION a instruire."),
    "DEGENERESCENCE": (
        "Le rappel eleve n'est PAS declare significatif : la garde anti-degenerescence echoue "
        "({motif}). Un rappel obtenu en declarant tout MATCH, ou sur des doublons quasi exacts, "
        "ne mesure pas la discrimination."),
    # ---- (b) zone grise ---------------------------------------------------------------
    "ZONE_GRISE_NON_TRIVIALE": (
        "La zone grise contient {n_gris} paires, dont {n_vraies_gris} vraies et "
        "{n_fausses_gris} fausses ; {part_mixtes} d'entre elles reposent sur une valeur de R "
        "ou les deux classes coexistent, et aucune regle lisant R seul ne peut en trancher au "
        "moins {plancher}. Une resolution parfaite de la bande porterait le rappel bout en "
        "bout de {rappel_pess} a {rappel_opt} et le F1 de {largeur_f1} point(s). IL EXISTE SUR "
        "V1.2 UN DOUTE QUE LE SCORE SEUL NE TRANCHE PAS ; U-B3 a matiere a instruire, et cet "
        "ecart est sa cible mesurable."),
    "ZONE_GRISE_TRIVIALE": (
        "La bande dimensionnee par budget contient {n_gris} paires, dont {n_vraies_gris} "
        "vraies. Condition en echec : {condition_echouee} ({valeur} contre {seuil} exige) ; "
        "classe dominante : {classe_dominante}. SUR V1.2, LE SCORE SEUL TRANCHE CE QUE LA "
        "BANDE CONTIENT : l'instruction du doute n'a pas de matiere mesurable sur ce jeu. "
        "C'est une mesure, pas un defaut de la fixture. Aucune modification de la donnee n'est "
        "demandee ; les seuls leviers examinables sont de mon cote (placement des seuils, "
        "definition de la bande) et relevent d'un arbitrage, pas de cette mesure."),
    "DOUTE_IRREDUCTIBLE": (
        "AUC interne a la bande = {auc} : R n'ordonne plus les classes dans la bande. Une "
        "revue qui regarde autre chose que R a de la place."),
    "DOUTE_RESIDUELLEMENT_ORDONNE": (
        "AUC interne a la bande = {auc} : R ordonne encore les classes dans la bande. La bande "
        "est placee conservativement ; une part du doute est artificielle et un meilleur seuil "
        "la trancherait."),
    "DOUTE_SANS_QUALIFICATIF": (
        "AUC interne a la bande = {auc} : publiee sans qualificatif (entre les deux regimes)."),
    "DOUTE_NON_EVALUABLE": (
        "La nature du doute n'est pas evaluable : {motif}. Rendre un nombre ferait passer du "
        "bruit pour une mesure."),
    # ---- (c) séparation ---------------------------------------------------------------
    "DISTRIBUTIONS_SEPAREES": (
        "Les distributions de R des vraies et des fausses paires sont LARGEMENT SEPAREES "
        "(auc = {auc}, soit {equiv} paire(s) equivalente(s) mal classee(s) sur {n_vraies} ; "
        "ovl = {ovl}). Sur cette donnee, la decision 3 zones n'est pas exercee."),
    "SUPPORTS_DISJOINTS": (
        "La marge de separation vaut {marge} > 0 : les supports de R sont disjoints, un seuil "
        "unique separe parfaitement les deux classes sur V1.2."),
    "RECOUVREMENT_SUBSTANTIEL": (
        "R est faiblement discriminant sur cette donnee (auc = {auc}, ovl = {ovl}) : le "
        "recouvrement est localise en {plage}, et la zone grise porte un enjeu reel."),
    "RECOUVREMENT_MARGINAL": (
        "Separation forte mais non totale (auc = {auc}, ovl = {ovl}) ; le recouvrement "
        "residuel est localise en {plage}, a confronter au placement des seuils."),
    # ---- (d) moteur excellent ---------------------------------------------------------
    "MOTEUR_EXCELLENT_RESULTAT_A_PUBLIER": (
        "Sur cette donnee realiste, le moteur tranche presque tout correctement (F1 = {f1}, "
        "precision = {precision}, rappel = {rappel}). C'EST UN RESULTAT VRAI A PUBLIER, PAS UN "
        "DEFAUT A CORRIGER."),
    # ---- (e) diagnostic supervisé -----------------------------------------------------
    "SANS_REGRET_NOTABLE": (
        "Le placement non supervise des seuils est sans regret notable : F1 d'evaluation "
        "{f1_non_supervise} contre {f1_oracle} au seuil calibre, regret {regret} <= "
        "{regret_max}. Valeur NON REINJECTABLE dans le moteur."),
    "REGRET_NOTABLE": (
        "Le placement non supervise laisse un regret de {regret} points de F1 sur l'evaluation "
        "({f1_non_supervise} contre {f1_oracle} au seuil calibre sur un jeu DISJOINT). Chiffre "
        "DIAGNOSTIQUE et NON REINJECTABLE : aucune ligne de code ne le passe au moteur."),
    "REGRET_NON_EVALUABLE": (
        "Le regret du placement non supervise n'est pas evaluable : {motif}."),
}

#: Fondement de chaque seuil, publié à côté de lui pour qu'un lecteur puisse le contester
#: sans avoir à deviner d'où il sort.
JUSTIFICATIONS = {
    "SEUIL_RAPPEL_PLOMBERIE": (
        "diagnostique, non une attente de performance : sous 0,50 la jointure est plus "
        "suspecte que le moteur"),
    "SEUIL_RAPPEL_SATURE": "1 paire manquee sur 271 est un cas singulier, pas un regime d'erreur",
    "SEUIL_RAPPEL_EXERCE": (
        "9 paires manquees = strictement plus que les 7 perdues structurellement annoncees ; "
        "coincide avec l'exclusion de 1,0 par l'IC de Wilson"),
    "MIN_PAIRES_INSPECTABLES": "plancher d'inspectabilite : 5 cas se lisent un a un",
    "SEUIL_PART_BLOCKING": "point ou l'une des deux causes de perte devient majoritaire",
    "SEUIL_FN_EXPLIQUES": "au-dela, le residu releve du cas particulier, non d'un motif de regle",
    "SEUIL_FN_FACILES": "au-dela, des paires faciles sont manquees : anomalie de decision",
    "MIN_VOLUME_GRIS": "sous 30, aucune proportion de la bande n'a une demi-largeur < ~18 points",
    "MIN_EFFECTIF_MINORITAIRE": "plancher d'inspectabilite de la classe minoritaire",
    "MIN_PART_MINORITAIRE": "2 % separe 'mixte' de 'quelques trainards' ; 5 % masquerait 3,7 pts de rappel",
    "MIN_PART_PAIRES_MIXTES": "seule condition repondant litteralement a 'le score seul tranche-t-il ?'",
    "MIN_PLANCHER_BAYES_BANDE": "nombre minimal d'erreurs irreductibles pour qu'une revue ait une cible",
    "MIN_RAPPEL_EN_JEU": "2 points de rappel = l'ordre de grandeur de l'IC de Wilson a ce denominateur",
    "MIN_LARGEUR_F1": "1 point de F1 ~ trois vraies paires reclassees",
    "MAX_EQUIV_MAL_CLASSEES_SEPAREES": "moins d'une demi-paire equivalente mal classee sur 271",
    "MIN_EQUIV_MAL_CLASSEES_RECOUVREMENT": "trois paires equivalentes mal classees : regime caracterisable",
    "SEUIL_F1_EXCELLENT": "seuil de LISIBILITE : au-dela, la conclusion operatoire ne change plus",
    "REGRET_MAX": "2 points de F1 : en deca, l'independance vaut plus que le gain",
}

#: Inventaire FERMÉ des critères émis. Un test compare, DANS LES DEUX SENS, l'ensemble des
#: codes réellement émis à cette liste : ni critère muet, ni critère surnuméraire.
CRITERES = {
    "P0_PLOMBERIE": {
        "enonce_du_critere": "integrite de la jointure et rappel minimal de plomberie",
        "seuil": SEUIL_RAPPEL_PLOMBERIE,
        "axe": "prealable",
    },
    "A1_RAPPEL": {
        "enonce_du_critere": "le rappel < 1,0 est-il credible ? (bandes SATURE / EXERCE_FAIBLEMENT / EXERCE)",
        "seuil": {"sature": SEUIL_RAPPEL_SATURE, "exerce": SEUIL_RAPPEL_EXERCE},
        "axe": "decision",
    },
    "A2_ATTRIBUTION": {
        "enonce_du_critere": "ou le rappel se perd-il : blocking, decision, ou ni l'un ni l'autre ?",
        "seuil": {"inspectables": MIN_PAIRES_INSPECTABLES, "part_blocking": SEUIL_PART_BLOCKING},
        "axe": "blocking",
    },
    "A3_FN_EXPLIQUES": {
        "enonce_du_critere": "les faux negatifs portent-ils une cause materielle identifiee ?",
        "seuil": SEUIL_FN_EXPLIQUES,
        "axe": "decision",
    },
    "A4_FN_FACILES": {
        "enonce_du_critere": "des paires faciles sont-elles manquees ? (anti-vacuite de la difficulte)",
        "seuil": SEUIL_FN_FACILES,
        "axe": "decision",
    },
    "A5_DEGENERESCENCE": {
        "enonce_du_critere": "un rappel eleve est-il obtenu autrement qu'en declarant tout MATCH ?",
        "seuil": {"precision": PRECISION_MIN_NON_DEGENERESCENCE,
                  "taux_match": TAUX_MATCH_MAX_NON_DEGENERESCENCE,
                  "part_corrompues": SEUIL_PART_VRAIES_CORROMPUES},
        "axe": "decision",
    },
    "B1_VOLUME": {
        "enonce_du_critere": "Z1 volume de la zone grise (NECESSAIRE, jamais probant : la taille est un parametre)",
        "seuil": {"n": MIN_VOLUME_GRIS, "part": MIN_PART_GRIS},
        "axe": "doute",
    },
    "B2_MIXITE": {
        "enonce_du_critere": "Z2 la bande contient-elle les deux classes en effectif inspectable ?",
        "seuil": {"effectif": MIN_EFFECTIF_MINORITAIRE, "part": MIN_PART_MINORITAIRE},
        "axe": "doute",
    },
    "B3_IRREDUCTIBILITE": {
        "enonce_du_critere": "Z3 le doute est-il irreductible au score seul ? (SEULE condition litterale)",
        "seuil": {"part_mixtes": MIN_PART_PAIRES_MIXTES, "plancher": MIN_PLANCHER_BAYES_BANDE},
        "axe": "doute",
    },
    "B4_ENJEU": {
        "enonce_du_critere": "Z4 resoudre la bande deplacerait-il quelque chose de mesurable ?",
        "seuil": {"rappel_en_jeu": MIN_RAPPEL_EN_JEU, "largeur_f1": MIN_LARGEUR_F1},
        "axe": "doute",
    },
    "B5_NATURE_DU_DOUTE": {
        "enonce_du_critere": "nature du doute dans la bande (qualificateur NON bloquant)",
        "seuil": {"irreductible": list(BORNES_DOUTE_IRREDUCTIBLE), "ordonne": SEUIL_DOUTE_ORDONNE},
        "axe": "doute",
    },
    "C1_SEPARATION": {
        "enonce_du_critere": "les distributions de R des vraies et des fausses paires se recouvrent-elles ?",
        "seuil": {"separees_equiv": MAX_EQUIV_MAL_CLASSEES_SEPAREES,
                  "recouvrement_equiv": MIN_EQUIV_MAL_CLASSEES_RECOUVREMENT,
                  "ovl_separe": OVL_SEPARE, "ovl_recouvrement": OVL_RECOUVREMENT},
        "axe": "separation",
    },
    "D1_MOTEUR_EXCELLENT": {
        "enonce_du_critere": "issue 'moteur excellent sur donnee realiste' (ecrite AVANT la mesure)",
        "seuil": SEUIL_F1_EXCELLENT,
        "axe": "decision",
    },
    "E1_REGRET": {
        "enonce_du_critere": "le placement non supervise des seuils laisse-t-il un regret notable ?",
        "seuil": REGRET_MAX,
        "axe": "separation",
    },
}


def sha256_criteres(chemin: Optional[str] = None) -> str:
    """Empreinte des OCTETS de ce fichier — la preuve citable de ce qui a été gelé.

    Recopiée dans l'artefact à côté du SHA du commit de gel : les deux ensemble rendent
    l'antériorité vérifiable par un tiers qui n'a que le dépôt et l'artefact.
    """
    with open(chemin or os.path.abspath(__file__), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _fini(x) -> bool:
    """Vrai si `x` est un nombre exploitable (ni None, ni NaN, ni infini)."""
    if x is None or isinstance(x, bool):
        return False
    if not isinstance(x, (int, float)):
        return False
    return x == x and x not in (float("inf"), float("-inf"))


def _critere(code: str, valeur_observee, issue: str, cle_enonce: Optional[str] = None,
            valeurs: Optional[dict] = None) -> dict:
    """Une entrée de verdict : le critère, son seuil, ce qui a été observé, l'issue.

    `enonce_retenu` porte le GABARIT verbatim (comparable à `ENONCES`), `enonce_rendu` la
    phrase avec ses valeurs substituées. Les séparer est ce qui rend le pré-enregistrement
    vérifiable : le gabarit n'a pas pu être réécrit après coup.
    """
    entree = {
        "code": code,
        "enonce_du_critere": CRITERES[code]["enonce_du_critere"],
        "axe": CRITERES[code]["axe"],
        "seuil": CRITERES[code]["seuil"],
        "valeur_observee": valeur_observee,
        "issue": issue,
    }
    if cle_enonce is not None:
        gabarit = ENONCES[cle_enonce]
        entree["cle_enonce"] = cle_enonce
        entree["enonce_retenu"] = gabarit
        entree["enonce_rendu"] = gabarit.format(**(valeurs or {}))
    return entree


def evalue_criteres(mesures: dict) -> list:
    """Applique les critères gelés aux mesures. Retourne une entrée PAR critère déclaré.

    Chaque critère est publié avec son seuil, sa valeur observée et son issue **même quand il
    est satisfait** : un verdict qui ne montrerait que les critères en échec laisserait croire
    que les autres n'ont pas été regardés.

    `mesures` est un dict plat dont le contrat est documenté dans `rapport.py`. Toute valeur
    absente ou non finie donne l'issue `NON_EVALUABLE` — jamais une valeur de remplacement
    commode, qui ferait passer une absence de mesure pour une mesure.
    """
    sortie = []
    n_vraies = mesures.get("n_vraies_paires") or 0

    # ---------------- P0 : préalable bloquant ----------------------------------------
    alerte = bool(mesures.get("alerte_plomberie"))
    rappel = mesures.get("rappel_bout_en_bout")
    if alerte:
        motif = mesures.get("motif_plomberie") or "incoherence d'integrite detectee"
        sortie.append(_critere("P0_PLOMBERIE", {"alerte_plomberie": True, "rappel": rappel},
                               "ECHEC", "PLOMBERIE_SUSPECTE", {"motif": motif}))
    elif not _fini(rappel):
        sortie.append(_critere("P0_PLOMBERIE", {"alerte_plomberie": False, "rappel": rappel},
                               "NON_EVALUABLE", "PLOMBERIE_SUSPECTE",
                               {"motif": "rappel non defini (aucune vraie paire ?)"}))
    elif rappel < SEUIL_RAPPEL_PLOMBERIE:
        sortie.append(_critere("P0_PLOMBERIE", {"alerte_plomberie": False, "rappel": rappel},
                               "ECHEC", "PLOMBERIE_SUSPECTE",
                               {"motif": "rappel %.6g < %.2f : jointure a revalider avant "
                                         "toute lecture" % (rappel, SEUIL_RAPPEL_PLOMBERIE)}))
    else:
        sortie.append(_critere("P0_PLOMBERIE", {"alerte_plomberie": False, "rappel": rappel},
                               "SATISFAIT"))

    # ---------------- (a) A1 : le rappel < 1,0 est-il crédible ? ----------------------
    ic = mesures.get("ic_wilson_rappel") or [None, None]
    n_perdues = mesures.get("n_perdues_blocking")
    n_dec = mesures.get("n_manquees_decision")
    if not _fini(rappel) or not n_vraies:
        sortie.append(_critere("A1_RAPPEL", rappel, "NON_EVALUABLE", "RAPPEL_NON_EVALUABLE",
                               {"motif": "rappel ou nombre de vraies paires indisponible"}))
        bande = "NON_EVALUABLE"
    elif rappel >= SEUIL_RAPPEL_SATURE:
        bande = "SATURE"
        part_c = mesures.get("part_vraies_paires_corrompues")
        sortie.append(_critere("A1_RAPPEL", rappel, bande, "RAPPEL_SATURE", {
            "n_vraies": n_vraies, "rappel": _f(rappel),
            "ic_bas": _f(ic[0]), "ic_haut": _f(ic[1]),
            "part_corrompues": _pct(part_c)}))
    else:
        bande = "EXERCE_FAIBLEMENT" if rappel >= SEUIL_RAPPEL_EXERCE else "EXERCE"
        n_manquees = n_vraies - (mesures.get("tp") or 0)
        exerce = _ce_qui_est_exerce(n_perdues, n_dec)
        sortie.append(_critere("A1_RAPPEL", rappel, bande, "RAPPEL_EXERCE", {
            "n_manquees": n_manquees, "n_vraies": n_vraies, "rappel": _f(rappel),
            "ic_bas": _f(ic[0]), "ic_haut": _f(ic[1]),
            "n_perdues_blocking": _i(n_perdues), "plafond": _f(mesures.get("rappel_blocking")),
            "n_manquees_decision": _i(n_dec), "ce_qui_est_exerce": exerce}))

    # ---------------- (a) A2 : attribution de la perte -------------------------------
    if n_perdues is None or n_dec is None:
        sortie.append(_critere("A2_ATTRIBUTION", None, "NON_EVALUABLE"))
    else:
        if n_dec >= MIN_PAIRES_INSPECTABLES:
            issue = "LA_DECISION_EST_EXERCEE"
        elif n_perdues >= MIN_PAIRES_INSPECTABLES:
            issue = "SEUL_LE_BLOCKING_EST_EXERCE"
        else:
            issue = "NI_L_UN_NI_L_AUTRE_N_EST_EXERCE"
        part = None
        if _fini(rappel) and rappel < 1.0 and _fini(mesures.get("rappel_blocking")):
            part = (1.0 - mesures["rappel_blocking"]) / (1.0 - rappel)
        sortie.append(_critere("A2_ATTRIBUTION",
                               {"n_perdues_blocking": n_perdues, "n_manquees_decision": n_dec,
                                "part_imputable_au_blocking": part}, issue))

    # ---------------- (a) A3 : les FN sont-ils expliqués ? ---------------------------
    part_exp = mesures.get("part_fn_expliques")
    if not _fini(part_exp):
        sortie.append(_critere("A3_FN_EXPLIQUES", part_exp, "NON_EVALUABLE"))
    elif part_exp >= SEUIL_FN_EXPLIQUES:
        sortie.append(_critere("A3_FN_EXPLIQUES", part_exp, "SATISFAIT", "FN_EXPLIQUES",
                               {"part": _pct(part_exp)}))
    else:
        sortie.append(_critere("A3_FN_EXPLIQUES", part_exp, "ECHEC", "FN_INEXPLIQUES",
                               {"part": _pct(part_exp)}))

    # ---------------- (a) A4 : anti-vacuité de la difficulté -------------------------
    part_fac = mesures.get("part_fn_au_dessus_de_la_mediane_des_vraies")
    if not _fini(part_fac):
        sortie.append(_critere("A4_FN_FACILES", part_fac, "NON_EVALUABLE"))
    elif part_fac > SEUIL_FN_FACILES:
        sortie.append(_critere("A4_FN_FACILES", part_fac, "SIGNAL", "FN_FACILES",
                               {"part": _pct(part_fac)}))
    else:
        sortie.append(_critere("A4_FN_FACILES", part_fac, "SATISFAIT"))

    # ---------------- (a) A5 : garde anti-dégénérescence -----------------------------
    prec = mesures.get("precision")
    taux_match = mesures.get("taux_match")
    part_cor = mesures.get("part_vraies_paires_corrompues")
    non_trivial = bool(mesures.get("au_moins_une_vraie_paire_non_triviale"))
    observe_a5 = {"precision": prec, "taux_match": taux_match,
                  "part_vraies_paires_corrompues": part_cor,
                  "au_moins_une_vraie_paire_non_triviale": non_trivial}
    manquants = [k for k, v in (("precision", prec), ("taux_match", taux_match),
                                ("part_vraies_paires_corrompues", part_cor)) if not _fini(v)]
    if manquants:
        sortie.append(_critere("A5_DEGENERESCENCE", observe_a5, "NON_EVALUABLE"))
        a5_ok = False
    else:
        echecs = []
        if prec < PRECISION_MIN_NON_DEGENERESCENCE:
            echecs.append("precision %.6g < %.2f" % (prec, PRECISION_MIN_NON_DEGENERESCENCE))
        if taux_match >= TAUX_MATCH_MAX_NON_DEGENERESCENCE:
            echecs.append("taux de MATCH %.6g >= %.2f" % (taux_match, TAUX_MATCH_MAX_NON_DEGENERESCENCE))
        if part_cor < SEUIL_PART_VRAIES_CORROMPUES:
            echecs.append("part de vraies paires corrompues %.6g < %.2f"
                          % (part_cor, SEUIL_PART_VRAIES_CORROMPUES))
        if not non_trivial:
            echecs.append("aucune vraie paire ne porte 2 composantes non-ACCORD_FORT")
        a5_ok = not echecs
        if a5_ok:
            sortie.append(_critere("A5_DEGENERESCENCE", observe_a5, "SATISFAIT"))
        else:
            sortie.append(_critere("A5_DEGENERESCENCE", observe_a5, "ECHEC", "DEGENERESCENCE",
                                   {"motif": " ; ".join(echecs)}))

    # ---------------- (b) Z1..Z4 : la zone grise est-elle non triviale ? -------------
    n_gris = mesures.get("n_gris")
    part_gris = mesures.get("part_gris")
    gv = mesures.get("n_vraies_gris")
    gf = mesures.get("n_fausses_gris")
    part_min = mesures.get("part_minoritaire")
    part_mix = mesures.get("part_paires_mixtes")
    plancher_bande = mesures.get("plancher_bayes_bande")
    rappel_en_jeu = mesures.get("rappel_en_jeu")
    largeur_f1 = mesures.get("largeur_intervalle_f1")

    z1 = _fini(n_gris) and _fini(part_gris) and n_gris >= MIN_VOLUME_GRIS and part_gris >= MIN_PART_GRIS
    sortie.append(_critere("B1_VOLUME", {"n_gris": n_gris, "part_gris": part_gris},
                           "SATISFAIT" if z1 else ("ECHEC" if _fini(n_gris) else "NON_EVALUABLE")))

    z2 = (_fini(gv) and _fini(gf) and _fini(part_min)
          and min(gv, gf) >= MIN_EFFECTIF_MINORITAIRE and part_min >= MIN_PART_MINORITAIRE)
    sortie.append(_critere("B2_MIXITE",
                           {"n_vraies_gris": gv, "n_fausses_gris": gf, "part_minoritaire": part_min},
                           "SATISFAIT" if z2 else ("ECHEC" if _fini(gv) else "NON_EVALUABLE")))

    z3 = ((_fini(part_mix) and part_mix >= MIN_PART_PAIRES_MIXTES)
          or (_fini(plancher_bande) and plancher_bande >= MIN_PLANCHER_BAYES_BANDE))
    sortie.append(_critere("B3_IRREDUCTIBILITE",
                           {"part_paires_mixtes": part_mix, "plancher_bayes_bande": plancher_bande},
                           "SATISFAIT" if z3 else ("ECHEC" if _fini(part_mix) or _fini(plancher_bande)
                                                   else "NON_EVALUABLE")))

    z4 = (_fini(rappel_en_jeu) and _fini(largeur_f1)
          and rappel_en_jeu >= MIN_RAPPEL_EN_JEU and largeur_f1 >= MIN_LARGEUR_F1)
    sortie.append(_critere("B4_ENJEU",
                           {"rappel_en_jeu": rappel_en_jeu, "largeur_intervalle_f1": largeur_f1},
                           "SATISFAIT" if z4 else ("ECHEC" if _fini(rappel_en_jeu) else "NON_EVALUABLE")))

    # Le verdict de bande est CONJONCTIF : chacune des quatre conditions seule est un faux
    # positif classique. La phrase retenue est portée par B3 (la condition littérale) quand
    # tout passe, et par la PREMIÈRE condition en échec sinon — nommée, avec son chiffre.
    if z1 and z2 and z3 and z4:
        rappel_opt = mesures.get("rappel_optimiste")
        rappel_pess = mesures.get("rappel_pessimiste")
        sortie[-1] = _critere("B4_ENJEU",
                              {"rappel_en_jeu": rappel_en_jeu, "largeur_intervalle_f1": largeur_f1},
                              "SATISFAIT", "ZONE_GRISE_NON_TRIVIALE", {
                                  "n_gris": _i(n_gris), "n_vraies_gris": _i(gv),
                                  "n_fausses_gris": _i(gf), "part_mixtes": _pct(part_mix),
                                  "plancher": _i(plancher_bande),
                                  "rappel_pess": _f(rappel_pess), "rappel_opt": _f(rappel_opt),
                                  "largeur_f1": _f(largeur_f1)})
    else:
        echouee, valeur, seuil = _premiere_condition_echouee(
            [("Z1 volume", z1, n_gris, MIN_VOLUME_GRIS),
             ("Z2 mixite", z2, part_min, MIN_PART_MINORITAIRE),
             ("Z3 irreductibilite au score seul", z3, part_mix, MIN_PART_PAIRES_MIXTES),
             ("Z4 enjeu", z4, largeur_f1, MIN_LARGEUR_F1)])
        dominante = "indeterminee"
        if _fini(gv) and _fini(gf):
            dominante = "fausses" if gf > gv else ("vraies" if gv > gf else "a egalite")
        sortie[-1] = _critere("B4_ENJEU",
                              {"rappel_en_jeu": rappel_en_jeu, "largeur_intervalle_f1": largeur_f1},
                              "ECHEC" if _fini(n_gris) else "NON_EVALUABLE",
                              "ZONE_GRISE_TRIVIALE", {
                                  "n_gris": _i(n_gris), "n_vraies_gris": _i(gv),
                                  "condition_echouee": echouee, "valeur": _f(valeur),
                                  "seuil": _f(seuil), "classe_dominante": dominante})

    # ---------------- (b) B5 : nature du doute (qualificateur non bloquant) ----------
    auc_zg = mesures.get("auc_dans_la_zone_grise")
    if not _fini(auc_zg):
        sortie.append(_critere("B5_NATURE_DU_DOUTE", auc_zg, "NON_EVALUABLE",
                               "DOUTE_NON_EVALUABLE",
                               {"motif": mesures.get("motif_auc_zone_grise")
                                or "moins de %d vraies paires dans la bande, ou aucune fausse"
                                   % MIN_VRAIES_ZG_EVALUABLE}))
    elif BORNES_DOUTE_IRREDUCTIBLE[0] <= auc_zg <= BORNES_DOUTE_IRREDUCTIBLE[1]:
        sortie.append(_critere("B5_NATURE_DU_DOUTE", auc_zg, "DOUTE_IRREDUCTIBLE",
                               "DOUTE_IRREDUCTIBLE", {"auc": _f(auc_zg)}))
    elif auc_zg > SEUIL_DOUTE_ORDONNE:
        sortie.append(_critere("B5_NATURE_DU_DOUTE", auc_zg, "DOUTE_RESIDUELLEMENT_ORDONNE",
                               "DOUTE_RESIDUELLEMENT_ORDONNE", {"auc": _f(auc_zg)}))
    else:
        sortie.append(_critere("B5_NATURE_DU_DOUTE", auc_zg, "SANS_QUALIFICATIF",
                               "DOUTE_SANS_QUALIFICATIF", {"auc": _f(auc_zg)}))

    # ---------------- (c) C1 : séparation globale ------------------------------------
    auc = mesures.get("auc")
    ovl = mesures.get("ovl")
    marge = mesures.get("marge_de_separation")
    equiv = (1.0 - auc) * n_vraies if (_fini(auc) and n_vraies) else None
    observe_c1 = {"auc": auc, "ovl": ovl, "paires_vraies_equivalentes_mal_classees": equiv,
                  "marge_de_separation": marge,
                  "plancher_bayes_r": mesures.get("plancher_bayes_r")}
    if not _fini(equiv):
        sortie.append(_critere("C1_SEPARATION", observe_c1, "NON_EVALUABLE"))
    elif _fini(marge) and marge > 0:
        sortie.append(_critere("C1_SEPARATION", observe_c1, "SUPPORTS_DISJOINTS",
                               "SUPPORTS_DISJOINTS", {"marge": _f(marge)}))
    elif equiv < MAX_EQUIV_MAL_CLASSEES_SEPAREES:
        sortie.append(_critere("C1_SEPARATION", observe_c1, "LARGEMENT_SEPAREES",
                               "DISTRIBUTIONS_SEPAREES",
                               {"auc": _f(auc), "equiv": _f(equiv), "n_vraies": n_vraies,
                                "ovl": _f(ovl)}))
    elif equiv >= MIN_EQUIV_MAL_CLASSEES_RECOUVREMENT:
        sortie.append(_critere("C1_SEPARATION", observe_c1, "RECOUVREMENT_SUBSTANTIEL",
                               "RECOUVREMENT_SUBSTANTIEL",
                               {"auc": _f(auc), "ovl": _f(ovl),
                                "plage": mesures.get("plage_commune")}))
    else:
        sortie.append(_critere("C1_SEPARATION", observe_c1, "RECOUVREMENT_MARGINAL",
                               "RECOUVREMENT_MARGINAL",
                               {"auc": _f(auc), "ovl": _f(ovl),
                                "plage": mesures.get("plage_commune")}))

    # ---------------- (d) D1 : issue « moteur excellent » ----------------------------
    f1 = mesures.get("f1_bout_en_bout")
    zone_triviale = not (z1 and z2 and z3 and z4)
    observe_d1 = {"f1_bout_en_bout": f1, "garde_anti_degenerescence": a5_ok,
                  "zone_grise_triviale": zone_triviale}
    if not _fini(f1):
        sortie.append(_critere("D1_MOTEUR_EXCELLENT", observe_d1, "NON_EVALUABLE"))
    elif f1 >= SEUIL_F1_EXCELLENT and a5_ok and zone_triviale:
        sortie.append(_critere("D1_MOTEUR_EXCELLENT", observe_d1,
                               "MOTEUR_EXCELLENT_RESULTAT_A_PUBLIER",
                               "MOTEUR_EXCELLENT_RESULTAT_A_PUBLIER",
                               {"f1": _f(f1), "precision": _f(prec), "rappel": _f(rappel)}))
    else:
        sortie.append(_critere("D1_MOTEUR_EXCELLENT", observe_d1, "NON_ATTEINTE"))

    # ---------------- (e) E1 : regret du placement non supervisé ---------------------
    f1_ns = mesures.get("f1_evaluation_non_supervise")
    f1_or = mesures.get("f1_evaluation_oracle")
    if not (_fini(f1_ns) and _fini(f1_or)):
        sortie.append(_critere("E1_REGRET", {"f1_non_supervise": f1_ns, "f1_oracle": f1_or},
                               "NON_EVALUABLE", "REGRET_NON_EVALUABLE",
                               {"motif": mesures.get("motif_regret")
                                or "F1 d'evaluation indisponible sur l'un des deux placements"}))
    else:
        regret = f1_or - f1_ns
        observe_e1 = {"f1_non_supervise": f1_ns, "f1_oracle": f1_or, "regret": regret}
        if regret <= REGRET_MAX:
            sortie.append(_critere("E1_REGRET", observe_e1, "SANS_REGRET_NOTABLE",
                                   "SANS_REGRET_NOTABLE",
                                   {"f1_non_supervise": _f(f1_ns), "f1_oracle": _f(f1_or),
                                    "regret": _f(regret), "regret_max": REGRET_MAX}))
        else:
            sortie.append(_critere("E1_REGRET", observe_e1, "REGRET_NOTABLE", "REGRET_NOTABLE",
                                   {"regret": _f(regret), "f1_non_supervise": _f(f1_ns),
                                    "f1_oracle": _f(f1_or)}))
    return sortie


def lis_verdict(mesures: dict) -> dict:
    """Verdict complet : un TRIPLET indépendant, jamais un jugement unique.

    Trois questions distinctes — (1) le BLOCKING est-il exercé ? (2) la DÉCISION est-elle
    exercée ? (3) le DOUTE est-il exercé ? Un jeu peut exercer le blocking sans exercer la
    décision, ou l'inverse ; écraser les trois en un mot ferait perdre l'information que la
    mesure a produite. `aucune_recommandation_sur_la_donnee` est posé en dur : ce verdict,
    quelle que soit son issue, n'a jamais la donnée pour destinataire.
    """
    criteres = evalue_criteres(mesures)
    par_code = {c["code"]: c for c in criteres}

    p0 = par_code["P0_PLOMBERIE"]["issue"]
    bande = par_code["A1_RAPPEL"]["issue"]
    attribution = par_code["A2_ATTRIBUTION"]["issue"]
    zone = all(par_code[c]["issue"] == "SATISFAIT"
               for c in ("B1_VOLUME", "B2_MIXITE", "B3_IRREDUCTIBILITE", "B4_ENJEU"))

    if p0 in ("ECHEC", "NON_EVALUABLE"):
        statut = "NOT_CONCLUSIVE"
    elif not mesures.get("n_vraies_paires") or not mesures.get("n_vraies_paires_candidates"):
        statut = "NON_EVALUABLE"
    else:
        statut = "MESURE"

    triplet = {
        "blocking_exerce": attribution in ("SEUL_LE_BLOCKING_EST_EXERCE", "LA_DECISION_EST_EXERCEE")
                           and (mesures.get("n_perdues_blocking") or 0) >= MIN_PAIRES_INSPECTABLES,
        "decision_exercee": bande in ("EXERCE", "EXERCE_FAIBLEMENT"),
        "doute_exerce": zone,
    }
    return {
        "statut": statut,
        "criteres": criteres,
        "triplet": triplet,
        "lecture_globale": _lecture_globale(triplet, statut),
        "enonces_pre_enregistres_utilises": sorted(
            {c["cle_enonce"] for c in criteres if "cle_enonce" in c}),
        "sha256_criteres": sha256_criteres(),
        "aucune_recommandation_sur_la_donnee": True,
        "note_anti_tautologie": (
            "La TAILLE de la zone grise (n_gris ~ budget) est un PARAMETRE du dimensionnement, "
            "pas une mesure : elle ne compte comme preuve de rien. Seule Z3 repond "
            "litteralement a 'le score seul tranche-t-il ?'."),
        "note_non_revision": (
            "Aucun critere n'est reecrit apres lecture des mesures. Si l'un s'avere mal pose, "
            "il est CONSERVE, son verdict est publie, et la critique est ajoutee dans "
            "'limites' — a cote du verdict qu'elle conteste, jamais a sa place."),
    }


# ---------------------- présentateurs (formatage, aucune décision) --------------------
def _f(x) -> str:
    """Nombre lisible dans une phrase, ou `n/d` s'il n'est pas mesurable."""
    return "n/d" if not _fini(x) else ("%.6g" % float(x))


def _i(x) -> str:
    return "n/d" if x is None else str(x)


def _pct(x) -> str:
    return "n/d" if not _fini(x) else ("%.1f %%" % (100.0 * float(x)))


def _ce_qui_est_exerce(n_perdues, n_dec) -> str:
    """Formule d'attribution employée dans l'énoncé du rappel exercé."""
    if n_perdues is None or n_dec is None:
        return "un composant non attribuable"
    blocking = n_perdues >= MIN_PAIRES_INSPECTABLES
    decision = n_dec >= MIN_PAIRES_INSPECTABLES
    if blocking and decision:
        return "le blocking ET la decision"
    if decision:
        return "la decision"
    if blocking:
        return "le blocking"
    return "ni le blocking ni la decision de maniere caracterisable"


def _premiere_condition_echouee(conditions):
    """Première condition en échec, avec sa valeur et son seuil — nommée, jamais résumée."""
    for nom, ok, valeur, seuil in conditions:
        if not ok:
            return nom, valeur, seuil
    return "aucune", None, None


def _lecture_globale(triplet: dict, statut: str) -> str:
    """Phrase de synthèse du triplet. Descriptive : elle ne prescrit rien à la donnée."""
    if statut == "NOT_CONCLUSIVE":
        return ("Prealable d'integrite en echec : aucune lecture de discrimination n'est "
                "publiee avant enquete.")
    if statut == "NON_EVALUABLE":
        return "Population insuffisante pour evaluer la discrimination."
    exerces = [nom for nom, actif in (("le blocking", triplet["blocking_exerce"]),
                                      ("la decision", triplet["decision_exercee"]),
                                      ("le doute", triplet["doute_exerce"])) if actif]
    if not exerces:
        return ("Sur V1.2, ni le blocking, ni la decision, ni le doute ne sont exerces de "
                "maniere mesurable. C'est une mesure de la donnee, pas un defaut a corriger.")
    reste = "" if len(exerces) == 3 else " ; les autres axes ne le sont pas"
    return ("Sur V1.2, " + ", ".join(exerces) + " " +
            ("est exerce" if len(exerces) == 1 else "sont exerces") +
            " de maniere mesurable" + reste + ". Chaque axe est lu par son propre critere, "
            "aucun n'est ecrase dans un jugement unique.")
