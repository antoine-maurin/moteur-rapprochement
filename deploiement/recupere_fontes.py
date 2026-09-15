# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Récupère les fontes de la maquette et les INSTALLE DANS LE DÉPÔT (O1).

    .venv\\Scripts\\python deploiement/recupere_fontes.py

## Pourquoi ce fichier n'est PAS dans `tools/`
`tools/` est la **zone de mesure**, et `test_llm_review.py` y pose un interdit que sa propre
docstring déclare sans exception : « le hors-ligne ne souffre aucune exception : aucun outil,
jamais, n'ouvre de socket ». La raison est juste — un artefact de mesure qui dépendrait d'un
serveur distant ne se régénérerait plus à l'octet, et l'interdit d'import est ce qui rend cette
propriété vérifiable sans avoir à lire le code.

Ce programme ouvre un socket. Il n'avait donc rien à faire dans `tools/`, et l'y loger aurait
obligé à percer un interdit posé comme inviolable — pour un fichier qui ne mesure rien. Il ne
produit pas d'artefact de mesure : il acquiert un **actif de livraison**, exactement comme
`install.bat` acquiert des dépendances. Sa place est ici, avec le `Dockerfile` et les
`requirements` : la zone de build et d'empaquetage, dont le réseau est le régime normal.

La propriété qui compte pour le produit — **le code livré n'ouvre jamais de socket** — est
gardée séparément et plus directement, par
`tests/test_surfaces.py::test_le_produit_livre_n_ouvre_jamais_de_socket`, qui analyse `src/`.
Et ce que ce programme télécharge est compensé par les empreintes du manifeste, vérifiées par
`test_les_fontes_sont_dans_le_depot_et_conformes_a_leur_empreinte`.

## Pourquoi ce fichier existe
Les surfaces s'appuyaient sur des piles système parce que *Space Grotesk*, *Inter* et
*JetBrains Mono* sont des fontes web, et qu'aller les chercher chez un tiers À CHAQUE
CHARGEMENT contredirait la promesse centrale de la Vitrine — « aucune donnée ne sort ». Le
titre avait dû être élargi de 14ch à 19ch pour compenser des glyphes plus larges.

Auto-héberger renverse la contrainte : le réseau ne sert qu'**une fois, ici, au build**, et le
produit livré ne contacte plus aucun serveur tiers. La promesse hors ligne n'est pas préservée
malgré les fontes, elle est **renforcée** par elles : un navigateur qui charge une fonte depuis
`fonts.gstatic.com` révèle à un tiers l'adresse IP du visiteur et la page consultée. Servie
depuis le dépôt, la même fonte ne révèle rien.

## Licences — la question n'est pas rhétorique
Les trois familles sont sous **SIL Open Font License 1.1**, qui autorise explicitement la
redistribution, y compris intégrée à un produit. Elle l'autorise **à condition** que la notice
de copyright et la licence accompagnent les fichiers : ce programme télécharge donc aussi les
`OFL.txt` en regard des fontes. Embarquer les binaires sans les licences serait une violation
de la seule condition que ces auteurs posent.

## Ce que ce programme garantit
Chaque fichier est publié avec son **URL d'origine, sa taille et son sha256** dans
`fontes/manifeste.json`. Relancer le programme et retrouver les mêmes empreintes est la seule
façon de savoir que ce qui est servi est bien ce qui a été téléchargé — un binaire dans un
dépôt, sans provenance, est un objet que personne ne peut auditer.

Il génère aussi `fontes.css` plutôt que de le faire écrire à la main : les `unicode-range` de
chaque sous-ensemble viennent de la source et doivent être reproduits **exactement**, sinon le
navigateur télécharge des fontes dont il n'a pas besoin, ou pire, en manque une.

## Non-circularité
Ce programme ne touche ni au moteur, ni aux artefacts de mesure. Il n'écrit que sous
`src/surfaces/statique/`, et n'est pas embarqué dans l'image livrée.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.request

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Chemins POSIX relatifs à la racine du repo (aucun chemin absolu OS-spécifique).
DOSSIER_FONTES = "src/surfaces/statique/fontes"
CHEMIN_CSS = "src/surfaces/statique/fontes.css"

#: Un navigateur récent est annoncé pour obtenir du **woff2** ; l'API sert des formats plus
#: anciens et bien plus lourds aux agents qu'elle ne reconnaît pas.
AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

#: Les sous-ensembles retenus. `latin` couvre le français courant ; `latin-ext` ajoute les
#: graphies que le moteur rencontre sur des noms européens (œ, ł, ș…). Les autres — cyrillique,
#: grec, vietnamien — pèseraient sans jamais servir : le produit est positionné FR.
SOUS_ENSEMBLES = ("latin", "latin-ext")

#: Familles, graisses et licence amont. Les graisses sont celles que `surfaces.css` emploie
#: réellement : en demander d'autres ferait grossir le dépôt sans rien changer à l'écran.
FAMILLES = (
    {
        "nom": "Space Grotesk",
        "cle": "space-grotesk",
        "graisses": (400, 500, 600, 700),
        "licence": "https://raw.githubusercontent.com/floriankarsten/space-grotesk/master/OFL.txt",
    },
    {
        "nom": "Inter",
        "cle": "inter",
        "graisses": (400, 500, 600, 700),
        "licence": "https://raw.githubusercontent.com/rsms/inter/master/LICENSE.txt",
    },
    {
        "nom": "JetBrains Mono",
        "cle": "jetbrains-mono",
        "graisses": (400, 500),
        "licence": "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/OFL.txt",
    },
)


def _telecharge(url: str, binaire: bool = True):
    requete = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(requete, timeout=60) as reponse:
        donnees = reponse.read()
    return donnees if binaire else donnees.decode("utf-8")


def _css_google(famille: dict) -> str:
    graisses = ";".join(str(g) for g in famille["graisses"])
    nom = famille["nom"].replace(" ", "+")
    return _telecharge(
        f"https://fonts.googleapis.com/css2?family={nom}:wght@{graisses}&display=swap",
        binaire=False)


def _blocs_font_face(css: str) -> list:
    """Les blocs `@font-face`, chacun avec le sous-ensemble que son commentaire annonce.

    L'API précède chaque bloc d'un commentaire `/* latin */`. C'est la seule façon de savoir
    à quel sous-ensemble appartient une URL : elles sont opaques.
    """
    blocs = []
    for correspondance in re.finditer(
            r"/\*\s*([a-z0-9-]+)\s*\*/\s*@font-face\s*\{(.*?)\}", css, flags=re.S):
        sous_ensemble, corps = correspondance.group(1), correspondance.group(2)
        url = re.search(r"src:\s*url\((https://[^)]+\.woff2)\)", corps)
        graisse = re.search(r"font-weight:\s*(\d+)", corps)
        style = re.search(r"font-style:\s*([a-z]+)", corps)
        plage = re.search(r"unicode-range:\s*([^;]+);", corps)
        if not (url and graisse):
            continue
        blocs.append({
            "sous_ensemble": sous_ensemble,
            "url": url.group(1),
            "graisse": int(graisse.group(1)),
            "style": style.group(1) if style else "normal",
            "unicode_range": plage.group(1).strip() if plage else None,
        })
    return blocs


def _ecrit_binaire(chemin_relatif: str, donnees: bytes) -> dict:
    complet = os.path.join(_RACINE, chemin_relatif)
    os.makedirs(os.path.dirname(complet), exist_ok=True)
    with open(complet, "wb") as fh:
        fh.write(donnees)
    return {
        "chemin": chemin_relatif.replace(os.sep, "/"),
        "octets": len(donnees),
        "sha256": hashlib.sha256(donnees).hexdigest(),
    }


def _vide_les_woff2():
    """Le dossier des fontes est ENGENDRÉ : on le repart propre.

    Sans cela, un fichier issu d'une exécution précédente — d'un nommage abandonné, d'une
    graisse retirée de la liste — survivrait dans le dépôt et dans l'image, servi par
    personne et audité par personne.
    """
    dossier = os.path.join(_RACINE, DOSSIER_FONTES)
    if not os.path.isdir(dossier):
        return
    for nom in os.listdir(dossier):
        if nom.endswith(".woff2"):
            os.remove(os.path.join(dossier, nom))


def main() -> int:
    _vide_les_woff2()
    entrees, licences = [], []
    for famille in FAMILLES:
        css = _css_google(famille)
        blocs = [b for b in _blocs_font_face(css) if b["sous_ensemble"] in SOUS_ENSEMBLES]
        if not blocs:
            raise RuntimeError(
                f"aucun sous-ensemble {SOUS_ENSEMBLES} pour {famille['nom']} : "
                f"l'API a change de forme, ne pas deviner")

        # Ces trois familles sont des fontes VARIABLES : l'API sert le MÊME fichier pour
        # toutes les graisses demandées et laisse le navigateur régler l'axe `wght` sur la
        # valeur déclarée par chaque `@font-face`. Télécharger naïvement une fois par graisse
        # mettait quatre copies identiques de 22 Ko dans le dépôt et dans l'image — 784 Ko au
        # lieu de 217. On télécharge par URL DISTINCTE et plusieurs `@font-face` pointent au
        # besoin sur le même fichier ; le comportement rendu est identique, à la duplication
        # près. Le nommage retombe sur la graisse si jamais une famille servait des fichiers
        # distincts : rien ici ne présume que la variable restera la norme.
        par_url = {}
        for bloc in blocs:
            if bloc["url"] in par_url:
                continue
            par_url[bloc["url"]] = _telecharge(bloc["url"])

        distincts_par_sous_ensemble = {}
        for bloc in blocs:
            distincts_par_sous_ensemble.setdefault(bloc["sous_ensemble"], set()).add(bloc["url"])

        fichier_par_url = {}
        for bloc in blocs:
            if bloc["url"] in fichier_par_url:
                continue
            unique = len(distincts_par_sous_ensemble[bloc["sous_ensemble"]]) == 1
            nom_fichier = (f"{famille['cle']}-{bloc['sous_ensemble']}.woff2" if unique
                           else f"{famille['cle']}-{bloc['graisse']}-"
                                f"{bloc['sous_ensemble']}.woff2")
            fiche = _ecrit_binaire(f"{DOSSIER_FONTES}/{nom_fichier}", par_url[bloc["url"]])
            fiche.update(famille=famille["nom"], sous_ensemble=bloc["sous_ensemble"],
                         source=bloc["url"],
                         graisses=sorted({b["graisse"] for b in blocs
                                          if b["url"] == bloc["url"]}))
            fichier_par_url[bloc["url"]] = nom_fichier
            entrees.append(fiche)
            print(f"  {nom_fichier:34s} {fiche['octets']:>7d} o  {fiche['sha256'][:16]}"
                  f"  graisses {fiche['graisses']}")

        for bloc in blocs:
            bloc["fichier"] = fichier_par_url[bloc["url"]]
            bloc["famille"] = famille["nom"]
        famille["blocs"] = blocs

        # La licence, sans laquelle la redistribution n'est pas autorisée.
        texte = _telecharge(famille["licence"], binaire=False)
        fiche = _ecrit_binaire(f"{DOSSIER_FONTES}/LICENCE-{famille['cle']}.txt",
                               texte.encode("utf-8"))
        fiche.update(famille=famille["nom"], source=famille["licence"])
        licences.append(fiche)
        print(f"  LICENCE-{famille['cle']}.txt : {fiche['octets']} o")

    # --- La feuille de style, engendrée pour que les `unicode-range` soient exacts --------
    lignes = [
        "/* Fontes auto-hébergées — ENGENDRÉ par deploiement/recupere_fontes.py, ne pas éditer.",
        " *",
        " * Servies depuis le dépôt : à l'exécution, le navigateur ne contacte aucun serveur",
        " * tiers. C'est ce qui rend vraie, et pas seulement plausible, la promesse « aucune",
        " * donnée ne sort » de la Vitrine — une fonte chargée chez un tiers lui révélerait",
        " * l'adresse IP du visiteur et la page consultée.",
        " *",
        " * Les trois familles sont sous SIL Open Font License 1.1 ; les licences accompagnent",
        " * les fichiers dans fontes/, comme cette licence l'exige.",
        " *",
        " * `font-display: swap` : le texte s'affiche immédiatement dans la pile système puis",
        " * bascule. Le budget de la Vitrine se compte jusqu'au texte LISIBLE, pas jusqu'au",
        " * texte définitif — bloquer le rendu pour une fonte le ferait échouer sur une",
        " * machine lente.",
        " */",
    ]
    # Un `@font-face` par (famille, graisse, sous-ensemble), comme la source — plusieurs
    # peuvent désigner le même fichier quand la fonte est variable.
    for famille in FAMILLES:
        for bloc in famille["blocs"]:
            lignes += [
                "@font-face {",
                f"  font-family: '{bloc['famille']}';",
                f"  font-style: {bloc['style']};",
                f"  font-weight: {bloc['graisse']};",
                "  font-display: swap;",
                f"  src: url('/statique/fontes/{bloc['fichier']}') format('woff2');",
            ]
            if bloc["unicode_range"]:
                lignes.append(f"  unicode-range: {bloc['unicode_range']};")
            lignes.append("}")
    _ecrit_binaire(CHEMIN_CSS, ("\n".join(lignes) + "\n").encode("utf-8"))

    manifeste = {
        "_lisez_moi": (
            "Provenance des fontes auto-hébergées. Relancer tools/recupere_fontes.py doit "
            "redonner ces empreintes : un binaire sans provenance n'est pas auditable."),
        "mandat": "DISP-UI-01",
        "licence": "SIL Open Font License 1.1 pour les trois familles",
        "sous_ensembles": list(SOUS_ENSEMBLES),
        "fontes": entrees,
        "licences": licences,
        "total_octets": sum(e["octets"] for e in entrees),
    }
    _ecrit_binaire(f"{DOSSIER_FONTES}/manifeste.json",
                   (json.dumps(manifeste, ensure_ascii=False, indent=1, sort_keys=True)
                    + "\n").encode("utf-8"))

    print(f"\n{len(entrees)} fontes, {manifeste['total_octets']} octets au total")
    print(f"ecrit {CHEMIN_CSS} et {DOSSIER_FONTES}/manifeste.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
