# Contexte pour Claude

## Le projet
Projet pédagogique : plateforme de traitement de données batch + temps réel, en 12 étapes
(voir « Avancement » dans README.md). Domaine : **distributeur d'électricité fictif au Sénégal,
compteurs intelligents** (l'utilisateur travaille dans l'énergie).

## Façon de travailler
- Répondre en **français**, de façon pédagogique : expliquer le *pourquoi* avant le *comment*,
  une étape à la fois. L'utilisateur veut un projet solide, « comme un expert », et tout comprendre.
- L'utilisateur fait lui-même ses commits (Conventional Commits : `feat:`, `fix:`, `chore:`, `docs:`).
- Avant de coder contre une source externe, sonder sa vraie structure (cf. codes ISO des régions).

## Choix d'architecture déjà actés
| Base | Contenu | Justification |
|---|---|---|
| PostgreSQL | clients, compteurs (OLTP) + Data Warehouse (base `warehouse`) | relationnel, intégrité |
| MySQL | facturation : recharges prépayées, factures postpayées | système de facturation séparé, comme en réalité |
| Cassandra | historique des relevés | séries temporelles, écriture massive |
| MongoDB | inspections terrain, alertes brutes | schéma variable |
| Neo4j | topologie région > poste source > transformateur > compteur | impact d'une panne |
| Redis | dernier relevé par compteur, conso live par région | cache temps réel |
| Elasticsearch/Kibana | relevés, alertes, logs JSON | monitoring |

Topics Kafka : `meter-readings`, `meter-alerts`. ML prévu : détection de fraude/anomalie,
étiquettes issues de `inspections` (anomalies injectées : fraude_bypass, fraude_intermittente, compteur_bloque).

## État actuel
- Étapes 1 et 2 terminées : `generator/` (package Python, 12 tests pytest qui passent).
  `python -m generator.batch --out data/raw` → data lake `data/raw/<entité>/dt=AAAA-MM-JJ/`.
- `consumption.py` est conçu pour être réutilisé par le futur producteur Kafka (étape 5).
- Défauts de qualité volontaires dans `clients` (emails manquants, téléphones, doublons) : à nettoyer dans l'ETL.
- Prochaine étape : 3/4 (bases de données + docker-compose).

## Environnement
- Windows, projet sur **D:** (disque USB NTFS) car **C: est plein** (~0 Go libre).
- **Docker Desktop pas encore installé** : l'utilisateur doit libérer de la place sur C:
  (OneDrive « Libérer de l'espace », `powercfg /h off`), puis déplacer le stockage Docker sur D:.
- venv : `D:\data-platform\.venv` (Python 3.14 local). Docker utilisera Python 3.12.
- Pour pip : `$env:TEMP="D:\.tmp"; $env:TMP="D:\.tmp"; $env:PIP_NO_CACHE_DIR="1"` (évite de remplir C:).
- pandas 3.x : utiliser `day_of_week` (et non `weekday`).
