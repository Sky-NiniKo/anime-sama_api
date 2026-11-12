# Profilage optionnel Core_Update

Ajouter profiling.py, run_profile.py et test_profiling.py au dossier Core_Update
existant. Ne remplacer aucun autre fichier : conserve les corrections de saisie,
de langues et la préparation parallèle.

Tests :
    python -m unittest Core_Update.test_profiling -v

Lancer avec mesures :
    python -m Core_Update.run_profile

Lancer normalement, sans mesures :
    python -m Core_Update.run_cli

Les mesures apparaissent sur la sortie d'erreur du terminal et sont ajoutées au
fichier timings.log dans Core_Update (créé au premier lancement profilé).
Le journal s'accumule : chaque session commence par Profilage activé.

Mesures : découverte du domaine si nécessaire, recherche, saisons, chargement
HTML par langue, parsing bdd, construction des épisodes, attente des menus,
préparation de toutes les URL sélectionnées, résolution de chaque référence
(cache compris), chaque requête HTTP HTTPX, métadonnées année, traitement du lot
et de chaque épisode, méthodes extract_info/process_info de yt-dlp, session totale.

Les URL HTTP sont journalisées uniquement par méthode et chemin : pas de query,
jeton j, cookies ou corps de réponse. Ce module n'affiche pas les exceptions.
Les autres logs de l'application et le diagnostic des URL existant ne sont pas
filtrés par ce module : vérifier leur contenu avant partage public.

INTERPRETATION
- HTTP GET /api/lien.php : temps d'envoi/réception HTTPX, pas la file du scheduler.
- Résolution référence : peut contenir cache, retries et renouvellement de jeton.
- Préparation URL : temps mural du lot, appels parallèles inclus.
- extract_info : peut inclure le téléchargement et des appels récursifs ; ce n'est
  PAS une mesure exclusive de l'extraction des métadonnées.
- process_info : peut inclure transfert, contrôles et post-traitements ; ce n'est
  PAS une mesure exclusive de bande passante.
- Attente utilisateur : inclut le rendu du menu et les éventuelles nouvelles saisies.
- Session complète inclut l'utilisateur et tous les traitements.
- Les mesures s'imbriquent et se chevauchent : NE PAS les additionner pour calculer
  la durée totale. Le cumul du bilan additionne seulement les appels d'une même
  étiquette, il n'est pas une estimation de temps CPU ou de temps mural exclusif.
- Les petits coûts non instrumentés (imports, reconstruction Python, affichage)
  restent inclus dans les étapes englobantes.

Les wrappers conservent les résultats et relancent les exceptions/annulations.
Six tests unitaires hors réseau réussis lors de la préparation. Compilation OK.
Le lanceur complet dépend de votre environnement anime_sama_api/yt-dlp et n'a pas
été exécuté ici. Aucun téléchargement ni gain de vitesse n'est revendiqué.
Le profilage concerne le processus du lanceur ; il modifie les références aux
fonctions seulement en mémoire. Aucun fichier du package original n'est changé.
