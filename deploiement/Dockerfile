# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

# Image du démonstrateur — Hugging Face Spaces, SDK `docker`, CPU.
#
#   docker build -f deploiement/Dockerfile -t concordance .
#   docker run --rm -p 7860:7860 concordance
#
# ## Ce que l'image contient, et ce qu'elle ne contient pas
# Elle embarque le moteur, la chaîne, les surfaces et les artefacts déjà mesurés. Elle
# n'embarque NI la fixture (`fixtures/`), NI le banc, NI le scoreur, NI
# Splink : le démonstrateur ne rejoue aucune mesure, il affiche celles qui sont publiées.
# C'est ce qui rend l'image petite, et c'est surtout ce qui rend la non-circularité vraie à
# l'exécution — la surface n'a pas embarqué de quoi recompter ce qu'elle montre.
#
# ## Hors ligne
# Le réseau ne sert qu'au BUILD, pour installer trois paquets. À l'exécution, rien ne sort :
# aucune police distante, aucun CDN, aucune télémétrie. Un test le vérifie sur le HTML rendu.
# Épinglé au PATCH, et non au `3.12-slim` flottant : deux constructions de cette image à un mois
# d'intervalle doivent embarquer le même interpréteur, faute de quoi « la même image » désigne
# deux choses. C'est de l'hygiène de construction, et rien de plus — ce n'est PAS ce qui rend les
# artefacts reproductibles. Ils le sont par eux-mêmes : leur sceau ne hache que la matière
# mesurée, et il a été vérifié identique sous Python 3.12.7, 3.12.14 et 3.14.3 (cf.
# `tools/empreinte_artefact.py`). Ne pas rétablir de lien de cause entre ce tag et la
# reproductibilité : il n'y en a pas.
FROM python:3.12.14-slim

# `PYTHONHASHSEED` fixé : le déterminisme est une promesse affichée en Salle des machines, pas
# une propriété qu'on espère. Un serveur qui redémarre doit redonner la même empreinte.
ENV PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

# Hugging Face Spaces exécute le conteneur sous l'UID 1000 : créer l'utilisateur évite que les
# fichiers copiés soient illisibles à l'exécution.
RUN useradd -m -u 1000 concordance
WORKDIR /app

COPY deploiement/requirements-surfaces.txt ./requirements-surfaces.txt
RUN pip install --no-cache-dir -r requirements-surfaces.txt

# Seulement ce que le runtime lit. `tests/`, `tools/`, `src/scorer/`, `src/benchmark/` et
# `src/generator/` restent dehors : ils appartiennent au build.
COPY --chown=concordance:concordance src/engine/    ./src/engine/
COPY --chown=concordance:concordance src/pipeline/  ./src/pipeline/
COPY --chown=concordance:concordance src/surfaces/  ./src/surfaces/
COPY --chown=concordance:concordance artifacts/     ./artifacts/
COPY --chown=concordance:concordance serveur.py     ./serveur.py

USER concordance
EXPOSE 7860
CMD ["python", "serveur.py"]
