# Environnement DEV embarqué — `moteur-rapprochement`

Amorçage reproductible de l'environnement Python du démonstrateur. Trois fichiers :

| Fichier | Rôle |
|---|---|
| `requirements.txt` | Manifeste des dépendances **directes** (source unique déclarative). Contient le seul pin dur imposé : `splink==4.0.16`. |
| `install.bat` | Installeur **double-clic**. Bootstrappe `uv`, récupère le Python cible, crée un environnement isolé, génère un lock à hashes, installe, vérifie. |
| `requirements.lock` | **Généré au 1ᵉʳ run** par `install.bat` : versions exactes résolues + hashes cryptographiques (reproductibilité). À conserver/versionner. |

## Utilisation

1. **Double-cliquer `install.bat`** (ou l'exécuter depuis un terminal dans ce dossier).
2. Laisser l'installeur dérouler ses 6 étapes. La fenêtre reste ouverte à la fin (succès ou échec détaillé).
3. Pour travailler ensuite dans l'environnement, dans un terminal :
   ```
   call .venv\Scripts\activate.bat
   ```

Ce que fait `install.bat`, dans l'ordre : (1) installe `uv` s'il est absent ; (2) récupère **Python 3.12** via `uv` — pas besoin d'avoir Python préinstallé ; (3) crée l'environnement isolé `.venv` ; (4) résout les dépendances et écrit `requirements.lock` **à hashes** ; (5) installe exactement le lock (hashes vérifiés) ; (6) vérifie les imports clés et affiche les versions.

## Environnement cible — point important

- **Cette machine (Windows)** : cible réelle du démonstrateur. `install.bat` configure **ici**. Le benchmark loyal Splink et les cibles relatives s'exécutent **ici**, dans le `.venv`.

## Node.js — dépendance de **test** (pas du produit)

Les surfaces embarquent une logique cliente (`src/surfaces/statique/logique.js`) : composition
des phrases et arithmétique des compteurs, exécutées dans le navigateur du prospect. Ses
oracles ne rejouent pas une réplique Python — ils **exécutent ce fichier-là**, sous Node, pour
que la garde porte sur le code réellement servi.

| | |
|---|---|
| **Requis pour** | `tests/test_surfaces.py` uniquement — les oracles marqués `@_SANS_NODE`, dont plusieurs contrôles positifs. Le décompte n'est pas écrit ici : il a été faux dès sa première écriture, et un chiffre de documentation que rien ne vérifie se périme en silence. `grep -c '^@_SANS_NODE' tests/test_surfaces.py` le donne. |
| **Version éprouvée** | Node v24.15.0 (aucune fonctionnalité récente employée ; toute version LTS convient) |
| **Installation** | Non gérée par `install.bat`. `node --version` doit répondre sur le `PATH`. |
| **Absent ?** | Ils **sautent proprement** (`SKIPPED`, motif explicite) ; le reste de la suite est vert. La garde est structurelle — un point de passage unique, `_execute_fichier_logique`, et un oracle qui interdit de le contourner — et non un marqueur à recopier sur chaque test. La suite ne tombe pas en erreur, mais la prose et l'arithmétique du navigateur ne sont alors **pas gardées**. |
| **Sous le job** | Ce saut devient un **échec**. `tools/job_ci.py` pose `MR_NODE_REQUIS=1`, lue au point de passage : sans elle, un job qui installe Node et le rate en silence rendrait un code 0 — vert, et n'ayant rien exécuté. La variable est posée par le script, pas par le YAML : on ne désarme pas la garde en éditant le workflow. |

## Le job d'oracles

`tools/job_ci.py` porte **les étapes**, une seule fois, pour deux appelants :
`.github/workflows/oracles.yml` (qui ne fait que provisionner l'environnement, puis l'appeler)
et `lancer_ci.bat`. Il n'existe nulle part ailleurs où écrire une étape, donc les deux voies
ne peuvent pas diverger.

| | |
|---|---|
| **Ce qui est constatable aujourd'hui** | `lancer_ci.bat complet rejeu` — le profil `complet` rejoué sur un **checkout nu** de `HEAD`, extrait hors du dépôt. C'est la seule preuve de verdeur que ce dépôt peut produire, et c'en est une. |
| **Ce qui ne l'est pas** | Le workflow GitHub. Ce dépôt n'a **aucun remote** (`git remote -v` est vide) : le YAML n'a à ce jour **aucune exécution**. Il est versionné pour vivre avec le code qu'il éprouve, pas pour qu'on écrive « CI verte » à côté. Son en-tête le dit aussi. |
| **Profil** | `complet` = `tests/` en entier, packs de fixtures compris (`fixtures/`). |
| **Système** | `windows-latest`, seul système où cette suite est **observée** verte, et celui du lanceur local. |
| **Item ouvert — Linux** | La suite n'a **jamais** tourné sur Linux, alors que c'est l'OS qui *sert* le démonstrateur (`deploiement/Dockerfile`, `python:3.12-slim`). Ce n'est ni une matrice `continue-on-error` ni une promesse : c'est un item ouvert, nommé ici. |

Le produit, lui, n'a **aucune** dépendance Node : le JavaScript servi est du script natif, sans
outil de construction ni paquet tiers. Node ne sert qu'à l'éprouver.

## Réseau

- **Requis uniquement à l'installation** (téléchargement de `uv`, de Python, des paquets).
- **Runtime ensuite offline** (`C7`) : une fois installé, le démonstrateur tourne sans réseau.

## Revue LLM de zone grise

Aucune dépendance LLM lourde (`torch`/`transformers`) n'est installée : la revue de zone grise tourne **offline via fixtures pré-calculées** (replay), pas un modèle live au runtime (blueprint §9.6). Le choix du modèle open-weight est différé en amont.

## En cas d'échec

L'installeur imprime une cause + une piste à chaque étape. Le cas le plus probable : `splink==4.0.16` incompatible avec Python 3.12 → rouvrir `install.bat`, remplacer `set "PYVER=3.12"` par `set "PYVER=3.11"`, relancer. Sinon, transmettre l'erreur exacte affichée.

## Ce que ce dossier NE contient pas encore

Le code (moteur `src/engine`, scoreur `src/scorer`, `benchmark/`, pipeline, surfaces), le `pyproject.toml` de packaging et le `Dockerfile` HF Space arrivent aux segments de build suivants, le long du graphe du blueprint (démarrage au gate `G-R3`, co-conception UX).
