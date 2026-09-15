---
title: Concordance
emoji: 🔗
colorFrom: gray
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: other
short_description: Rapprochement de fiches — souverain, hors ligne, auditable.
---

# Concordance — démonstrateur

Trois surfaces au-dessus d'un moteur de rapprochement de fiches (dédoublonnage / résolution
d'entités) pour données françaises :

| Surface | Route | Pour qui |
|---|---|---|
| Vitrine | `/` | comprendre en dix secondes |
| Salle des machines | `/salle-des-machines` | tout vérifier en cinq minutes |
| Bac à sable | `/bac-a-sable` | essayer le moteur en direct |

## Ce que le démonstrateur calcule, et ce qu'il ne calcule pas

Le **bac à sable** exécute réellement le moteur sur l'entrée saisie : normalisation, blocking,
comparaison, décision en trois zones, clôture transitive, fusion. Rien n'y est simulé.

La **Vitrine** et la **Salle des machines**, elles, ne calculent rien. Elles lisent des
artefacts JSON produits ailleurs — et les métriques qu'elles affichent (précision, rappel, F1)
ont été mesurées par un **scoreur indépendant du moteur**, jamais par le moteur lui-même. Le
paquet déployé n'embarque d'ailleurs pas ce scoreur : la surface n'a structurellement pas de
quoi recompter ce qu'elle montre.

## Hors ligne

Aucun appel réseau à l'exécution : ni police web, ni CDN, ni service distant, ni télémétrie.
Le réseau ne sert qu'à installer trois paquets au moment du build (`starlette`, `uvicorn`,
`jinja2`). Le moteur lui-même n'a aucune dépendance tierce.

## Déterminisme

Même entrée, même sortie, y compris après redémarrage : `PYTHONHASHSEED` est fixé dans
l'image, et chaque calcul du bac à sable publie l'empreinte de sa sortie canonique.

## Rebâtir les artefacts

Les sorties du moteur affichées par la Vitrine sont figées dans
`artifacts/ui_demonstration.json`, régénérable depuis le dépôt de build :

```
.venv\Scripts\python tools/produit_artefacts_ui.py
```

Ce programme lit la fixture de référence (hors image), rejoue le moteur au point DIMS-v2, et
choisit le cas montré par une **règle déterministe** publiée à côté de son résultat.
