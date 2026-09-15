"""Blocking multi-passes : records -> CANDIDATE_PAIR.

Le blocking réduit l'espace quadratique des paires à un ensemble de candidats plausibles,
au moyen de clés **bon marché** (égalité stricte sur une valeur dérivée). Les passes par
défaut, dont l'**union** forme l'ensemble des candidats :

| passe      | clé                                             | statut               |
|------------|-------------------------------------------------|----------------------|
| `CP`       | `code_postal` normalisé (égalité)               | par défaut           |
| `PREF`     | préfixe de `nom` + `prenom` normalisés          | par défaut           |
| `SDX_NOM`  | code phonétique Soundex du `nom` normalisé      | RETIRÉE du défaut    |

**Le code phonétique est une clé de blocking, jamais un scoreur** (mandat §2) : il ne
sort pas d'ici et n'entre dans aucun poids.

## Retrait de `SDX_NOM` du défaut — acte ARCHI (objectif O0a)
La passe est retirée du **défaut** ; la fonction `soundex` et la clé `"SDX_NOM"` restent
disponibles et testées, et un appelant peut toujours demander la passe explicitement. Retirer
le code plutôt que le défaut rendrait le retrait irréversible et invérifiable — or c'est
précisément sa réversibilité qui permet de le contrôler (cf. `PASSES_RETIREES_DU_DEFAUT`).

**Déclaration, et elle est inconfortable.** Le motif du retrait — contribution marginale nulle
— est une information de **vérité terrain**, mesurée par le scoreur, dont l'artefact de
l'époque avertissait lui-même : « régler les passes après l'avoir lue transformerait un
blocking non calibré en blocking calibré sur l'évaluation ». Ce retrait est donc un paramètre
**choisi après lecture de la vérité terrain**. Trois choses le rendent néanmoins publiable, et
aucune ne l'efface :
  1. il est **ordonné par le mandat** (acte d'architecture), non décidé ici pour améliorer un
     chiffre — la surface d'exécution ne l'a ni proposé ni arbitré ;
  2. son effet est **borné et vérifié** : il ne retire que des paires candidates, jamais une
     vraie paire unique, donc le rappel de blocking est inchangé au chiffre près — ce que la
     DoD du banc de comparaison exige de re-vérifier plutôt que de supposer ;
  3. il est **déclaré dans l'artefact de comparaison** comme asymétrie, avec sa direction :
     il ne peut que réduire le nombre de faux positifs offerts à la décision, donc il joue en
     faveur du moteur maison, et il est publié comme tel.
Ce qu'il ne faut pas en conclure : que le blocking est « calibré ». Aucune autre valeur (les
passes restantes, la longueur de préfixe) n'a été touchée, et aucune ne le sera dans cette
unité.

Paramétrage (quelles passes, quelle longueur de préfixe) = **calibration différée** :
les valeurs ci-dessous sont des défauts raisonnables DÉCLARÉS, non calibrés.

Frontière de non-circularité : aucune donnée de vérité terrain n'est lue ; rien n'est mesuré ici.
"""
from __future__ import annotations

from typing import Optional

# --- Paramètres par défaut — NON CALIBRÉS (mandat §0 constraints) --------------------
PASSES_DEFAUT = ("CP", "PREF")    # SDX_NOM retirée (O0a) : cf. PASSES_RETIREES_DU_DEFAUT.
LONGUEUR_PREFIXE_DEFAUT = 4       # NON CALIBRÉ : défaut raisonnable, à arbitrer après le scoreur.
SOUNDEX_LONGUEUR = 4              # Longueur classique du code Soundex (1 lettre + 3 chiffres).

#: Passes disponibles mais RETIRÉES du défaut, avec le motif et le statut du retrait. Cette
#: table existe pour qu'un retrait ne puisse pas se faire en silence : elle est publiée dans
#: l'artefact de comparaison, et un test vérifie que le retrait est bien absent du défaut ET
#: que la passe reste appelable — un paramètre retiré sans trace serait un paramètre calibré.
PASSES_RETIREES_DU_DEFAUT = {
    "SDX_NOM": {
        "retiree_en": "banc de comparaison",
        "decide_par": "ARCHI — acte d'architecture, non arbitré par la surface d'exécution",
        "motif": ("contribution marginale nulle mesurée par le scoreur : la passe apportait 5 079 paires "
                  "candidates et pas une seule vraie paire qu'une autre passe n'apportait déjà"),
        "statut": "choisie_apres_lecture_verite_terrain",
        "effet_attendu": ("réduit l'ensemble candidat sans toucher au rappel de blocking ; ne peut "
                          "que retirer des faux positifs offerts à la décision"),
        "direction_du_biais": "moteur_maison",
        "reversible": "oui — passer passes=('CP', 'SDX_NOM', 'PREF') rétablit le comportement",
    },
}

_CODES_SOUNDEX = {
    "B": "1", "F": "1", "P": "1", "V": "1",
    "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
    "D": "3", "T": "3",
    "L": "4",
    "M": "5", "N": "5",
    "R": "6",
    "A": "0", "E": "0", "I": "0", "O": "0", "U": "0", "Y": "0",
    "H": "H", "W": "H",
}


def _lettres(valeur: str) -> str:
    """Suite des lettres ASCII majuscules d'une forme déjà normalisée (accents repliés)."""
    return "".join(c for c in valeur.upper() if "A" <= c <= "Z")


def soundex(valeur: Optional[str]) -> Optional[str]:
    """Code Soundex (variante classique) d'une chaîne DÉJÀ normalisée.

    Les espaces sont ignorés avant codage : « ben ali » et « benali » reçoivent donc le
    même code — c'est précisément le genre de variante de segmentation qu'une passe
    phonétique doit rattraper. `H` et `W` sont *transparents* (ils ne rompent pas une
    suite de consonnes de même code) alors que les voyelles la rompent : c'est la règle
    classique, et l'écart entre les deux est la source d'erreur habituelle.

    Retourne `None` si la valeur ne contient aucune lettre (jamais une clé vide, qui
    regrouperait à tort tous les enregistrements sans nom).
    """
    if valeur is None:
        return None
    lettres = _lettres(valeur)
    if not lettres:
        return None
    sortie = [lettres[0]]
    precedent = _CODES_SOUNDEX.get(lettres[0], "0")
    for caractere in lettres[1:]:
        code = _CODES_SOUNDEX.get(caractere, "0")
        if code == "H":
            continue                      # transparent : `precedent` est conservé
        if code != "0" and code != precedent:
            sortie.append(code)
        precedent = code                  # une voyelle remet le compteur à zéro
    return ("".join(sortie) + "000")[:SOUNDEX_LONGUEUR]


def cle_prefixe(nrecord: dict, longueur: int = LONGUEUR_PREFIXE_DEFAUT) -> Optional[str]:
    """Clé « préfixe » : `longueur` premiers caractères de `nom` + `prenom` concaténés.

    Les espaces internes sont retirés pour que « ben ali » et « benali » partagent le
    préfixe. Un `prenom` absent (cas des personnes morales) n'invalide pas la clé : le nom
    seul suffit — sinon aucune personne morale ne serait jamais bloquée par cette passe.
    Retourne `None` si le nom est absent : un record sans nom est **écarté** de la passe,
    il n'est pas versé dans un seau « clé vide » (ce seau apparierait entre eux tous les
    records dépourvus de nom, ce qui est un faux bloc).
    """
    if not nrecord.get("nom"):
        return None
    brut = (nrecord.get("nom") or "").replace(" ", "") + (nrecord.get("prenom") or "").replace(" ", "")
    cle = brut[:longueur]
    return cle or None


def cles_de_blocking(nrecord: dict, passes=PASSES_DEFAUT,
                     longueur_prefixe: int = LONGUEUR_PREFIXE_DEFAUT) -> list:
    """Clés d'un enregistrement normalisé, sous forme `[(passe, cle), ...]`.

    Une passe dont la clé vaut `None` est simplement absente : le record ne participe pas
    à cette passe. L'ordre suit `passes` (déterminisme).
    """
    calcul = {
        "CP": lambda r: r.get("code_postal") or None,
        "SDX_NOM": lambda r: soundex(r.get("nom")),
        "PREF": lambda r: cle_prefixe(r, longueur_prefixe),
    }
    sortie = []
    for passe in passes:
        if passe not in calcul:
            raise ValueError(f"passe de blocking inconnue : {passe!r}")
        cle = calcul[passe](nrecord)
        if cle:
            sortie.append((passe, cle))
    return sortie


def genere_paires_candidates(nrecords, passes=PASSES_DEFAUT,
                             longueur_prefixe: int = LONGUEUR_PREFIXE_DEFAUT,
                             taille_bloc_max: Optional[int] = None) -> dict:
    """Union multi-passes des paires candidates.

    Retourne `{"paires": [CANDIDATE_PAIR, ...], "trace": {...}}`.

    CANDIDATE_PAIR = `{"record_id_a", "record_id_b", "bloc_origine"}` avec :
      - `record_id_a < record_id_b` (comparaison lexicographique de chaînes, stricte :
        l'auto-paire est donc structurellement impossible) ;
      - `bloc_origine` : liste TRIÉE des `"<passe>:<clé>"` ayant produit la paire — une
        paire trouvée par deux passes en porte deux, l'union ne perd aucune provenance.

    La liste de paires est triée par `(record_id_a, record_id_b)` : la sortie ne dépend
    donc d'aucun ordre d'itération de dict ou de set.

    `taille_bloc_max` est `None` par défaut : **aucun plafond silencieux**. Si un plafond
    est fourni, les blocs écartés sont énumérés dans `trace["blocs_ecartes"]` — une
    troncature doit toujours être visible dans la sortie (mandat : « no silent caps »).
    """
    nrecords = list(nrecords)        # matérialisé une fois : un itérateur ne se relit pas
    seaux = {}                       # (passe, cle) -> [record_id, ...] dans l'ordre d'entrée
    doublons_id = []
    vus = set()
    for nrec in nrecords:
        rid = nrec.get("record_id")
        if rid in vus:
            doublons_id.append(rid)
        vus.add(rid)
        for passe, cle in cles_de_blocking(nrec, passes, longueur_prefixe):
            seaux.setdefault((passe, cle), []).append(rid)

    origines = {}                    # (a, b) -> set des étiquettes de provenance
    blocs_ecartes = []
    for (passe, cle) in sorted(seaux):
        membres = seaux[(passe, cle)]
        if len(membres) < 2:
            continue
        if taille_bloc_max is not None and len(membres) > taille_bloc_max:
            blocs_ecartes.append({"passe": passe, "cle": cle, "taille": len(membres)})
            continue
        etiquette = f"{passe}:{cle}"
        ordonnes = sorted(membres)
        for i in range(len(ordonnes)):
            for j in range(i + 1, len(ordonnes)):
                a, b = ordonnes[i], ordonnes[j]
                if a == b:
                    continue         # même identifiant deux fois : jamais d'auto-paire
                origines.setdefault((a, b), set()).add(etiquette)

    paires = [{"record_id_a": a, "record_id_b": b,
               "bloc_origine": sorted(origines[(a, b)])}
              for (a, b) in sorted(origines)]

    trace = {
        "passes": list(passes),
        "longueur_prefixe": longueur_prefixe,
        "taille_bloc_max": taille_bloc_max,
        "n_records": len(nrecords),
        "n_blocs_utiles": sum(1 for k in seaux if len(seaux[k]) >= 2),
        "n_paires": len(paires),
        "blocs_ecartes": blocs_ecartes,
        "record_id_dupliques": sorted(set(doublons_id)),
        "parametres_non_calibres": ["longueur_prefixe", "passes"],
    }
    return {"paires": paires, "trace": trace}
