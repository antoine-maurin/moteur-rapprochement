# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Mise en forme française des valeurs LUES. Aucune valeur n'est produite ici.

La distinction porte tout le mandat : formater, c'est écrire autrement une valeur qui existe
déjà ; calculer, ce serait en fabriquer une. Ces fonctions prennent un flottant mesuré et
rendent une chaîne — elles ne combinent jamais deux mesures, et ne connaissent aucun seuil.

## Pourquoi ce module existe séparément
Pour que l'oracle « aucun chiffre en dur » ait un endroit où ne PAS regarder. Les gabarits ne
contiennent aucun littéral numérique ; les modules de lecture non plus. Les seuls entiers du
paquet vivent ici, et ce sont des nombres de décimales — `3` dans `nombre(x, 3)` n'est pas une
valeur d'affichage, c'est une précision d'écriture. Les isoler rend la revue triviale.
"""
from __future__ import annotations

__all__ = ["nombre", "pourcent", "signe", "entier", "booleen", "libelle", "liste_libelles",
           "avec_article", "liste_libelles_avec_articles", "accorde",
           "MOINS", "ESPACE_FINE", "LIBELLES_CHAMPS", "GENRES_CHAMPS"]

#: Nom lisible des attributs comparés. La Vitrine parle d'« informations », pas d'attributs :
#: ces libellés sont ce qu'un acheteur reconnaît sur sa propre fiche client.
LIBELLES_CHAMPS = {
    "record_id": "identifiant",
    "source_id": "source",
    "nom": "nom",
    "prenom": "prénom",
    "date_naissance": "date de naissance",
    "adresse": "adresse",
    "code_postal": "code postal",
    "ville": "ville",
    "email": "e-mail",
    "telephone": "téléphone",
}

#: Genre de chaque libellé, pour poser l'article. La même table existe dans `logique.js`, où
#: elle sert la prose du navigateur ; les deux sont tenues égales par un oracle qui LIT le
#: fichier servi plutôt que de le recopier.
GENRES_CHAMPS = {
    "record_id": "m", "source_id": "f", "nom": "m", "prenom": "m", "date_naissance": "f",
    "adresse": "f", "code_postal": "m", "ville": "f", "email": "m", "telephone": "m",
}

#: Signe moins typographique (U+2212), et non le trait d'union du clavier. Sur « −0,017 » la
#: différence est visible : le trait d'union se lit comme une césure.
MOINS = "−"

#: Espace fine insécable, séparateur de milliers français.
ESPACE_FINE = " "


def _virgule(texte: str) -> str:
    """Séparateur décimal français."""
    return texte.replace(".", ",")


def nombre(valeur, decimales: int = 3) -> str:
    """Un flottant, à N décimales, en écriture française. `None` reste visible comme absence."""
    if valeur is None:
        return "—"
    texte = _virgule(f"{abs(float(valeur)):.{decimales}f}")
    return (MOINS if float(valeur) < 0 else "") + texte


def signe(valeur, decimales: int = 3) -> str:
    """Comme `nombre`, mais le signe positif est écrit. Pour un écart, « +0,085 » se lit mieux."""
    if valeur is None:
        return "—"
    texte = nombre(valeur, decimales)
    return ("+" + texte) if float(valeur) > 0 else texte


def pourcent(valeur, decimales: int = 1) -> str:
    """Un taux DÉJÀ exprimé en pourcentage. La multiplication par cent se fait dans `vue`."""
    if valeur is None:
        return "—"
    return _virgule(f"{float(valeur):.{decimales}f}") + ESPACE_FINE + "%"


def booleen(valeur, vrai: str = "oui", faux: str = "non") -> str:
    """Un booléen, en français. Un « True » nu dans une prose française signale une valeur
    passée sans relecture — sur la page qui doit convaincre qu'aucun chiffre n'est bricolé,
    c'est la tuyauterie qui affleure."""
    if valeur is None:
        return "—"
    return vrai if valeur else faux


def libelle(champ: str) -> str:
    """Le nom lisible d'un attribut. Un champ inconnu se montre tel quel plutôt que de
    disparaître : une surface qui masque ce qu'elle ne sait pas nommer ment par omission."""
    return LIBELLES_CHAMPS.get(champ, champ)


def liste_libelles(champs) -> str:
    """« nom, adresse et e-mail » — énumération française, avec « et » avant le dernier."""
    noms = [libelle(c) for c in champs]
    if not noms:
        return ""
    if len(noms) == 1:
        return noms[0]
    return ", ".join(noms[:-1]) + " et " + noms[-1]


def avec_article(champ: str) -> str:
    """« le nom », « la ville », « l'adresse » — le libellé, précédé de son article défini.

    Sans article, une énumération devient du télégramme : « les différences d'écriture sur nom
    et téléphone » se lit comme une entrée de formulaire, pas comme une phrase, sur la surface
    dont le mandat exige une écriture soignée. La règle existait côté navigateur
    (`logique.js`), et un oracle y déclare fautive l'absence d'article ; elle manquait côté
    gabarits, où aucun scan de prose ne portait.
    """
    nom = libelle(champ)
    if nom[:1].lower() in "aeiouéèêà":
        return "l'" + nom
    return ("la " if GENRES_CHAMPS.get(champ) == "f" else "le ") + nom


def liste_libelles_avec_articles(champs) -> str:
    """« le nom, la ville et l'e-mail » — l'énumération, articles posés."""
    noms = [avec_article(c) for c in champs]
    if not noms:
        return ""
    if len(noms) == 1:
        return noms[0]
    return ", ".join(noms[:-1]) + " et " + noms[-1]


def accorde(participe: str, champs) -> str:
    """« renseigné » accordé aux champs nommés : renseignée, renseignés, renseignées.

    Le gabarit ne peut pas accorder seul : le genre des libellés vit dans `GENRES_CHAMPS`, et
    le nombre dépend de la liste. Écrire « la ville n'est renseigné que d'un côté » sur la
    carte la plus regardée de la Vitrine est exactement la faute qu'un accord fait à la main
    finit par produire, sur la branche que les données du jour n'exercent pas.

    Le féminin ne s'applique que si TOUS les champs sont féminins — c'est la règle française,
    et c'est aussi le sens sûr : un mélange se met au masculin pluriel.
    """
    champs = list(champs)
    feminin = bool(champs) and all(GENRES_CHAMPS.get(c) == "f" for c in champs)
    return participe + ("e" if feminin else "") + ("s" if len(champs) > 1 else "")


def entier(valeur) -> str:
    """Un entier, avec séparateur de milliers français."""
    if valeur is None:
        return "—"
    return f"{int(valeur):,}".replace(",", ESPACE_FINE)
