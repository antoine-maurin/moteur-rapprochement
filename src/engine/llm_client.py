"""Interface d'adjudication hors ligne + clients.

Ce module porte **le joint** (la couture) entre le moteur et un adjudicateur externe, et
rien d'autre : il ne décide pas, il ne mesure pas, il n'ouvre aucun fichier.

    charge_de_revue(a, b)  ->  cle_de_charge(charge)  ->  client.repond(invite)  ->
    analyse_reponse(texte) -> (decision, justification)

## Ce que ce module NE fait PAS, et pourquoi
- **Aucune entrée/sortie.** La liste blanche d'imports du moteur (C7, éprouvée par la
  suite) ne contient pas `os`, et le module n'appelle pas `open` : un client de rejeu
  reçoit donc une transcription **déjà chargée**. Le chargement depuis le disque appartient
  à l'outillage (`tools/`), jamais au produit. Cette contrainte est heureuse : elle rend
  structurellement impossible qu'un chemin de machine entre dans le moteur.
- **Aucune classe abstraite `abc`.** Le paquet `abc` n'est pas dans la liste blanche : la
  base est une classe ordinaire dont les méthodes lèvent `NotImplementedError`.

## La question posée, et ce que la clé de rejeu couvre
La charge soumise est la **projection normalisée** des deux enregistrements sur les 8
attributs comparés — pas leurs niveaux d'accord. Ce choix est décisif :

- les niveaux d'accord dépendent des cutoffs `c_fort` / `c_partiel`, qui sont des
  placeholders déclarés destinés à bouger. Une clé bâtie dessus rendrait, après
  recalibration, une réponse **périmée sans le moindre raté** : la clé serait inchangée
  alors que la question aurait changé. C'est exactement le mode d'invention silencieuse que
  l'on exclut ;
- les valeurs normalisées, elles, sont la question elle-même. Un adjudicateur réel reçoit
  du texte ; modeler la clé sur ce que sait faire un client de rejeu produirait une fausse
  abstraction, où brancher un vrai modèle invaliderait tout le corpus.

La clé **n'inclut pas** les identifiants d'enregistrement : deux paires dont les 8 valeurs
coïncident des deux côtés posent littéralement la même question, et doivent recevoir la
même réponse. Elle n'inclut pas non plus l'agrégat de vraisemblance ni les seuils, qui ne
sont pas locaux à la paire : les y mettre lierait chaque fixture à une population et à un
dimensionnement, alors qu'un re-dimensionnement doit pouvoir changer l'ensemble des paires
à instruire **sans invalider une seule fixture**.

## Le verrou de paramètres
Une transcription porte un en-tête décrivant la projection qui l'a produite. Le client de
rejeu **refuse** une transcription dont l'en-tête ne coïncide pas avec la projection
courante. La clé couvre la question ; le verrou couvre ce que la clé ne peut pas couvrir.

## Frontière de non-circularité
Le constructeur d'invite ne lit que les 8 attributs comparés, et il les lit sur des
enregistrements **normalisés** — or la normalisation projette défensivement sur ces 8
attributs plus 2 clés techniques. Toute colonne surnuméraire d'une source est donc écartée
**avant** que ce module ne voie quoi que ce soit : la garde est structurelle, pas
disciplinaire.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Optional

from .normalize import ATTRIBUTS_COMPARE

__all__ = [
    "MATCH_APRES_REVUE", "NON_MATCH_APRES_REVUE", "NON_TRANCHE", "DECISIONS",
    "CLE_GABARIT", "PROJECTION", "entete_de_projection",
    "charge_de_revue", "cle_de_charge", "invite_de_charge", "analyse_reponse",
    "ClientRevue", "ClientIndisponible", "ClientRejeu",
    "AdjudicationIndisponible", "ReponseAbsente", "TranscriptionIncompatible",
]

# --- Énumération FERMÉE des décisions de revue (mandat §3) ----------------------------
MATCH_APRES_REVUE = "MATCH_APRES_REVUE"
NON_MATCH_APRES_REVUE = "NON_MATCH_APRES_REVUE"
NON_TRANCHE = "NON_TRANCHE"
DECISIONS = (MATCH_APRES_REVUE, NON_MATCH_APRES_REVUE, NON_TRANCHE)

#: Gabarit d'invite, VERSIONNÉ et constante de module. Jamais lu depuis un fichier et
#: jamais assemblé avec un séparateur de ligne dépendant du système : la clé de rejeu en
#: dérive, elle doit donc être identique sur toute machine.
CLE_GABARIT = "U-B3::E-LLM::gabarit-revue::v1"

#: Nature de ce qui est soumis. Verrouillé dans l'en-tête des transcriptions.
PROJECTION = "valeurs_normalisees_8_attributs"

#: Séparateurs de la sérialisation qui alimente le hachage. Nommés, et volontairement
#: DISTINCTS de ceux de `engine.sortie_canonique` : ce sont deux contrats sans rapport, et
#: les confondre ferait qu'un changement d'affichage déplacerait toutes les clés.
SEPARATEURS_CLE = (",", ":")

#: Ligne de verdict attendue dans une réponse. **Ancrée** : le jeton de rejet CONTIENT le
#: jeton de promotion (`"NON_MATCH_APRES_REVUE".find("MATCH_APRES_REVUE") == 4`), si bien
#: qu'un `in`, un `startswith` ou un `endswith` promouvrait un rejet. L'ancrage n'est pas
#: une élégance : c'est la seule écriture qui ne retourne pas le sens d'un refus.
#: Les classes d'espaces sont écrites `[ \t]` et non `\s` : une barre oblique inverse
#: placée juste après un deux-points forme le motif d'un chemin absolu de type Windows,
#: que la suite proscrit dans la zone moteur. Écriture équivalente ici — la ligne est déjà
#: découpée et débarrassée de ses bords — et qui ne fait pas mentir l'oracle.
_LIGNE_DECISION = re.compile(
    r"DECISION:[ \t]*(MATCH_APRES_REVUE|NON_MATCH_APRES_REVUE|NON_TRANCHE)[ \t]*$")
_LIGNE_JUSTIFICATION = re.compile(r"JUSTIFICATION:[ \t]*(.*?)[ \t]*$")

#: Longueur d'une clé : le sha256 ENTIER. Une clé tronquée « pour la lisibilité » rendrait
#: possible une collision, donc la réponse d'une AUTRE question sans le moindre raté.
LONGUEUR_CLE = 64


class AdjudicationIndisponible(Exception):
    """Aucun adjudicateur n'est joignable. La paire reste indéterminée."""


class ReponseAbsente(Exception):
    """La transcription ne porte pas de réponse pour cette clé.

    Levée plutôt que rendue : un raté de rejeu doit **remonter**, jamais se blanchir en
    abstention. Confondre « je n'ai pas la réponse » et « je m'abstiens » ferait d'un
    corpus de fixtures incomplet une revue d'apparence complète.
    """


class TranscriptionIncompatible(Exception):
    """L'en-tête de la transcription ne décrit pas la projection courante."""


def entete_de_projection() -> dict:
    """En-tête décrivant la projection courante — le verrou d'une transcription.

    Ne contient **que** ce dont la question dépend. Les cutoffs de comparaison en sont
    volontairement absents : la charge porte des valeurs, pas des niveaux d'accord, donc
    une recalibration des cutoffs ne périme aucune fixture.
    """
    return {"gabarit": CLE_GABARIT, "projection": PROJECTION,
            "attributs": list(ATTRIBUTS_COMPARE)}


def _valeur_canonique(valeur) -> Optional[str]:
    """Valeur prête pour le hachage : `None` conservé, texte replié en NFC.

    Le repli NFC n'est pas cosmétique. La normalisation d'un courriel ne retire pas les
    diacritiques (c'est une clé structurée, on n'y touche pas) : c'est le seul des 8
    attributs qui peut porter jusqu'ici de l'Unicode non replié. Deux écritures
    visuellement identiques donneraient alors deux clés distinctes, et le raté n'apparaît
    que sur la première source réelle qui en contient.
    """
    if valeur is None:
        return None
    return unicodedata.normalize("NFC", str(valeur))


def _cle_de_tri(record: dict) -> tuple:
    """Clé d'ordre total d'un enregistrement normalisé, par ses valeurs.

    Le drapeau de présence `0` / `1` est nécessaire : `None < "x"` lève un `TypeError` en
    Python 3, et ce plantage n'apparaîtrait que sur les populations où le premier attribut
    discriminant est manquant — donc tard, et sur les données de quelqu'un d'autre.

    L'ordre ne se prend PAS sur les identifiants d'enregistrement : il réintroduirait
    l'identité de la population dans une clé qu'on veut locale à la preuve.
    """
    return tuple((0, "") if (v := _valeur_canonique(record.get(j))) is None else (1, v)
                 for j in ATTRIBUTS_COMPARE)


def charge_de_revue(record_a: dict, record_b: dict) -> dict:
    """Charge soumise à l'adjudicateur : les 8 attributs comparés des deux enregistrements.

    Les deux enregistrements sont **orientés par leur contenu** (et non par leur
    identifiant) de sorte que soumettre `(a, b)` ou `(b, a)` pose la même question et
    produise la même clé.
    """
    gauche, droite = sorted((record_a, record_b), key=_cle_de_tri)
    return {
        "gabarit": CLE_GABARIT,
        "projection": PROJECTION,
        "attributs": [{"attribut": j,
                       "gauche": _valeur_canonique(gauche.get(j)),
                       "droite": _valeur_canonique(droite.get(j))}
                      for j in ATTRIBUTS_COMPARE],
    }


def cle_de_charge(charge: dict) -> str:
    """sha256 de la charge sérialisée canoniquement — la clé de rejeu, entière.

    Via sha256 et **jamais** via `hash()` : le `hash()` des chaînes est salé par processus,
    ce qui casserait la reproductibilité inter-processus exigée par le déterminisme.
    """
    octets = json.dumps(charge, sort_keys=True, ensure_ascii=False,
                        separators=SEPARATEURS_CLE).encode("utf-8")
    return hashlib.sha256(octets).hexdigest()


def invite_de_charge(charge: dict) -> str:
    """Rendu textuel de la charge — ce qu'un adjudicateur reçoit réellement.

    Aucune étiquette de décision, aucun agrégat de vraisemblance, aucun identifiant
    d'enregistrement : uniquement les valeurs comparées, et la consigne de format qui rend
    la réponse analysable. Les lignes sont jointes par `"\\n"` littéral, jamais par un
    séparateur dépendant du système.
    """
    lignes = ["Deux fiches issues de sources distinctes. Meme entite, ou non ?",
              "Repondre exactement deux lignes :",
              "DECISION: " + " | ".join(DECISIONS),
              "JUSTIFICATION: <une phrase courte>",
              ""]
    for entree in charge["attributs"]:
        gauche = entree["gauche"] if entree["gauche"] is not None else "(absent)"
        droite = entree["droite"] if entree["droite"] is not None else "(absent)"
        lignes.append(f"{entree['attribut']} : {gauche}  ||  {droite}")
    return "\n".join(lignes)


def analyse_reponse(texte) -> tuple:
    """Analyse une réponse brute -> `(decision, justification)`.

    **Toute ambiguïté est une abstention, jamais un choix.** Zéro jeton reconnu, ou deux
    jetons distincts, donnent `NON_TRANCHE` : c'est la lecture prudente exigée par le
    mandat (une paire n'est jamais promue sans preuve). Le verdict est extrait d'une ligne
    **ancrée** — voir `_LIGNE_DECISION` pour la raison, qui est un piège de sous-chaîne.

    Une entrée qui n'est pas une chaîne est REFUSÉE plutôt qu'analysée : sans ce contrôle,
    un `None` rendu par un accès manqué se lirait comme une abstention légitime.
    """
    if not isinstance(texte, str):
        raise TypeError(f"reponse attendue en texte, recu {type(texte).__name__}")
    trouvees, justification = [], ""
    for ligne in texte.split("\n"):
        ligne = ligne.strip()
        correspondance = _LIGNE_DECISION.match(ligne)
        if correspondance:
            trouvees.append(correspondance.group(1))
            continue
        correspondance = _LIGNE_JUSTIFICATION.match(ligne)
        if correspondance and not justification:
            justification = correspondance.group(1)
    distinctes = set(trouvees)
    if len(distinctes) != 1:
        return NON_TRANCHE, justification
    return trouvees[0], justification


class ClientRevue:
    """Interface d'adjudication. Un seul point de variation : `repond`.

    Volontairement minimale : elle transporte du **texte** dans les deux sens, ce qui est
    ce qu'un modèle local échange réellement. Une interface modelée sur le client de rejeu
    (qui, lui, pourrait se contenter d'une clé) serait une fausse abstraction — elle
    passerait au vert sur un client factice et casserait le jour où l'on branche autre
    chose. `nom` et `cout_declare_par_appel` sont de la traçabilité **publiée à côté** de
    la coupe budgétaire ; ils n'entrent jamais dedans (cf. `llm_review`).
    """

    nom = "interface"
    #: Coût déclaré d'un appel, en unités arbitraires. PUBLIÉ, jamais soustrait d'un budget.
    cout_declare_par_appel = None

    def disponible(self) -> bool:
        """Un adjudicateur joignable répond `True`. La base ne l'est pas."""
        return False

    def repond(self, invite: str) -> str:
        """Rend la réponse brute à une invite. À implémenter."""
        raise NotImplementedError("un client de revue doit implementer repond()")

    def description(self) -> dict:
        """Carte d'identité publiable du client."""
        return {"nom": self.nom, "disponible": self.disponible(),
                "cout_declare_par_appel": self.cout_declare_par_appel}


class ClientIndisponible(ClientRevue):
    """Adaptateur d'un modèle local **absent de ce build** — l'état réel, pas un artifice.

    Aucun runtime de modèle local n'est déclaré dans le manifeste de dépendances, et
    l'installation d'une dépendance est impossible au runtime (offline strict). Cet
    adaptateur est donc le **point de branchement** d'un modèle qui n'est pas là : il
    l'annonce (`disponible()` est faux) et refuse de répondre.

    Il ne fabrique rien, ne devine rien et ne se replie sur aucune heuristique : c'est
    précisément la branche prévue — les paires non revues restent
    indéterminées, et le repli est tracé par l'appelant.
    """

    nom = "modele_local_absent"

    def __init__(self, runtime=None, motif: str = ""):
        self._runtime = runtime
        self.motif = motif or (
            "aucun runtime de modele local n'est declare dans le manifeste de dependances "
            "et le runtime est hors ligne strict : rien a interroger")

    def disponible(self) -> bool:
        return self._runtime is not None

    def repond(self, invite: str) -> str:
        if self._runtime is None:
            raise AdjudicationIndisponible(self.motif)
        return self._runtime(invite)

    def description(self) -> dict:
        carte = super().description()
        carte["motif_indisponibilite"] = None if self.disponible() else self.motif
        return carte


class ClientRejeu(ClientRevue):
    """Rejoue une transcription **déjà chargée** : `{cle: {"texte": ...}}`.

    C'est ce client qui tourne en test et en démonstration, et c'est lui qui rend la revue
    déterministe malgré l'exception que constitue un adjudicateur externe.

    Contrôles à la construction, tous destinés à empêcher qu'un défaut d'enregistrement ne
    se blanchisse en abstention :
      - l'en-tête doit décrire la projection courante, sinon `TranscriptionIncompatible` ;
      - une clé mal formée est refusée (la clé entière, jamais un préfixe) ;
      - un `texte` vide est refusé au chargement : vide et abstention sont indiscernables
        en aval, donc l'ambiguïté est tranchée ici, où l'on sait encore laquelle c'est.

    Un raté lève `ReponseAbsente` : la structure est un `dict` nu, jamais un `defaultdict`,
    dont la valeur par défaut inventerait une réponse.
    """

    nom = "rejeu"
    cout_declare_par_appel = 0

    def __init__(self, transcription: dict, verifie_entete: bool = True):
        entete = dict(transcription.get("entete") or {})
        reponses = transcription.get("reponses")
        if not isinstance(reponses, dict):
            raise TranscriptionIncompatible(
                "transcription sans table 'reponses' : rien a rejouer")
        if verifie_entete:
            attendu = entete_de_projection()
            for cle in sorted(attendu):
                if entete.get(cle) != attendu[cle]:
                    raise TranscriptionIncompatible(
                        f"en-tete incompatible sur {cle!r} : transcription="
                        f"{entete.get(cle)!r}, projection courante={attendu[cle]!r}")
        table = {}
        for cle in sorted(reponses):
            if not (isinstance(cle, str) and len(cle) == LONGUEUR_CLE):
                raise TranscriptionIncompatible(
                    f"cle de rejeu mal formee (sha256 entier attendu) : {cle!r}")
            texte = (reponses[cle] or {}).get("texte")
            if not isinstance(texte, str) or not texte.strip():
                raise TranscriptionIncompatible(
                    f"reponse vide pour la cle {cle} : un enregistrement rate ne doit pas "
                    f"se lire comme une abstention")
            table[cle] = texte
        self._table = table
        self.entete = entete
        self.provenance = dict(transcription.get("provenance") or {})

    def disponible(self) -> bool:
        return True

    def contient(self, cle: str) -> bool:
        return cle in self._table

    def repond(self, invite: str) -> str:
        raise NotImplementedError(
            "le client de rejeu repond a une CLE, pas a une invite : utiliser repond_a_cle")

    def repond_a_cle(self, cle: str) -> str:
        """Réponse enregistrée pour cette clé, ou `ReponseAbsente`. Jamais d'invention."""
        if cle not in self._table:
            raise ReponseAbsente(cle)
        return self._table[cle]

    def description(self) -> dict:
        carte = super().description()
        carte["n_reponses"] = len(self._table)
        carte["provenance"] = dict(self.provenance)
        return carte
