/* Bac à sable — client. Vanilla, aucune dépendance distante (le produit tourne hors ligne).
 *
 * Ce script ne DÉCIDE rien. Les scénarios affichent un résultat calculé au build et servi
 * par /api/scenario ; la saisie manuelle envoie l'entrée au moteur et rend ce qui revient.
 * Toute la logique de rapprochement vit côté serveur, dans `engine`. Un rendu qui
 * recalculerait ici ferait exister un second chemin de décision, et le premier symptôme en
 * serait une démonstration qui ne correspond plus au moteur mesuré.
 *
 * La seule chose que ce script fait « bouger » est l'ARBITRAGE DE L'UTILISATEUR sur un cas
 * douteux : il déplace la paire d'une section à l'autre et met les compteurs à jour. C'est
 * une décision humaine appliquée à l'affichage, pas un verdict du moteur recalculé.
 */
"use strict";

/* `libelle`, `accord`, `enumere`, `enumereAvecArticles`, `phraseDeProuve` et `compteurs`
 * viennent de logique.js, chargé avant ce fichier. Ils y vivent parce que les tests les
 * exécutent, TELS QUELS, sous Node : les oracles éprouvent ainsi le code servi au navigateur
 * plutôt qu'une réplique qu'il faudrait tenir à jour. */

const CHAMPS = JSON.parse(document.getElementById("champs-record").textContent);
/* Le plafond du serveur, LU et non recopié : les deux ont vocation à diverger, et c'est le
 * navigateur qui aurait tronqué en silence. */
const LONGUEUR_MAX_VALEUR =
  JSON.parse(document.getElementById("longueur-max-valeur").textContent);
const EXTRAIT = JSON.parse(document.getElementById("extrait-initial").textContent);

const $ = (id) => document.getElementById(id);
const lignes = $("lignes");

function elt(balise, classe, texte) {
  const noeud = document.createElement(balise);
  if (classe) noeud.className = classe;
  if (texte != null) noeud.textContent = texte;
  return noeud;
}

function nomLisible(record) {
  return [record.prenom, record.nom].filter(Boolean).join(" ") || record.record_id;
}

/* ============================ Les scénarios ============================ */

let scenarioCourant = null;
let arbitrages = {};       // paire -> "fusionner" | "separer" | "inconnu"


function rendFichiers(scenario) {
  const zone = $("cartes-fichiers");
  zone.innerHTML = "";
  for (const fichier of scenario.fichiers) {
    const carte = elt("div", "carte-fichier");
    carte.appendChild(elt("span", "format " + fichier.format, fichier.format.toUpperCase()));
    carte.appendChild(elt("span", "nom", fichier.nom));
    carte.appendChild(elt("span", "lignes", fichier.n_lignes + " lignes"));
    zone.appendChild(carte);
  }
}

function rendResume(scenario) {
  const c = compteurs(scenario, arbitrages);
  const bloc = elt("div", "resume-nettoyage");
  const avant = elt("div", "avant-apres");
  avant.appendChild(elt("span", "nombre", String(scenario.n_lignes)));
  avant.appendChild(elt("span", "legende",
    scenario.n_lignes > 1 ? "lignes en désordre" : "ligne en désordre"));
  avant.appendChild(elt("span", "fleche", "→"));
  avant.appendChild(elt("span", "nombre resultat", String(c.fiches)));
  avant.appendChild(elt("span", "legende",
    c.fiches > 1 ? "fiches uniques" : "fiche unique"));
  bloc.appendChild(avant);
  const detail = elt("p", "detail-sections");
  detail.textContent = accord(c.consolidees, "fiche consolidée", "fiches consolidées")
    + " · " + c.deja_uniques + " déjà "
    + (c.deja_uniques > 1 ? "uniques" : "unique")
    + " · " + c.a_confirmer + " à confirmer";
  bloc.appendChild(detail);
  return bloc;
}

function rendGroupe(groupe) {
  /* Les deux modes du bac à sable passent ici, et le mode manuel a longtemps omis
   * `valeurs_ecartees` : la carte affichait alors la graphie corrompue en gras comme fiche
   * propre. Un repli silencieux rendait ce manque invisible ; on l'exige. */
  if (!groupe.valeurs_ecartees) {
    throw new TypeError("rendGroupe : valeurs_ecartees manquant — la fiche consolidée "
                        + "afficherait la valeur retenue sans son arbitrage");
  }
  const bloc = elt("div", "entite");
  const haut = elt("div", "haut");
  const titre = elt("b", null, nomLisible(groupe.enregistrement_dore));
  /* Le titre en gras portait la graphie retenue par la fusion — parfois la corrompue
   * (« Aubri ») — sans la concurrente, alors que le corps de la carte l'affiche. Le lecteur
   * voyait un nom fabriqué en tête d'une « fiche propre ». On lui donne l'arbitrage là aussi. */
  const ecarteesNom = groupe.valeurs_ecartees.nom;
  if (ecarteesNom && ecarteesNom.length) {
    titre.appendChild(elt("span", "ecartee", " (ou " + ecarteesNom.join(", ") + ")"));
  }
  haut.appendChild(titre);
  haut.appendChild(elt("span", "compte",
    accord(groupe.membres.length, "fiche réunie", "fiches réunies")));
  bloc.appendChild(haut);

  const corps = elt("div", "dore");
  /* Pas de `|| {}` : une table absente est un défaut d'appel, et le repli silencieux avait
   * caché que le mode manuel ne la construisait jamais. `phraseValeursEcartees` lève. */
  const ecartees = groupe.valeurs_ecartees;
  for (const champ of CHAMPS) {
    if (champ === "record_id" || champ === "source_id") continue;
    const valeur = groupe.enregistrement_dore[champ];
    if (!valeur) continue;
    const ligne = elt("div", "ligne");
    ligne.appendChild(elt("span", "cle", libelle(champ)));
    const val = elt("span", "val", String(valeur));
    /* Quand les sources divergeaient, on montre la valeur ÉCARTÉE à côté de celle retenue.
     * Sans cela, un groupe où « Thomas » et « Thomaxs » s'affrontent affichait « Thomaxs »
     * comme fiche propre, sans un mot — sur la section même qui promet le nettoyage. */
    if (ecartees[champ] && ecartees[champ].length) {
      val.appendChild(elt("span", "ecartee", " (ou " + ecartees[champ].join(", ") + ")"));
      ligne.classList.add("arbitre");
    }
    ligne.appendChild(val);
    corps.appendChild(ligne);
  }
  bloc.appendChild(corps);
  const noteEcartees = phraseValeursEcartees(ecartees);
  if (noteEcartees) bloc.appendChild(elt("div", "membres", noteEcartees));
  bloc.appendChild(elt("div", "membres", "Réunit " + groupe.membres.join(", ")
    + " — " + groupe.membres.length + " fiches."));
  const parId = {};
  for (const record of (groupe.records || [])) parId[record.record_id] = record;
  for (const paire of groupe.paires.slice(0, 2)) {
    bloc.appendChild(elt("div", "pourquoi",
      phraseDeProuve(paire.preuve, `${paire.a} et ${paire.b} sont la même entité`,
                     parId[paire.a], parId[paire.b])));
  }
  return bloc;
}

function rendDoute(scenario, doute, indice) {
  const bloc = elt("div", "doute");
  const cle = doute.a + "|" + doute.b;
  const decide = arbitrages[cle];

  /* En navigation par titres ou par liste de boutons — le mode normal d'un lecteur d'écran —
   * trois doutes au titre identique et neuf boutons aux libellés identiques ne se
   * distinguaient pas : l'utilisateur entendait « Oui, à fusionner » trois fois sans savoir
   * sur quelle paire il votait. Chaque doute porte donc son sujet dans son titre, et chaque
   * bouton un nom accessible qui le nomme. */
  const sujet = `${nomLisible(doute.record_a)} (${doute.a}) et `
    + `${nomLisible(doute.record_b)} (${doute.b})`;
  bloc.setAttribute("role", "group");
  bloc.dataset.doute = cle;
  bloc.setAttribute("tabindex", "-1");
  bloc.setAttribute("aria-label", `Cas à confirmer : ${sujet}`);
  bloc.appendChild(elt("h4", null, `Est-ce la même entité ? ${sujet}`));
  const cote = elt("div", "deux-fiches");
  for (const [record, siret] of [[doute.record_a, doute.siret_a], [doute.record_b, doute.siret_b]]) {
    const fiche = elt("div", "fiche");
    fiche.appendChild(elt("span", "source", record.source_id));
    for (const champ of CHAMPS) {
      if (champ === "record_id" || champ === "source_id") continue;
      if (!record[champ]) continue;
      const ligne = elt("div", "ligne");
      ligne.appendChild(elt("span", "cle", libelle(champ)));
      ligne.appendChild(elt("span", "val", String(record[champ])));
      fiche.appendChild(ligne);
    }
    if (siret) {
      const ligne = elt("div", "ligne siret");
      ligne.appendChild(elt("span", "cle", "SIRET"));
      ligne.appendChild(elt("span", "val", siret));
      fiche.appendChild(ligne);
    }
    cote.appendChild(fiche);
  }
  bloc.appendChild(cote);

  bloc.appendChild(elt("p", "raison",
    phraseDeProuve(doute.preuve, "Le moteur hésite", doute.record_a, doute.record_b)));

  /* Le SIRET n'entre pas dans la décision du moteur : il aide l'humain. On le dit. */
  if (doute.siret_a && doute.siret_b && doute.siret_a !== doute.siret_b) {
    bloc.appendChild(elt("p", "raison siret-note",
      "Le moteur compare le nom, l'adresse et les coordonnées — il ne lit pas le SIRET. "
      + "Ici, les deux SIRET diffèrent : ce sont deux entreprises distinctes. Le moteur "
      + "signale le doute, et c'est vous qui tranchez avec l'information légale."));
  }

  if (decide) {
    const dit = { fusionner: "Fusionnées, sur votre décision.",
                  separer: "Gardées séparées, sur votre décision.",
                  inconnu: "Laissée en attente, comme le moteur l'avait laissée." }[decide];
    /* « le moteur retient vos choix » affirmait une boucle d'apprentissage qui n'existe pas
     * dans le produit livré — la promesse que tout acheteur demande en premier, énoncée à
     * l'indicatif au moment où le visiteur est le plus réceptif. Au conditionnel, comme les
     * sept pistes de la Vitrine, et rangée où sont les extensions à construire. */
    bloc.appendChild(elt("p", "arbitre-fait", dit
      + " Dans une version sur mesure, ce circuit de validation se construirait avec vous."));
    const revenir = elt("button", "btn btn-fantome", "Revenir sur ce choix");
    revenir.type = "button";
    revenir.addEventListener("click", () => {
      delete arbitrages[cle];
      rendScenario(scenario);
    });
    bloc.appendChild(revenir);
  } else {
    const boutons = elt("div", "arbitrage");
    for (const [code, texte] of [["fusionner", "Oui, à fusionner"],
                                 ["separer", "Non, à garder séparées"],
                                 ["inconnu", "Je ne sais pas"]]) {
      const bouton = elt("button", "btn btn-fantome", texte);
      bouton.type = "button";
      bouton.setAttribute("aria-label", `${texte} — ${sujet}`);
      bouton.addEventListener("click", () => {
        arbitrages[cle] = code;
        rendScenario(scenario);
        /* Le rendu remplace le bloc, donc le focus doit être replacé — mais SUR LE MÊME
         * doute, pas sur le premier de la liste. Renvoyer en tête faisait tourner en rond
         * l'utilisateur au clavier, et lui faisait entendre le nom d'une AUTRE paire juste
         * après son vote : exactement la confusion que les libellés par sujet éliminent. */
        const rendu = document.querySelector(`[data-doute="${CSS.escape(cle)}"]`);
        const cible = rendu && (rendu.querySelector("button") || rendu);
        if (cible && cible.focus) cible.focus();
      });
      boutons.appendChild(bouton);
    }
    bloc.appendChild(boutons);
  }
  return bloc;
}

function section(titre, compte, description) {
  const bloc = elt("section", "section-resultat");
  const entete = elt("div", "entete-section");
  entete.appendChild(elt("h3", null, titre));
  entete.appendChild(elt("span", "compte-section", String(compte)));
  bloc.appendChild(entete);
  if (description) bloc.appendChild(elt("p", "description-section", description));
  return bloc;
}

function rendScenario(scenario) {
  const zone = $("resultat-scenario");
  zone.innerHTML = "";
  const c = compteurs(scenario, arbitrages);
  zone.appendChild(rendResume(scenario));

  const consolidees = section("Fiches consolidées", c.consolidees,
    "Des doublons réunis en une seule fiche propre. C'est le nettoyage.");
  for (const groupe of scenario.consolidees.slice(0, 6)) {
    consolidees.appendChild(rendGroupe(groupe));
  }
  /* Le compte restant suit les COMPTEURS VIVANTS, pas l'artefact figé : après un arbitrage,
   * « et 91 autres » contredisait l'en-tête de sa propre section. */
  if (c.consolidees > 6) {
    consolidees.appendChild(elt("p", "reste",
      "et " + accord(c.consolidees - 6, "autre fiche consolidée", "autres fiches consolidées") + "."));
  }
  zone.appendChild(consolidees);

  const doutes = section("À confirmer", c.a_confirmer,
    "Le moteur préfère vous demander plutôt que de deviner. Votre avis met le résultat à jour.");
  doutes.classList.add("section-doute");
  /* Le total est affiché, et la troncature annoncée : la section des consolidées dit « et N
   * autres », celle des doutes le taisait — le lecteur croyait voir toute la zone grise. La
   * RÈGLE est dans `logique.js`, où les oracles l'exécutent ; ici, on ne fait que la poser. */
  const troncature = annonceTroncature(c);
  if (troncature) doutes.appendChild(elt("p", "description-section", troncature));
  if (c.arbitres && c.arbitres >= c.montres) {
    doutes.appendChild(elt("p", "reste",
      "Vous avez arbitré tous les cas détaillés ici."));
  }
  scenario.a_confirmer.forEach((doute, i) => doutes.appendChild(rendDoute(scenario, doute, i)));
  zone.appendChild(doutes);

  /* « Le moteur a vérifié » convertissait une NON-DÉTECTION en vérification — exactement la
   * lecture que le dossier technique interdit verbatim sur la revue de zone grise. On dit ce
   * que le moteur a fait : il n'a pas trouvé de doublon. */
  const uniques = section("Déjà uniques", c.deja_uniques,
    "Le moteur n'a trouvé aucun doublon pour ces fiches : elles sont conservées telles quelles.");
  uniques.classList.add("section-unique");
  const liste = elt("div", "liste-uniques");
  /* La puce porte la VILLE, et le SIRET quand il existe. Sans cela, le scénario fournisseurs
   * ouvrait sa liste « aucun doublon trouvé » sur cinq paires de raisons sociales identiques,
   * et le prospect y lisait dix doublons manqués — alors que ce sont des sociétés distinctes,
   * et que le moteur refusant de les fusionner est précisément l'argument du produit. Rien ne
   * le disait à l'écran ; maintenant si. */
  const sirets = scenario.sirets || {};
  const montrees = scenario.deja_uniques.slice(0, 12);
  for (const record of montrees) {
    const puce = elt("span", "puce-unique", nomLisible(record));
    if (record.ville) puce.appendChild(elt("span", "lieu", " · " + record.ville));
    if (sirets[record.record_id]) {
      puce.appendChild(elt("span", "siret-puce", " · SIRET " + sirets[record.record_id]));
    }
    puce.title = `${record.record_id} · ${record.source_id} — `
      + [record.adresse, record.code_postal, record.ville].filter(Boolean).join(", ")
      + (sirets[record.record_id] ? ` — SIRET ${sirets[record.record_id]}` : "");
    liste.appendChild(puce);
  }
  uniques.appendChild(liste);
  if (c.deja_uniques > montrees.length) {
    uniques.appendChild(elt("p", "reste",
      "et " + accord(c.deja_uniques - montrees.length, "autre fiche déjà unique", "autres fiches déjà uniques") + "."));
  }
  zone.appendChild(uniques);

  /* Ce qui a réglé CE scénario. La page n'affichait que les seuils de la saisie manuelle,
   * alors que chaque scénario a re-dérivé les siens : le lecteur attribuait aux résultats
   * qu'il regarde des seuils qui ne les ont pas produits. */
  zone.appendChild(elt("p", "note-point", noteDuPoint(scenario)));
}

async function ouvreScenario(cle) {
  $("choix-scenarios-section").hidden = true;
  $("vue-manuelle").hidden = true;
  $("vue-scenario").hidden = false;
  $("resultat-scenario").innerHTML = "";
  $("chrono-scenario").textContent = "";
  arbitrages = {};
  const reponse = await fetch("/api/scenario/" + encodeURIComponent(cle));
  if (!reponse.ok) { $("resultat-scenario").textContent = "Scénario indisponible."; return; }
  scenarioCourant = await reponse.json();
  $("titre-scenario").textContent = scenarioCourant.titre;
  $("accroche-scenario").textContent = scenarioCourant.accroche;
  $("benefice-scenario").textContent = scenarioCourant.benefice;
  rendFichiers(scenarioCourant);
}

/* Le résultat est calculé au build : on ne prétend PAS le calculer maintenant, et on
 * n'affiche aucune durée fabriquée. La courte attente ne sert qu'à rendre l'enchaînement
 * lisible ; le libellé dit ce qui se passe réellement. */
function lanceScenario() {
  if (!scenarioCourant) return;
  const bouton = $("rapprocher-scenario");
  bouton.disabled = true;
  $("chrono-scenario").textContent = "rapprochement…";
  setTimeout(() => {
    rendScenario(scenarioCourant);
    $("chrono-scenario").textContent = "résultat préparé à l'avance sur ces données d'exemple";
    bouton.disabled = false;
  }, 700);
}

function retourAuChoix() {
  $("vue-scenario").hidden = true;
  $("vue-manuelle").hidden = true;
  $("choix-scenarios-section").hidden = false;
  for (const carte of document.querySelectorAll(".carte-scenario")) {
    carte.setAttribute("aria-pressed", "false");
  }
}

/* ============================ La saisie manuelle ============================ */

function ajouteLigne(record) {
  const tr = document.createElement("tr");
  for (const champ of CHAMPS) {
    const td = document.createElement("td");
    const input = document.createElement("input");
    input.type = "text";
    input.dataset.champ = champ;
    input.maxLength = LONGUEUR_MAX_VALEUR;
    input.value = (record && record[champ] != null) ? record[champ] : "";
    input.setAttribute("aria-label", libelle(champ));
    td.appendChild(input);
    tr.appendChild(td);
  }
  const tdSuppr = document.createElement("td");
  const bouton = document.createElement("button");
  bouton.type = "button";
  bouton.className = "btn btn-fantome";
  bouton.style.padding = "4px 9px";
  bouton.textContent = "×";
  bouton.setAttribute("aria-label", "Retirer cette ligne");
  bouton.addEventListener("click", () => { tr.remove(); majCompteurs(); });
  tdSuppr.appendChild(bouton);
  tr.appendChild(tdSuppr);
  lignes.appendChild(tr);
}

function litEntree() {
  return Array.from(lignes.querySelectorAll("tr")).map((tr) => {
    const record = {};
    for (const input of tr.querySelectorAll("input")) {
      record[input.dataset.champ] = input.value.trim();
    }
    return record;
  }).filter((r) => Object.values(r).some((valeur) => valeur !== ""));
}

function majCompteurs() {
  const records = litEntree();
  $("compte-lignes").textContent = accord(records.length, "enregistrement");
  const sources = new Set(records.map((r) => r.source_id).filter(Boolean));
  $("compte-sources").textContent = sources.size ? accord(sources.size, "source") : "";
}

function effaceEtapes() { /* le bandeau d'étapes a été retiré : le résultat prime. */ }

function reinitialise() {
  lignes.innerHTML = "";
  EXTRAIT.forEach(ajouteLigne);
  majCompteurs();
  $("sortie").innerHTML = "";
  $("message").innerHTML = "";
  $("chrono").textContent = "";
}

function rendResultatManuel(resultat) {
  const sortie = $("sortie");
  sortie.innerHTML = "";
  const bloc = elt("div", "resume-nettoyage");
  const avant = elt("div", "avant-apres");
  /* L'accord était corrigé côté scénario et pas ici — c'est-à-dire sur le seul écran où le
   * prospect voit le moteur calculer sur SES données, donc celui qu'il regarde le mieux. */
  avant.appendChild(elt("span", "nombre", String(resultat.n_records)));
  avant.appendChild(elt("span", "legende", resultat.n_records > 1 ? "lignes" : "ligne"));
  avant.appendChild(elt("span", "fleche", "→"));
  avant.appendChild(elt("span", "nombre resultat", String(resultat.n_entites)));
  avant.appendChild(elt("span", "legende",
    resultat.n_entites > 1 ? "fiches uniques" : "fiche unique"));
  bloc.appendChild(avant);
  sortie.appendChild(bloc);

  const groupes = resultat.entites.filter((e) => e.membres.length > 1);
  const consolidees = section("Fiches consolidées", groupes.length,
    "Des doublons réunis en une seule fiche propre.");
  for (const entite of groupes) {
    /* `records` est INDISPENSABLE : sans lui, `phraseDeProuve` ne peut pas distinguer deux
     * valeurs identiques de deux graphies, et écrivait « mêmes adresse » au-dessus de deux
     * adresses que le visiteur venait de saisir différemment — sur le seul écran où le
     * moteur tourne en direct devant lui. */
    /* `valeurs_ecartees` de même : sans lui, la fiche consolidée affichait « Aubri » en gras
     * comme fiche propre alors que « Aubry » avait été saisi juste à côté. Le mode scénario
     * le montrait, le mode manuel non — la correction n'avait été appliquée qu'à un des deux
     * écrans, et pas à celui que le prospect regarde le mieux. */
    consolidees.appendChild(rendGroupe({
      membres: entite.membres,
      records: entite.records,
      enregistrement_dore: entite.enregistrement_dore,
      valeurs_ecartees: entite.valeurs_ecartees,
      paires: entite.paires.filter((p) => p.verdict === "MATCH"),
    }));
  }
  sortie.appendChild(consolidees);

  if (resultat.a_verifier.length) {
    const doutes = section("À confirmer", resultat.a_verifier.length,
      "Le moteur préfère vous demander plutôt que de deviner.");
    doutes.classList.add("section-doute");
    for (const paire of resultat.a_verifier) {
      doutes.appendChild(elt("div", "pourquoi",
        phraseDeProuve(paire.preuve,
          `Le moteur hésite entre ${paire.a} et ${paire.b}`,
          paire.record_a, paire.record_b)));
    }
    sortie.appendChild(doutes);
  }

  const seuls = resultat.entites.filter((e) => e.membres.length === 1);
  const uniques = section("Déjà uniques", seuls.length,
    "Aucun doublon trouvé : conservées telles quelles.");
  uniques.classList.add("section-unique");
  const liste = elt("div", "liste-uniques");
  for (const entite of seuls) {
    liste.appendChild(elt("span", "puce-unique", nomLisible(entite.records[0])));
  }
  uniques.appendChild(liste);
  sortie.appendChild(uniques);

  $("chrono").textContent = `calculé en direct, en ${(resultat.duree_s * 1000).toFixed(0)} ms`;

  const messages = [];
  if (resultat.estimation.repli) {
    messages.push({
      classe: "avis alerte",
      html: "<b>Estimation repliée.</b> Sur cette entrée, les deux classes ne se séparent pas "
        + `(${resultat.estimation.motif_repli || "mélange dégénéré"}). Les poids retombent sur `
        + `des a priori <b>non calibrés</b> : il faut au moins ${resultat.estimation.min_paires_em} `
        + "paires, et une entrée qui contienne à la fois des rapprochements et des "
        + "non-rapprochements. Ce que vous voyez n'est pas le moteur mesuré ailleurs.",
    });
  }
  messages.push({
    classe: "avis",
    html: "<b>Même entrée, même résultat.</b> Ce calcul est reproductible à l'identique : "
      + accord(resultat.n_paires, "paire comparée", "paires comparées") + ".",
  });
  $("message").innerHTML = messages
    .map((m) => `<div class="${m.classe}">${m.html}</div>`).join("");
}

function rendErreur(texte) {
  $("sortie").innerHTML = "";
  $("chrono").textContent = "";
  const bloc = elt("div", "avis erreur");
  bloc.appendChild(elt("b", null, "Calcul refusé. "));
  bloc.appendChild(document.createTextNode(texte));
  $("message").innerHTML = "";
  $("message").appendChild(bloc);
}

async function rapproche() {
  const bouton = $("rapprocher");
  bouton.disabled = true;
  $("chrono").textContent = "calcul…";
  try {
    const reponse = await fetch("/api/rapprocher", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ records: litEntree() }),
    });
    const charge = await reponse.json();
    if (!reponse.ok) { rendErreur(charge.erreur || "erreur inconnue"); return; }
    rendResultatManuel(charge);
  } catch (erreur) {
    rendErreur("le moteur n'a pas répondu (" + erreur.message + ")");
  } finally {
    bouton.disabled = false;
  }
}

/* ============================ Câblage ============================ */

for (const carte of document.querySelectorAll(".carte-scenario")) {
  carte.addEventListener("click", () => {
    carte.setAttribute("aria-pressed", "true");
    if (carte.dataset.scenario === "manuel") {
      $("choix-scenarios-section").hidden = true;
      $("vue-scenario").hidden = true;
      $("vue-manuelle").hidden = false;
      reinitialise();
    } else {
      ouvreScenario(carte.dataset.scenario);
    }
  });
}

$("rapprocher-scenario").addEventListener("click", lanceScenario);
$("retour-choix").addEventListener("click", retourAuChoix);
$("retour-choix-2").addEventListener("click", retourAuChoix);
$("rapprocher").addEventListener("click", rapproche);
$("ajouter").addEventListener("click", () => { ajouteLigne(null); majCompteurs(); });
$("reinitialiser").addEventListener("click", reinitialise);
lignes.addEventListener("input", majCompteurs);
