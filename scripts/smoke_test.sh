#!/usr/bin/env bash
# =============================================================================
#  Smoke test : vérifie que chaque base du socle répond (après `make up`)
# =============================================================================
#  Un "smoke test" ne teste pas la logique métier : il vérifie juste que « rien
#  ne prend feu » — que chaque service est joignable et répond. C'est le premier
#  réflexe après avoir démarré la plateforme.
#
#  Lit le .env pour les identifiants. À lancer depuis la racine du projet.
# =============================================================================
set -u

# Charge le .env si présent (pour les mots de passe).
[ -f .env ] && set -a && . ./.env && set +a

ok=0; ko=0
check() {
    local label="$1"; shift
    if "$@" >/dev/null 2>&1; then
        echo "  [OK]   $label"; ok=$((ok + 1))
    else
        echo "  [ÉCHEC] $label"; ko=$((ko + 1))
    fi
}

echo "== Smoke test des bases =="

check "PostgreSQL (OLTP)"  docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-platform}"
check "PostgreSQL (warehouse existe)" docker compose exec -T postgres \
    psql -U "${POSTGRES_USER:-platform}" -d "${DW_DB:-warehouse}" -c "SELECT 1"
check "MySQL (facturation)" docker compose exec -T mysql \
    mysqladmin ping -h localhost -u root -p"${MYSQL_ROOT_PASSWORD:-change_me_root}"
check "Cassandra"          docker compose exec -T cassandra cqlsh -e "SHOW VERSION"
check "MongoDB"            docker compose exec -T mongo mongosh --quiet --eval "db.adminCommand('ping')"
check "Neo4j"             docker compose exec -T neo4j wget -qO- http://localhost:7474
check "Redis"             docker compose exec -T redis redis-cli ping
check "Kafka (topics)"    docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
check "Elasticsearch"     docker compose exec -T elasticsearch curl -sf http://localhost:9200/_cluster/health
check "Kibana"            docker compose exec -T kibana curl -sf http://localhost:5601/api/status

echo ""
echo "== Résultat : $ok OK, $ko échec(s) =="
[ "$ko" -eq 0 ]
