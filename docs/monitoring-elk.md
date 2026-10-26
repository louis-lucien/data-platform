# Monitoring avec la stack ELK (étape 7)

## L'idée en une phrase

ELK rend le flux temps réel **cherchable et visualisable** : chaque relevé et
chaque alerte qui passent par Kafka sont indexés dans Elasticsearch, et Kibana
permet de les explorer et d'en faire des tableaux de bord.

## Qui fait quoi

```
Kafka ──► Logstash ──► Elasticsearch ──► Kibana
        (lit+route)    (stocke+indexe)   (cherche+affiche)
```

| Composant | Rôle | Image |
|---|---|---|
| **Elasticsearch** | stocke et indexe tout (moteur de recherche) | `elasticsearch:8.15.3` |
| **Logstash** | lit Kafka, transforme, envoie à Elastic | `logstash:8.15.3` |
| **Kibana** | exploration et dashboards (http://localhost:5601) | `kibana:8.15.3` |

Logstash est un **3e lecteur** des topics Kafka (groupe `elk-logstash`), à côté
des consumers Redis et Mongo : grâce aux groupes Kafka, chacun reçoit tout le
flux sans gêner les autres.

## Le pipeline Logstash

Défini dans [config/logstash/pipeline/kafka-to-es.conf](../config/logstash/pipeline/kafka-to-es.conf).
Trois sections :

- **input** : s'abonne à `meter-readings` et `meter-alerts` ; `decorate_events`
  expose le nom du topic de chaque message.
- **filter** : traduit le topic en index parlant (`meter-readings` → `releves`,
  `meter-alerts` → `alertes`) et aligne `@timestamp` sur l'horodatage **métier**
  du relevé (pas l'heure d'ingestion) — essentiel pour des graphes justes.
- **output** : écrit dans un index daté, ex. `releves-2026.10.26`.

## Sécurité : désactivée (dev)

`xpack.security.enabled=false` : pas de mot de passe ni de TLS. C'est le choix
assumé pour un environnement **local/pédagogique** — Kibana et Logstash se
connectent sans friction. **En production**, il faut l'activer (mots de passe,
certificats TLS, tokens Kibana) et passer en cluster multi-nœuds.

## Démarrer

```bash
docker compose up -d                    # inclut elasticsearch, logstash, kibana
docker compose --profile stream up      # producteur + consumers : alimente le flux
```

Elasticsearch et Kibana sont **lents à démarrer** (~1 min chacun) : c'est normal,
les healthchecks ont une marge (`start_period`). Le conteneur `kibana-setup`
crée automatiquement les **data views** `releves-*` et `alertes-*` dès que Kibana
est prêt, puis s'arrête.

## Explorer dans Kibana

1. Ouvrir **http://localhost:5601**.
2. Menu **Discover** : choisir la data view *Relevés compteurs* ou *Alertes*.
   On voit les documents arriver en direct, filtrables par région, type, etc.
3. Menu **Dashboard** : créer des visualisations (conso moyenne par région,
   nombre d'alertes par heure, répartition par type de client...).

### Vérifier en ligne de commande

```bash
# Les index existent-ils et se remplissent-ils ?
curl -s "http://localhost:9200/_cat/indices/releves-*,alertes-*?v"

# Un échantillon de relevés indexés
curl -s "http://localhost:9200/releves-*/_search?size=2&pretty"
```

## Logs JSON de toute la plateforme

Le générateur et les consumers émettent déjà leurs logs en **JSON structuré**
(même format partout). Ils sont donc prêts à être collectés par ELK si on le
souhaite plus tard — c'est pourquoi ce format commun a été choisi dès le début.

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| Elasticsearch `unhealthy` longtemps | démarrage lent / RAM | patienter (~1 min) ; vérifier `ES_JAVA_OPTS` |
| Aucun index `releves-*` | pas de flux | lancer `--profile stream` pour produire des messages |
| Kibana "Kibana server is not ready" | Elastic pas encore prêt | attendre que `elasticsearch` soit `healthy` |
| `max virtual memory` au boot ES | `vm.max_map_count` trop bas (Linux) | `sysctl -w vm.max_map_count=262144` |
