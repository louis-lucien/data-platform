# Redis — cache temps réel (conventions de clés)

## Pourquoi Redis, et pourquoi pas de « schéma » ?

Redis stocke des paires **clé → valeur** en mémoire vive. Il n'y a ni table ni
schéma à créer au démarrage : une clé naît quand on l'écrit. La seule vraie
décision de conception est donc la **convention de nommage des clés**. C'est ce
document — l'équivalent Redis d'un schéma — que les producteurs (étape 6) et les
lecteurs (dashboard, API) devront respecter à la lettre.

Redis répond à une seule question, mais instantanément : **« quelle est la
valeur *maintenant* ? »** (dernier relevé d'un compteur, conso live d'une
région). L'historique, lui, vit dans Cassandra ; l'analyse, dans le Data
Warehouse. Redis ne garde que le présent.

## Convention de nommage

Règle : `domaine:entité:identifiant[:champ]`, en `snake_case`, `:` comme
séparateur (convention Redis universelle, exploitée par les outils comme
RedisInsight pour afficher les clés en arborescence).

| Clé | Type Redis | Contenu | Écrit par |
|---|---|---|---|
| `compteur:<id>:dernier` | Hash | dernier relevé du compteur (`horodatage`, `energie_kwh`, `index_kwh`, `tension_v`, `courant_a`) | consumer `meter-readings` |
| `region:<code>:conso_live` | String (float) | consommation cumulée de la région sur l'heure courante (kWh) | consumer `meter-readings` |
| `region:<code>:compteurs_actifs` | Set | identifiants des compteurs ayant émis récemment | consumer `meter-readings` |
| `alertes:recentes` | List (capée) | N dernières alertes (JSON), pour un affichage « live » | consumer `meter-alerts` |

Exemples :

```
compteur:CPT-10000001:dernier     -> { horodatage, energie_kwh, index_kwh, tension_v, courant_a }
region:SN-DK:conso_live           -> "1843.72"
region:SN-DK:compteurs_actifs     -> { CPT-10000001, CPT-10000002, ... }
```

## TTL (durée de vie)

Comme Redis ne doit garder que le **présent**, les clés volatiles portent un
**TTL** (expiration automatique) pour ne pas accumuler de la donnée morte en
mémoire :

- `compteur:*:dernier` : TTL de quelques heures (un compteur muet finit par
  disparaître du cache — on ne veut pas afficher un « dernier relevé » vieux
  d'une semaine comme s'il était frais).
- `region:*:conso_live` : réinitialisée à chaque heure.

> Ces TTL sont posés par le code des consumers (étape 6) au moment de l'écriture
> (`SET ... EX`, `EXPIRE`), pas ici : Redis n'a pas de fichier d'init. Ce
> document fait foi pour toute l'équipe.
