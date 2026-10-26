# Installer Docker Desktop avec tout le stockage sur D:

> Guide adapté à **votre machine** : Windows 11, disque **C: plein** (~0 Go),
> projet et données sur le disque USB **D: (NTFS)**. L'objectif est que Docker
> n'écrive **rien de lourd sur C:** — ni ses images, ni les volumes des bases.

## Pourquoi c'est un vrai sujet (et pas juste « installer un .exe »)

Par défaut, Docker Desktop stocke tout dans votre profil utilisateur, donc
**sur C:** : l'image disque de la VM Linux (`docker_data`), qui grossit vite
(plusieurs Go dès qu'on tire Postgres, Cassandra, Neo4j...). Avec C: plein,
l'installation échouerait ou saturerait le disque au premier `docker pull`.
Il faut donc **rediriger ce stockage vers D: dès le départ.**

Docker Desktop sous Windows s'appuie sur **WSL 2** (une VM Linux légère). La
redirection se fait donc à deux niveaux : WSL *et* Docker. Les deux sont
couverts ci-dessous.

---

## Étape 0 — Libérer un minimum d'espace sur C:

WSL et Docker ont besoin d'un **petit** socle sur C: même en redirigeant les
données (quelques centaines de Mo pour les binaires). D'après les pistes déjà
notées pour ce projet :

```powershell
# Désactiver la mise en veille prolongée : supprime C:\hiberfil.sys
# (souvent plusieurs Go). À ne faire que si vous n'utilisez pas la veille
# prolongée (la mise en veille simple, elle, continue de fonctionner).
powercfg /h off
```

- **OneDrive** : clic droit sur les gros dossiers synchronisés > « Libérer de
  l'espace » (garde les fichiers dans le cloud, libère le disque local).
- **Nettoyage de disque** : `cleanmgr` > cocher « Fichiers temporaires »,
  « Corbeille », « Windows Update nettoyage ».

Objectif : disposer d'au moins **2–3 Go libres sur C:** avant de continuer.

---

## Étape 1 — Activer WSL 2 et déplacer son stockage sur D:

### 1a. Installer WSL 2

```powershell
# Dans un PowerShell ADMINISTRATEUR
wsl --install --no-distribution     # installe le moteur WSL 2 sans distro Linux
wsl --set-default-version 2
```

Redémarrez si Windows le demande.

### 1b. (Recommandé) Forcer WSL à stocker sur D:

Docker Desktop crée ses propres distributions WSL (`docker-desktop`). On peut
indiquer à WSL où poser ses VHDX. Le plus simple et fiable reste de régler
l'emplacement **dans Docker Desktop** (étape 3) ; ce bloc est un complément si
vous créez d'autres distros WSL.

Créez `C:\Users\<vous>\.wslconfig` (petit fichier, reste sur C:) :

```ini
[wsl2]
memory=4GB          # plafonne la RAM de la VM (ajustez à votre machine)
processors=2
swap=2GB
swapfile=D:\\wsl\\swap.vhdx   # le swap, potentiellement gros, va sur D:
```

---

## Étape 2 — Installer Docker Desktop

1. Téléchargez l'installeur depuis le site officiel Docker (Docker Desktop for
   Windows).
2. **Avant de lancer l'installeur**, placez-vous si possible sur D: pour le
   téléchargement (le `.exe` lui-même est petit, mais autant prendre l'habitude).
3. Lancez l'installation en cochant **« Use WSL 2 instead of Hyper-V »**.
4. **Ne lancez pas encore de conteneur** : on règle d'abord le stockage.

---

## Étape 3 — Rediriger le stockage de Docker vers D: ⭐

C'est **l'étape qui évite de saturer C:**. Dans Docker Desktop :

**Settings (roue crantée) > Resources > Advanced**

- **Disk image location** → changez pour un dossier sur D:, par ex. :
  ```
  D:\docker-data
  ```
  Docker déplacera (ou recréera) là son image disque. Tous les **volumes** des
  bases (`postgres_data`, `cassandra_data`, etc. définis dans le compose)
  vivront alors **sur D:**, pas sur C:.

- **Disk image size limit** : laissez une marge confortable (ex. 60 Go) ;
  l'espace n'est pris qu'au fur et à mesure.

Cliquez **Apply & Restart**.

> Vérification : après redémarrage de Docker, le dossier `D:\docker-data`
> doit commencer à se remplir. C: ne doit **pas** gonfler.

---

## Étape 4 — Vérifier que Docker fonctionne

```powershell
docker version          # client + serveur doivent répondre
docker run --rm hello-world   # tire une mini-image et l'exécute
```

Si `hello-world` affiche son message, Docker est opérationnel.

---

## Étape 5 — Lancer la plateforme

Depuis le dossier du projet sur D: :

```powershell
cd D:\data-platform
Copy-Item .env.example .env     # puis ÉDITEZ .env pour changer les mots de passe
docker compose up -d            # démarre les 6 bases + le conteneur d'init
```

Ce qui se passe, dans l'ordre :

1. Docker **tire les images** (postgres, mysql, cassandra, mongo, neo4j, redis)
   → écrites sur **D:**.
2. **Postgres, MySQL, Mongo** jouent seuls leurs scripts d'init (schémas).
3. Les **healthchecks** passent au vert quand chaque base est prête
   (Cassandra est la plus lente : ~1 min).
4. Le conteneur **`init`** attend Cassandra + Neo4j saines, applique leurs
   scripts (keyspace relevés, contraintes topologie), puis **s'arrête**.

### Suivre le démarrage

```powershell
docker compose ps               # état + santé de chaque conteneur
docker compose logs -f init     # voir l'init Cassandra/Neo4j se dérouler
```

`energy-init` doit finir avec « Initialisation terminee avec succes » puis
passer en état `Exited (0)` — c'est **normal** : il a fini son travail.

---

## Étape 6 — Vérifier chaque base (facultatif mais formateur)

```powershell
# PostgreSQL : lister les tables du schéma oltp
docker compose exec postgres psql -U platform -d energy -c "\dt oltp.*"

# MySQL : voir les tables de facturation
docker compose exec mysql mysql -u platform -p billing -e "SHOW TABLES;"

# Cassandra : vérifier le keyspace et la table
docker compose exec cassandra cqlsh -e "DESCRIBE KEYSPACE releves;"

# MongoDB : lister les collections
docker compose exec mongo mongosh terrain --eval "db.getCollectionNames()"

# Neo4j : lister les contraintes (interface web : http://localhost:7474)
docker compose exec neo4j cypher-shell -u neo4j -p <mdp> "SHOW CONSTRAINTS;"

# Redis : ping
docker compose exec redis redis-cli ping
```

---

## Arrêter / réinitialiser

```powershell
docker compose down       # arrête tout, GARDE les données (volumes sur D:)
docker compose down -v    # arrête tout et SUPPRIME les données (repart de zéro)
```

Utilisez `down -v` si vous voulez rejouer les scripts d'init depuis une base
vierge (par ex. après avoir modifié un schéma).

---

## Dépannage ciblé pour votre config

| Symptôme | Cause probable | Solution |
|---|---|---|
| `no space left on device` au `docker pull` | stockage toujours sur C: | revérifier Étape 3 (Disk image location = D:) |
| `energy-init` en erreur `bad interpreter` | `run_init.sh` passé en CRLF | `.gitattributes` l'évite ; sinon reconvertir en LF |
| Cassandra `unhealthy` longtemps | boot normal (~1 min) ou RAM trop basse | patienter, ou augmenter la RAM dans `.wslconfig` |
| Neo4j refuse la connexion | mot de passe `.env` ≠ celui du 1er démarrage | `down -v` puis `up` (le mot de passe se fige au 1er boot) |
```
