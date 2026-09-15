/* Logique PURE du bac à sable : composition des phrases et arithmétique des compteurs.
 *
 * ## Pourquoi ce fichier est séparé
 * Toute la logique métier qui vit dans le navigateur est ici — composition des phrases,
 * arithmétique des compteurs, règles d'annonce — et rien ne la gardait. Une première
 * tentative l'avait RÉPLIQUÉE en Python dans la suite de tests : les
 * oracles éprouvaient alors la réplique, jamais le code servi, et le seul lien entre les deux
 * était une recherche de sous-chaînes qui survivait à n'importe quelle réécriture. La garde
 * annoncée n'existait pas — c'est le motif exact que ce projet a déjà rencontré trois fois.
 *
 * Isolées ici, sans aucune dépendance au DOM, elles sont chargées telles quelles par la page
 * ET exécutées telles quelles par les tests, via Node. Les oracles éprouvent donc le code qui
 * tourne réellement devant le prospect, et non une paraphrase qu'il faudrait tenir à jour.
 */
"use strict";

const LIBELLES = {
  record_id: "identifiant", source_id: "source", nom: "nom", prenom: "prénom",
  date_naissance: "date de naissance", adresse: "adresse", code_postal: "code postal",
  ville: "ville", email: "e-mail", telephone: "téléphone",
};

/* Genre des libellés, pour accorder « seul » / « seule » et poser l'article. Sans cela la
 * phrase de preuve écrivait « Seul téléphone diffère » — sans article et au masculin quel que
 * soit le champ — sur les trois scénarios livrés. */
const GENRES = {
  nom: "m", prenom: "m", date_naissance: "f", adresse: "f",
  code_postal: "m", ville: "f", email: "m", telephone: "m",
};

function libelle(champ) { return LIBELLES[champ] || champ; }

/* L'accord du nombre était traité pour les sources et pour rien d'autre : un essai à deux
 * lignes affichait « 1 fiches uniques », « 1 paires comparées ». */
function accord(n, singulier, pluriel) {
  return `${n} ${n > 1 ? (pluriel || singulier + "s") : singulier}`;
}

function enumere(champs) {
  const noms = champs.map(libelle);
  if (noms.length === 0) return "";
  if (noms.length === 1) return noms[0];
  return noms.slice(0, -1).join(", ") + " et " + noms[noms.length - 1];
}

function avecArticle(champ) {
  const nom = libelle(champ);
  if (/^[aeiouéèêAEIOU]/.test(nom)) return "l'" + nom;
  return (GENRES[champ] === "f" ? "la " : "le ") + nom;
}

function enumereAvecArticles(champs) {
  const noms = champs.map(avecArticle);
  if (noms.length === 0) return "";
  if (noms.length === 1) return noms[0];
  return noms.slice(0, -1).join(", ") + " et " + noms[noms.length - 1];
}

/** La phrase qui explique un rapprochement, en français et non en télégramme.
 *
 * Trois classes, et la distinction n'est pas cosmétique :
 *   - IDENTIQUES : les deux valeurs brutes sont les mêmes ;
 *   - ÉQUIVALENTES : les valeurs brutes diffèrent mais la NORMALISATION les rend égales
 *     (« 3 rue de la Gare » / « 3 r. de la Gare »). C'est là, et là seulement, qu'on peut
 *     dire « la même chose écrite différemment » ;
 *   - PROCHES : le moteur a conclu à un accord fort par SIMILARITÉ (seuil 0,90), sans que la
 *     normalisation les rende égales. « 10 avenue Jean Jaurès » et « 12 avenue Jean Jaurès »
 *     sont proches, ce ne sont PAS deux graphies de la même adresse — l'écrire serait
 *     affirmer, sur la carte la plus argumentative de la démonstration, quelque chose que le
 *     lecteur voit être faux.
 */
function phraseDeProuve(preuve, sujet, recordA, recordB) {
  const egalesApresNormalisation = new Set(preuve.identiques_apres_normalisation || []);
  const identiques = [], equivalentes = [], proches = [];
  for (const champ of preuve.concordent) {
    const a = recordA && recordA[champ], b = recordB && recordB[champ];
    /* L'ABSENCE de valeur ne vaut pas égalité. La version précédente rangeait dans
     * « identiques » tout champ dont une valeur manquait — y compris quand les deux
     * enregistrements étaient absents faute d'avoir été passés — et la phrase affirmait
     * « mêmes adresse » au-dessus de deux adresses différentes. Le correctif qui a fait
     * passer les enregistrements ne suffit pas : si un jour ils cessent d'arriver, il faut
     * que la phrase devienne PRUDENTE, et non fausse. Sans valeurs, on n'affirme rien. */
    if (a == null || b == null) proches.push(champ);
    else if (String(a) === String(b)) identiques.push(champ);
    else if (egalesApresNormalisation.has(champ)) equivalentes.push(champ);
    else proches.push(champ);
  }
  for (const champ of preuve.concordent_partiellement) proches.push(champ);

  const morceaux = [];
  if (identiques.length) {
    morceaux.push((identiques.length > 1 ? "mêmes " : "même ") + enumere(identiques));
  }
  if (equivalentes.length) {
    morceaux.push(enumereAvecArticles(equivalentes)
      + (equivalentes.length > 1 ? " concordent" : " concorde")
      + " malgré une écriture différente");
  }
  if (proches.length) {
    morceaux.push(enumereAvecArticles(proches)
      + (proches.length > 1 ? " sont proches" : " est proche"));
  }

  let phrase = sujet + " : " + (morceaux.join(" ; ") || "aucune information commune");
  if (preuve.divergent.length) {
    const pluriel = preuve.divergent.length > 1;
    const tete = pluriel ? "Seuls "
      : (GENRES[preuve.divergent[0]] === "f" ? "Seule " : "Seul ");
    phrase += ". " + tete + enumereAvecArticles(preuve.divergent)
      + (pluriel ? " diffèrent." : " diffère.");
  } else {
    phrase += ".";
  }
  return phrase;
}

/** Les compteurs après arbitrage de l'utilisateur.
 *
 * SEUL « fusionner » change quelque chose : les deux fiches d'un doute sont déjà comptées là
 * où le moteur les a laissées, et « garder séparées » ne fait que confirmer sa décision.
 *
 * Union-find sur les ENTITÉS, et non traitement isolé de chaque doute : un même
 * enregistrement peut figurer dans deux doutes, et fusionner A-B puis B-C ne retire qu'une
 * entité la seconde fois. Traiter les arbitrages indépendamment, à partir des tailles
 * d'origine, donnait des compteurs faux dès la deuxième fusion.
 */
function compteurs(scenario, arbitrages) {
  let consolidees = scenario.n_consolidees;
  let dejaUniques = scenario.n_deja_uniques;
  let fiches = scenario.n_fiches_uniques;
  let arbitres = 0;

  const parent = new Map(), taille = new Map();
  const racine = (x) => {
    if (!parent.has(x)) parent.set(x, x);
    while (parent.get(x) !== x) { parent.set(x, parent.get(parent.get(x))); x = parent.get(x); }
    return x;
  };

  for (const doute of scenario.a_confirmer) {
    if (!taille.has(doute.entite_a)) taille.set(doute.entite_a, doute.taille_entite_a);
    if (!taille.has(doute.entite_b)) taille.set(doute.entite_b, doute.taille_entite_b);
  }

  for (const doute of scenario.a_confirmer) {
    const choix = arbitrages[doute.a + "|" + doute.b];
    if (!choix) continue;
    /* « Je ne sais pas » ne RÉSOUT pas le doute : le compter comme arbitré faisait tomber la
     * file à zéro pendant que trois cas restaient explicitement en attente — le produit
     * sous-déclarait le doute dans le sens qui le flatte, ce que la surface reproche
     * ailleurs. « Garder séparées », lui, tranche : il confirme la décision du moteur. */
    if (choix === "inconnu") continue;
    arbitres += 1;
    if (choix !== "fusionner") continue;
    const ra = racine(doute.entite_a), rb = racine(doute.entite_b);
    if (ra === rb) continue;
    const ta = taille.get(ra), tb = taille.get(rb);
    fiches -= 1;
    if (ta === 1 && tb === 1) { dejaUniques -= 2; consolidees += 1; }
    else if (ta === 1 || tb === 1) { dejaUniques -= 1; }
    else { consolidees -= 1; }
    parent.set(rb, ra);
    taille.set(ra, ta + tb);
  }
  return {
    consolidees, deja_uniques: dejaUniques, fiches,
    a_confirmer: scenario.n_a_confirmer - arbitres,
    montres: scenario.a_confirmer.length,
    total: scenario.n_a_confirmer,
    arbitres,
  };
}

/** La note qui explique la parenthèse sur une fiche consolidée.
 *
 * Deux accords, et non un : le nombre de CHAMPS en désaccord commande « la valeur retenue » /
 * « les valeurs retenues », le nombre de VALEURS écartées commande « l'autre » / « les
 * autres ». La phrase écrivait « l'autre entre parenthèses » au singulier devant trois champs
 * et deux graphies concurrentes — sous une carte qui promet la fiche propre.
 *
 * `ecartees` : { champ: [valeurs écartées] }, tel que l'artefact le publie.
 */
function phraseValeursEcartees(ecartees) {
  /* Comme `annonceTroncature` : l'absence de la table est un DÉFAUT, pas un cas vide. Le
   * `|| {}` qui tenait ici a masqué pendant tout le mode manuel le fait que la table n'y
   * était jamais construite — la note ne s'affichait pas, et rien ne le disait. */
  if (ecartees == null || typeof ecartees !== "object") {
    throw new TypeError("phraseValeursEcartees attend la table des valeurs écartées");
  }
  const champs = Object.keys(ecartees).filter((c) => (ecartees[c] || []).length);
  if (!champs.length) return "";
  const nValeurs = champs.reduce((n, c) => n + ecartees[c].length, 0);
  return "Les sources divergeaient sur " + enumereAvecArticles(champs) + " : "
    + (champs.length > 1 ? "les valeurs retenues sont indiquées"
                         : "la valeur retenue est indiquée") + " en premier, "
    + (nValeurs > 1 ? "les autres" : "l'autre") + " entre parenthèses.";
}

/** Un nombre écrit à la française : virgule décimale, espace fine avant les milliers. */
function nombreFr(valeur, decimales) {
  if (valeur == null || Number.isNaN(Number(valeur))) return "—";
  const fixe = Number(valeur).toFixed(decimales == null ? 3 : decimales);
  /* Le signe moins TYPOGRAPHIQUE (U+2212), et non le trait d'union du clavier : c'est la
   * convention du projet (`format.py` la porte côté serveur), et sur « −8,325 » la différence
   * se voit — le trait d'union se lit comme une césure. */
  const negatif = fixe.startsWith("-");
  const [entier, fraction] = (negatif ? fixe.slice(1) : fixe).split(".");
  const groupe = entier.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return (negatif ? "−" : "") + (fraction ? `${groupe},${fraction}` : groupe);
}

/** Ce qui a réglé CE scénario : ses propres seuils, et le budget de revue qui les a fixés.
 *
 * La page n'affichait qu'un seul couple de seuils — celui de la saisie manuelle — alors que
 * chaque scénario a re-dérivé le sien sur ses propres données : +2,650 d'un côté, −8,325 de
 * l'autre. Le lecteur attribuait aux résultats qu'il regarde des seuils qui ne les ont pas
 * produits. Et il ne voyait pas non plus pourquoi la file de doutes est si courte : le budget
 * de revue de ces scénarios est volontairement bas, pour qu'elle s'instruise en un coup d'œil.
 * Taire ce réglage, c'est laisser croire à une propriété du moteur ce qui est un choix de
 * démonstration.
 */
function noteDuPoint(scenario) {
  const point = scenario && scenario.point;
  if (!point || point.t_mu == null || point.t_lambda == null) {
    throw new TypeError("noteDuPoint attend le point de fonctionnement du scénario");
  }
  const budget = (point.provenance || {}).budget_vise;
  const seuils = `Tμ = ${nombreFr(point.t_mu)}, Tλ = ${nombreFr(point.t_lambda)}`;
  let phrase = `Seuils propres à ce scénario (${seuils}) : ils ont été redimensionnés sur `
             + `ses propres données, pas repris d'ailleurs.`;
  if (budget != null) {
    phrase += ` Le budget de revue visé y est volontairement bas — `
            // « cas » et « à confirmer » sont invariables : le pluriel est donné, sans quoi
            // `accord` écrirait « 4 cas à confirmers ».
            + `${accord(budget, "cas à confirmer", "cas à confirmer")} — pour que la file `
            + `s'instruise ici d'un `
            + `coup d'œil. C'est un réglage de démonstration, pas une propriété du moteur.`;
  }
  return phrase;
}

/** L'annonce de troncature de la file de doutes, ou la chaîne vide s'il n'y a rien à annoncer.
 *
 * La section des consolidées dit « et N autres » ; celle des doutes le taisait, et le lecteur
 * croyait voir toute la zone grise. La règle vit ICI, et non dans le rendu, pour une raison
 * précise : elle était gardée par une recherche de la sous-chaîne `"c.total > c.montres"` dans
 * le source de `bac.js`. Un oracle qui cherche du texte dans du code ne prouve pas que le code
 * fait ce qu'il dit — n'importe quelle réécriture équivalente le fait rougir, n'importe quelle
 * suppression du comportement en gardant la ligne le laisse vert. Sortie ici, la règle
 * s'exécute et se teste.
 */
function annonceTroncature(c) {
  /* Les clés sont EXIGÉES, pas lues au petit bonheur. Avec un simple `c.total > c.montres`,
   * un objet auquel il manque `montres` — parce qu'on aurait renommé un champ dans
   * `compteurs` — rendait la chaîne vide en silence : l'annonce disparaissait de la page sans
   * qu'aucun test ne rougisse, et le lecteur croyait de nouveau voir toute la zone grise.
   * Une clé absente est un défaut de programmation, pas une valeur : elle doit crier. */
  if (!c || typeof c.total !== "number" || typeof c.montres !== "number") {
    throw new TypeError("annonceTroncature attend les compteurs {total, montres}");
  }
  if (!(c.total > c.montres)) return "";
  /* `accord` et non une concaténation : « 1 cas détaillés ci-dessous » était la seule phrase
   * de prose du fichier qu'aucun scan ne traversait, et elle était fautive. */
  return `${accord(c.montres, "cas détaillé")} ci-dessous, sur ${c.total} que le moteur a `
       + `laissés en attente.`;
}

/* Le navigateur ignore cette ligne (`module` y est indéfini) ; Node s'en sert pour charger
 * EXACTEMENT ce code dans les tests. C'est ce qui fait que les oracles éprouvent le fichier
 * servi, et non une réplique. */
if (typeof module !== "undefined" && module.exports) {
  module.exports = { LIBELLES, GENRES, libelle, accord, enumere, avecArticle,
                     enumereAvecArticles, phraseDeProuve, compteurs, annonceTroncature,
                     phraseValeursEcartees, nombreFr, noteDuPoint };
}
