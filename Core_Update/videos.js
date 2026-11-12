///////////////////* CONSTANTES GLOBALES */////////////////////////

const listeEpisodes = document.getElementById('selectEpisodes');
const listeLecteurs = document.getElementById('selectLecteurs');
const lienCurrent = window.location.href;
const premierEpisode = eps1[0];
const tailleEpisodes = eps1.length;
const lastEpisode = tailleEpisodes-1;
const linkOeuvre = window.location.pathname;
const nomOeuvre = document.getElementById('titreOeuvre').innerHTML;
var refresh = 0;


///////////////////* CREER LISTES */////////////////////////

/* echanger les deux var eps */
function swapLecteurs(){
	var epsTemp1, epsTemp2;
	if(typeof eps2 !== 'undefined'){
		epsTemp1 = eps1;
		epsTemp2 = eps2; 
		eps1 = epsTemp2;
		eps2 = epsTemp1; 
	}
}

// La page met déjà les lecteurs dans le bon ordre (Vidmoly en premier) : plus d'échange (12/11/2026)
if (!window.epsOrdreFinal) swapLecteurs();

/* Liens des épisodes (12/11/2026) : la page ne contient plus les adresses des vidéos, seulement
   « lien:<n° » ; l'adresse d'un épisode est demandée à /api/lien.php au moment de le regarder
   (jeton de la page : epsJeton). Une adresse déjà reçue n'est pas redemandée. */
var _liensRecus = {}, _demandeLien = 0;
/* Réponse impossible (coupure réseau, page de vérification Cloudflare, serveur occupé…) : on réessaie
   deux fois (1 s puis 3 s), puis message sur la vidéo (« Réessayer » / autre lecteur, js/contenu/lecteur.js)
   et petit signalement anonyme (/signal-lecteur.php → hors-site/signalements/lien-echec.log). 12/11/2026 */
function echecLien(repere, erreur, essai, suite){
    if (essai < 2) {
        setTimeout(function(){ resoudreLien(repere, suite, essai + 1); }, essai ? 3000 : 1000);
        return;
    }
    try {
        window.dispatchEvent(new CustomEvent('as-lien-echec', { detail: { erreur: erreur } }));
        var corps = JSON.stringify({ moment: 'lien-echec', erreur: String(erreur).slice(0, 120), page: location.pathname,
            ua: navigator.userAgent, enLigne: navigator.onLine });
        if (navigator.sendBeacon) navigator.sendBeacon('/signal-lecteur.php', corps);
    } catch (e) {}
    suite('');
}
function resoudreLien(repere, suite, essai){
    essai = essai || 0;
    if (_liensRecus[repere]) return suite(_liensRecus[repere]);
    var statut = 0;
    fetch('/api/lien.php?j=' + encodeURIComponent(window.epsJeton || '') + '&l=' + encodeURIComponent(repere.slice(5)), { credentials: 'same-origin' })
        .then(function(r){ statut = r.status; return r.json(); })
        .then(function(d){
            if (d && d.u) {
                _liensRecus[repere] = d.u;
                try { sessionStorage.removeItem('asJetonRecharge'); } catch (e) {}
                return suite(d.u);
            }
            // Page ouverte depuis plus de 24 h : on la recharge une fois pour avoir un nouveau jeton
            if (d && d.erreur === 'expire') {
                try { if (!sessionStorage.getItem('asJetonRecharge')) { sessionStorage.setItem('asJetonRecharge', '1'); location.reload(); return; } } catch (e) {}
            }
            echecLien(repere, (d && d.erreur ? d.erreur : 'reponse') + ' ' + statut, (d && d.erreur === 'absent') ? 2 : essai, suite);
        })
        .catch(function(e){ echecLien(repere, (statut || 'reseau') + ' ' + (e && e.message || ''), essai, suite); });
}

function setPlayerSrc(url){
    if (typeof url === 'string' && url.indexOf('lien:') === 0) {
        var demande = ++_demandeLien;
        resoudreLien(url, function(vrai){
            if (demande !== _demandeLien || !vrai) return;      // un autre épisode a été choisi entre-temps
            var actuel = document.getElementById('playerDF');
            // déjà affiché (même vidéo) : on ne recharge pas le lecteur
            if (actuel && (actuel.getAttribute('src') || '').replace(/vidmoly\.(to|net)/g, 'vidmoly.biz') === vrai.replace(/vidmoly\.(to|net)/g, 'vidmoly.biz')) return;
            placerLecteur(vrai);
        });
        return;
    }
    _demandeLien++;
    placerLecteur(url);
}

function placerLecteur(url){
    var old = document.getElementById('playerDF');
    if (!old || !url) return;

    var neuf = old.cloneNode(false);   // copie de l'iframe, sans son contenu
    neuf.removeAttribute('src');
    old.parentNode.replaceChild(neuf, old);
    neuf.src = url;
}


function creerListeEpisodes(){
	//créer la liste
	for (var i = 1; i <= tailleEpisodes; i++){
		optEpisode = document.createElement('option');
		optEpisode.text = "Episode " + i;
		listeEpisodes.appendChild(optEpisode);
	}
}
creerListeEpisodes();
function creerListeLecteurs(){
	var tailleLecteurs = 0;
	//avoir le nb max de lecteurs
	if (typeof eps1 !== 'undefined') tailleLecteurs++;
	if (typeof eps2 !== 'undefined') tailleLecteurs++;
	if (typeof eps3 !== 'undefined') tailleLecteurs++;
	if (typeof eps4 !== 'undefined') tailleLecteurs++;
	if (typeof eps5 !== 'undefined') tailleLecteurs++;
	if (typeof eps6 !== 'undefined') tailleLecteurs++;
	if (typeof eps7 !== 'undefined') tailleLecteurs++;
	if (typeof eps8 !== 'undefined') tailleLecteurs++;
	//créer la liste
	for(var k = 1; k <= tailleLecteurs; k++){
		optLecteur = document.createElement('option');
		optLecteur.text = "Lecteur " + k;
		listeLecteurs.appendChild(optLecteur);
	}
}
creerListeLecteurs();

/* +Episodes spéciaux */
var epRetards = 0;
function resetListe(){
	$('#selectEpisodes').find('option').remove().end();
}
function creerListe(debut, fin){
	for (var i = debut; i <= fin; i++){
		var optEpisode = document.createElement('option');
		optEpisode.text = "Episode " + i;
		listeEpisodes.appendChild(optEpisode);
	}
	setCorrectEpisode();
}
function newSP(spe){
	var optEpisode = document.createElement('option');
	optEpisode.text = "Episode " + spe;
	listeEpisodes.appendChild(optEpisode);
	epRetards++;
	setCorrectEpisode();
}
function newSPF(spe){
	var optEpisode = document.createElement('option');
	optEpisode.text = spe;
	listeEpisodes.appendChild(optEpisode);
	epRetards++;
	setCorrectEpisode();
}
function finirListe(debut){
	for (var i = debut; i <= (tailleEpisodes-epRetards); i++){
		var optEpisode = document.createElement('option');
		optEpisode.text = "Episode " + i;
		listeEpisodes.appendChild(optEpisode);
	}
	setCorrectEpisode();
}
/* -Episodes spéciaux */

///////////////////* CREER NAVIGATION */////////////////////////
	
/* ON LOAD */
// setCorrectEpisode() est appelée plusieurs fois au chargement (ici, puis par
// finirListe/creerListe...). Avant, chaque appel refaisait sa requête à
// get-data.php ; maintenant les appels rapprochés partagent la même réponse.
var _progressFetch = null;
function fetchProgressData(){
    if (!_progressFetch) {
        _progressFetch = fetch('/api/get-data.php').then(function(r){ return r.json(); });
        _progressFetch.catch(function(){}).then(function(){ setTimeout(function(){ _progressFetch = null; }, 2000); });
    }
    return _progressFetch;
}

async function setCorrectEpisode(){
    var currentLecteur = listeLecteurs.selectedIndex;
    var tableauCorrect = eval('eps' + ++currentLecteur);
    
    // ÉTAPE 1 : Vérifier si connecté ET si need_merge
    try {
        const serverData = await fetchProgressData();
        
        if (serverData.logged_in && serverData.progress && serverData.progress[linkOeuvre]) {
            // ⚠️ CORRECTION : NE PAS écraser le localStorage si need_merge=true
            // Car le merge va se faire après et on veut garder les données locales
            if (serverData.need_merge === true) {
                //console.log('⏳ need_merge=true, on garde les données locales pour le merge...');
                // Ne pas écraser, laisser loadAllDataFromServer() faire le merge
            } else {
                // need_merge=false → réconcilier local et serveur SANS reculer :
                // on garde la position la PLUS AVANCÉE des deux. Évite qu'une
                // valeur serveur périmée écrase une progression locale plus récente
                // (ex : épisodes regardés en étant déconnecté).
                const savedProgress = serverData.progress[linkOeuvre];
                const serverNum = parseInt(savedProgress.num, 10) || 0;
                const localNum = parseInt(localStorage.getItem('savedEpNb' + linkOeuvre), 10);
                if (isNaN(localNum) || serverNum > localNum) {
                    localStorage.setItem('savedEpName' + linkOeuvre, JSON.stringify(savedProgress.name));
                    localStorage.setItem('savedEpNb' + linkOeuvre, serverNum);
                }
                // sinon : le local est égal ou plus avancé → on n'écrase pas
            }
        }
    } catch (e) {
        //console.log('⚠️ Impossible de charger du serveur, utilisation du localStorage local');
    }

    // ✅ GARDE-FOU : si la liste d'épisodes n'est pas (encore) construite, on
    // abandonne. setCorrectEpisode() est appelée plusieurs fois (module + finirListe)
    // et un resetListe() peut vider la liste pendant l'await get-data. Écrire un
    // index sur une liste vide donnerait un num faux (0/-1). Un appel ultérieur,
    // avec la liste prête, fera le positionnement correct.
    if (!listeEpisodes.options || listeEpisodes.options.length === 0) {
        return;
    }

    // ÉTAPE 2 : Lire le localStorage
    var lastEpSavedName = JSON.parse(localStorage.getItem('savedEpName'+linkOeuvre)) || listeEpisodes.options[0].text;
    var lastEpSavedNb = parseInt(localStorage.getItem('savedEpNb'+linkOeuvre), 10);
    if (isNaN(lastEpSavedNb)) lastEpSavedNb = 0;

    // ✅ Le NOM fait foi : si l'option à cet index ne correspond pas au nom
    // sauvegardé (num périmé ou migré), on retrouve le bon index par le nom.
    if (!listeEpisodes.options[lastEpSavedNb] || listeEpisodes.options[lastEpSavedNb].text !== lastEpSavedName) {
        for (var i = 0; i < listeEpisodes.options.length; i++) {
            if (listeEpisodes.options[i].text === lastEpSavedName) { lastEpSavedNb = i; break; }
        }
    }

    // Vérifier que l'index est valide
    var validIndex = Math.min(Math.max(lastEpSavedNb, 0), listeEpisodes.options.length - 1);

    // Réécrire l'index corrigé pour qu'addHistorique synchronise la bonne valeur
    localStorage.setItem('savedEpNb'+linkOeuvre, validIndex);
    
    /* print et mettre le dernier episode vu sauvegardé onload */
    document.getElementById('savedEpisodeId').innerHTML = lastEpSavedName;
    listeEpisodes.selectedIndex = validIndex;
    addHistorique();
    setPlayerSrc(tableauCorrect[validIndex]);
    updateNavBoundaries();
}

setCorrectEpisode();

function refreshVariables(){
	/* variables */
	var currentEpisode = listeEpisodes.selectedIndex;
	var currentEpisodeName = listeEpisodes.options[listeEpisodes.selectedIndex].text;
	var currentLecteur = listeLecteurs.selectedIndex;
	var tableauCorrect = eval('eps' + ++currentLecteur);

	/* variables saved actualiser */
	localStorage.setItem('savedEpName'+linkOeuvre, JSON.stringify(currentEpisodeName));
	localStorage.setItem('savedEpNb'+linkOeuvre, currentEpisode);
	addHistorique();
	syncCurrentProgressToServer(currentEpisode, currentEpisodeName);

	/* print dynamiquement l'épisode qu'on selectionne */
	//document.getElementById('savedEpisodeId').innerHTML = currentEpisodeName;

	/* mettre l'épisode aux lecteurs */
    setPlayerSrc(tableauCorrect[currentEpisode]);
    updateNavBoundaries();
}

// Griser / désactiver les boutons de navigation arrivés aux extrémités
function updateNavBoundaries() {
	if (!listeEpisodes.options || listeEpisodes.options.length === 0) return;

	var index = listeEpisodes.selectedIndex;
	// Même borne que nextEp(), plafonnée par la taille réelle de la liste
	// (les épisodes spéciaux peuvent la faire varier)
	var dernierIndex = Math.min(lastEpisode, listeEpisodes.options.length - 1);

	var premierEp = index <= 0;
	var dernierEp = index >= dernierIndex;

	// Les boutons existent en double (navigation haut et bas)
	document.querySelectorAll('#prevEpisode').forEach(function(btn) { setBtnDisabled(btn, premierEp); });
	document.querySelectorAll('#nextEpisode').forEach(function(btn) { setBtnDisabled(btn, dernierEp); });
	document.querySelectorAll('#lastEpisode').forEach(function(btn) { setBtnDisabled(btn, dernierEp); });
}

function setBtnDisabled(btn, disabled) {
	if (!btn) return;
	btn.disabled = disabled;
	if (disabled) btn.classList.add('nav-btn-disabled');
	else btn.classList.remove('nav-btn-disabled');
}

// Étape 1 : la progression est désormais portée par l'historique
// (addHistorique() écrit ep + num et appelle syncHistoryToServer()).
// Cette fonction est conservée en no-op pour ne pas casser les appels.
async function syncCurrentProgressToServer(episodeNum, episodeName) {
    // déprécié : ne fait plus rien (voir addHistorique / syncHistoryToServer)
    return;
}
  


function selectEpisode() {
	refreshVariables();
}
function selectLecteur() {
	refreshVariables();
}
function prevEp() {
  if(listeEpisodes.selectedIndex>0){
	--listeEpisodes.selectedIndex;
    refreshVariables();
  }
}
function nextEp() {
  if(listeEpisodes.selectedIndex<lastEpisode){
	++listeEpisodes.selectedIndex;
    refreshVariables();
  }
}
function lastEp() {
	listeEpisodes.selectedIndex = lastEpisode;
	refreshVariables();
}

////////////////////////* AJOUTER HISTORIQUE *////////////////////////////////

function addHistorique(){
	// get favorites from local storage or empty array
	var histoNom = JSON.parse(localStorage.getItem('histoNom')) || [];
	var histoUrl = JSON.parse(localStorage.getItem('histoUrl')) || [];
	var histoImg = JSON.parse(localStorage.getItem('histoImg')) || [];
	var histoType = JSON.parse(localStorage.getItem('histoType')) || [];
	var histoLang = JSON.parse(localStorage.getItem('histoLang')) || [];
	var histoEp = JSON.parse(localStorage.getItem('histoEp')) || [];
	var histoNum = JSON.parse(localStorage.getItem('histoNum')) || [];

	var nom = nomOeuvre;
	var url = linkOeuvre;
	var image = document.getElementById('imgOeuvre').src; //$('#imgOeuvre').prop('src');
	// Jaquette : uniquement une adresse web (une extension peut la remplacer par une image de plusieurs Mo en base64)
	if (!/^https?:\/\//.test(image) || image.length > 500) image = 'https://raw.githubusercontent.com/Anime-Sama/IMG/img/contenu/' + linkOeuvre.split('/')[2] + '.jpg';
	var type = document.getElementById('avOeuvre').innerHTML; //$('#avOeuvre').html();

	//avoir la langue
	var locaz = linkOeuvre;
	var path = locaz.substring(0, locaz.lastIndexOf("/"));
	var directoryName = path.substring(path.lastIndexOf("/")+1);
	var langue = "VO";
	if(directoryName === "vf" || directoryName === "vf1" || directoryName === "vf2"){langue = "VF";}
	if(directoryName === "vj"){langue = "VJ";}
	if(directoryName === "vcn"){langue = "VCN";}
	if(directoryName === "vqc"){langue = "VQC";}
	if(directoryName === "vkr"){langue = "VKR";}
	if(directoryName === "va"){langue = "VA";}
	if(directoryName === "var"){langue = "VAR";}
	if(directoryName === "vostfr"){
		// Détecter la vraie langue VO depuis le drapeau du bouton switchVOSTFR
		var switchImg = document.querySelector('#switchVOSTFR img');
		if(switchImg){
			var match = switchImg.src.match(/flag_(\w+)\.png/);
			if(match){
				var flagToLang = {'jp':'VOSTFR','en':'VASTFR','cn':'VCN','kr':'VKR','ar':'VAR','qc':'VQC','fr':'VF'};
				langue = flagToLang[match[1]] || 'VOSTFR';
			} else { langue = "VOSTFR"; }
		} else { langue = "VOSTFR"; }
	}

	var episode = JSON.parse(localStorage.getItem('savedEpName'+linkOeuvre)) || listeEpisodes.options[0].text;
	// ✅ Étape 1 : la progression (index du sélecteur) vit dans l'historique
	var num = parseInt(localStorage.getItem('savedEpNb'+linkOeuvre), 10) || 0;

	// si y a pas deja l'oeuvre enregistrées
	if (histoUrl.includes(linkOeuvre) === false) {
		histoNom.push(nomOeuvre);	
		histoUrl.push(linkOeuvre);
		histoImg.push(image);
		histoType.push(type);
		histoLang.push(langue);
		histoEp.push(episode);
		histoNum.push(num);
	}
	// sinon remplacer ses données et push le tout au début de la liste
	else{
		var index = histoUrl.indexOf(linkOeuvre);
		histoNom[index] = nom;
		histoUrl[index] = url;
		histoImg[index] = image;
		histoType[index] = type;
		histoLang[index] = langue;
		histoEp[index] = episode;
		histoNum[index] = num;
		histoNom.push(histoNom.splice(index, 1)[0]);
		histoUrl.push(histoUrl.splice(index, 1)[0]);
		histoImg.push(histoImg.splice(index, 1)[0]);
		histoType.push(histoType.splice(index, 1)[0]);
		histoLang.push(histoLang.splice(index, 1)[0]);
		histoEp.push(histoEp.splice(index, 1)[0]);
		histoNum.push(histoNum.splice(index, 1)[0]);
	}
	// store array in local storage
	localStorage.setItem('histoNom', JSON.stringify(histoNom));
	localStorage.setItem('histoUrl', JSON.stringify(histoUrl));
	localStorage.setItem('histoImg', JSON.stringify(histoImg));
	localStorage.setItem('histoType', JSON.stringify(histoType));
	localStorage.setItem('histoLang', JSON.stringify(histoLang));
	localStorage.setItem('histoEp', JSON.stringify(histoEp));
	localStorage.setItem('histoNum', JSON.stringify(histoNum));

	// Après `addHistorique()`, appeler la sync
	syncHistoryToServer();
}

// SYNCHRONISER L'HISTORIQUE VERS LE SERVEUR
async function syncHistoryToServer() {
    const loggedIn = await isUserLoggedIn();
    if (!loggedIn) return;
    
    const history = {
        nom: JSON.parse(localStorage.getItem('histoNom')) || [],
        url: JSON.parse(localStorage.getItem('histoUrl')) || [],
        img: JSON.parse(localStorage.getItem('histoImg')) || [],
        type: JSON.parse(localStorage.getItem('histoType')) || [],
        lang: JSON.parse(localStorage.getItem('histoLang')) || [],
        ep: JSON.parse(localStorage.getItem('histoEp')) || [],
        num: JSON.parse(localStorage.getItem('histoNum')) || []
    };
    
    fetch('/api/sync-history.php', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({history: history})
    }).catch(err => console.log('Sync historique échouée:', err));
}


// RAFRAÎCHIR L'AFFICHAGE APRÈS QUE loadAllDataFromServer() charge les données
function updateUIAfterLoad() {
    if (!listeEpisodes.options || listeEpisodes.options.length === 0) return;
    // Relire les données du localStorage (maintenant à jour du serveur)
    var lastEpSavedName = JSON.parse(localStorage.getItem('savedEpName'+linkOeuvre)) || listeEpisodes.options[0].text;
    var lastEpSavedNb = parseInt(localStorage.getItem('savedEpNb'+linkOeuvre), 10);
    if (isNaN(lastEpSavedNb)) lastEpSavedNb = 0;

    // ✅ Le NOM fait foi (même règle que setCorrectEpisode) : le numéro venu du compte peut être
    // absent (0) ou décalé, ce qui remettait la page à l'épisode 1 alors que la reprise disait « Episode 3 ».
    if (!listeEpisodes.options[lastEpSavedNb] || listeEpisodes.options[lastEpSavedNb].text !== lastEpSavedName) {
        for (var i = 0; i < listeEpisodes.options.length; i++) {
            if (listeEpisodes.options[i].text === lastEpSavedName) { lastEpSavedNb = i; break; }
        }
    }
    var validIndex = Math.min(Math.max(lastEpSavedNb, 0), listeEpisodes.options.length - 1);
    localStorage.setItem('savedEpNb'+linkOeuvre, validIndex);

    // Mettre à jour l'affichage
    document.getElementById('savedEpisodeId').innerHTML = lastEpSavedName;
    listeEpisodes.selectedIndex = validIndex;

    var currentLecteur = listeLecteurs.selectedIndex;
    var tableauCorrect = eval('eps' + ++currentLecteur);

    // ✅ Pas de « petit refresh » : si le lecteur affiche déjà cet épisode (même lien),
    // on ne le recharge pas. Avant, l'arrivée des données du compte relançait le lecteur
    // une seconde après l'ouverture de la page, même quand rien ne changeait.
    var lecteurActuel = document.getElementById('playerDF');
    var lien = tableauCorrect[validIndex];
    if (!lecteurActuel || !lien || lecteurActuel.getAttribute('src') !== lien) {
        setPlayerSrc(lien);
    }
    updateNavBoundaries();
    // ✅ Historique : les données du compte qui viennent d'arriver ont remplacé l'historique local,
    // qui ne contenait pas encore cette page (ajoutée une fraction de seconde avant). Sans ça,
    // l'œuvre n'apparaissait dans l'historique qu'après un changement d'épisode.
    if (typeof addHistorique === 'function') addHistorique();
}


////////////////////////* UTILITAIRES *////////////////////////////////

function afficheLangueAnime(){

	var locaz = linkOeuvre;
	var path = locaz.substring(0, locaz.lastIndexOf("/"));
	var directoryName = path.substring(path.lastIndexOf("/")+1);
	var urlVOSTFR = "../vostfr";
	var urlVF = "../vf";
	var urlVJ = "../vj";
	var urlVAR = "../var";
	var urlVCN = "../vcn";
	var urlVQC = "../vqc";
	var urlVKR = "../vkr";
	var urlVA = "../va";
	var urlVF1 = "../vf1";
	var urlVF2 = "../vf2";

 	
	//si y a langue on affiche
	// languesDispo est fourni par video_body.php (une seule vérif côté serveur)
	if (typeof languesDispo !== 'undefined') {
		languesDispo.forEach(function(l) {
			var id = '#switch' + l.toUpperCase();
			$(id).removeClass("hidden").attr("href", "../" + l);
		});
	} else {
	$.get(urlVOSTFR).done(function() { $('#switchVOSTFR').removeClass("hidden");$("#switchVOSTFR").attr("href", urlVOSTFR); });
	$.get(urlVF).done(function() { $('#switchVF').removeClass("hidden");$("#switchVF").attr("href", urlVF); });
	$.get(urlVJ).done(function() { $('#switchVJ').removeClass("hidden");$("#switchVJ").attr("href", urlVJ); });
	$.get(urlVAR).done(function() { $('#switchVAR').removeClass("hidden");$("#switchVAR").attr("href", urlVAR); });
	$.get(urlVCN).done(function() { $('#switchVCN').removeClass("hidden");$("#switchVCN").attr("href", urlVCN); });
	$.get(urlVQC).done(function() { $('#switchVQC').removeClass("hidden");$("#switchVQC").attr("href", urlVQC); });
	$.get(urlVKR).done(function() { $('#switchVKR').removeClass("hidden");$("#switchVKR").attr("href", urlVKR); });
	$.get(urlVA).done(function() { $('#switchVA').removeClass("hidden");$("#switchVA").attr("href", urlVA); });
	$.get(urlVF1).done(function() { $('#switchVF1').removeClass("hidden");$("#switchVF1").attr("href", urlVF1); });
	$.get(urlVF2).done(function() { $('#switchVF2').removeClass("hidden");$("#switchVF2").attr("href", urlVF2); });
	}
	
	if(directoryName === "vostfr"){ $("#switchVOSTFR").addClass("opacity-100");$("#switchVOSTFR").removeClass("opacity-20");}
	if(directoryName === "vf"){ $("#switchVF").addClass("opacity-100");	$("#switchVF").removeClass("opacity-20");}
	if(directoryName === "vj"){ $("#switchVJ").addClass("opacity-100");	$("#switchVJ").removeClass("opacity-20");}
	if(directoryName === "var"){ $("#switchVAR").addClass("opacity-100");	$("#switchVAR").removeClass("opacity-20");}
	if(directoryName === "vcn"){ $("#switchVCN").addClass("opacity-100");$("#switchVCN").removeClass("opacity-20");}
	if(directoryName === "vqc"){ $("#switchVQC").addClass("opacity-100");$("#switchVQC").removeClass("opacity-20");}
	if(directoryName === "vkr"){ $("#switchVKR").addClass("opacity-100");$("#switchVKR").removeClass("opacity-20");}
	if(directoryName === "va"){ $("#switchVA").addClass("opacity-100");	$("#switchVA").removeClass("opacity-20");}
	if(directoryName === "vf1"){ $("#switchVF1").addClass("opacity-100");$("#switchVF1").removeClass("opacity-20");}
	if(directoryName === "vf2"){ $("#switchVF2").addClass("opacity-100");$("#switchVF2").removeClass("opacity-20");}

}
afficheLangueAnime();

/* Changer lien vidmoly */
;(function() {
	// 1. Remplace toutes les occurrences de vidmoly.to et vidmoly.net par vidmoly.biz  
	function replaceVidmoly(url) {
	  return url.replace(/vidmoly\.(to|net)/g, 'vidmoly.biz');
	}
  
	// 2. On surcharge le setter de la propriété `src` pour tous les <iframe>
	const proto = HTMLIFrameElement.prototype;
	const descriptor = Object.getOwnPropertyDescriptor(proto, 'src');
	Object.defineProperty(proto, 'src', {
	  get: descriptor.get,
	  set: function(value) {
		// on ajuste l'URL avant de passer au setter d'origine
		const newVal = (typeof value === 'string')
		  ? replaceVidmoly(value)
		  : value;
		return descriptor.set.call(this, newVal);
	  }
	});
  
	// 3. À l'initialisation du DOM, on corrige l'attribut déjà présent
	function fixExistingIframe() {
	  const iframe = document.getElementById('playerDF');
	  if (!iframe) return;
	  const src = iframe.getAttribute('src') || '';
	  if (src.includes('vidmoly.to')) {
		iframe.setAttribute('src', replaceVidmoly(src));
	  }
	}
  
	// 4. Exécution immédiate ou sur DOMContentLoaded
	if (document.readyState === 'loading') {
	  document.addEventListener('DOMContentLoaded', fixExistingIframe);
	} else {
	  fixExistingIframe();
	}
})();



///////////////////* INPUT LISTE ANIMES */////////////////////////

var touchTimer;
var input;

// appui long sur tel au lieu du double clic
function handleTouchStart(event) {
  touchTimer = setTimeout(function() {
    createInputField();
  }, 500); // 500 ms pour détecter un appui long
}

function createInputField() {
  var select = $('#selectEpisodes');
  input = $('<input type="text" placeholder="Entrez la valeur" class="scrollBarStyled bg-black outline outline-sky-700 outline-1 rounded uppercase font-extrabold text-xs pl-1 text-white items-center cursor-pointer transition-all duration-200"/>');

  // css de la position de l'input
  input.css({
    position: 'absolute',
    left: select.offset().left + 'px',
    top: select.offset().top + 'px',
    width: select.outerWidth() + 'px',
    height: select.outerHeight() + 'px',
    zIndex: 1000
  });

  // press enter ou blur pour confirmer
  input.on('blur keydown', function(event) {
    if (event.type === 'blur' || event.key === 'Enter') {
		input.remove();
      validateInput();
      $(window).off('resize', adjustInputPosition);
    }
  });

  $('body').append(input);
  input.focus();
  $(window).on('resize', adjustInputPosition);
}

function validateInput() {
  var select = $('#selectEpisodes');
  var index = parseInt(input.val(), 10) - 1; // Assumant que l'utilisateur entre un chiffre de 1 à N
  if (index >= 0 && index < select[0].options.length) {
    select[0].selectedIndex = index;
    selectEpisode(); // Appeler la fonction onchange si nécessaire
  }
}

// gérer l'input qui se barre sur les resize
function adjustInputPosition() {
  var select = $('#selectEpisodes');
  input.css({
    left: select.offset().left + 'px',
    top: select.offset().top + 'px',
    width: select.outerWidth() + 'px',
    height: select.outerHeight() + 'px'
  });
}

// Pour éviter l'appel multiple lors d'une brève pression
document.addEventListener('touchend', function(event) {
  clearTimeout(touchTimer);
});