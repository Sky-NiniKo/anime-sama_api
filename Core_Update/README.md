# Core_Update — téléchargement lazy avec double repli

## Installation
Sauvegarder votre dossier Core_Update actuel, puis le remplacer par le dossier
complet de cette archive. Aucun fichier de anime_sama_api n'est modifié.
Votre config.toml existant n'est pas modifié et reste chargé par le package.

Commandes depuis la racine :
 python -m unittest Core_Update.test_resolver Core_Update.test_lazy_engine Core_Update.test_lang_fix Core_Update.test_integration -v
 python -m Core_Update.run_cli
 python -m Core_Update.run_profile

## Parcours
1. HTML des langues et liste des épisodes sans appel lien.php.
2. Après sélection, chaque worker parcourt les langues préférées de la config,
   puis les autres langues comme secours, et les lecteurs dans l'ordre du site.
3. Résolution d'une seule référence, puis tentative yt-dlp.
4. Succès yt-dlp : arrêt des lecteurs pour cet épisode. Un fichier déjà présent
   peut également être considéré comme un succès par yt-dlp.
5. Erreur API (LinkError/HTTPError après reprises limitées) : candidat suivant.
6. Échec DownloadError ou code retour non nul : candidat suivant, après reprises
   du même lecteur pour les erreurs reconnues comme temporaires.
7. Erreur expire : HTML renouvelé une fois. 429 API : plus de nouvelles résolutions;
   les téléchargements déjà en cours peuvent finir, puis l'erreur est remontée.

Aucun préchargement des URL suivantes et aucun diagnostic listant toutes les URL.
Déduplication par contexte/référence avant résolution et par URL après résolution.
La langue n'est pas fixée dans le code. Les bans d'hébergeurs sont appliqués après
résolution. Le classement prefers d'hébergeurs n'est pas utilisé dans ce lanceur,
conformément au choix de respecter l'ordre du site.
Les catégories alias de langues sont conservées, sans répéter la même référence.
Les numéros du log sont des positions parmi les candidats non vides, pas
nécessairement les noms epsN originaux s'il y a des trous.

## Téléchargements et configuration
concurrent_downloads.video fixe le nombre de workers épisodes.
concurrent_downloads.fragment, download_path, episode_path, format, format_sort,
prefer_languages, players_config.bans et max_retry_time restent utilisés.
Les reprises internes yt-dlp HTTP/fragments sont bornées à 3. Pour les erreurs
classées retry par la fonction existante reaction_to, reprises du même candidat
avec délai exponentiel jusqu'au plafond max_retry_time (même sens que le code
initial). Les autres DownloadError passent au candidat suivant.
Les erreurs inattendues sont remontées, pas transformées en succès.
Les fichiers partiels ne sont pas repris d'une tentative précédente
(continuedl=False), pour éviter une reprise sur un autre média lors d'un fallback.
Les reprises HTTP/fragments au sein de la même tentative restent possibles.

Les appels API sont limités à 3 pour le lot et sérialisés par page de résolution,
ce qui protège cache/jeton. Les téléchargements restent parallèles entre épisodes.
Le client HTTP partagé reste sur la boucle asyncio ; aucun partage inter-boucles.
yt-dlp tourne dans des threads. Une annulation coopérative est vérifiée par ses
hooks ; un thread bloqué hors des hooks peut prendre du temps à s'arrêter.

## Interface et logs
La saisie bleue est conservée depuis votre console_fix joint.
Le compteur est nommé Épisodes traités, pas téléchargements réussis.
Bilan séparé réussis/déjà présents et non aboutis ; code sortie non nul si échec.
Profilage désormais intégré au chemin lazy : durée API à la demande, tentative
yt-dlp, temps jusqu'au premier hook de transfert et durée du lot. run_profile
ajoute un journal timings.log et la durée globale. Ce module de profilage
remplace l'ancien profilage exhaustif, qui instrumentait le downloader initial.
Les tokens ne sont pas écrits par nos messages ; yt-dlp peut émettre ses propres
messages. Ne pas publier de logs non vérifiés.

## Portée
Ce lanceur lazy cible download=true. Le mode lecteur externe est explicitement
refusé, plutôt que de prétendre assurer un fallback sur un lecteur externe dont
on ne connaît pas le résultat. La commande initiale du package reste disponible
pour ce mode. La sélection multi-saisons garde tous les épisodes de ces saisons.
L'ancienne fonction prepare_selected_episodes reste pour compatibilité, mais
n'est jamais appelée par la CLI lazy. parallel_fetch et les anciens tests de
préparation parallèle ne sont plus nécessaires : utiliser le dossier fourni.

## Tests
29 tests unitaires hors réseau réussis lors de la préparation (résolveur,
langues, moteur lazy). 4 tests d'intégration inclus, ignorés ici car le package
anime_sama_api complet n'est pas installé. Ils doivent tourner sur votre machine
avec les dépendances CLI. Aucun téléchargement réel n'a été effectué ici.
Les tests lazy vérifient explicitement : un seul appel au premier succès,
fallback API, fallback téléchargement, cumul des deux types d'échec, arrêt
429, absence de résolution du lecteur suivant pendant le téléchargement.
