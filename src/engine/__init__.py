"""`engine` — cœur décisionnel puis consolidation en entités.

    normalisation -> blocking -> comparateurs -> décision
                                                       |
                                     clôture transitive -> fusion

Trois structures traversent la chaîne décisionnelle : `CANDIDATE_PAIR` (paire non ordonnée
issue du blocking), `COMPARISON_VECTOR` (8 composantes d'accord) et `CORRESPONDENCE` (le
verdict, une par paire). Le point d'entrée est `execute_moteur`. En aval, `clustering`
regroupe les CORRESPONDENCE en entités par clôture transitive, et `fusion` consolide chaque
entité en enregistrement doré.

## Frontière interne, et elle est BILATÉRALE
L'aval **consomme** les verdicts du cœur ; il ne les refait pas. Aucun module de clustering
ou de fusion ne redéfinit la normalisation, le blocking, la comparaison ou la décision — un
second chemin de décision rendrait le moteur ininterprétable. Cette frontière est tenue par
un test dans chaque sens : `tests/test_engine.py` interdit à la zone moteur de construire ce
qui ne lui appartient pas, `tests/test_clustering.py` interdit à l'aval de reconstruire le cœur.

## La revue du doute est DANS le paquet, mais PAS dans cette surface
Les modules `llm_client` et `llm_review` vivent ici : la revue est construite. Elle reste
**délibérément absente de `__all__`** — elle s'applique en AVAL, sur la sortie du bloc B2,
et un consommateur qui la veut l'importe nommément (`from engine.llm_review import …`).
Ne pas la réexporter rend vérifiable la proposition « la surface du cœur est inchangée »,
au lieu de la laisser à l'appréciation d'un relecteur — c'est ce qu'éprouve la suite.

Hors de ce paquet, et pour de bon : la mesure de qualité (`src/scorer/`, indépendante
par construction — c'est la condition de non-circularité de la preuve) et la comparaison à
l'état de l'art (`src/benchmark/`), qui importe ce paquet sans que l'inverse soit
jamais vrai. L'orchestration bout-en-bout vit dans `src/pipeline/` et ne fait que
CHAÎNER ce paquet : elle n'y ajoute aucune décision.
"""
from .engine import ParametresMoteur, execute_moteur, sortie_canonique
from .normalize import ATTRIBUTS_COMPARE, normalise_record, normalise_records
from .blocking import (genere_paires_candidates, soundex, cles_de_blocking,
                       PASSES_DEFAUT, PASSES_RETIREES_DU_DEFAUT)
from .compare import (ACCORD_FORT, ACCORD_PARTIEL, DESACCORD, INDETERMINE_MANQUANT,
                      NIVEAUX, NIVEAUX_INFORMATIFS, COMPOSANTES,
                      composantes, vecteur_comparaison, vecteurs_comparaison)
from .decide import (MATCH, NON_MATCH, ZONE_GRISE, VERDICTS, GRAINE_EM_SCELLEE,
                     estime_m_u, oriente_classes, table_de_poids, agregat,
                     verdict_3_zones, correspondance, correspondances)
from .threshold_sizing import (FRONTIERE_NEUTRE, BUDGET_REVUE_DEFAUT,
                               budget_depuis_debit, statistiques_r, dimensionne_seuils,
                               dimensionne_depuis_correspondances)
# Clustering et fusion — la surface exportée est EXACTEMENT celle que chaque module déclare dans son
# `__all__` : le paquet ne décide pas à la place de l'unité ce qui est public chez elle, et
# ne promeut donc aucun auxiliaire interne au rang d'API par simple commodité d'import.
from .clustering import (cle_paire, est_liante, aretes_liantes, univers_depuis_records,
                         cloture_transitive, couverture_transitive)
from .fusion import (MAJORITE, COMPLETUDE, SOURCE_PRIORITAIRE, ORDRE_CANONIQUE, REGLES,
                     REGLE_TERMINALE, AUCUN_CANDIDAT, CANDIDAT_UNIQUE, MOTIFS,
                     CODES_SELECTION, POLITIQUE_DEFAUT, POLITIQUE_COMPLETUDE_DABORD,
                     PARAMETRES_NON_CALIBRES,
                     valide_politique, valeurs_candidates, regle_majorite, regle_completude,
                     regle_source_prioritaire, regle_ordre_canonique, forme_retenue,
                     arbitre_attribut, trace_selection, consolide_entite, consolide_partition)

__all__ = [
    # orchestration
    "ParametresMoteur", "execute_moteur", "sortie_canonique",
    # normalisation
    "ATTRIBUTS_COMPARE", "normalise_record", "normalise_records",
    # blocking
    "genere_paires_candidates", "soundex", "cles_de_blocking",
    "PASSES_DEFAUT", "PASSES_RETIREES_DU_DEFAUT",
    # comparateurs
    "ACCORD_FORT", "ACCORD_PARTIEL", "DESACCORD", "INDETERMINE_MANQUANT",
    "NIVEAUX", "NIVEAUX_INFORMATIFS", "COMPOSANTES",
    "composantes", "vecteur_comparaison", "vecteurs_comparaison",
    # décision
    "MATCH", "NON_MATCH", "ZONE_GRISE", "VERDICTS", "GRAINE_EM_SCELLEE",
    "estime_m_u", "oriente_classes", "table_de_poids", "agregat", "verdict_3_zones",
    "correspondance", "correspondances",
    # dimensionnement des seuils (provisoire)
    "FRONTIERE_NEUTRE", "BUDGET_REVUE_DEFAUT", "budget_depuis_debit",
    "statistiques_r", "dimensionne_seuils", "dimensionne_depuis_correspondances",
    # clôture transitive. `clustering.MATCH_APRES_REVUE` et `JETONS_LIANTS` sont
    # DÉLIBÉRÉMENT absents : la règle « la revue n'entre pas dans cette surface » est gelée, et un
    # jeton portant son nom l'y ferait entrer par la bande. Le consommateur qui en a besoin
    # les lit sur le module (`from engine import clustering`), comme la chaîne bout-en-bout le fait.
    "cle_paire", "est_liante", "aretes_liantes", "univers_depuis_records",
    "cloture_transitive", "couverture_transitive",
    # fusion en enregistrements dorés
    "MAJORITE", "COMPLETUDE", "SOURCE_PRIORITAIRE", "ORDRE_CANONIQUE", "REGLES",
    "REGLE_TERMINALE", "AUCUN_CANDIDAT", "CANDIDAT_UNIQUE", "MOTIFS", "CODES_SELECTION",
    "POLITIQUE_DEFAUT", "POLITIQUE_COMPLETUDE_DABORD", "PARAMETRES_NON_CALIBRES",
    "valide_politique", "valeurs_candidates", "regle_majorite", "regle_completude",
    "regle_source_prioritaire", "regle_ordre_canonique", "forme_retenue",
    "arbitre_attribut", "trace_selection", "consolide_entite", "consolide_partition",
]
