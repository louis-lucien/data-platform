# Exploitation : BI & Machine Learning (étape 10)

Deux façons d'exploiter les données : la **BI** (comprendre le passé) et le **ML**
(prédire / détecter). Les deux s'appuient sur les étapes précédentes.

---

## Partie 1 — Business Intelligence (Power BI)

### Source : le Data Warehouse

La BI lit le **Data Warehouse** (base `warehouse`, schéma en étoile), pas les
bases opérationnelles : c'est fait pour ça (données propres, agrégats rapides).

### Connecter Power BI

Power BI Desktop (Windows) → **Obtenir les données** → **PostgreSQL** :

| Champ | Valeur |
|---|---|
| Serveur | `localhost:5432` |
| Base de données | `warehouse` |
| Identifiants | ceux du `.env` (`POSTGRES_USER` / `POSTGRES_PASSWORD`) |

Importer les tables du schéma `dw` : les dimensions (`dim_*`) et les faits
(`fait_*`). Power BI reconnaît le schéma en étoile et propose les bonnes
relations (fait → dimensions).

### Visualisations suggérées

- **Consommation par région et par mois** (carte / histogramme empilé).
- **Profil horaire moyen** par type de client (courbe) : le pic du soir des
  ménages vs la journée des professionnels.
- **Qualité des données** : part de clients à email valide par région.
- **Top compteurs à risque** : alimenté par le score ML (partie 2).

### Livrables BI concrets

1. **Vues SQL** — [bi/sql/vues_bi.sql](../bi/sql/vues_bi.sql) : une vue par
   question métier (`vue_conso_region_mois`, `vue_profil_horaire`,
   `vue_conso_par_type`, `vue_qualite_clients`, `vue_synthese_region`). Power BI
   importe la vue directement, sans recopier de requête. Créées par le service
   `bi-init` :
   ```bash
   docker compose --profile load up bi-init     # après l'ETL
   ```

2. **Dashboard HTML de démonstration** — [bi/dashboard/index.html](../bi/dashboard/index.html) :
   un tableau de bord autonome (ouvrable dans un navigateur, sans rien installer)
   qui visualise les mêmes agrégats sur les **vraies données** du data lake :
   consommation par région, profil horaire par type, qualité des données. Sert à
   *voir* le résultat immédiatement et à illustrer ce qu'un Power BI produirait.

### Brancher Power BI sur les vues

Les requêtes de [sql/analytics/exemples_requetes.sql](../sql/analytics/exemples_requetes.sql)
sont aussi disponibles comme vues. Dans Power BI, importer les vues du schéma
`dw` plutôt que d'écrire du SQL.

> Power BI est un outil propriétaire Windows : il ne fait pas partie du
> docker-compose. Le DW et ses vues, eux, sont la source ouverte et stable sur
> laquelle il (ou Metabase, Superset, ou le dashboard HTML ci-dessus) se branche.

---

## Partie 2 — Détection de fraude/anomalie (Machine Learning)

### Le problème et le fil rouge

Objectif métier : **repérer les compteurs anormaux** (fraude ou panne) à partir
de leur profil de consommation, pour **prioriser les inspections terrain**.

C'est l'aboutissement d'un fil tendu depuis l'étape 2 :
- le générateur **injecte** des anomalies dans les relevés ;
- les **inspections** (MongoDB) en étiquettent une partie (comme en vrai : toutes
  les anomalies ne sont pas inspectées).

→ apprentissage **supervisé binaire** : anomalie (1) / normal (0).

### Les features (ce que le modèle regarde)

Une ligne par compteur, calculée depuis le DW. Features choisies pour capturer
les signatures des anomalies injectées :

| Feature | Capte quelle anomalie |
|---|---|
| `part_zero`, `part_zero_nuit` | compteur bloqué, fraude intermittente (zéros, surtout la nuit) |
| `ratio_2de_1re` | fraude bypass (chute de conso dans le temps) |
| `conso_moy`, `conso_std`, `ratio_nuit_jour` | profil général |

**Pas de fuite de données** : aucune feature ne dit si le compteur a été inspecté.
Les inspections ne servent QUE d'étiquettes.

### Le modèle

`RandomForest` avec `class_weight='balanced'` (compense le déséquilibre : peu
d'anomalies). Choisi pour sa robustesse sur petit jeu et son **interprétabilité**
(importance des features → on peut expliquer pourquoi un compteur est signalé).

### Évaluation : pas l'accuracy !

Avec ~4% d'anomalies, un modèle qui dit « tout normal » aurait 96% d'accuracy et
serait inutile. On mesure donc :
- **recall** : parmi les vraies anomalies, combien on en trouve (ne pas en rater) ;
- **precision** : parmi les signalés, combien sont vraiment anormaux (ne pas
  envoyer les techniciens pour rien) ;
- **ROC-AUC** : qualité du classement global.

### Lancer

```bash
# Prérequis : l'ETL a rempli le Data Warehouse (étape 9).
docker compose --profile ml up ml-train    # entraîne + évalue + sauvegarde le modèle
docker compose --profile ml up ml-score     # top compteurs à inspecter en priorité
```

Le modèle est sauvegardé dans `ml/models/` (non versionné). `ml-score` produit
le **classement des compteurs par risque** — la sortie directement actionnable
par le service d'inspection.

### ⚠️ À propos des scores « parfaits »

Sur ce jeu de données, le modèle obtient des métriques proches de 1.0
(precision/recall/AUC). **C'est attendu, et ce n'est PAS représentatif du réel.**
Les anomalies sont **injectées de façon très marquée** par le générateur
(consommation divisée par 2 à 10, zéros francs) : elles sont donc très faciles à
séparer. Dans la vraie vie, une fraude est plus subtile (petit détournement,
intermittence rare) et les scores seraient nettement plus bas. Ce projet montre
la **chaîne ML complète et correcte** (features sans fuite, évaluation adaptée au
déséquilibre, scoring actionnable) ; la performance, elle, reflète la facilité des
données synthétiques, pas une promesse de résultat en production.

### Tester la logique sans base

```bash
pip install -e "ml[dev]"
pytest ml
```

Les tests vérifient que les features capturent bien les signatures (zéros, chute)
et que les étiquettes sont correctes — sans Docker ni bases.
