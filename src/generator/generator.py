# SPDX-License-Identifier: LicenseRef-AntoineMaurin-Proprietary
# Copyright © 2026 Antoine Maurin — https://antoine-maurin.com
# Tous droits réservés / All rights reserved.
# Composant du démonstrateur « moteur-rapprochement ».
# Reproduction, modification ou redistribution interdites sans autorisation écrite.

"""Générateur GEN_001 — population BULK vérité terrain, reproductible from-seed.

Spec : design GEN-01 +
§5.1 (schéma SOURCE_RECORD), §5.4 (vérité terrain), §5.6 (8 catégories de corruption),
§7.6 (dédup 1-à-1). 100% synthétique (OS-1). Déterministe (même graine => même pack).

Frontière de non-circularité : ce module produit données + vérité terrain ; il NE recompte JAMAIS de
métriques (précision/rappel = scoreur indépendant). Le moteur ne lit jamais la vérité
terrain. GEN_001 produit la population BULK ; FIXTURE_PACK_GT_V1_1 est un pack
curaté distinct (référence de benchmark), vérifiable via canonicalization.verify_pack.
"""
from __future__ import annotations
import hashlib
import random
from typing import Optional

from .canonicalization import content_sha256, seal_sha256_16

# --- Taux scellés (design GEN-01 §3, rates_sealed du manifest FX_001) ---
RATES_SEALED = {
    "frac_multi_records": 0.35,
    "records_per_entity": "2-3",
    "cat_rates": {"FORMAT": 0.30, "TYPO": 0.25, "BRUIT_STRUCT": 0.18,
                  "PHON": 0.12, "MANQUANT": 0.12, "TRONC": 0.08, "TRANSPO": 0.05},
    "max_cats_per_record": "1-3",
}
GENERATOR_VERSION = "GEN-01_V1"
SOURCES = ("SRC_A", "SRC_B", "SRC_C")
ATTRIBUTS_COMPARE = ("nom", "prenom", "date_naissance", "adresse",
                     "code_postal", "ville", "email", "telephone")

# --- Banques synthétiques FR (valeurs générées, jamais réelles — OS-1) ---
_NOMS = ["Dupont", "Martin", "Bernard", "Dubois", "Thomas", "Petit", "Durand", "Leroy",
         "Moreau", "Simon", "Laurent", "Lefebvre", "Michel", "Bertrand", "Roux", "Vincent",
         "Fournier", "Girard", "Rousseau", "Fontaine", "Benali", "Lefevre", "Morel", "Andre"]
_PRENOMS = ["Marie", "Jean", "Pierre", "Sophie", "Luc", "Claire", "Paul", "Julie", "Nicolas",
            "Emma", "Camille", "Antoine", "Hugo", "Louis", "Manon", "Alexandre", "Sarah",
            "Isabelle", "Ahmed", "Emilie", "Thomas", "Chloe"]
_VILLES = [("Paris", "75011"), ("Lyon", "69003"), ("Marseille", "13001"), ("Bordeaux", "33000"),
           ("Lille", "59000"), ("Nantes", "44000"), ("Strasbourg", "67000"), ("Dijon", "21000"),
           ("Toulouse", "31000"), ("Nice", "06000")]
_VOIE_TYPES = ["rue", "avenue", "boulevard", "place", "impasse", "allee", "chemin"]
_VOIE_NOMS = ["des Lilas", "Victor Hugo", "de la Republique", "Bellecour", "du Marche",
              "Nationale", "des Vignes", "des Fleurs", "des Roses", "de la Paix"]
_DOMAINES = ["example.fr", "mail.fr", "test.fr"]
_MORALES = ["SARL Boulangerie du Coin", "SAS Menuiserie Martin", "EURL Conseil Plus",
            "SA Transports Rapides", "SARL Fleurs et Jardins"]


def _seed_int(seed: str) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % (2 ** 32)


def _clean_entity(rng: random.Random, ent_idx: int) -> dict:
    """Un enregistrement propre (les 8 attributs §5.1). ~15% personnes morales."""
    if rng.random() < 0.15:
        nom = rng.choice(_MORALES)
        an = rng.randint(1995, 2020)
        return {"nom": nom, "prenom": None,
                "date_naissance": f"{an:04d}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
                "adresse": f"{rng.randint(1,99)} {rng.choice(_VOIE_TYPES)} {rng.choice(_VOIE_NOMS)}",
                "code_postal": rng.choice(_VILLES)[1], "ville": None,
                "email": "contact@" + nom.split()[-1].lower().replace('.', '') + ".fr",
                "telephone": _tel(rng), "_ville_src": rng.choice(_VILLES)}
    nom = rng.choice(_NOMS)
    prenom = rng.choice(_PRENOMS)
    ville, cp = rng.choice(_VILLES)
    an = rng.randint(1955, 2000)
    local = f"{prenom[0].lower()}.{nom.lower()}"
    return {"nom": nom, "prenom": prenom,
            "date_naissance": f"{an:04d}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "adresse": f"{rng.randint(1,99)} {rng.choice(_VOIE_TYPES)} {rng.choice(_VOIE_NOMS)}",
            "code_postal": cp, "ville": ville,
            "email": f"{local}@{rng.choice(_DOMAINES)}", "telephone": _tel(rng)}


def _tel(rng: random.Random) -> str:
    d = [rng.randint(0, 9) for _ in range(8)]
    return "0" + str(rng.randint(1, 9)) + " " + " ".join(
        f"{d[i]}{d[i+1]}" for i in range(0, 8, 2))


# --- Corruptions §5.6 (chacune déterministe via rng ; retourne le record modifié) ---
def _c_typo(r, rng):
    for f in ("nom", "adresse", "ville"):
        if r.get(f):
            s = list(r[f]); i = rng.randrange(len(s))
            s[i] = rng.choice("abcdefghijklmnopqrstuvwxyz")
            r[f] = "".join(s); return r
    return r

def _c_phon(r, rng):
    subs = [("f", "ph"), ("Lefevre", "Lefebvre"), ("s", "ss"), ("i", "y"), ("c", "k")]
    for f in ("nom", "prenom", "ville"):
        if r.get(f):
            a, b = rng.choice(subs)
            if a in r[f].lower():
                idx = r[f].lower().index(a)
                r[f] = r[f][:idx] + b + r[f][idx + len(a):]; return r
    if r.get("nom"):
        r["nom"] = r["nom"] + "e"
    return r

def _c_format(r, rng):
    choix = rng.randrange(4)
    if choix == 0 and r.get("nom"):
        r["nom"] = r["nom"].upper()
    elif choix == 1 and r.get("adresse"):
        r["adresse"] = (r["adresse"].replace("avenue", "av.").replace("boulevard", "bd")
                        .replace("rue", "r."))
    elif choix == 2 and r.get("ville"):
        r["ville"] = r["ville"].upper()
    elif r.get("email"):
        r["email"] = r["email"].capitalize()
    return r

def _c_manquant(r, rng):
    cands = [f for f in ATTRIBUTS_COMPARE if r.get(f)]
    if cands:
        r[rng.choice(cands)] = None
    return r

def _c_tronc(r, rng):
    f = "nom" if r.get("nom") and rng.random() < 0.5 else "prenom"
    if r.get(f) and len(r[f]) > 2:
        r[f] = r[f][0] + ("-" + r[f].split("-")[-1][0] if "-" in r[f] else "")
    return r

def _c_transpo(r, rng):
    if r.get("nom") and r.get("prenom"):
        r["nom"], r["prenom"] = r["prenom"], r["nom"]
    return r

def _c_bruit_struct(r, rng):
    if rng.random() < 0.5 and r.get("telephone"):
        r["telephone"] = r["telephone"].replace(" ", "")
    elif r.get("code_postal") and r["code_postal"]:
        cp = list(r["code_postal"]); cp[-1] = str(rng.randint(0, 9)); r["code_postal"] = "".join(cp)
    elif r.get("email"):
        r["email"] = r["email"].replace("i", "", 1)
    return r

_CORRUPTORS = {"TYPO": _c_typo, "PHON": _c_phon, "FORMAT": _c_format, "MANQUANT": _c_manquant,
               "TRONC": _c_tronc, "TRANSPO": _c_transpo, "BRUIT_STRUCT": _c_bruit_struct}


def _pick_categories(rng: random.Random) -> list:
    """Choix stratifié des catégories (hors DOUBLON) selon cat_rates, 1..3 cumulées."""
    cats = [c for c in _CORRUPTORS if rng.random() < RATES_SEALED["cat_rates"][c]]
    rng.shuffle(cats)
    cats = cats[:rng.randint(1, 3)]
    if not cats:
        cats = [rng.choices(list(RATES_SEALED["cat_rates"]),
                            weights=list(RATES_SEALED["cat_rates"].values()))[0]]
    return sorted(cats)


def generate_pack(seed: str = "SP_CYCLE_001::GEN-01::seed-0001",
                  n_entities: int = 40) -> dict:
    """Produit un pack BULK vérité terrain reproductible-from-seed.

    Pipeline design §1 : entités propres -> projection en records (multi/singleton, dédup
    1-à-1 intra-source §7.6) -> corruption scellée §5.6 -> vérité terrain §5.4 -> annotation.
    Retourne {records, ground_truth, corruption_annotation, zone_intention_design, manifest}.
    """
    rng = random.Random(_seed_int(seed))
    records, ground_truth, corruption, zones = [], [], [], []
    rec_n = 0

    for e in range(1, n_entities + 1):
        ent_id = f"ENT_{e:04d}"
        clean = _clean_entity(rng, e)
        clean.pop("_ville_src", None)
        multi = rng.random() < RATES_SEALED["frac_multi_records"]
        k = (2 if rng.random() < 0.7 else 3) if multi else 1
        k = min(k, len(SOURCES))  # dédup 1-à-1 : au plus 1 record/source pour une entité
        srcs = rng.sample(SOURCES, k)
        origin_rec_id = None
        for j, src in enumerate(srcs):
            rec_n += 1
            rid = f"REC_{rec_n:04d}"
            rec = {"record_id": rid, "source_id": src}
            rec.update({a: clean[a] for a in ATTRIBUTS_COMPARE})
            if j == 0:
                cats_appl = None; origin = None; origin_rec_id = rid
                zone = "singleton" if not multi else "pivot"
            else:
                cats = _pick_categories(rng)
                # Voie (b) — annotation HONNETE : on applique toutes les categories tirees
                # (les taux scelles ne changent pas), mais on ne consigne que celles dont le
                # corrupteur a REELLEMENT mute >= 1 des 8 attributs compares. Un corrupteur
                # peut etre no-op selon l'etat du record (valeur None, motif absent, branche
                # sans effet) : l'annoter serait surdeclarer, alors que le design GEN-01 §1
                # etape 5 en fait un « support de preuve ».
                base = {a: rec[a] for a in ATTRIBUTS_COMPARE}  # = attributs du pivot d'origine
                cats_eff = []
                for c in cats:
                    avant = {a: rec[a] for a in ATTRIBUTS_COMPARE}
                    rec = {**rec, **{"record_id": rid, "source_id": src}}
                    _CORRUPTORS[c](rec, rng)
                    if any(rec[a] != avant[a] for a in ATTRIBUTS_COMPARE):
                        cats_eff.append(c)
                # Garde de coherence finale : si les effets se sont annules, le record est un
                # doublon exact — aucune categorie n'est reelle, quel que soit l'effet par etape.
                if all(rec[a] == base[a] for a in ATTRIBUTS_COMPARE):
                    cats_eff = []
                cats_appl = sorted(cats_eff + ["DOUBLON"]); origin = origin_rec_id
                n_deg = len([c for c in cats_eff if c in ("MANQUANT", "TRONC", "TRANSPO")])
                zone = "ZONE_GRISE" if (len(cats_eff) >= 2 and n_deg >= 1) else "MATCH"
            records.append(rec)
            ground_truth.append({"record_id": rid, "id_entite_vraie": ent_id})
            corruption.append({"record_id": rid, "categories_appliquees": cats_appl,
                               "record_id_origine": origin})
            zones.append({"record_id": rid, "zone_intention": zone})

    pack = {"records": records, "ground_truth": ground_truth,
            "corruption_annotation": corruption, "zone_intention_design": zones}
    ch = content_sha256(pack)
    pack["manifest"] = {
        "pack_id": "GEN_001_BULK", "generator_version": GENERATOR_VERSION, "seed": seed,
        "rates_sealed": RATES_SEALED, "content_sha256": ch,
        "seal_sha256_16": seal_sha256_16(seed, GENERATOR_VERSION, RATES_SEALED, ch),
        "disclaimer": "100% synthétique — aucune donnée réelle ni personnelle (OS-1).",
        "stats": {"n_entites_vraies": n_entities, "n_records": len(records)},
    }
    return pack
