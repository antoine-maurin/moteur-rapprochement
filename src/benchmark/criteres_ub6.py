"""Critères de lecture PRÉ-ENREGISTRÉS de la comparaison U-B6 (mandat DISP-UB6-01 §6).

Ce fichier est **gelé** et committé SEUL, AVANT le moindre code de mesure : git rend
l'antériorité vérifiable par un tiers, et `sha256_criteres_ub6()` la rend citable dans
l'artefact. Aucun seuil ci-dessous n'est révisable après avoir vu un résultat. Si l'un se
révèle mal posé, on publie la mesure ET la critique du critère ; on ne réécrit pas le critère.

## Pourquoi pré-enregistrer une COMPARAISON
La question posée — « le moteur maison est-il crédible face à Splink v4.0.16 ? » — se prête à
un biais plus fort encore que celui d'une vérification : celui qui construit le banc est aussi
celui qu'on y juge. Il dispose de mille réglages parfaitement défendables un par un, dont
chacun déplace l'écart d'un demi-point dans le sens qui l'arrange. Le seul remède est de fixer
d'avance la grille, l'inventaire des cellules, et **la phrase publiée pour chaque issue**.

## Déclaration d'antériorité (à lire avant de faire confiance à quoi que ce soit d'ici)
**Aucun chiffre de qualité concernant Splink, une baseline, ou un écart entre systèmes n'a été
consulté pour poser ces seuils — aucun n'existait.** La reconnaissance technique qui a précédé
ce gel a été conduite sous contrainte CC1 : elle pouvait lire `records`, jamais `ground_truth`,
et n'a produit que des grandeurs mécaniques (volumétries, temps, déterminisme).

Ce qui ÉTAIT connu au moment du gel est déclaré ici, pour que le lecteur juge lui-même d'une
éventuelle contamination plutôt que de devoir la supposer :

  (a) les mesures de l'unité U-B5 sur V1.2, déjà publiées et **citées par le mandat lui-même**.
      Elles portent sur le MOTEUR SEUL — rappel de blocking 0,96679, 271 vraies paires, 6 235
      paires candidates à trois passes — et sur AUCUN comparateur. Aucun seuil d'ici n'en est
      dérivé ; en particulier, aucune cible n'a été placée juste au-dessus ou juste en dessous
      d'une valeur connue du moteur.
  (b) les valeurs cibles de la thèse O-P1 — 15 points de F1 et 30 points de rappel face aux
      baselines, 5 points de F1 face à Splink. Elles sont **fournies par le mandat**, pas
      choisies ici : ce fichier les transcrit et les rend opérables, il ne les dérive pas. Ce
      point est le plus important de la déclaration : le risque classique du pré-enregistrement
      — « choisir la barre à la hauteur qu'on sait pouvoir franchir » — est ici structurellement
      absent, la barre ayant été posée par l'émetteur du mandat.
  (c) des grandeurs purement mécaniques mesurées en aveugle : 5 932 paires candidates pour le
      blocking maison sans SDX_NOM, 6 305 pour le blocking naturel de Splink — ce dernier étant
      un SUR-ENSEMBLE STRICT du premier. Ce fait, et lui seul, a déterminé la structure à deux
      bras (§ BRAS) : il aurait été déloyal d'imposer à Splink un univers candidat où il ne perd
      rien et gagne 373 paires, sans le dire.

## Ce que « crédible » veut dire, posé AVANT la mesure
`CREDIBLE_SUR_V1_2` est une **conjonction fermée** : plomberie (P1..P7) ET loyauté (L1..L10) ET
O1 ET O2 ET O3 ET O4, dans la CELLULE_DE_REFERENCE désignée ci-dessous. « Crédible » ne veut
dire ni « meilleur », ni « suffisant en production », ni « généralisable » : la définition
tolère explicitement d'être derrière Splink de 5 points, et être devant n'améliore pas le
verdict. Une comparaison cassée ne donne pas `NON_CREDIBLE` mais `NOT_CONCLUSIVE` : un banc
défaillant ne mesure rien, et surtout pas l'absence de crédibilité.

## Anti-circularité — le dispositif, énoncé avant d'en avoir besoin
L'issue « le moteur maison fait moins bien que Splink » a déjà, dans `ENONCES_UB6`, une phrase
rédigée avec le même soin que l'issue favorable, et cette phrase **nomme d'avance les
échappatoires qu'elle s'interdit** : elle ne pourra être requalifiée ni en « écart à
instruire », ni en « défaut à corriger », ni en « configuration Splink à revoir », ni en
« fixture défavorable ». C'est le sens de l'objectif `O-S1` du mandat : si le moteur maison fait
moins bien, on publie.

Symétriquement, `H6_DISTINGUABILITE` interdit de célébrer une avance de 1,5 point exactement
comme elle interdit de dramatiser un retard de 1,5 point : la règle de résolution n'est jamais
invoquée d'un seul côté.

## Frontière CC1
Ce module n'importe rien de `src/engine/`, de `src/scorer/` ni de `splink` — il ne connaît que
des nombres. Bibliothèque standard seulement (C7, hors réseau strict).
"""
from __future__ import annotations

import hashlib
import os
from typing import Optional

__all__ = [
    "SOCLE_DE_RESOLUTION", "JUSTIFICATIONS",
    "SYSTEMES", "POINTS", "BRAS", "BASELINES", "SENSIBILITES", "METRIQUES_OBLIGATOIRES",
    "PRETRAITEMENTS_DECLARES", "ASYMETRIES_PRE_ENREGISTREES",
    "CELLULE_DE_REFERENCE", "REGLE_DE_COMPLETION", "REGLE_DE_DEPARTAGE",
    "CRITERES", "ENONCES_UB6", "FAMILLES",
    "sha256_criteres_ub6", "evalue_criteres_ub6", "lis_verdict_ub6",
]

# ===================================================================================
# SOCLE DE RÉSOLUTION — ce qu'un écart peut signifier, compte tenu du dénominateur
# ===================================================================================
#: Commun à TOUS les seuils : aucun critère ne s'appuie sur un écart plus fin que ce que le
#: dénominateur permet de distinguer. Les valeurs viennent de la fixture telle qu'elle se
#: DÉCLARE (manifest), pas d'une mesure de qualité.
SOCLE_DE_RESOLUTION = {
    "n_vraies_paires_annonce": 271,
    "n_records_annonce": 537,
    "n_paires_possibles": 537 * 536 // 2,                  # 143 916
    "poids_d_une_vraie_paire_en_rappel": 1.0 / 271.0,      # ≈ 0,369 point
    "demi_largeur_wilson_95_ordre_de_grandeur": 0.02,      # ≈ 2 points à ce dénominateur
    "note": (
        "Une vraie paire vaut environ 0,37 point de rappel. La demi-largeur de l'intervalle "
        "de Wilson a 95 % est de l'ordre de 2 points a ce denominateur. Tout seuil pose "
        "ci-dessous est un multiple lisible de cette resolution ; aucun ne pretend "
        "distinguer plus finement que la donnee ne le permet."),
}

# ===================================================================================
# SEUILS — chacun avec sa justification A PRIORI (jamais « parce que le résultat le donne »)
# ===================================================================================
#: Deux systèmes ne sont déclarés différents qu'au-delà de cet écart ET avec un test apparié.
RESOLUTION_ECART = 0.02
#: McNemar exact sur les discordances : l'instrument APPARIÉ. Le chevauchement d'IC ne l'est pas.
SEUIL_MCNEMAR = 0.05

#: Cibles O-P1 — TRANSCRITES DU MANDAT, non dérivées ici (cf. déclaration d'antériorité (b)).
MARGE_F1_BASELINES = 0.150
MARGE_RAPPEL_BASELINES = 0.300
TOLERANCE_F1_SPLINK = -0.050

#: Garde anti-homme-de-paille. Mêmes planchers que ceux déjà pré-enregistrés en U-B5 : le banc
#: ne s'invente pas des gardes plus douces que celles qu'il s'est déjà imposées.
MIN_RAPPEL_BASELINE_NON_DEGENEREE = 0.30
PRECISION_MIN_NON_DEGENERESCENCE = 0.50
TAUX_MATCH_MAX_NON_DEGENERESCENCE = 0.50

#: Budget de revue commun, offert à TOUT système à score signé (cf. L5_SYMETRIE_DE_REGLAGE).
#: Valeur reprise de `engine.BUDGET_REVUE_DEFAUT` (60 paires/min x 5 min), non re-dérivée ici.
BUDGET_REVUE_COMMUN = 300
#: Grille de livraison des scores, alignée sur l'arrondi du moteur : absorbe la dérive flottante.
DECIMALES_LIVRAISON = 9

#: Épinglages durs (GAP-REF-004 pour Splink ; `source_env_hash` du mandat pour la fixture).
VERSION_SPLINK_EXIGEE = "4.0.16"
CONTENT_SHA256_V1_2 = "66f627edb37022dcecab04dae9c327b342d8dfbb785533ffe8017919000117a2"
N_RECORDS_ATTENDU = 537

JUSTIFICATIONS = {
    "RESOLUTION_ECART": (
        "2 points ~ la demi-largeur de Wilson a 95 % sur 271 vraies paires, soit environ 5 "
        "vraies paires reclassees. En deca, deux systemes ne sont pas departages par cette "
        "fixture : le dire est une information, pretendre le contraire n'en est pas une."),
    "SEUIL_MCNEMAR": (
        "Les systemes sont evalues sur LES MEMES paires : les erreurs sont appariees, et le "
        "test apparie est McNemar. Comparer deux IC independants ignorerait l'appariement et "
        "conclurait moins souvent qu'il ne faut."),
    "MARGE_F1_BASELINES": (
        "TRANSCRIT DU MANDAT (cible N). Verification de LISIBILITE seulement : 0,150 vaut "
        "environ 40 paires equivalentes sur 271, soit ~7 fois la resolution de 0,02 - l'ecart "
        "vise est donc mesurable par cette fixture."),
    "MARGE_RAPPEL_BASELINES": (
        "TRANSCRIT DU MANDAT (cible N). 0,300 vaut environ 81 vraies paires sur 271, tres "
        "au-dessus de la resolution : la cible est lisible."),
    "TOLERANCE_F1_SPLINK": (
        "TRANSCRIT DU MANDAT (cible Y). 0,050 vaut environ 13 paires equivalentes, ~2,5 fois "
        "la resolution : un retard de 5 points est distinguable d'une parite."),
    "MIN_RAPPEL_BASELINE_NON_DEGENEREE": (
        "Une baseline qui ne retrouve pas une vraie paire sur trois n'est pas un adversaire : "
        "la battre ne demontre rien. Plancher pose AVANT de savoir ce que les baselines font."),
    "PRECISION_MIN_NON_DEGENERESCENCE": (
        "Repris tel quel de U-B5. Sous 0,50, un systeme se trompe plus souvent qu'il n'a "
        "raison quand il declare MATCH : son F1 ne decrit plus une decision utile."),
    "TAUX_MATCH_MAX_NON_DEGENERESCENCE": (
        "Repris tel quel de U-B5. Declarer MATCH plus d'une paire candidate sur deux, a une "
        "prevalence de 0,19 %, est le comportement du classifieur trivial."),
    "BUDGET_REVUE_COMMUN": (
        "Le dispositif de placement de seuil du moteur est OFFERT a ses concurrents, au meme "
        "budget : c'est la condition pour que le second point ne soit pas un avantage maison."),
    "DECIMALES_LIVRAISON": (
        "Alignee sur l'arrondi de `decide.agregat`. Deux systemes dont les scores sont livres "
        "a des granularites differentes ne sont pas comparables au bit pres."),
}

# ===================================================================================
# INVENTAIRE FERMÉ — rien ne s'ajoute ni ne se retire après la mesure (cf. H7)
# ===================================================================================
#: Les systèmes comparés. `moteur_maison` est le sujet ; les autres sont les comparateurs.
SYSTEMES = ("moteur_maison", "splink_4_0_16", "baseline")

#: Deux points de fonctionnement par système, issus des MÊMES DEUX RÈGLES pour tous.
#: Point 1 : ce que le système déclare sans regarder la donnée.
#: Point 2 : point dérivé de la SEULE distribution de score du système, à budget de revue égal.
POINTS = {
    "point_1_a_priori_declare": {
        "regle": ("le point que le systeme declare sans regarder la donnee"),
        "moteur_maison": "seuils placeholder T_mu=+8.0 / T_lambda=-8.0 (GAP-A, declares non calibres)",
        "splink_4_0_16": "match_probability >= 0.5 (<=> match_weight >= 0) : regle de Bayes a "
                         "couts egaux, defaut documente de la bibliotheque",
        "baseline": "sa regle native (cle forte exacte OU >= 3 champs concordants)",
    },
    "point_2_budget_de_revue_egal": {
        "regle": ("point derive de la seule distribution de score du systeme, au budget commun "
                  "de %d paires, frontiere evidentielle 0,0" % BUDGET_REVUE_COMMUN),
        "moteur_maison": "DIMS-v2 : engine.dimensionne_depuis_correspondances(budget=300, frontiere=0.0)",
        "splink_4_0_16": "LA MEME FONCTION, sur son score prive du prior, meme budget, meme frontiere",
        "baseline": ("VOLUME EGALISE : DIMS est inapplicable a un score entier non signe (aucune "
                     "frontiere neutre ou placer une bande). La baseline declare MATCH ses K "
                     "meilleures paires, K = n_MATCH du moteur au point 2. Cette difference est "
                     "imprimee DANS la cellule, jamais en note."),
    },
}

#: Les deux bras. Les DEUX sont publiés, dans le même artefact, avec les mêmes clés.
BRAS = {
    "A_univers_appari": {
        "role": "BRAS DE TETE — porte le verdict O-P1",
        "definition": ("tous les systemes notent EXACTEMENT le meme ensemble candidat C0, issu "
                       "du blocking maison (passes CP + PREF, prefixe 4), egalite ENSEMBLISTE "
                       "verifiee et non simple egalite de cardinal"),
        "ce_qu_il_isole": ("la couche de DECISION : a ensemble candidat identique, un ecart est "
                           "imputable a la decision et a rien d'autre, et le plafond de rappel "
                           "est litteralement le meme pour tous"),
        "cout_declare": ("ce bras NE MESURE PAS la chaine. C0 est le blocking du moteur maison : "
                         "la competence de blocage de Splink n'y existe pas et son rappel y est "
                         "plafonne par celui du moteur. C'est pourquoi le bras B est obligatoire."),
    },
    "B_chaine_complete": {
        "role": "OBLIGATOIRE — publie dans le meme artefact, immediatement adjacent",
        "definition": ("chaque systeme avec SON blocking : le moteur ses passes CP + PREF, Splink "
                       "ses regles natives, les baselines l'espace complet"),
        "ce_qu_il_isole": ("les chaines completes, seul regime ou une comparaison produit contre "
                           "produit est licite"),
        "cout_declare": ("l'ecart y MELANGE blocking et decision et ne les attribue pas. Seul le "
                         "rappel BOUT EN BOUT (denominateur |M| entier) y est comparable entre "
                         "ensembles candidats differents ; `f1_post_blocking` et "
                         "`rappel_post_blocking` sont INTERDITS en comparaison croisee."),
    },
}

#: Les baselines. B0 est un ÉTALON, jamais un concurrent dans l'arithmétique O-P1.
BASELINES = {
    "B0_tout_candidat": {
        "regle": "toute paire candidate est declaree MATCH",
        "role": "ETALON — exclu des cibles O1/O2",
        "motif_exclusion": ("son rappel EST le plafond de rappel de tout systeme consommant le "
                            "meme ensemble candidat : exiger de le battre de 30 points serait "
                            "mathematiquement impossible. Sa PRECISION est le plancher contre "
                            "lequel se lit toute precision."),
    },
    "B1_exact_triplet": {
        "regle": "nom ET prenom ET date_naissance simultanement presents et strictement egaux",
        "role": "concurrent — le match exact deterministe exige par le mandat",
    },
    "B2_cle_forte": {
        "regle": "email egal OU telephone egal OU triplet B1",
        "role": "concurrent",
    },
    "B3_jaccard_jetons": {
        "regle": "Jaccard sur sacs de jetons >= 0,50",
        "role": "concurrent — la regle simple a seuil exigee par le mandat",
    },
    "B4_concordance_3_sur_8": {
        "regle": ("au moins 3 champs concordants sur 8 (texte : ratio de similarite >= 0,85 ; "
                  "structure : egalite stricte ; champ absent d'un cote : ni accord ni desaccord)"),
        "role": ("concurrent — LE MOTEUR PRIVE DE FELLEGI-SUNTER : memes 8 champs, memes valeurs "
                 "normalisees, meme tolerance aux fautes de frappe, mais comptage non pondere au "
                 "lieu de la ponderation log-vraisemblance et de l'EM"),
    },
    "B5_cle_forte_ou_concordance": {
        "regle": "cle forte exacte OU >= 3 champs concordants au sens de B4",
        "role": ("concurrent — la meilleure regle « d'une heure » ; c'est elle que O-P1 doit "
                 "affronter si elle est la plus forte"),
    },
}

#: Sensibilités déclarées d'avance. Elles ne portent JAMAIS de verdict (cf. H3), mais elles
#: entrent dans la recherche du MEILLEUR point de Splink (cf. H4) : la comparaison la plus dure
#: pour le moteur est choisie en aveugle, donc non requalifiable.
SENSIBILITES = (
    "SENS_1_splink_donnees_brutes",
    "SENS_2_splink_u_estime_sur_C0",
    "SENS_3_cp_avec_niveau_departement",
    "SENS_4_lambda_recall_0_5_0_7_0_9",
    "SENS_5_moteur_trois_passes",
    "SENS_6_arbitrage_force_sans_abstention",
)

#: Les clés que CHAQUE cellule publiée doit porter, sans exception (cf. L4).
METRIQUES_OBLIGATOIRES = (
    "precision", "rappel_bout_en_bout", "f1_bout_en_bout",
    "tp", "fp", "fn", "fn_blocking",
    "n_candidates", "n_zone_grise",
)

#: Le prétraitement est UNIQUE et appliqué une seule fois. Tout écart doit figurer ici.
PRETRAITEMENTS_DECLARES = {
    "normalisation": ("engine.normalise_records, appliquee UNE FOIS, sha256 du resultat publie ; "
                      "la MEME liste est remise aux trois systemes"),
    "motif": ("la normalisation FR est du SUBSTRAT, pas un differenciateur. La priver a Splink "
              "mesurerait un handicap de plomberie deguise en handicap d'algorithme : Splink "
              "documente qu'il ne nettoie pas et attend une donnee standardisee."),
    "prix_declare": ("le bras Splink est donc honnetement « Splink + normalisation maison ». "
                     "C'est l'asymetrie A2, et la sensibilite SENS_1 la chiffre."),
}

#: Inventaire d'asymétries posé AVANT la mesure. Chacune porte la DIRECTION de son biais.
#: `favorise` appartient à l'énumération fermée {moteur_maison, splink, baselines, symetrique,
#: indetermine}. Une asymétrie découverte pendant l'exécution est AJOUTÉE avec la mention
#: `decouverte_apres_gel`, jamais retirée, et jamais invoquée pour effacer un chiffre défavorable.
ASYMETRIES_PRE_ENREGISTREES = (
    {"code": "A1_univers_candidat_maison", "favorise": "moteur_maison",
     "quelle": ("dans le bras A, l'ensemble candidat est celui du blocking maison ; Splink y perd "
                "les 373 paires que son propre blocking voit en plus"),
     "parade": "le bras B, obligatoire, lui rend son terrain"},
    {"code": "A2_normalisation_maison", "favorise": "indetermine",
     "quelle": "tous les systemes recoivent la normalisation FR ecrite pour le moteur",
     "parade": "SENS_1 chiffre Splink sur donnees brutes"},
    {"code": "A3_abstention_du_moteur", "favorise": "splink",
     "quelle": ("le moteur peut s'abstenir (3 zones) ; sous la convention stricte ses abstentions "
                "comptent comme predit-NEGATIF et penalisent son rappel, la ou un systeme binaire "
                "ne paie aucune abstention"),
     "parade": "SENS_6 rejoue les trois systemes en arbitrage force, couverture 1,0 partout"},
    {"code": "A4_seuil_oracle_aux_concurrents", "favorise": "splink",
     "quelle": ("un point a seuil oracle - le meilleur seuil connaissant la verite - est accorde "
                "aux concurrents et JAMAIS au moteur"),
     "parade": "aucune : l'asymetrie est deliberee et joue contre le moteur"},
    {"code": "A5_auteur_du_banc", "favorise": "moteur_maison",
     "quelle": ("le banc est ecrit par l'auteur du moteur : la configuration Splink a recu moins "
                "d'attention experte que le moteur, et le nombre d'essais de configuration "
                "anterieurs est declare dans l'artefact"),
     "parade": ("L7 exige les constructeurs par defaut de la bibliotheque partout ou leurs niveaux "
                "sont entrainables, et la publication verbatim des settings, contestables ligne a ligne")},
    {"code": "A6_donnee_du_meme_projet", "favorise": "indetermine",
     "quelle": ("FX_001 V1.2 est produite par le meme projet que le moteur, quoique par une "
                "surface distincte et AVEUGLE au resultat"),
     "parade": ("declaree ; le banc ne peut pas la lever, et aucune conclusion ne porte au-dela "
                "de cette fixture")},
    {"code": "A7_f1_pairwise_pessimiste", "favorise": "indetermine",
     "quelle": ("le F1 pairwise ne compte pas la recuperation par transitivite (unite U-B4, hors "
                "perimetre) ; il est pessimiste pour TOUT systeme evalue en chaine complete, "
                "moteur compris"),
     "parade": "declaree ; aucune correction n'est appliquee, aucune n'est estimee"},
    {"code": "A8_em_non_supervise_des_deux_cotes", "favorise": "symetrique",
     "quelle": "le moteur et Splink estiment tous deux m/u par EM non supervise",
     "parade": "aucune requise"},
    {"code": "A9_baselines_normalisees", "favorise": "baselines",
     "quelle": "les baselines beneficient de la normalisation FR du moteur",
     "parade": "concession deliberee : elle rend les baselines plus fortes, donc la cible plus dure"},
    {"code": "A10_budget_de_revue_maison", "favorise": "moteur_maison",
     "quelle": ("le budget de revue de 300 paires est celui qu'a retenu le moteur ; il est offert "
                "a Splink mais n'a pas ete choisi avec lui"),
     "parade": "declare ; le point 1 de chaque systeme est independant de ce budget"},
    {"code": "A11_splink_sans_expert", "favorise": "moteur_maison",
     "quelle": ("Splink est configure selon sa documentation, non regle par un praticien "
                "experimente ; tout enonce de comparaison est borne a cette configuration"),
     "parade": "la formulation du verdict O4 le dit explicitement, dans la phrase elle-meme"},
    {"code": "A12_une_seule_fixture", "favorise": "indetermine",
     "quelle": "un seul jeu de donnees, une seule execution du protocole",
     "parade": "declaree ; aucune generalisation n'est publiee"},
)

#: La cellule qui porte le verdict, désignée AVANT toute mesure.
#: Motif de PROVENANCE, et non de performance : le point 2 est le seul point du moteur issu
#: d'une procédure déclarée, reproductible et non supervisée ; le placeholder ±8 est déclaré
#: NON CALIBRÉ dans le code du moteur lui-même. Le prix de cette désignation est payé ici :
#: si c'est le placeholder qui devance DIMS-v2, LE VERDICT RESTE RENDU AU POINT DÉSIGNÉ.
CELLULE_DE_REFERENCE = {
    "bras": "A_univers_appari",
    "point": "point_2_budget_de_revue_egal",
    "convention": "stricte",
    "metriques": ("f1_bout_en_bout", "rappel_bout_en_bout"),
    "motif_de_designation": ("provenance, non performance : DIMS-v2 est le seul point du moteur "
                             "issu d'une procedure declaree, reproductible et non supervisee"),
}

#: Ce que devient une paire de C0 qu'un système n'a pas notée. Gelé : sans règle écrite
#: d'avance, un système pourrait « ne pas répondre » sur ses cas difficiles et voir sa
#: précision monter. Le nombre de complétions est publié par système.
REGLE_DE_COMPLETION = (
    "une paire de C0 non emise par un systeme recoit verdict NON_MATCH et poids_match egal au "
    "score fini minimal emis par CE systeme, moins 1,0. Le nombre de completions est publie par "
    "systeme. Aucune paire de C0 n'est retiree de la mesure au motif qu'un systeme ne l'a pas vue.")

#: Ce qui se passe si les deux bras ne concordent pas. Écrit d'avance pour que le bras A ne
#: puisse pas, à lui seul, effacer la compétence de blocage de Splink.
REGLE_DE_DEPARTAGE = (
    "si le verdict d'une cible differe entre le bras A et le bras B, LES DEUX verdicts sont "
    "publies cote a cote et la cible est declaree NON DEPARTAGEE. Aucun des deux bras ne peut "
    "etre presente seul comme « le » resultat.")

FAMILLES = ("plomberie", "loyaute", "honnetete", "cible")

# ===================================================================================
# CRITÈRES — inventaire FERMÉ (30). Chacun a ses DEUX énoncés dans ENONCES_UB6.
# ===================================================================================
CRITERES = {
    # ---- PLOMBERIE : leur échec interdit TOUTE déclaration de crédibilité --------------
    "P1_DONNEE_INTACTE": {
        "enonce_du_critere": "la mesure porte-t-elle sur la fixture que le mandat designe ?",
        "seuil": {"content_sha256": CONTENT_SHA256_V1_2, "n_records": N_RECORDS_ATTENDU},
        "famille": "plomberie"},
    "P2_DETERMINISME": {
        "enonce_du_critere": "deux executions independantes produisent-elles le meme artefact ?",
        "seuil": "egalite d'octets de la serialisation canonique ; tolerance ZERO",
        "famille": "plomberie"},
    "P3_SYSTEME_A_TOURNE": {
        "enonce_du_critere": "chaque systeme declare a-t-il reellement produit une sortie ?",
        "seuil": "statut dans {OK, ABSENT} ; toute cellule non-OK a des metriques nulles ET un motif",
        "famille": "plomberie"},
    "P4_CONTRAT_DE_SORTIE": {
        "enonce_du_critere": "les correspondances passent-elles l'audit d'integrite de l'oracle ?",
        "seuil": "valide_correspondances(...)['alerte'] is False pour chaque systeme",
        "famille": "plomberie"},
    "P5_INVARIANTS_ORACLE": {
        "enonce_du_critere": "les contingences ferment-elles, et sur LE MEME denominateur ?",
        "seuil": "verifie_invariants ne leve pas ; (n_vraies, n_candidates) est un SINGLETON",
        "famille": "plomberie"},
    "P6_VERSIONS_EPINGLEES": {
        "enonce_du_critere": "la version de Splink executee est-elle celle que le mandat exige ?",
        "seuil": VERSION_SPLINK_EXIGEE,
        "famille": "plomberie"},
    "P7_PRODUIT_INTACT": {
        "enonce_du_critere": "le produit reste-t-il stdlib-seule, hors reseau, et CC1 tenue ?",
        "seuil": ("zero import de splink/duckdb/pandas dans src/engine et src/scorer ; zero import "
                  "croise engine<->scorer ; src/benchmark n'importe jamais scorer"),
        "famille": "plomberie"},

    # ---- LOYAUTÉ (CC5) ------------------------------------------------------------------
    "L1_MEME_DONNEE": {
        "enonce_du_critere": "les systemes recoivent-ils litteralement la meme donnee ?",
        "seuil": "egalite EXACTE des sha256 des listes remises a chaque adaptateur",
        "famille": "loyaute"},
    "L2_MEME_ENSEMBLE_CANDIDAT": {
        "enonce_du_critere": "le bras A repose-t-il sur un ensemble candidat unique et partage ?",
        "seuil": "egalite ENSEMBLISTE exacte avec C0 pour chaque systeme (pas egalite de cardinal)",
        "famille": "loyaute"},
    "L3_MEME_ORACLE": {
        "enonce_du_critere": "tous les systemes sont-ils notes par le meme oracle, au meme endroit ?",
        "seuil": ("un seul chemin d'appel, aucune branche par systeme dans la boucle de notation, "
                  "aucune metrique reimplementee dans src/benchmark"),
        "famille": "loyaute"},
    "L4_MEMES_METRIQUES": {
        "enonce_du_critere": "chaque cellule publie-t-elle exactement les memes cles ?",
        "seuil": METRIQUES_OBLIGATOIRES,
        "famille": "loyaute"},
    "L5_SYMETRIE_DE_REGLAGE": {
        "enonce_du_critere": "le moteur dispose-t-il d'un outil de reglage que ses concurrents n'ont pas ?",
        "seuil": ("meme cardinal de points par systeme ; chaque point tracable a une regle gelee ; "
                  "le dispositif DIMS offert a tout systeme a score signe, au meme budget"),
        "famille": "loyaute"},
    "L6_AUCUNE_SUPERVISION": {
        "enonce_du_critere": "un parametre d'un systeme a-t-il ete place a l'aide de la verite terrain ?",
        "seuil": ("zero ; les configurations sont hachees AVANT le premier appel au scoreur et leur "
                  "sha256 est asserte inchange apres"),
        "famille": "loyaute"},
    "L7_SPLINK_NON_SOUS_CONFIGURE": {
        "enonce_du_critere": "Splink est-il configure de bonne foi, ou reduit a un homme de paille ?",
        "seuil": ("les 8 attributs presents ; tout niveau d'occupation mesuree >= 1 retenu ; "
                  "settings publies verbatim et contestables ligne a ligne"),
        "famille": "loyaute"},
    "L8_ASYMETRIES_DECLAREES": {
        "enonce_du_critere": "les asymetries residuelles sont-elles publiees AVEC leur direction ?",
        "seuil": "les %d asymetries pre-enregistrees au moins, chacune avec un champ `favorise`"
                 % len(ASYMETRIES_PRE_ENREGISTREES),
        "famille": "loyaute"},
    "L9_CONVENTION_UNIQUE": {
        "enonce_du_critere": "le tableau de tete est-il homogene en convention de zone grise ?",
        "seuil": "une seule convention (`stricte`) en tete ; les 4 conventions en annexe POUR TOUS",
        "famille": "loyaute"},
    "L10_BRAS_B_PUBLIE": {
        "enonce_du_critere": "la competence de blocage des concurrents est-elle rendue visible ?",
        "seuil": "presence obligatoire du bras B avec les memes cles ; regle de non-departage",
        "famille": "loyaute"},

    # ---- HONNÊTETÉ ----------------------------------------------------------------------
    "H1_LES_DEUX_POINTS_PUBLIES": {
        "enonce_du_critere": "les deux points de chaque systeme figurent-ils partout ?",
        "seuil": "exactement 2 points par systeme, verifie DANS LES DEUX SENS",
        "famille": "honnetete"},
    "H2_ECART_SIGNE": {
        "enonce_du_critere": "les ecarts sont-ils signes et orientes, ou presentes en valeur absolue ?",
        "seuil": "tout ecart porte {valeur signee, sens: 'moteur_maison - <autre>'} ; aucune valeur absolue",
        "famille": "honnetete"},
    "H3_CELLULE_DE_REFERENCE_GELEE": {
        "enonce_du_critere": "le verdict est-il rendu dans la cellule designee avant la mesure ?",
        "seuil": CELLULE_DE_REFERENCE,
        "famille": "honnetete"},
    "H4_REFERENCE_SPLINK_MAXIMALE": {
        "enonce_du_critere": "la comparaison se fait-elle contre le MEILLEUR point de Splink ?",
        "seuil": "argmax du F1 bout en bout sur toutes ses cellules ET ses sensibilites declarees",
        "famille": "honnetete"},
    "H5_MATRICE_COMPLETE": {
        "enonce_du_critere": "toutes les cellules attendues sont-elles publiees ?",
        "seuil": "cardinalite publiee == cardinalite reconstruite depuis l'inventaire gele",
        "famille": "honnetete"},
    "H6_DISTINGUABILITE": {
        "enonce_du_critere": "les ecarts sont-ils lus contre la resolution du denominateur ?",
        "seuil": {"resolution": RESOLUTION_ECART, "mcnemar": SEUIL_MCNEMAR},
        "famille": "honnetete"},
    "H7_INVENTAIRE_FERME": {
        "enonce_du_critere": "l'inventaire publie coincide-t-il avec l'inventaire gele ?",
        "seuil": "egalite d'ensembles DANS LES DEUX SENS ; clause de non-retrait",
        "famille": "honnetete"},
    "H8_ANTERIORITE_DU_GEL": {
        "enonce_du_critere": "un tiers peut-il verifier que les criteres precedent la mesure ?",
        "seuil": ("un seul commit sur ce fichier ; commit de gel ancetre du commit de mesure ; "
                  "sha256 du fichier cite dans l'artefact"),
        "famille": "honnetete"},

    # ---- CIBLES O-P1 ---------------------------------------------------------------------
    "O1_MARGE_BASELINE_F1": {
        "enonce_du_critere": "le moteur devance-t-il la meilleure baseline de 15 points de F1 ?",
        "seuil": MARGE_F1_BASELINES,
        "famille": "cible"},
    "O2_MARGE_BASELINE_RAPPEL": {
        "enonce_du_critere": "le moteur devance-t-il la meilleure baseline de 30 points de rappel ?",
        "seuil": MARGE_RAPPEL_BASELINES,
        "famille": "cible"},
    "O3_ANTI_HOMME_DE_PAILLE": {
        "enonce_du_critere": "l'adversaire battu est-il un adversaire reel ?",
        "seuil": {"rappel_baseline": MIN_RAPPEL_BASELINE_NON_DEGENEREE,
                  "precision": PRECISION_MIN_NON_DEGENERESCENCE,
                  "taux_match": TAUX_MATCH_MAX_NON_DEGENERESCENCE},
        "famille": "cible"},
    "O4_ECART_SPLINK": {
        "enonce_du_critere": "le moteur se tient-il a moins de 5 points de F1 de Splink 4.0.16 ?",
        "seuil": TOLERANCE_F1_SPLINK,
        "famille": "cible"},
    "O5_CREDIBILITE_O_P1": {
        "enonce_du_critere": "le moteur maison est-il CREDIBLE au sens pre-enregistre ?",
        "seuil": "conjonction stricte : P1..P7 ET L1..L10 ET O1 ET O2 ET O3 ET O4",
        "famille": "cible"},
}

# ===================================================================================
# ÉNONCÉS — la phrase publiée pour CHAQUE issue, rédigée AVANT la mesure
# ===================================================================================
#: Deux entrées par critère : `<CODE>_SAT` et `<CODE>_NON_SAT`. La phrase défavorable est
#: rédigée avec le même soin que la favorable — c'est tout le dispositif : une issue qui a déjà
#: son énoncé ne peut plus être requalifiée en autre chose.
ENONCES_UB6 = {
    # ---- plomberie -----------------------------------------------------------------------
    "P1_DONNEE_INTACTE_SAT": (
        "Les {n_systemes} systemes ont tourne sur FX_001 V1.2 : content_sha256 recalcule "
        "conforme ({sha}), {n_records} enregistrements, fixture ouverte en lecture seule."),
    "P1_DONNEE_INTACTE_NON_SAT": (
        "Prealable P1 en echec : {motif}. AUCUN chiffre n'est publie, d'aucun systeme. Une "
        "comparaison sur une donnee dont on ne sait pas ce qu'elle est n'est pas une mesure "
        "degradee, c'est un artefact. La fixture n'est pas reparee dans cette unite : l'anomalie "
        "est escaladee telle quelle et le verdict est NOT_CONCLUSIVE."),
    "P2_DETERMINISME_SAT": (
        "Le banc est deterministe : des executions independantes produisent le meme artefact "
        "canonique (sha256 {sha}). Les ecarts publies sont des ecarts entre systemes, jamais "
        "entre executions."),
    "P2_DETERMINISME_NON_SAT": (
        "Non-determinisme detecte : {motif}. Aucun ecart impliquant un systeme non deterministe "
        "n'est publie comme mesure - un chiffre qui bouge d'une execution a l'autre ne peut pas "
        "etre compare a 2 points pres. Le systeme figure au tableau avec le statut "
        "NON_DETERMINISTE et la divergence observee ; il n'est ni retire, ni remplace par sa "
        "premiere execution."),
    "P3_SYSTEME_A_TOURNE_SAT": (
        "Les {n_systemes} systemes ont tourne et emis une sortie complete. Aucun chiffre publie "
        "n'est une valeur par defaut, recopiee d'une autre source, ou tiree de la litterature."),
    "P3_SYSTEME_A_TOURNE_NON_SAT": (
        "{motif}. Le ou les systemes concernes figurent au tableau avec le statut ABSENT. AUCUNE "
        "valeur ne leur est imputee - ni zero, ni moyenne, ni valeur favorable par defaut. Toute "
        "cible qui en dependait est NON EVALUABLE, jamais atteinte par defaut."),
    "P4_CONTRAT_DE_SORTIE_SAT": (
        "Les correspondances des {n_systemes} systemes passent l'audit d'integrite sans alerte : "
        "cles canoniques, aucun doublon, aucune auto-paire, verdicts dans l'enumeration, "
        "poids_match finis. L'oracle mesure la meme chose chez tous."),
    "P4_CONTRAT_DE_SORTIE_NON_SAT": (
        "Audit d'integrite en echec : {motif}. Ces chiffres ne sont pas des mesures degradees, ce "
        "sont des artefacts : publies comme NON MESURABLES, sans valeur, et la cible qui les "
        "prenait pour reference est NON EVALUABLE. Corriger l'ADAPTATEUR (la traduction vers le "
        "contrat) est licite, c'est une correction de FORME ; corriger le SYSTEME pour ameliorer "
        "son chiffre ne l'est pas."),
    "P5_INVARIANTS_ORACLE_SAT": (
        "Pour chacun des {n_systemes} systemes : mv+gv+nv+pb = |M| = {n_vraies} et somme des six "
        "cases = |C| = {n_candidates}. Les denominateurs sont litteralement identiques d'une "
        "ligne a l'autre."),
    "P5_INVARIANTS_ORACLE_NON_SAT": (
        "Invariant de contingence rompu : {motif}. Aucune metrique n'est publiee pour le systeme "
        "concerne. Une contingence fausse fausse tout ce qui en derive, et l'erreur ressemblerait "
        "a une erreur du SYSTEME alors qu'elle est une erreur de MESURE : le soupcon porte "
        "d'abord sur le banc."),
    "P6_VERSIONS_EPINGLEES_SAT": (
        "Splink {v_splink}, duckdb {v_duckdb}, pandas {v_pandas}, Python {v_python}, releves a "
        "l'execution. La reference nommee dans le verdict est celle qui a effectivement tourne."),
    "P6_VERSIONS_EPINGLEES_NON_SAT": (
        "La version relevee ({v_splink}) n'est pas {v_exigee}. La colonne Splink est publiee avec "
        "sa version reelle et la cible O4 est NON EVALUABLE au titre de la reference exigee par "
        "le mandat. Nommer une version qu'on n'a pas executee serait la seule malhonnetete que ce "
        "banc ne pourrait pas rattraper."),
    "P7_PRODUIT_INTACT_SAT": (
        "Le produit reste stdlib-seule et hors reseau : aucun import de la bibliotheque du "
        "concurrent dans le moteur ni dans le scoreur, aucun import croise, la dependance de banc "
        "est confinee a src/benchmark/ et le point de rencontre est tools/banc_ub6.py, hors de src/."),
    "P7_PRODUIT_INTACT_NON_SAT": (
        "P7 en echec : {motif}. La mesure est invalidee a la racine - un scoreur ou un moteur qui "
        "dependrait de la bibliotheque du concurrent ne prouve plus rien sur lui, et le produit "
        "n'est plus livrable hors reseau. Aucun chiffre n'est publie ; l'import fautif est retire "
        "avant toute re-execution."),

    # ---- loyauté -------------------------------------------------------------------------
    "L1_MEME_DONNEE_SAT": (
        "Les {n_systemes} systemes recoivent la MEME liste de {n_records} enregistrements "
        "normalises (sha256 {sha}). Le pretraitement est unique, declare, et applique une seule fois."),
    "L1_MEME_DONNEE_NON_SAT": (
        "Les systemes ne voient pas la meme donnee : {motif}. Aucun ecart n'est publie comme "
        "comparaison. Donner a un systeme une donnee mieux preparee qu'a un autre est la premiere "
        "facon, et la plus discrete, de fabriquer un ecart."),
    "L2_MEME_ENSEMBLE_CANDIDAT_SAT": (
        "Bras A : ensemble candidat unique et partage de {n_c0} paires, identique pour les "
        "{n_systemes} systemes (0 en trop, 0 en moins). {n_completions} completion(s) au total. "
        "Aucun systeme ne peut gagner ni perdre sur son blocking : ce bras compare des REGLES DE "
        "DECISION, a plafond de rappel identique ({pb} vraies paires perdues, le meme pour tous)."),
    "L2_MEME_ENSEMBLE_CANDIDAT_NON_SAT": (
        "Les ensembles candidats ne coincident pas : {motif}. La lecture « decision seule » n'est "
        "pas produite ; seul le bras B subsiste, publie en disant explicitement que l'ecart MELANGE "
        "blocking et decision et n'attribue ni l'un ni l'autre. Aucune phrase de l'artefact ne "
        "presente cet ecart comme un ecart de qualite de decision."),
    "L3_MEME_ORACLE_SAT": (
        "Les {n_systemes} systemes sont notes par le MEME oracle S_PROOF, par le MEME chemin "
        "d'appel, sous la MEME convention, avec le MEME objet de verite et le MEME denominateur. "
        "La notation est litteralement la meme fonction appelee en boucle."),
    "L3_MEME_ORACLE_NON_SAT": (
        "Un systeme au moins est note hors du chemin unique : {motif}. Les chiffres concernes "
        "sortent du tableau comparatif et sont republies dans une section « mesures non "
        "comparables », avec leur mode de calcul. Comparer deux nombres produits par deux "
        "mesureurs differents est une operation sans signification, meme quand les deux mesureurs "
        "sont justes."),
    "L4_MEMES_METRIQUES_SAT": (
        "Chaque cellule publie exactement les memes {n_cles} cles obligatoires, avec denominateurs "
        "explicites. Aucune metrique n'est publiee pour un systeme et tue pour un autre."),
    "L4_MEMES_METRIQUES_NON_SAT": (
        "Les cles publiees different entre systemes : {motif}. Une metrique presente d'un cote et "
        "absente de l'autre est une selection, meme involontaire : elle laisse le lecteur "
        "completer par le meilleur cas. Les cles manquantes sont soit calculees, soit publiees a "
        "null avec le motif de leur indisponibilite ; aucune cellule n'est publiee incomplete en "
        "silence."),
    "L5_SYMETRIE_DE_REGLAGE_SAT": (
        "Chaque systeme est presente avec 2 points issus des MEMES deux regles declarees a priori. "
        "Splink recoit le MEME dispositif de placement de seuil que le moteur, sur sa propre "
        "distribution, au meme budget de {budget} paires. Le moteur ne dispose d'aucun outil de "
        "calibration que ses concurrents n'aient pas, et de pas un seul tirage de plus."),
    "L5_SYMETRIE_DE_REGLAGE_NON_SAT": (
        "Asymetrie de reglage : {motif}. L'ecart impliquant ce systeme n'est pas publie comme un "
        "ecart de qualite : regler un cote et pas l'autre, ou lui accorder plus d'essais, produit "
        "un ecart qui mesure l'attention recue et non la qualite. Consequence appliquee "
        "immediatement, et non differee a une relecture : la cible est evaluee au SEUL point "
        "designe a priori, le second point du moteur restant descriptif, et le nombre d'essais de "
        "configuration consentis a chaque systeme est publie dans l'artefact. Un banc dont l'auteur "
        "est aussi le concurrent ne se defend pas en promettant d'avoir ete equitable : il se "
        "defend en rendant l'inequite comptable."),
    "L6_AUCUNE_SUPERVISION_SAT": (
        "Aucun seuil, aucun poids, aucun parametre d'aucun systeme n'a ete place a l'aide de la "
        "verite terrain. Les EM du moteur et de Splink sont non supervises, les baselines sont a "
        "regle fixe, DIMS ne lit qu'une distribution de scores. Les seuils oracle sont "
        "DIAGNOSTIQUES, accordes aux concurrents et non au moteur, et non reinjectables."),
    "L6_AUCUNE_SUPERVISION_NON_SAT": (
        "L6 en echec : {motif}. Un systeme regle sur la verite terrain n'est pas compare aux "
        "autres, il est compare a lui-meme. La colonne concernee est RETIREE de toute cible et son "
        "chiffre porte en permanence l'etiquette « supervise, non comparable ». La regle vaut "
        "d'abord contre le moteur maison : si c'est LUI dont un parametre a vu les etiquettes, "
        "l'unite entiere est NOT_CONCLUSIVE, car la these O-P1 porte precisement sur un moteur non "
        "supervise. Aucune re-execution « propre » ne peut effacer cette lecture : le fait qu'une "
        "fuite ait eu lieu est publie avec la mesure qui l'a suivie."),
    "L7_SPLINK_NON_SOUS_CONFIGURE_SAT": (
        "La configuration Splink est publiee integralement et peut etre contestee ligne a ligne. "
        "Elle couvre les 8 memes attributs que le moteur, emploie les constructeurs PAR DEFAUT de "
        "la bibliotheque partout ou leurs niveaux sont entrainables, et ne retire que des niveaux "
        "mesures a occupation zero. Splink n'est pas un homme de paille."),
    "L7_SPLINK_NON_SOUS_CONFIGURE_NON_SAT": (
        "L7 en echec : {motif}. Splink est ici SOUS-CONFIGURE. Tout ecart favorable au moteur est "
        "sans valeur probante : il mesure la configuration que j'ai ecrite pour Splink, pas "
        "Splink. La cible O4 est declaree NON EVALUABLE, et non satisfaite par defaut - "
        "l'asymetrie de competence entre celui qui configure son propre outil depuis un an et "
        "celui qui configure l'outil du concurrent en une journee est la faiblesse structurelle de "
        "tout banc conduit par une partie prenante. Elle ne se corrige pas en s'appliquant "
        "davantage : elle se declare, et la configuration est publiee verbatim pour qu'un "
        "praticien Splink puisse la contester ligne a ligne et refaire la mesure."),
    "L8_ASYMETRIES_DECLAREES_SAT": (
        "Les {n_asymetries} asymetries residuelles sont publiees avec leur DIRECTION. Aucune n'est "
        "corrigee : elles sont declarees, et le lecteur peut appliquer lui-meme la correction de "
        "lecture. {n_favorisent_moteur} d'entre elles jouent en faveur du moteur maison et sont "
        "publiees au meme titre que les autres."),
    "L8_ASYMETRIES_DECLAREES_NON_SAT": (
        "L'inventaire des asymetries est incomplet : {motif}. L'artefact ne se lit pas comme une "
        "comparaison loyale tant que les manquantes n'y figurent pas avec leur sens. Une asymetrie "
        "decouverte pendant l'execution est AJOUTEE avec la mention « decouverte apres le gel » ; "
        "elle n'est jamais retiree, et jamais utilisee pour effacer un chiffre defavorable."),
    "L9_CONVENTION_UNIQUE_SAT": (
        "Le tableau de tete est homogene : F1 pairwise bout en bout, precision, rappel bout en "
        "bout, convention stricte, denominateur |M| = {n_vraies}. Les {n_gris} paires que le "
        "moteur refuse de trancher comptent comme predit-NEGATIF et penalisent son rappel : le "
        "crediter de ces abstentions lui attribuerait une decision qu'il a explicitement refuse "
        "de prendre."),
    "L9_CONVENTION_UNIQUE_NON_SAT": (
        "Le tableau n'est pas homogene : {motif}. Il est reconstruit sous la convention stricte "
        "pour tous, ou publie sous le titre « comparaison non homogene » avec la convention "
        "employee par ligne. Choisir par systeme la convention qui l'avantage produit un tableau "
        "dont chaque case est vraie et dont l'ensemble est faux."),
    "L10_BRAS_B_PUBLIE_SAT": (
        "Les DEUX bras sont publies : le bras A isole la decision a ensemble candidat identique, "
        "le bras B mesure les chaines completes et rend a Splink son propre blocking ({n_splink} "
        "paires contre {n_moteur}, sur-ensemble strict). Le verdict est concordant entre les deux bras."),
    "L10_BRAS_B_PUBLIE_NON_SAT": (
        "{motif}. Le bras A seul comparerait le moteur sur SON terrain de blocking sans le dire ; "
        "la competence de blocage de Splink serait confisquee en silence. Les deux verdicts sont "
        "publies cote a cote et la cible concernee est declaree NON DEPARTAGEE."),

    # ---- honnêteté ------------------------------------------------------------------------
    "H1_LES_DEUX_POINTS_PUBLIES_SAT": (
        "Les deux points de chaque systeme sont publies avec le meme vecteur de metriques. Le "
        "lecteur voit les regimes qui servent le moins la these comme les autres."),
    "H1_LES_DEUX_POINTS_PUBLIES_NON_SAT": (
        "Un point manque au tableau ou n'apparait que dans une partie des comparaisons : {motif}. "
        "Ne publier qu'un point sur deux revient a choisir apres coup le regime qui se presente le "
        "mieux - ce que ce pre-enregistrement existe pour interdire."),
    "H2_ECART_SIGNE_SAT": (
        "Les {n_ecarts} comparaisons sont publiees comme des ecarts SIGNES, orientes « moteur "
        "maison moins autre ». Un ecart negatif occupe la meme colonne, la meme place et la meme "
        "typographie qu'un ecart positif."),
    "H2_ECART_SIGNE_NON_SAT": (
        "Au moins un ecart n'est pas signe ou pas oriente : {motif}. L'artefact est corrige avant "
        "publication ; a defaut la section est retiree. Une valeur absolue, ou un ecart dont on ne "
        "sait pas qui est devant, transforme une defaite en « difference » - c'est la forme la "
        "plus courante du mensonge par mise en page."),
    "H3_CELLULE_DE_REFERENCE_GELEE_SAT": (
        "Le verdict O-P1 est rendu dans la cellule gelee avant toute mesure : bras {bras}, "
        "{point}, convention {convention}. Les autres cellules et les sensibilites sont publiees, "
        "avec leurs chiffres complets, comme lectures secondaires."),
    "H3_CELLULE_DE_REFERENCE_GELEE_NON_SAT": (
        "La cible n'est pas atteinte dans la cellule de reference et l'est ailleurs : {motif}. "
        "L'enonce publie est : CIBLE NON ATTEINTE AU POINT DE REFERENCE. Le resultat favorable "
        "obtenu ailleurs est publie a cote, nomme, avec sa cellule - il ne remplace pas le verdict "
        "et ne le nuance pas. Une cible atteinte dans une cellule choisie apres coup n'est pas une "
        "cible atteinte : c'est un resultat trouve en cherchant. Si c'est le point placeholder qui "
        "devance DIMS-v2, LE VERDICT RESTE RENDU AU POINT DESIGNE : c'est le prix, paye ici, "
        "d'avoir designe le point avant de voir les chiffres."),
    "H4_REFERENCE_SPLINK_MAXIMALE_SAT": (
        "La cible O4 est evaluee contre le MEILLEUR point de Splink, sensibilites declarees "
        "comprises ({point}, F1 = {f1}). La comparaison symetrique point a point est publiee a "
        "cote comme lecture secondaire, jamais comme repli."),
    "H4_REFERENCE_SPLINK_MAXIMALE_NON_SAT": (
        "La reference retenue n'est pas le meilleur point de Splink : {motif}. Comparer au point "
        "le plus faible d'un concurrent qui en a plusieurs est un choix, et un choix qui flatte. "
        "L'ecart est recalcule contre son meilleur point avant toute lecture de cible ; l'ecart "
        "contre le point plus faible reste publie, nomme comme tel."),
    "H5_MATRICE_COMPLETE_SAT": (
        "La matrice complete est publiee : {n_publiees} cellules, toutes presentes, aucune "
        "retiree. Les cellules en echec technique figurent avec leur statut et leur motif, jamais "
        "supprimees ni remplacees par une valeur."),
    "H5_MATRICE_COMPLETE_NON_SAT": (
        "{motif}. Une cellule absente est indiscernable, pour le lecteur, d'une cellule qui n'a "
        "jamais existe. Elles sont republiees avec statut et motif, ou l'artefact est declare "
        "incomplet en tete ; aucune cible n'est evaluee sur une matrice trouee."),
    "H6_DISTINGUABILITE_SAT": (
        "Chaque ecart est lu contre la resolution du denominateur ({resolution}) et contre le test "
        "apparie. {n_non_departages} ecart(s) sont declares « non departages a ce denominateur » "
        "et ne fondent aucune phrase d'avantage ni de retard."),
    "H6_DISTINGUABILITE_NON_SAT": (
        "Un ecart sous la resolution est lu comme un avantage ou un retard : {motif}. La phrase "
        "est remplacee par « a parite, a la resolution pres ». Cette regle interdit de celebrer "
        "une avance de 1,5 point exactement autant qu'elle interdit de dramatiser un retard de "
        "1,5 point, et elle n'est jamais invoquee d'un seul cote."),
    "H7_INVENTAIRE_FERME_SAT": (
        "L'inventaire publie coincide exactement avec l'inventaire gele : {n_systemes} systemes, "
        "{n_points} points, {n_bras} bras, {n_baselines} baselines. Aucun ajout, aucun retrait "
        "apres la mesure."),
    "H7_INVENTAIRE_FERME_NON_SAT": (
        "L'inventaire s'ecarte du gel : {motif}. L'artefact est publie AVEC cet ecart en tete ; "
        "les entrees ajoutees apres le gel sont marquees « hors pre-enregistrement » et ne comptent "
        "dans aucun verdict ; une entree retiree est reinscrite avec son statut. Il n'existe pas "
        "de raison de retirer une ligne d'un tableau comparatif qui ne soit pas une raison de la "
        "publier."),
    "H8_ANTERIORITE_DU_GEL_SAT": (
        "Anteriorite verifiable par un tiers qui n'a que le depot et l'artefact : criteres geles "
        "au commit {commit_gel} (un seul commit sur ce fichier, sha256 {sha_fichier}), anterieur "
        "au commit de mesure {commit_mesure}."),
    "H8_ANTERIORITE_DU_GEL_NON_SAT": (
        "Le code employe n'est pas celui qui a ete gele : {motif}. L'artefact est publie comme "
        "artefact ADDITIONNEL, jamais en remplacement, et porte en tete la nature exacte de la "
        "modification, sa date, et le chiffre qui etait connu au moment ou elle a ete faite. Le "
        "dispositif n'empeche pas de modifier apres coup : il rend impossible de le dissimuler."),

    # ---- cibles O-P1 ------------------------------------------------------------------------
    "O1_MARGE_BASELINE_F1_SAT": (
        "Cible O-P1 (marge F1) ATTEINTE au point designe : ecart signe {ecart} face a {baseline} "
        "({exige} exige, McNemar p = {p}). Le moteur fait significativement mieux qu'une regle "
        "simple - enonce borne a cette fixture, a ce point, en pairwise."),
    "O1_MARGE_BASELINE_F1_NON_SAT": (
        "Cible O-P1 (marge F1) NON ATTEINTE : ecart signe {ecart} face a {baseline}, en deca des "
        "{exige} vises. SUR CETTE DONNEE, LA MACHINERIE FELLEGI-SUNTER NE PAIE PAS SON COUT FACE "
        "A UNE REGLE SIMPLE. C'est un resultat de mesure, publie tel quel : ce n'est pas un defaut "
        "du moteur a corriger, pas une insuffisance de la fixture, pas un reglage a reprendre. "
        "Aucune modification du moteur, des seuils, du blocking ou de la donnee n'est demandee ni "
        "suggeree par ce constat."),
    "O2_MARGE_BASELINE_RAPPEL_SAT": (
        "Cible O-P1 (marge rappel) ATTEINTE : ecart signe {ecart} face a {baseline} ({exige} "
        "exige). Le moteur retrouve nettement plus de vraies paires qu'une regle simple sur cette "
        "donnee."),
    "O2_MARGE_BASELINE_RAPPEL_NON_SAT": (
        "Cible O-P1 (marge rappel) NON ATTEINTE : ecart signe {ecart} face a {baseline}. SUR CETTE "
        "DONNEE, LE MOTEUR NE RATTRAPE PAS SIGNIFICATIVEMENT PLUS DE VRAIES PAIRES QU'UNE REGLE "
        "SIMPLE. Publie tel quel. Si la cause est structurelle (plafond de rappel du blocking "
        "partage, {pb} vraies paires perdues pour tous), elle est nommee et chiffree dans la meme "
        "phrase, mais elle n'excuse rien : le chiffre publie reste le chiffre bout en bout."),
    "O3_ANTI_HOMME_DE_PAILLE_SAT": (
        "Garde tenue : la meilleure baseline atteint un rappel de {rappel_baseline} (>= {exige}) "
        "et aucun systeme du tableau n'est degenere. L'avance mesuree du moteur est une avance sur "
        "un adversaire reel."),
    "O3_ANTI_HOMME_DE_PAILLE_NON_SAT": (
        "Garde EN ECHEC : {motif}. L'ecart aux baselines est publie mais n'est PAS lu comme une "
        "performance : battre de 40 points un systeme qui ne trouve pas une vraie paire sur trois, "
        "ou qui declare tout MATCH, ne demontre rien. O1 et O2 sont declarees NON PROBANTES - ni "
        "atteintes, ni non atteintes. Cette troisieme issue est ecrite ici, avant la mesure, "
        "precisement pour qu'un ecart flatteur ne puisse pas etre encaisse sans son adversaire."),
    "O4_ECART_SPLINK_SAT": (
        "Cible O-P1 (credibilite face a Splink) ATTEINTE : ecart signe {ecart} (McNemar p = {p}). "
        "Le moteur se tient dans la tolerance que la these s'etait donnee. Formulation exacte et "
        "pas davantage : sur cette fixture, dans cette cellule, contre un Splink configure selon "
        "sa documentation et non regle par un expert, le moteur est {qualificatif}. Si l'ecart est "
        "sous la resolution, la phrase publiee est « a parite, a la resolution pres » : un ecart "
        "favorable trop petit n'est pas transforme en victoire."),
    "O4_ECART_SPLINK_NON_SAT": (
        "Cible O-P1 (credibilite face a Splink) NON ATTEINTE : le moteur est EN DESSOUS de Splink "
        "{v_splink} de {ecart_absolu} de F1 ({f1_moteur} contre {f1_splink}), au-dela des {exige} "
        "de tolerance. C'est le resultat de l'unite, il est publie EN TETE de l'artefact, et il "
        "repond a la question posee : sur FX_001 V1.2, a ensemble candidat impose, convention "
        "stricte et denominateur |M| entier, l'outil de reference de l'etat de l'art fait mieux "
        "que le moteur maison. Cet enonce a ete ecrit AVANT la mesure, precisement pour qu'il ne "
        "puisse etre requalifie aujourd'hui ni en « ecart a instruire », ni en « defaut a "
        "corriger », ni en « configuration Splink a revoir », ni en « fixture defavorable ». Ce "
        "que la mesure NE dit pas est publie immediatement apres, avec le meme soin : elle ne dit "
        "pas que le moteur est inutilisable, elle ne dit pas que l'ecart tiendrait sur une autre "
        "donnee, et elle ne dit pas D'OU vient l'ecart - le banc mesure une difference, il ne "
        "l'attribue pas. Les asymetries declarees restent publiees a cote, y compris celles qui "
        "jouent en faveur du moteur, mais aucune n'est invoquee pour attenuer ce constat."),
    "O5_CREDIBILITE_O_P1_SAT": (
        "VERDICT O-P1 : le moteur maison est CREDIBLE sur FX_001 V1.2, au sens defini en aveugle "
        "avant toute mesure. « Credible » ne veut pas dire « meilleur » : la definition tolerait "
        "explicitement d'etre derriere Splink de 5 points, et etre au-dessus n'ameliore pas le "
        "verdict. La portee est bornee a cette fixture, a ce point, en pairwise, sur un ensemble "
        "candidat partage issu du blocking maison."),
    "O5_CREDIBILITE_O_P1_NON_SAT": (
        "VERDICT O-P1 : le moteur n'est PAS declare credible au sens pre-enregistre. Cible(s) en "
        "echec : {liste}. Publie EN TETE de l'artefact, avant tout detail favorable. Ce verdict ne "
        "declenche, dans cette unite, AUCUNE modification du moteur, des seuils, du blocking, de "
        "la configuration Splink ni de la donnee : la comparaison a ete faite une fois, dans des "
        "conditions declarees, et son resultat est ce qu'il est. Toute evolution ulterieure "
        "produira un SECOND artefact, date et distinct ; le present artefact n'est ni retire, ni "
        "ecrase, ni republie."),
    "O5_CREDIBILITE_O_P1_NOT_CONCLUSIVE": (
        "VERDICT O-P1 : NOT_CONCLUSIVE. Un critere de plomberie ou de loyaute est en echec "
        "({liste}) : une comparaison cassee ne mesure rien, et surtout pas l'absence de "
        "credibilite. Le statut n'est donc pas « non credible » ; aucune cible n'est lue."),
}

# ===================================================================================
# ÉVALUATION — applique les critères gelés à des mesures, sans jamais les réécrire
# ===================================================================================
SATISFAIT = "SATISFAIT"
ECHEC = "ECHEC"
NON_EVALUABLE = "NON_EVALUABLE"


def sha256_criteres_ub6(chemin: Optional[str] = None) -> str:
    """Empreinte des OCTETS de ce fichier — la preuve citable de ce qui a été gelé.

    Recopiée dans l'artefact à côté du SHA du commit de gel : les deux ensemble rendent
    l'antériorité vérifiable par un tiers qui n'a que le dépôt et l'artefact.
    """
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

    Choix déclaré : une phrase de verdict ne doit jamais faire échouer la mesure qui la
    motive. Le GABARIT reste intact et comparable à `ENONCES_UB6` — c'est lui, et non la
    phrase rendue, qui atteste le pré-enregistrement.
    """

    def __missing__(self, cle):
        return "n/d"


def _critere(code: str, valeur_observee, issue: str, cle_enonce: Optional[str] = None,
             valeurs: Optional[dict] = None) -> dict:
    """Une entrée de verdict : le critère, son seuil, ce qui a été observé, l'issue.

    `enonce_retenu` porte le GABARIT verbatim (comparable à `ENONCES_UB6`), `enonce_rendu` la
    phrase avec ses valeurs substituées. Les séparer est ce qui rend le pré-enregistrement
    vérifiable : le gabarit n'a pas pu être réécrit après coup.
    """
    entree = {
        "code": code,
        "enonce_du_critere": CRITERES[code]["enonce_du_critere"],
        "famille": CRITERES[code]["famille"],
        "seuil": CRITERES[code]["seuil"],
        "valeur_observee": valeur_observee,
        "issue": issue,
    }
    if cle_enonce is None:
        cle_enonce = code + ("_SAT" if issue == SATISFAIT else "_NON_SAT")
    gabarit = ENONCES_UB6[cle_enonce]
    entree["cle_enonce"] = cle_enonce
    entree["enonce_retenu"] = gabarit
    entree["enonce_rendu"] = gabarit.format_map(_Defaut(valeurs or {}))
    return entree


def _issue(condition: Optional[bool]) -> str:
    """`None` (indéterminé) ne devient jamais un succès : il devient NON_EVALUABLE."""
    if condition is None:
        return NON_EVALUABLE
    return SATISFAIT if condition else ECHEC


def evalue_criteres_ub6(mesures: dict) -> list:
    """Applique les critères gelés aux mesures. Une entrée PAR critère déclaré.

    Chaque critère est publié avec son seuil, sa valeur observée et son issue **même quand il
    est satisfait** : un verdict qui ne montrerait que les critères en échec laisserait croire
    que les autres n'ont pas été regardés.

    ## Contrat d'entrée (`mesures`)
    Un dict assemblé par `tools/banc_ub6.py`, dont les clés sont lues ici mais jamais
    calculées ici — ce module ne mesure rien. Toute clé absente donne `NON_EVALUABLE`, jamais
    `SATISFAIT` : l'absence d'information n'est pas une information favorable.

        donnee            {content_sha256, n_records, conforme}
        determinisme      {identique: bool, sha, motif}
        systemes          {nom: {statut: "OK"|"ABSENT", motif}}
        contrat           {alerte: bool, motif}
        invariants        {ok: bool, n_vraies, n_candidates, motif}
        versions          {splink, duckdb, pandas, python}
        etancheite        {ok: bool, motif}
        substrat          {sha256, identique_pour_tous: bool, motif}
        ensemble_candidat {identique: bool, n_c0, n_completions, pb, motif}
        oracle            {chemin_unique: bool, motif}
        cles_metriques    {identiques: bool, motif}
        symetrie_reglage  {ok: bool, motif}
        supervision       {ok: bool, motif}
        config_splink     {ok: bool, motif}
        asymetries        [ {code, favorise, ...}, ... ]
        convention        {homogene: bool, n_gris, motif}
        bras_b            {publie: bool, concordant: bool, n_splink, n_moteur, motif}
        points_publies    {ok: bool, motif}
        ecarts_signes     {ok: bool, n, motif}
        cellule_reference {conforme: bool, motif}
        reference_splink  {maximale: bool, point, f1, motif}
        matrice           {complete: bool, n_publiees, motif}
        distinguabilite   {ok: bool, n_non_departages, motif}
        inventaire        {conforme: bool, motif}
        anteriorite       {ok: bool, commit_gel, commit_mesure, sha_fichier, motif}
        cibles            {o1: {...}, o2: {...}, o3: {...}, o4: {...}}
    """
    m = mesures
    sortie = []
    n_sys = len(m.get("systemes") or {}) or None

    # ---- plomberie ---------------------------------------------------------------------
    d = m.get("donnee") or {}
    ok = None if not d else (d.get("content_sha256") == CONTENT_SHA256_V1_2
                             and d.get("n_records") == N_RECORDS_ATTENDU)
    sortie.append(_critere("P1_DONNEE_INTACTE", d or None, _issue(ok),
                           valeurs={"n_systemes": n_sys, "sha": d.get("content_sha256"),
                                    "n_records": d.get("n_records"),
                                    "motif": d.get("motif") or "empreinte ou effectif divergent"}))

    det = m.get("determinisme") or {}
    sortie.append(_critere("P2_DETERMINISME", det or None, _issue(det.get("identique") if det else None),
                           valeurs={"sha": det.get("sha"), "motif": det.get("motif")}))

    sys_ = m.get("systemes") or {}
    absents = sorted(n for n, v in sys_.items() if (v or {}).get("statut") != "OK")
    sortie.append(_critere("P3_SYSTEME_A_TOURNE", {"absents": absents} if sys_ else None,
                           _issue(not absents if sys_ else None),
                           valeurs={"n_systemes": n_sys,
                                    "motif": "systeme(s) sans sortie exploitable : " + ", ".join(absents)}))

    ct = m.get("contrat") or {}
    sortie.append(_critere("P4_CONTRAT_DE_SORTIE", ct or None,
                           _issue((ct.get("alerte") is False) if ct else None),
                           valeurs={"n_systemes": n_sys, "motif": ct.get("motif")}))

    inv = m.get("invariants") or {}
    sortie.append(_critere("P5_INVARIANTS_ORACLE", inv or None,
                           _issue(inv.get("ok") if inv else None),
                           valeurs={"n_systemes": n_sys, "n_vraies": inv.get("n_vraies"),
                                    "n_candidates": inv.get("n_candidates"),
                                    "motif": inv.get("motif")}))

    v = m.get("versions") or {}
    sortie.append(_critere("P6_VERSIONS_EPINGLEES", v or None,
                           _issue((v.get("splink") == VERSION_SPLINK_EXIGEE) if v else None),
                           valeurs={"v_splink": v.get("splink"), "v_duckdb": v.get("duckdb"),
                                    "v_pandas": v.get("pandas"), "v_python": v.get("python"),
                                    "v_exigee": VERSION_SPLINK_EXIGEE}))

    et = m.get("etancheite") or {}
    sortie.append(_critere("P7_PRODUIT_INTACT", et or None, _issue(et.get("ok") if et else None),
                           valeurs={"motif": et.get("motif")}))

    # ---- loyauté -----------------------------------------------------------------------
    sub = m.get("substrat") or {}
    sortie.append(_critere("L1_MEME_DONNEE", sub or None,
                           _issue(sub.get("identique_pour_tous") if sub else None),
                           valeurs={"n_systemes": n_sys, "n_records": d.get("n_records"),
                                    "sha": sub.get("sha256"), "motif": sub.get("motif")}))

    ec = m.get("ensemble_candidat") or {}
    sortie.append(_critere("L2_MEME_ENSEMBLE_CANDIDAT", ec or None,
                           _issue(ec.get("identique") if ec else None),
                           valeurs={"n_c0": ec.get("n_c0"), "n_systemes": n_sys,
                                    "n_completions": ec.get("n_completions"), "pb": ec.get("pb"),
                                    "motif": ec.get("motif")}))

    orc = m.get("oracle") or {}
    sortie.append(_critere("L3_MEME_ORACLE", orc or None,
                           _issue(orc.get("chemin_unique") if orc else None),
                           valeurs={"n_systemes": n_sys, "motif": orc.get("motif")}))

    cm = m.get("cles_metriques") or {}
    sortie.append(_critere("L4_MEMES_METRIQUES", cm or None,
                           _issue(cm.get("identiques") if cm else None),
                           valeurs={"n_cles": len(METRIQUES_OBLIGATOIRES), "motif": cm.get("motif")}))

    sr = m.get("symetrie_reglage") or {}
    sortie.append(_critere("L5_SYMETRIE_DE_REGLAGE", sr or None,
                           _issue(sr.get("ok") if sr else None),
                           valeurs={"budget": BUDGET_REVUE_COMMUN, "motif": sr.get("motif")}))

    sp = m.get("supervision") or {}
    sortie.append(_critere("L6_AUCUNE_SUPERVISION", sp or None,
                           _issue(sp.get("ok") if sp else None),
                           valeurs={"motif": sp.get("motif")}))

    cs = m.get("config_splink") or {}
    sortie.append(_critere("L7_SPLINK_NON_SOUS_CONFIGURE", cs or None,
                           _issue(cs.get("ok") if cs else None),
                           valeurs={"motif": cs.get("motif")}))

    asy = m.get("asymetries")
    codes_gel = {a["code"] for a in ASYMETRIES_PRE_ENREGISTREES}
    codes_pub = {a.get("code") for a in (asy or [])}
    manquantes = sorted(codes_gel - codes_pub)
    sans_direction = sorted(a.get("code") for a in (asy or []) if not a.get("favorise"))
    ok_asy = None if asy is None else (not manquantes and not sans_direction)
    sortie.append(_critere("L8_ASYMETRIES_DECLAREES",
                           {"n": len(asy or []), "manquantes": manquantes,
                            "sans_direction": sans_direction} if asy is not None else None,
                           _issue(ok_asy),
                           valeurs={"n_asymetries": len(asy or []),
                                    "n_favorisent_moteur": sum(
                                        1 for a in (asy or []) if a.get("favorise") == "moteur_maison"),
                                    "motif": "manquantes : %s ; sans direction : %s"
                                             % (manquantes or "aucune", sans_direction or "aucune")}))

    cv = m.get("convention") or {}
    sortie.append(_critere("L9_CONVENTION_UNIQUE", cv or None,
                           _issue(cv.get("homogene") if cv else None),
                           valeurs={"n_vraies": inv.get("n_vraies"), "n_gris": cv.get("n_gris"),
                                    "motif": cv.get("motif")}))

    bb = m.get("bras_b") or {}
    ok_bb = None if not bb else bool(bb.get("publie") and bb.get("concordant"))
    sortie.append(_critere("L10_BRAS_B_PUBLIE", bb or None, _issue(ok_bb),
                           valeurs={"n_splink": bb.get("n_splink"), "n_moteur": bb.get("n_moteur"),
                                    "motif": bb.get("motif")}))

    # ---- honnêteté ---------------------------------------------------------------------
    pp = m.get("points_publies") or {}
    sortie.append(_critere("H1_LES_DEUX_POINTS_PUBLIES", pp or None,
                           _issue(pp.get("ok") if pp else None),
                           valeurs={"motif": pp.get("motif")}))

    es = m.get("ecarts_signes") or {}
    sortie.append(_critere("H2_ECART_SIGNE", es or None, _issue(es.get("ok") if es else None),
                           valeurs={"n_ecarts": es.get("n"), "motif": es.get("motif")}))

    cr = m.get("cellule_reference") or {}
    sortie.append(_critere("H3_CELLULE_DE_REFERENCE_GELEE", cr or None,
                           _issue(cr.get("conforme") if cr else None),
                           valeurs={"bras": CELLULE_DE_REFERENCE["bras"],
                                    "point": CELLULE_DE_REFERENCE["point"],
                                    "convention": CELLULE_DE_REFERENCE["convention"],
                                    "motif": cr.get("motif")}))

    rs = m.get("reference_splink") or {}
    sortie.append(_critere("H4_REFERENCE_SPLINK_MAXIMALE", rs or None,
                           _issue(rs.get("maximale") if rs else None),
                           valeurs={"point": rs.get("point"), "f1": rs.get("f1"),
                                    "motif": rs.get("motif")}))

    mx = m.get("matrice") or {}
    sortie.append(_critere("H5_MATRICE_COMPLETE", mx or None,
                           _issue(mx.get("complete") if mx else None),
                           valeurs={"n_publiees": mx.get("n_publiees"), "motif": mx.get("motif")}))

    di = m.get("distinguabilite") or {}
    sortie.append(_critere("H6_DISTINGUABILITE", di or None, _issue(di.get("ok") if di else None),
                           valeurs={"resolution": RESOLUTION_ECART,
                                    "n_non_departages": di.get("n_non_departages"),
                                    "motif": di.get("motif")}))

    iv = m.get("inventaire") or {}
    sortie.append(_critere("H7_INVENTAIRE_FERME", iv or None,
                           _issue(iv.get("conforme") if iv else None),
                           valeurs={"n_systemes": len(SYSTEMES), "n_points": len(POINTS),
                                    "n_bras": len(BRAS), "n_baselines": len(BASELINES),
                                    "motif": iv.get("motif")}))

    an = m.get("anteriorite") or {}
    sortie.append(_critere("H8_ANTERIORITE_DU_GEL", an or None,
                           _issue(an.get("ok") if an else None),
                           valeurs={"commit_gel": an.get("commit_gel"),
                                    "commit_mesure": an.get("commit_mesure"),
                                    "sha_fichier": an.get("sha_fichier"), "motif": an.get("motif")}))

    # ---- cibles O-P1 -------------------------------------------------------------------
    cibles = m.get("cibles") or {}

    o3 = cibles.get("o3") or {}
    ok3 = None if not o3 else bool(o3.get("ok"))
    sortie.append(_critere("O3_ANTI_HOMME_DE_PAILLE", o3 or None, _issue(ok3),
                           valeurs={"rappel_baseline": o3.get("rappel_baseline"),
                                    "exige": MIN_RAPPEL_BASELINE_NON_DEGENEREE,
                                    "motif": o3.get("motif")}))

    # O1 et O2 ne sont PAS lues si la garde anti-homme-de-paille est en echec : c'est la
    # troisieme issue, ecrite avant la mesure, qui interdit d'encaisser un ecart flatteur.
    for code, cle, exige, extra in (
            ("O1_MARGE_BASELINE_F1", "o1", MARGE_F1_BASELINES, {}),
            ("O2_MARGE_BASELINE_RAPPEL", "o2", MARGE_RAPPEL_BASELINES, {"pb": ec.get("pb")})):
        c = cibles.get(cle) or {}
        ecart = c.get("ecart")
        if ok3 is False:
            issue, obs = NON_EVALUABLE, {"motif": "NON PROBANTE : garde O3 en echec", **c}
        elif not _fini(ecart):
            issue, obs = NON_EVALUABLE, (c or None)
        else:
            issue, obs = _issue(ecart >= exige), c
        vals = {"ecart": ecart, "baseline": c.get("baseline"), "exige": exige,
                "p": c.get("mcnemar_p"), "motif": c.get("motif")}
        vals.update(extra)
        sortie.append(_critere(code, obs, issue, valeurs=vals))

    o4 = cibles.get("o4") or {}
    e4 = o4.get("ecart")
    if not _fini(e4):
        issue4 = NON_EVALUABLE
    else:
        issue4 = _issue(e4 >= TOLERANCE_F1_SPLINK)
    sortie.append(_critere("O4_ECART_SPLINK", o4 or None, issue4,
                           valeurs={"ecart": e4,
                                    "ecart_absolu": abs(e4) if _fini(e4) else None,
                                    "f1_moteur": o4.get("f1_moteur"),
                                    "f1_splink": o4.get("f1_splink"),
                                    "v_splink": v.get("splink") or VERSION_SPLINK_EXIGEE,
                                    "exige": abs(TOLERANCE_F1_SPLINK),
                                    "p": o4.get("mcnemar_p"),
                                    "qualificatif": o4.get("qualificatif"),
                                    "motif": o4.get("motif")}))
    return sortie


def lis_verdict_ub6(mesures: dict) -> dict:
    """Verdict O-P1 complet. Trois statuts, et la distinction entre deux d'entre eux compte.

    `NOT_CONCLUSIVE` (plomberie ou loyauté en échec) n'est PAS `NON_CREDIBLE` : un banc cassé
    ne mesure rien, et surtout pas l'absence de crédibilité. Confondre les deux transformerait
    une panne en résultat défavorable — ou, dans l'autre sens, permettrait de faire passer un
    résultat défavorable pour une panne.

    `aucune_recommandation_sur_la_donnee` et `aucune_modification_du_moteur` sont posés en dur :
    ce verdict, quelle que soit son issue, n'a pour destinataire ni la fixture ni le moteur.
    """
    criteres = evalue_criteres_ub6(mesures)
    par_code = {c["code"]: c for c in criteres}

    prealables = [c for c in criteres if c["famille"] in ("plomberie", "loyaute")]
    prealables_en_echec = sorted(c["code"] for c in prealables if c["issue"] != SATISFAIT)

    codes_cibles = ("O1_MARGE_BASELINE_F1", "O2_MARGE_BASELINE_RAPPEL",
                    "O3_ANTI_HOMME_DE_PAILLE", "O4_ECART_SPLINK")
    cibles_en_echec = sorted(c for c in codes_cibles if par_code[c]["issue"] != SATISFAIT)

    if prealables_en_echec:
        statut = "NOT_CONCLUSIVE"
        cle = "O5_CREDIBILITE_O_P1_NOT_CONCLUSIVE"
        liste = ", ".join(prealables_en_echec)
        issue5 = NON_EVALUABLE
    elif not cibles_en_echec:
        statut = "CREDIBLE_SUR_V1_2"
        cle = "O5_CREDIBILITE_O_P1_SAT"
        liste = ""
        issue5 = SATISFAIT
    else:
        statut = "NON_CREDIBLE_SUR_V1_2"
        cle = "O5_CREDIBILITE_O_P1_NON_SAT"
        liste = ", ".join(cibles_en_echec)
        issue5 = ECHEC

    criteres.append(_critere("O5_CREDIBILITE_O_P1",
                             {"prealables_en_echec": prealables_en_echec,
                              "cibles_en_echec": cibles_en_echec},
                             issue5, cle_enonce=cle, valeurs={"liste": liste}))

    return {
        "statut": statut,
        "criteres": criteres,
        "cibles_en_echec": cibles_en_echec,
        "prealables_en_echec": prealables_en_echec,
        "regle_de_departage": REGLE_DE_DEPARTAGE,
        "cellule_de_reference": CELLULE_DE_REFERENCE,
        "enonces_pre_enregistres_utilises": sorted({c["cle_enonce"] for c in criteres}),
        "sha256_criteres_ub6": sha256_criteres_ub6(),
        "aucune_recommandation_sur_la_donnee": True,
        "aucune_modification_du_moteur": True,
        "note_portee": (
            "Toute conclusion est bornee a FX_001 V1.2, a la cellule de reference, en pairwise, "
            "et a une configuration Splink issue de sa documentation et non reglee par un "
            "praticien experimente. Le banc mesure une difference ; il ne l'attribue pas."),
        "note_non_revision": (
            "Aucun critere n'est reecrit apres lecture des mesures. Si l'un s'avere mal pose, il "
            "est CONSERVE, son verdict est publie, et la critique est ajoutee dans 'limites' - a "
            "cote du verdict qu'elle conteste, jamais a sa place."),
        "note_transitivite": (
            "Le F1 pairwise publie ici est PESSIMISTE du point de vue du systeme complet : la "
            "recuperation par cloture transitive releve de l'unite U-B4 et n'est pas comptee. "
            "Cette reserve vaut pour TOUS les systemes du tableau, pas seulement pour le moteur."),
    }
