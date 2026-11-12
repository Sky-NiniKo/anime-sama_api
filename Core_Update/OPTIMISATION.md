# Correctif de préparation parallèle

Complément à votre Core_Update actuel, pas un dossier complet.
Remplacer resolver.py et season_api.py, ajouter parallel_fetch.py et
test_parallel_fetch.py. Garder run_cli.py, lang_fix.py, console_fix.py et les tests
existants. Le code cible les derniers fichiers joints (lang_fix.py).

Aucun changement de langue ni de configuration : toutes les langues/lecteurs
sélectionnés restent préparés, puis le downloader applique la configuration.
Aucun argument allowed_languages : enlever cet argument si vous aviez essayé
la proposition précédente. L'appel original (episodes, progress) reste valide.

Concurrence par défaut : 3 opérations de résolution pour tout le lot, sans
pause artificielle entre les appels. Déduplication avant envoi par résolveur
et référence ; ordre des résultats préservé. Cache existant conservé.
Un renouvellement concurrent du même jeton est protégé par un verrou.
429 : arrêt de la file, annulation des tâches en cours, aucune relance automatique.
Les requêtes déjà arrivées au serveur ne peuvent pas être annulées rétroactivement.
Les délais de reprise existants en cas d'autres erreurs sont conservés.

Tests :
 python -m unittest Core_Update.test_parallel_fetch -v
 python -m unittest Core_Update.test_resolver Core_Update.test_integration Core_Update.test_lang_fix Core_Update.test_parallel_fetch -v
 python -m Core_Update.run_cli

Quatre tests du moteur parallèle ont réussi ici. Compilation des fichiers OK.
Tests d'intégration du package et téléchargement réel non exécutés ici.
Les assertions d'ordre des appels HTTP dans un ancien test d'intégration doivent
porter sur les IDs attendus (ensemble ou tri) plutôt que l'ordre de départ réseau.
Les résultats reconstruits conservent leur ordre logique.
La concurrence 3 est un choix initial, pas un quota serveur connu. Si un 429
survient, respecter le délai serveur et réduire concurrence à 1 ou 2 lors d'un
essai ultérieur (keyword concurrency dans prepare_selected_episodes).

Le logger INFO rapporte la durée de préparation si activé. Le temps supplémentaire
après préparation peut aussi inclure catalogue.year() et l'extraction yt-dlp.
Aucune promesse de latence : mesurer avant/après avec la même sélection.
