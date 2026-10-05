# PPSSPP HUB + Flux TV

Projet Flask avec une seule application et une seule base SQLite `data.db`.

## Administration
- URL : `/admin`
- Identifiant par défaut : `monetise4@gmail.com`
- Mot de passe par défaut : `monetise4@gmail.com`
- Il est recommandé de définir `ADMIN_USERNAME`, `ADMIN_PASSWORD` et `SECRET_KEY` dans Render.

## Paiements sans API
Chaque jeu peut avoir son propre prix et son propre lien de paiement.
Sans API/webhook, la confirmation « J'ai terminé le paiement » est déclarative : le serveur ne peut pas vérifier réellement auprès du prestataire que le paiement a été effectué.

## Publicité
Les trois régies fournies ont été conservées sur les pages publiques et ne sont pas chargées dans l'administration.

## Important
Utiliser uniquement des fichiers, liens de téléchargement et flux TV que tu es autorisé à distribuer ou diffuser.
