"""Normalisation déterministe — étape 1 du bloc B2.

La normalisation s'applique AVANT tout : elle conditionne à la fois les clés de blocking
(`blocking.py`) et les comparateurs (`compare.py`). Deux exigences non négociables :

- **pureté** : la fonction ne mute jamais son entrée et ne dépend d'aucun état global ;
- **déterminisme** : même entrée => même forme normalisée, à travers les processus
  (aucun recours à `hash()`, aucun parcours d'ensemble non trié, aucune locale).

Frontière de non-circularité : ce module ne connaît que les 8 attributs comparés + les
2 identifiants techniques. Il ne consomme aucune donnée de vérité terrain et ne mesure rien.

Convention de manquant (décision V1, déclarée) : une valeur `None` **ou** dont la forme
normalisée est la chaîne vide est ramenée à `None`. « Vide après normalisation » et
« absent » sont donc le même état — c'est ce que consommera `INDETERMINE_MANQUANT`.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

# Les 8 attributs comparés (schéma SOURCE_RECORD) + les 2 champs techniques conservés.
ATTRIBUTS_COMPARE = ("nom", "prenom", "date_naissance", "adresse",
                     "code_postal", "ville", "email", "telephone")
CLES_TECHNIQUES = ("record_id", "source_id")

# --- Abréviations de voie (FR) : token -> forme longue (mandat §2) -------------------
# Table volontairement close et ordonnée : toute extension est une décision tracée.
ABREV_VOIE = {
    "av": "avenue", "ave": "avenue", "aven": "avenue",
    "bd": "boulevard", "bld": "boulevard", "boul": "boulevard", "blvd": "boulevard",
    "r": "rue",
    "pl": "place",
    "imp": "impasse",
    "all": "allee",
    "ch": "chemin", "che": "chemin",
    "rte": "route",
    "sq": "square",
    "fg": "faubourg", "fbg": "faubourg",
    "res": "residence",
    "bat": "batiment",
    "appt": "appartement", "apt": "appartement",
    "st": "saint", "ste": "sainte", "sts": "saints",
    "quai": "quai",
}

# Formes juridiques retirées du nom d'une personne morale : « SARL Boulangerie du Coin »
# et « Boulangerie du Coin S.A.R.L. » désignent la même entité. Le sigle est du bruit de
# source, pas un discriminant d'identité.
FORMES_JURIDIQUES = frozenset({
    "sarl", "sas", "sasu", "sa", "eurl", "sci", "snc", "scop", "scs", "sca",
    "gie", "asso", "association", "ei", "eirl", "sel", "selarl",
})

_PONCTUATION = re.compile(r"[^0-9a-z]+")
_ESPACES = re.compile(r"\s+")
_NON_CHIFFRE = re.compile(r"[^0-9]")
_DATE_ISO = re.compile(r"^(\d{4})\D(\d{1,2})\D(\d{1,2})$")
_DATE_FR = re.compile(r"^(\d{1,2})\D(\d{1,2})\D(\d{4})$")
_DATE_COMPACTE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")


def sans_accents(s: str) -> str:
    """Replie les diacritiques (NFD puis retrait des marques combinantes).

    « Marché » -> « Marche », « République » -> « Republique ». Déterministe : la
    décomposition Unicode ne dépend ni de la locale ni de l'ordre d'itération.
    """
    decompose = unicodedata.normalize("NFD", s)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def texte(valeur: Optional[str]) -> Optional[str]:
    """Forme canonique d'un champ texte : minuscules, sans accents, sans ponctuation.

    La ponctuation devient un séparateur (et non une suppression) : « Jean-Pierre » donne
    « jean pierre » et non « jeanpierre ». Retourne `None` si le résultat est vide.
    """
    if valeur is None:
        return None
    s = sans_accents(str(valeur)).lower()
    s = _PONCTUATION.sub(" ", s)
    s = _ESPACES.sub(" ", s).strip()
    return s or None


def _recolle_sigles(tokens: list) -> list:
    """Recolle les suites d'au moins deux tokens d'une seule lettre : « s a r l » -> « sarl ».

    C'est la contrepartie du fait que la ponctuation est devenue un séparateur : sans cela,
    « S.A.R.L. » et « SARL » ne se rejoindraient jamais. Le seuil de 2 protège les tokens
    d'une lettre isolés qui portent du sens (l'abréviation « r » de « rue », l'initiale
    « J » de « J-P ») : ils ne sont recollés à rien.
    """
    sortie, i = [], 0
    while i < len(tokens):
        j = i
        while j < len(tokens) and len(tokens[j]) == 1 and tokens[j].isalpha():
            j += 1
        if j - i >= 2:
            sortie.append("".join(tokens[i:j]))
        else:
            sortie.extend(tokens[i:j])
            if j == i:
                sortie.append(tokens[i])
                j = i + 1
        i = j
    return sortie


def nom(valeur: Optional[str]) -> Optional[str]:
    """Forme canonique d'un nom (personne physique ou morale).

    Chaîne : forme texte -> recollage des sigles pointés -> retrait des formes juridiques.
    Garde-fou : si le retrait des formes juridiques ne laisse rien (un nom qui ne serait
    QUE la forme juridique), on conserve la forme non filtrée plutôt que de produire un
    manquant artificiel.
    """
    s = texte(valeur)
    if s is None:
        return None
    tokens = _recolle_sigles(s.split(" "))
    filtres = [t for t in tokens if t not in FORMES_JURIDIQUES]
    retenus = filtres if filtres else tokens
    return " ".join(retenus) or None


def prenom(valeur: Optional[str]) -> Optional[str]:
    """Forme canonique d'un prénom. Pas de retrait de forme juridique (hors sujet)."""
    return texte(valeur)


def ville(valeur: Optional[str]) -> Optional[str]:
    """Forme canonique d'une ville : forme texte + expansion « st » -> « saint »."""
    s = texte(valeur)
    if s is None:
        return None
    tokens = [ABREV_VOIE[t] if t in ("st", "ste") else t for t in s.split(" ")]
    return " ".join(tokens) or None


def adresse(valeur: Optional[str]) -> Optional[str]:
    """Forme canonique d'une adresse : forme texte + expansion des abréviations de voie.

    L'expansion est **token à token** et jamais en sous-chaîne : « bd » ne se déclenche que
    sur le token entier, donc « bdx » ou « hubert » ne sont pas touchés. C'est ce qui rend
    « 3 r. du Marché » et « 3 rue du Marche » identiques, et « 17 bd de la République »
    identique à « 17 boulevard de la Republique ».
    """
    s = texte(valeur)
    if s is None:
        return None
    tokens = [ABREV_VOIE.get(t, t) for t in s.split(" ")]
    return " ".join(tokens) or None


def email(valeur: Optional[str]) -> Optional[str]:
    """Forme canonique d'un email : minuscules, espaces retirés. Ponctuation CONSERVÉE.

    Un email est une clé structurée (`local@domaine`) : y écraser les points détruirait
    l'information. On ne replie donc que la casse et les espaces parasites.
    """
    if valeur is None:
        return None
    s = _ESPACES.sub("", str(valeur)).lower()
    return s or None


def code_postal(valeur: Optional[str]) -> Optional[str]:
    """Forme canonique d'un code postal : chiffres seuls (les zéros de tête sont gardés)."""
    if valeur is None:
        return None
    s = _NON_CHIFFRE.sub("", str(valeur))
    return s or None


def telephone(valeur: Optional[str]) -> Optional[str]:
    """Forme canonique d'un téléphone : chaîne de chiffres, indicatif FR replié sur « 0 ».

    « 01 45 67 89 01 », « 0145678901 », « +33 1 45 67 89 01 » et « 0033145678901 »
    donnent tous « 0145678901 ». Le repli n'a lieu que sur la longueur attendue, pour ne
    pas mutiler un numéro étranger.
    """
    if valeur is None:
        return None
    s = _NON_CHIFFRE.sub("", str(valeur))
    if s.startswith("0033") and len(s) == 13:
        s = "0" + s[4:]
    elif s.startswith("33") and len(s) == 11:
        s = "0" + s[2:]
    return s or None


def date_naissance(valeur: Optional[str]) -> Optional[str]:
    """Forme canonique d'une date : « AAAA-MM-JJ » quand la date est reconnaissable.

    Règle de désambiguïsation déterministe : le groupe à 4 chiffres décide. S'il est en
    tête, l'ordre est ISO (AAAA?MM?JJ) ; s'il est en queue, l'ordre est français
    (JJ?MM?AAAA). Aucune heuristique sur la valeur des champs (un « 03/12 » n'est jamais
    retourné dans les deux sens selon qu'il est plausible ou non) : la forme prime, ce qui
    garantit la pureté. Une chaîne non reconnue est rendue en forme texte, jamais devinée.
    """
    if valeur is None:
        return None
    brut = str(valeur).strip()
    for motif, ordre in ((_DATE_ISO, "iso"), (_DATE_COMPACTE, "iso"), (_DATE_FR, "fr")):
        m = motif.match(brut)
        if not m:
            continue
        if ordre == "iso":
            an, mois, jour = m.group(1), m.group(2), m.group(3)
        else:
            jour, mois, an = m.group(1), m.group(2), m.group(3)
        return f"{int(an):04d}-{int(mois):02d}-{int(jour):02d}"
    return texte(brut)


# Table de dispatch : attribut -> normaliseur. Ordre fixe, close.
NORMALISEURS = {
    "nom": nom,
    "prenom": prenom,
    "date_naissance": date_naissance,
    "adresse": adresse,
    "code_postal": code_postal,
    "ville": ville,
    "email": email,
    "telephone": telephone,
}


def normalise_record(record: dict) -> dict:
    """Projette et normalise un enregistrement source.

    Retourne un dict NEUF portant exactement `record_id`, `source_id` et les 8 attributs
    normalisés. La **projection est défensive** : toute colonne surnuméraire présente en
    entrée est écartée, si bien que le moteur est structurellement incapable de lire autre
    chose que les 8 attributs comparés (garde de non-circularité par construction, et pas seulement
    par discipline). L'entrée n'est jamais mutée.
    """
    sortie = {c: record.get(c) for c in CLES_TECHNIQUES}
    for attribut in ATTRIBUTS_COMPARE:
        sortie[attribut] = NORMALISEURS[attribut](record.get(attribut))
    return sortie


def normalise_records(records) -> list:
    """Normalise une collection, en conservant l'ordre d'entrée (déterminisme)."""
    return [normalise_record(r) for r in records]
