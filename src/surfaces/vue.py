# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Le MODÈLE D'AFFICHAGE — une seule vérité, lue une seule fois (G4).

`construit()` rend l'objet unique dont les trois surfaces tirent tout ce qu'elles montrent.
C'est ce qui rend `G4` vrai **par construction** plutôt que par vigilance : la Vitrine et la
Salle des machines ne lisent pas deux fois le même artefact — elles lisent le même objet. Il
n'existe aucun chemin par lequel le chiffre d'affiche de l'une et sa contrepartie dans l'autre
pourraient diverger, parce qu'il n'y a qu'une valeur et deux façons de l'écrire.

## Ce que ce module ne fait pas
Il ne calcule **aucune métrique**. Précision, rappel, F1, écart, p de McNemar : tout est lu.
La seule arithmétique qu'on trouve ici est de la **mise en forme** — multiplier un taux par
cent, en prendre la dizaine entière — appliquée à une valeur déjà mesurée. Recomposer un F1 à
partir d'une précision et d'un rappel serait un recomptage, donc une violation de la
non-circularité ; ça n'arrive nulle part, et un test l'éprouve.

Il ne compose pas non plus les phrases de verdict. Les artefacts portent des **énoncés
pré-enregistrés**, gelés AVANT la mesure (`verdict.criteres[*].enonce_rendu`,
`cibles.o4.qualificatif`) : les rendre verbatim est le seul moyen de garantir qu'un libellé de
surface ne contredit pas le libellé sous lequel la mesure a été publiée. Une paraphrase, même
fidèle, rouvrirait la question.

## Le point de fonctionnement, et pourquoi il n'y en a qu'un
Le banc publie deux points (`point_1_a_priori_declare`, `point_2_budget_de_revue_egal`) et
deux bras. Le moteur est MEILLEUR au point 1 (F1 0,9267) qu'au point 2 (F1 0,9194) — et c'est
le point 2 qui est la cellule de référence, parce que c'est celle qui a été pré-enregistrée.
Afficher le point 1 à côté d'un écart calculé au point 2 donnerait deux chiffres justes et une
lecture fausse. `CELLULE_MOTEUR` fige donc le point retenu, une fois, ici.
"""
from __future__ import annotations

import math

from . import lecture

__all__ = [
    "CELLULE_MOTEUR", "CELLULE_SPLINK_DEFAUT", "CELLULE_SPLINK_REFERENCE", "CELLULE_BASELINE",
    "JARGON_INTERDIT", "FABRICATION_PAR_IA_INTERDITE", "construit",
]

#: LA cellule du moteur : celle qui a été pré-enregistrée comme référence, et contre laquelle
#: l'écart O4 est lu. `(systeme, point, bras)` — jamais un index.
CELLULE_MOTEUR = ("moteur_maison", "point_2_budget_de_revue_egal", "A_univers_appari")

#: Splink dans sa configuration par défaut. C'est la ligne que la maquette montrait seule.
CELLULE_SPLINK_DEFAUT = ("splink_4_0_16", "point_1_a_priori_declare", "A_univers_appari")

#: Splink dans sa MEILLEURE configuration, toutes sensibilités confondues : le comparateur
#: réellement retenu (`ecarts.reference_splink.point_retenu`), et donc la lecture la plus dure
#: pour le moteur. C'est contre CELLE-CI que valent l'écart de F1 et le p de McNemar. Les
#: afficher sous la cellule par défaut donnait deux nombres qui ne se recoupaient pas.
CELLULE_SPLINK_REFERENCE = ("splink_4_0_16", "SENS_3_cp_avec_niveau_departement", "sensibilite")

#: La meilleure baseline en F1 — le « comptage naïf », sans pondération.
CELLULE_BASELINE = ("B4_concordance_3_sur_8", "point_2_budget_de_revue_egal", "A_univers_appari")

#: La meilleure baseline en RAPPEL, qui n'est PAS la même cellule. Le maximum de F1 et celui
#: de rappel viennent de deux points différents, et chaque cible est lue contre le meilleur
#: comparateur pour SA métrique. Afficher le F1 de l'une sous l'écart de l'autre attacherait
#: un nombre juste à la mauvaise affirmation.
CELLULE_BASELINE_RAPPEL = ("B4_concordance_3_sur_8", "point_1_a_priori_declare",
                           "A_univers_appari")

#: Vocabulaire proscrit en Vitrine. Scanné sur le HTML rendu, pas sur la source : ce
#: qui compte est ce que le lecteur voit.
#:
#: ## « IA » n'y figure plus, et c'est une correction de doctrine, pas un relâchement
#: La règle corrigée (briefing de clôture, point 5) sépare deux choses que le bannissement
#: confondait :
#:
#:   - « IA » pour la FABRICATION du code — « codé par IA », « généré par IA » — reste
#:     interdit : le produit est conçu et vérifié par un ingénieur, et le prétendre
#:     autrement serait faux ;
#:   - « IA » pour les CAPACITÉS du produit est permis, et c'est un argument d'achat : lire
#:     un document dégradé, comprendre un libellé, trancher un cas ambigu, expliquer en
#:     clair. L'acheteur connaît « IA » ; il ne connaît pas « LLM », qui reste proscrit.
#:
#: Un scan de texte ne peut pas distinguer les deux — les deux contiennent « IA ». Il ne
#: cherche donc plus le mot du tout, plutôt que de simuler une détection de contexte qu'il
#: n'a pas. L'absence de revendication de code fabriqué par IA est tenue par la copie
#: elle-même (elle dit l'inverse) et par un oracle qui cherche les LOCUTIONS complètes, pas
#: le mot isolé — voir `tests/test_surfaces.py`.
#:
#: Ce que le scan garde, intact : les noms de concurrents, et le jargon R&D que le parcours
#: acheteur n'a pas à porter.
JARGON_INTERDIT = (
    "précision", "precision", "rappel", "f1", "fellegi", "sunter", "blocking",
    "clustering", "llm", "splink", "mcnemar", "bayes", "em",
    "apprentissage automatique", "réseau de neurones",
    "reseau de neurones", "machine learning", "deep learning", "gpt", "openai",
    "dedupe", "duckdb", "record linkage", "entity resolution",
)

#: Les participes qui, suivis d'un agent, attribuent la FABRICATION à quelqu'un. La liste a
#: été complétée après une revue qui a montré son trou le plus béant : « conçu » y manquait,
#: alors que c'est le mot même que la copie emploie pour dire l'inverse (« conçu et vérifié
#: par un ingénieur »). Une garde qui rate la négation exacte de la phrase qu'elle protège ne
#: garde rien.
_PARTICIPES_DE_FABRICATION = (
    "codé", "code", "généré", "genere", "écrit", "ecrit", "développé", "developpe",
    "fabriqué", "fabrique", "programmé", "programme", "rédigé", "redige",
    "conçu", "concu", "créé", "cree", "réalisé", "realise", "construit", "bâti", "bati",
    "produit", "fait", "implémenté", "implemente", "assemblé", "assemble",
)

#: Les façons d'écrire l'agent. L'apostrophe existe en deux caractères, et une garde qui
#: n'en connaîtrait qu'un se contournerait au clavier.
_AGENTS_IA = tuple(
    f"par {determinant}{terme}"
    for determinant in ("", "une ", "l'", "l’", "de l'", "de l’")
    for terme in ("ia", "intelligence artificielle")
)

#: Les locutions qui revendiqueraient un code FABRIQUÉ par une IA. Interdites partout, y
#: compris au dossier technique : c'est la seule affirmation sur l'IA que ce projet ne peut
#: pas soutenir, et un dossier qui la porterait démonterait la Vitrine qui affirme l'inverse.
#:
#: Ce sont des LOCUTIONS entières, jamais le mot seul : c'est ce qui rend la garde décidable
#: là où un scan de « IA » ne l'était pas. « Notre IA lit vos factures » et « notre code est
#: généré par IA » ne diffèrent pas par un mot mais par une phrase.
#:
#: Deux limites, nommées plutôt que tues. **Elle est un peu large** : « un rapport généré par
#: l'IA » — une capacité légitime — tomberait aussi. C'est le sens sûr de l'erreur : elle
#: force une reformulation, elle ne laisse jamais passer une fausse affirmation, et aucune
#: copie du produit n'emploie ces tournures. **Elle est littérale** : une paraphrase
#: (« nous n'avons pas écrit une ligne nous-mêmes ») lui échappe, et c'est la relecture
#: humaine qui la couvre — le briefing de clôture le dit ainsi.
FABRICATION_PAR_IA_INTERDITE = tuple(sorted(
    f"{participe}{accord} {agent}"
    for participe in _PARTICIPES_DE_FABRICATION
    for accord in ("", "e", "s", "es")
    for agent in _AGENTS_IA
))

#: La mention d'IA, bornée en mot : « média » et « diagnostic » n'en sont pas une.
MENTION_D_IA = r"\b(?:ia|intelligences?\s+artificielles?)\b"

#: La TROISIÈME règle de vocabulaire, celle qui n'était jusqu'ici qu'écrite en commentaire : l'IA
#: se vend comme une CAPACITÉ, jamais comme ce qui fait le résultat. La performance vient du
#: moteur ; l'apport de la revue par IA est mesuré, et il vaut zéro
#: (`artifacts/contribution_llm.json`). Une phrase qui donne le résultat à l'IA serait donc
#: fausse au regard du banc du projet lui-même — c'est la plus dangereuse des trois, et
#: c'était la seule qu'aucun oracle ne tenait.
#:
#: La garde est une CO-OCCURRENCE dans une même PHRASE, pas un vocabulaire : « notre IA lit
#: vos factures » et « notre IA porte 92 % du résultat » ne diffèrent par aucun mot du
#: lexique de l'IA, mais par la présence d'un marqueur de résultat dans le même souffle.
#:
#: Ce que la liste ne contient PAS, et c'est un choix mesuré : les NOMS DE MÉTRIQUES
#: (« précision », « rappel », « F1 »). Sur la Vitrine et le Bac à sable ils sont déjà
#: interdits par `JARGON_INTERDIT` — les remettre ici serait du poids mort ; sur la Salle des
#: machines ils sont OBLIGATOIRES (`tests/test_surfaces.py`), et un marqueur qui rougit sur
#: le vocabulaire exigé d'une page ne garde pas cette page, il l'interdit.
MARQUEURS_DE_PERFORMANCE = (
    r"\d+\s*%",
    r"\bsur (?:dix|10)\b",
    r"\bperformances?\b",
    r"\bparit[ée]s?\b",
    r"\bmieux que\b",
    r"\bniveau des\b",
    r"[ée]tat de l'art",
    r"gr[âa]ce [àa]",
    # L'adverbe intercalé compte : la copie écrivait « fait VRAIMENT la différence », et un
    # motif littéral « fait la différence » ne l'aurait pas vue. Une garde qui rate la phrase
    # pour laquelle on l'écrit ne garde rien.
    r"fait (?:\w+ )?la diff[ée]rence",
    r"\bdoit (?:sa|son|ses)\b",
    r"permet d'atteindre",
    r"\brend possible\b",
    r"\best la raison\b",
    r"\bporte\b.{0,25}\b(?:r[ée]sultats?|scores?|chiffres?)\b",
)

#: L'exemption de DÉNÉGATION, sans laquelle la garde interdirait la phrase même que la
#: doctrine réclame. Mesuré avant de l'écrire : « la performance vient du moteur, pas de
#: l'IA » porte `performances?` et rougirait — l'énoncé littéral de la règle serait refusé
#: par l'oracle censé la tenir, et la face de vente se retrouverait à ne pouvoir dire « IA »
#: qu'à condition de n'en rien dire de mesurable, y compris pour le nier. C'est la
#: ré-interdiction par le côté honnête.
#:
#: Les locutions sont ENTIÈRES et rattachées à l'IA, jamais des mots isolés : un simple
#: « sans » dans la liste ferait passer « l'IA porte 92 % du résultat, sans exception ».
DENEGATIONS_D_ATTRIBUTION = (
    r"\bpas (?:de )?l['’]ia\b",
    r"\bpas (?:de )?l['’]intelligence artificielle\b",
    r"\bsans (?:ia|intelligence artificielle)\b",
    r"\bni (?:ia|intelligence artificielle)\b",
    r"\bne (?:vient|viennent|doit|doivent) (?:rien )?(?:pas )?(?:de |à )?l['’]ia\b",
    r"\baucun apport\b",
    r"\bapport (?:mesur[ée]|nul)\b",
    r"\bvaut z[ée]ro\b",
    r"\bn['’]a (?:rien )?(?:modifi[ée]|chang[ée])\b",
    r"\bcontribution nulle\b",
)


#: Depuis le briefing de clôture (point 1), la comparaison au marché a QUITTÉ la face de
#: vente — plus de tableau comparatif, plus de nom de concurrent, plus de « au niveau des
#: meilleurs ». Les surfaces de vente publient les métriques du moteur, seules, et n'ont donc
#: plus besoin de nommer personne : la table `LIBELLES_VENTE` qui vivait ici a été retirée
#: avec son dernier lecteur. Elle n'était pas inoffensive une fois orpheline — son repli
#: rendait l'IDENTIFIANT du concurrent, et un gabarit qui l'aurait rebranchée par mégarde
#: aurait affiché « splink_4_0_16 » en toutes lettres sur la Vitrine.
#:
#: La comparaison n'a pas disparu pour autant : elle vit INTACTE au dossier technique, qui
#: NOMME les systèmes (`libelle_technique`) — un évaluateur doit pouvoir la reproduire, et
#: une cellule anonyme n'est pas reproductible. C'est ce qui préserve `O5` et la loyauté là où ils
#: comptent. Le déplacement porte sur l'emplacement, jamais sur le contenu.
def _metriques(banc: dict, identite: tuple) -> dict:
    """Les trois métriques d'une cellule, LUES. Convention `stricte` uniquement."""
    cel = lecture.cellule(banc, *identite)
    metriques = cel["metriques"]
    return {
        "systeme": cel["systeme"],
        "libelle_technique": cel["systeme"],
        "point": cel["point"],
        "bras": cel["bras"],
        "convention": cel["convention"],
        "precision": lecture.valeur(metriques, "precision"),
        "rappel": lecture.valeur(metriques, "rappel_bout_en_bout"),
        "f1": lecture.valeur(metriques, "f1_bout_en_bout"),
        "n_zone_grise": lecture.valeur(metriques, "n_zone_grise"),
        "n_candidates": lecture.valeur(metriques, "n_candidates"),
        "ic_rappel": cel.get("ic_wilson_95", {}).get("rappel_bout_en_bout"),
    }


def _enonces_pre_enregistres(banc: dict) -> dict:
    """Les phrases de verdict gelées avant mesure, indexées par code de critère."""
    return {critere["code"]: critere.get("enonce_rendu")
            for critere in banc.get("verdict", {}).get("criteres", [])
            if isinstance(critere, dict) and "code" in critere}


def _chiffre_affiche(rappel: float) -> dict:
    """Le chiffre d'affiche, dans ses trois registres, depuis UNE valeur.

    Décision owner du 2026-09-06 : la Vitrine dit « plus de N doublons sur 10 » et la Salle des
    machines publie la valeur exacte. Le briefing de clôture y ajoute un troisième registre,
    la phrase de la Salle des machines : « environ N % des doublons ». Ce sont trois écritures
    de la MÊME mesure, jamais trois mesures — c'est la totalité de la preuve `G4`, et elle
    tient dans cette fonction.

    `math.floor` et non `round` : « plus de 9 sur 10 » doit rester vrai. Arrondir donnerait
    « plus de 9 » pour un rappel de 0,87, ce qui serait faux. Tronquer ne peut que sous-estimer,
    et une promesse qui sous-estime reste tenue. `pourcent_entier` suit la même règle : le
    rappel mesuré vaut 0,9262, la page dit « environ 92 % » et non « 93 % ».

    ## Le « 100 % » de la Salle des machines n'est PAS un quatrième registre d'ici
    La phrase de la Salle des machines dit « Le 100 %, c'est vous qui le tenez ». Ce nombre
    n'a pas sa place dans cette fonction, et pas pour une raison de style : `chiffre_affiche`
    ne porte QUE des écritures du rappel mesuré, et c'est de cette pureté que `G4` tire sa
    force. Y glisser un 100 mêlerait deux grandeurs sous une seule clé — le taux que le
    moteur atteint seul, et la complétude que l'arbitrage humain tient — et la première
    relecture pressée les lirait comme la même.

    Le 100 vit donc sous `controle_humain`, à part, avec la raison pour laquelle il n'est pas
    une mesure. Une écriture antérieure l'exposait ici sous le nom `echelle_pourcent` ; le
    nom disait « échelle » là où le sens est « ce dont vous gardez la main », et c'est ce
    flou qu'on retire.
    """
    return {
        "valeur_brute": rappel,
        "sur_dix": math.floor(rappel * 10),
        "pourcent": rappel * 100,
        "pourcent_entier": math.floor(rappel * 100),
    }


def construit(artefacts=None, racine: str = ".") -> dict:
    """Le modèle d'affichage complet. Tout ce qui s'affiche vient d'ici, et de nulle part ailleurs."""
    artefacts = artefacts or lecture.charge(racine)
    banc = artefacts["banc"]
    dims = artefacts["dims"]
    contribution = artefacts["contribution"]
    demo = artefacts["demonstration"]

    moteur = _metriques(banc, CELLULE_MOTEUR)
    splink_defaut = _metriques(banc, CELLULE_SPLINK_DEFAUT)
    splink_reference = _metriques(banc, CELLULE_SPLINK_REFERENCE)
    baseline = _metriques(banc, CELLULE_BASELINE)
    baseline_rappel = _metriques(banc, CELLULE_BASELINE_RAPPEL)
    enonces = _enonces_pre_enregistres(banc)

    o4 = lecture.valeur(banc, "cibles.o4")
    o1 = lecture.valeur(banc, "cibles.o1")
    o2 = lecture.valeur(banc, "cibles.o2")
    mesure_revue = lecture.valeur(contribution, "mesure_dims_v2.mesures")

    return {
        # --- Le chiffre d'affiche, une fois, pour les deux surfaces (G4) ----------------
        "chiffre_affiche": _chiffre_affiche(moteur["rappel"]),

        # --- La complétude que l'arbitrage humain tient, qui n'est PAS une mesure --------
        # Deux grandeurs, et la Salle des machines les sépare à l'écran plutôt que de les
        # additionner : le rappel dit ce que le MOTEUR retrouve seul (mesuré, lu du banc) ;
        # ce 100 dit que la DÉCISION reste entière entre les mains de l'utilisateur — le
        # moteur tranche l'essentiel, présente les cas de doute, et c'est lui qui arbitre.
        #
        # Ce n'est donc pas une affirmation de performance, et rien ici ne prétend que le
        # moteur atteindrait 100 % : la page dit qui tient la complétude, pas qui l'atteint.
        # Le « 6 / 301 » du dossier technique borne le rappel du MOTEUR SEUL ; il ne parle pas
        # de cette grandeur-ci, et il n'y a donc rien à recouper entre les deux.
        #
        # Il passe par le modèle et non par le gabarit pour une raison de garde : aucun
        # gabarit n'écrit de nombre, et l'oracle qui lit la SOURCE des gabarits continue de
        # refuser tout littéral. Côté rendu, le pourcentage n'est admis que dans l'élément
        # que le gabarit MARQUE comme non-mesure, et un oracle vérifie que c'est le seul —
        # l'échappatoire est unique, visible, et sa valeur est fixée ici.
        "controle_humain": {
            "completude_pourcent": 100,
            "note": ("complétude tenue par l'arbitrage humain, non mesurée et non "
                     "mesurable ici : c'est une propriété du dispositif de décision, pas "
                     "un taux de détection du moteur"),
        },

        #: Les huit attributs comparés, dans l'ordre du moteur. Lus, pas importés.
        "champs_compares": lecture.valeur(demo, "provenance.champs_compares"),

        # --- Le banc ---------------------------------------------------------------------
        "moteur": moteur,
        "splink_defaut": splink_defaut,
        "splink_reference": splink_reference,
        "baseline": baseline,
        "versions": lecture.valeur(banc, "provenance.versions"),

        "parite": {
            "ecart_f1": lecture.valeur(o4, "ecart"),
            "ecart_en_points": lecture.valeur(banc, "ecarts.o4_f1_vs_splink.en_points"),
            "mcnemar_p": lecture.valeur(o4, "mcnemar_p"),
            "seuil": lecture.valeur(o4, "seuil"),
            # Énoncé gelé AVANT mesure : « a parite, a la resolution pres ». Rendu verbatim.
            "qualificatif": lecture.valeur(o4, "qualificatif"),
            "point_retenu": lecture.valeur(banc, "ecarts.reference_splink.point_retenu"),
            "regle_du_comparateur": lecture.valeur(banc, "ecarts.reference_splink.regle"),
        },

        # --- Les cibles, y compris celles qui échouent -----------------------------------
        "cibles": [
            {
                "code": "O1",
                "libelle": "marge de F1 sur la meilleure baseline",
                "seuil": lecture.valeur(o1, "seuil"),
                "ecart": lecture.valeur(o1, "ecart"),
                "en_points": lecture.valeur(banc, "ecarts.o1_f1_vs_baselines.en_points"),
                "atteinte": lecture.valeur(
                    banc, "cibles.lecture_brute.o1_f1_vs_meilleure_baseline.atteinte"),
                "reference": lecture.valeur(o1, "baseline"),
                "reference_metrique": "F1",
                "reference_valeur": baseline["f1"],
                "valeur_moteur": moteur["f1"],
                "enonce": enonces["O1_MARGE_BASELINE_F1"],
            },
            {
                "code": "O2",
                "libelle": "marge de rappel sur la meilleure baseline",
                "seuil": lecture.valeur(o2, "seuil"),
                "ecart": lecture.valeur(o2, "ecart"),
                "en_points": lecture.valeur(banc, "ecarts.o2_rappel_vs_baselines.en_points"),
                "atteinte": lecture.valeur(
                    banc, "cibles.lecture_brute.o2_rappel_vs_meilleure_baseline.atteinte"),
                "reference": lecture.valeur(o2, "baseline"),
                "reference_metrique": "rappel",
                "reference_valeur": baseline_rappel["rappel"],
                "valeur_moteur": moteur["rappel"],
                "enonce": enonces["O2_MARGE_BASELINE_RAPPEL"],
            },
            {
                "code": "O4",
                "libelle": "position face à l'état de l'art",
                "seuil": lecture.valeur(o4, "seuil"),
                "ecart": lecture.valeur(o4, "ecart"),
                "en_points": lecture.valeur(banc, "ecarts.o4_f1_vs_splink.en_points"),
                "atteinte": lecture.valeur(
                    banc, "cibles.lecture_brute.o4_f1_vs_meilleur_splink.atteinte"),
                "reference": lecture.valeur(banc, "ecarts.reference_splink.point_retenu"),
                "reference_metrique": "F1",
                "reference_valeur": splink_reference["f1"],
                "valeur_moteur": moteur["f1"],
                # Le code réel est `O4_ECART_SPLINK`. Sous un nom inventé, `.get` rendait
                # `None` en silence et la SEULE cible atteinte — celle qui porte tout le
                # positionnement — perdait son énoncé gelé, tandis que les deux cibles en
                # échec gardaient le leur. La lecture des artefacts se fait par clé exacte
                # ailleurs dans ce module ; ici un `.get` tolérant masquait la faute.
                "enonce": enonces["O4_ECART_SPLINK"],
            },
        ],
        "verdict_global": {
            "statut": lecture.valeur(banc, "verdict.statut"),
            "cibles_en_echec": lecture.valeur(banc, "verdict.cibles_en_echec"),
        },

        # --- Le point de fonctionnement --------------------------------------------------
        "point": {
            "t_mu": lecture.valeur(dims, "seuils_dimensions.t_mu"),
            "t_lambda": lecture.valeur(dims, "seuils_dimensions.t_lambda"),
            "taille_zone_grise": lecture.valeur(dims, "seuils_dimensions.taille_zone_grise"),
            "budget_vise": lecture.valeur(dims, "seuils_dimensions.budget_vise"),
            "provisoire": lecture.valeur(dims, "seuils_dimensions.provisoire"),
            "methode": lecture.valeur(dims, "seuils_dimensions.methode"),
            "n_paires_notees": lecture.valeur(dims, "derivation.n_paires_notees"),
            "gap": lecture.valeur(dims, "gap"),
        },

        # --- La revue de la zone grise ---------------------------------------------------
        "revue": {
            "plafond": lecture.valeur(mesure_revue, "plafond.n_vraies_en_zone_grise"),
            "n_zone_grise": lecture.valeur(mesure_revue, "plafond.n_zone_grise"),
            "delta_rappel": lecture.valeur(mesure_revue, "effets.delta_rappel"),
            "delta_f1": lecture.valeur(mesure_revue, "effets.delta_f1"),
            "valeur_d_une_paire_en_rappel": lecture.valeur(
                mesure_revue, "incertitude.valeur_d_une_paire_en_rappel"),
            "n_instruites": lecture.valeur(mesure_revue, "cout.n_instruites"),
            "note_plafond": lecture.valeur(mesure_revue, "plafond.note"),
            # LA distinction obligatoire du mandat : « la chaine n'a rien produit » n'est pas
            # « un adjudicateur a examine et rien trouve ». Le texte est celui de l'artefact.
            "distinction": lecture.valeur(
                contribution,
                "mesure_dims_v2.critique_du_critere_gele.0.consequence_sur_cette_mesure"),
        },

        # --- Les asymétries, avec leur sens ----------------------------------------------
        "asymetries": [
            {
                "code": a["code"],
                "favorise": a["favorise"],
                "quelle": a["quelle"],
                "parade": a.get("parade"),
                # A1 cite « 373 paires » dans un texte GELÉ dont l'artefact déclare lui-même
                # qu'il est faux, la mesure définitive donnant autre chose. Sans `mesure`, la
                # surface laissait à l'écran un nombre qu'une de ses propres réserves
                # désavoue, en renvoyant le lecteur au JSON pour la correction.
                "mesure": a.get("mesure"),
            }
            for a in lecture.valeur(banc, "asymetries_declarees")
        ],

        # --- Reproductibilité --------------------------------------------------------------
        "reproductibilite": {
            "graine_em": lecture.valeur(demo, "provenance.graine_em"),
            "empreinte_e2e": lecture.valeur(
                contribution, "mesure_dims_v2.sortie_e2e_content_sha256"),
            "empreinte_fixture": lecture.valeur(demo, "provenance.fixture.content_sha256"),
            "determinisme_identique": lecture.valeur(banc, "determinisme.identique"),
            "commit": lecture.valeur(demo, "provenance.commit"),
            "version_python": lecture.valeur(demo, "provenance.version_python"),
        },

        # --- Réserves : les six limites publiées, pas trois -------------------------------
        "reserves": lecture.valeur(banc, "limites"),

        # --- L'indépendance du scoreur, montrée et non seulement appliquée ----------------
        "independance": {
            "verite_terrain_lue_au_dimensionnement": lecture.valeur(
                dims, "cc1.verite_terrain_lue"),
            "note": lecture.valeur(dims, "cc1.note"),
            "modules_importes": lecture.valeur(dims, "cc1.modules_importes"),
        },

        # --- Les scénarios de démonstration, calculés au build ------------------------------
        "scenarios": lecture.valeur(artefacts["scenarios"], "scenarios"),
        "scenarios_provenance": lecture.valeur(artefacts["scenarios"], "provenance"),

        # --- Les sorties du moteur, figées -------------------------------------------------
        "demonstration": {
            "cas_heros": lecture.valeur(demo, "cas_heros"),
            "extrait": lecture.valeur(demo, "extrait_demonstration"),
            "file_a_verifier": lecture.valeur(demo, "file_a_verifier"),
            "population": lecture.valeur(demo, "population"),
        },
    }
