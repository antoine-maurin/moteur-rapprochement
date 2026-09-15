# moteur-rapprochement

**Démonstrateur de rapprochement et de déduplication d'entités** — un moteur qui
identifie, parmi des enregistrements hétérogènes, ceux qui désignent la même
entité réelle, avec une interface web interactive pour explorer les résultats.

> Projet démonstrateur. © 2026 Antoine Maurin — **Tous droits réservés** (voir [`LICENSE`](./LICENSE)).

---

## Ce que fait le moteur

À partir d'un jeu d'enregistrements, le moteur :

- **rapproche** les paires susceptibles de désigner la même entité (blocage +
  scoring de similarité) ;
- **décide** via des seuils dimensionnés et documentés (match / non-match /
  zone de doute) ;
- **regroupe** les enregistrements en entités consolidées ;
- **mesure** sa propre qualité sur un banc de référence (précision, discrimination,
  contribution des dimensions) ;
- **expose** le tout dans des surfaces web hors-ligne pour explorer les décisions.

## Sous le capot

- **Python**. Le moteur de rapprochement est **natif** — sans dépendance tierce.
  [Splink](https://github.com/moj-analytical-services/splink) sur [DuckDB](https://duckdb.org/)
  et [pandas](https://pandas.pydata.org/) ne servent qu'au **banc de mesure** (`src/benchmark`),
  pour comparer le moteur à des références externes.
- Moteur (`src/engine`, `src/scorer`, `src/pipeline`), surfaces web (`src/surfaces`,
  `serveur.py`), banc de mesure et générateurs (`tools/`, `src/generator`).
- Décisions et mesures **pré-enregistrées** : les critères sont gelés avant la
  mesure (anti-circularité), et chaque artefact publié est reproductible.

## Lancer la démonstration

### En ligne
Le démonstrateur est déployé en tant que **Hugging Face Space** (conteneur Docker) —
interface interactive, rien à installer.

### En local (Docker)
```bash
# construit et lance le serveur de démonstration (port 7860)
docker build -t moteur-rapprochement -f deploiement/Dockerfile .
docker run --rm -p 7860:7860 moteur-rapprochement
# puis ouvrir http://localhost:7860
```

### En local (Windows, sans Docker)
```bat
install.bat        REM installe l'environnement (réseau requis une fois)
lancer_demo.bat    REM lance la démonstration
```

## Tests

La suite fonctionnelle est verte de bout en bout. Quelques tests d'anti-circularité
s'appuient sur l'historique de fabrique et ne sont pas rejouables sur un historique
neuf : leur preuve vit dans l'attestation du produit, pas dans le dépôt public.

## Licence

**Propriétaire — Tous droits réservés.** Le code est visible à des fins de
démonstration et d'évaluation ; aucun droit de réutilisation, de modification ou de
redistribution n'est accordé sans autorisation écrite. Détails dans [`LICENSE`](./LICENSE).

Les composants tiers embarqués (polices sous SIL OFL ; bibliothèques Splink, DuckDB,
pandas…) restent régis par leurs propres licences.

## Auteur

**Antoine Maurin** — [antoine-maurin.com](https://antoine-maurin.com) ·
antoine@antoine-maurin.com · GitHub [@antoine-maurin](https://github.com/antoine-maurin)
