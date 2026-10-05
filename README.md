# PPSSPP + Flux TV — application unifiée

Un seul projet Flask :
- un seul `app.py`
- un seul dossier `templates/`
- un seul dossier `static/`
- une seule base SQLite `data.db`
- une seule connexion administrateur pour les deux parties.

Pages publiques :
- `/ppsspp` : catalogue PPSSPP
- `/flux` : catalogue Flux TV
- `/ppsspp/<id>` : détail d'un jeu
- `/flux/<id>` : lecteur d'une chaîne

Les pages publiques ne contiennent aucun bouton/lien vers l'autre site.
L'administration commune est accessible directement par `/admin/login`.

Identifiant administrateur configuré par défaut :
`monetise4@gmail.com`

Mot de passe configuré par défaut :
`monetise4@gmail.com`

Pour la production, il est fortement recommandé de remplacer ce mot de passe par un mot de passe unique et fort via les variables d'environnement.

Les trois codes publicitaires fournis sont intégrés aux pages publiques :
- HighRevenueFormat 300x250
- HighRevenueFormat 320x50
- Profitableratecpm

Les pages d'administration ne chargent pas ces publicités.

Les liens de jeux et les flux TV doivent être utilisés uniquement avec les autorisations nécessaires.
