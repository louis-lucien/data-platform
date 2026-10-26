#!/usr/bin/env bash
# =============================================================================
#  Orchestrateur d'initialisation des bases SANS auto-init (Cassandra, Neo4j)
# =============================================================================
#  Postgres, MySQL et Mongo jouent leurs scripts tout seuls au premier démarrage
#  (dossier /docker-entrypoint-initdb.d). Cassandra et Neo4j, NON : il faut les
#  attendre puis leur pousser leurs scripts à la main. C'est le rôle de ce
#  conteneur jetable `init`, lancé par docker-compose une fois les bases saines.
#
#  Idempotent : les scripts CQL/Cypher utilisent IF NOT EXISTS, donc rejouer
#  cet init (ex. après un `docker compose up` sur des volumes existants) ne
#  casse rien.
#
#  set -euo pipefail : on s'arrête à la première vraie erreur (fail fast), et
#  une variable non définie est une erreur (évite les bugs silencieux).
# =============================================================================
set -euo pipefail

echo "==> [init] Demarrage de l'orchestrateur d'initialisation"

# -----------------------------------------------------------------------------
#  Fonction d'attente générique : réessaie une commande jusqu'à succès.
#  Même si depends_on garantit déjà l'état "healthy", on garde une attente
#  défensive : un healthcheck "up" ne veut pas toujours dire "prêt à écrire".
# -----------------------------------------------------------------------------
wait_for() {
    local label="$1"; shift         # le reste des arguments = la commande à tester
    local tries=0 max=30
    until "$@" >/dev/null 2>&1; do
        tries=$((tries + 1))
        if [ "$tries" -ge "$max" ]; then
            echo "==> [init] ECHEC : $label toujours injoignable apres $max tentatives" >&2
            return 1
        fi
        echo "    [init] $label pas encore pret (tentative $tries/$max)..."
        sleep 5
    done
    echo "==> [init] $label est pret."
}

# -----------------------------------------------------------------------------
#  1) Cassandra — on joue le keyspace + la table des relevés
# -----------------------------------------------------------------------------
#  Les variables d'hôte (cassandra, neo4j) sont les NOMS DE SERVICE du compose :
#  Docker fournit un DNS interne, "cassandra" résout vers le bon conteneur.
wait_for "Cassandra" cqlsh cassandra 9042 -e "SHOW VERSION"
echo "==> [init] Application du schema Cassandra..."
cqlsh cassandra 9042 -f /init/cassandra/01_keyspace_releves.cql
echo "==> [init] Schema Cassandra applique."

# -----------------------------------------------------------------------------
#  2) Neo4j — on pose les contraintes de la topologie
# -----------------------------------------------------------------------------
#  NEO4J_AUTH a la forme "user/password" ; cypher-shell veut les deux séparés.
NEO4J_USER="${NEO4J_AUTH%%/*}"       # avant le '/'
NEO4J_PASS="${NEO4J_AUTH##*/}"       # après le '/'

wait_for "Neo4j" cypher-shell -a "bolt://neo4j:7687" -u "$NEO4J_USER" -p "$NEO4J_PASS" "RETURN 1"
echo "==> [init] Application des contraintes Neo4j..."
cypher-shell -a "bolt://neo4j:7687" -u "$NEO4J_USER" -p "$NEO4J_PASS" \
    -f /init/neo4j/01_contraintes_topologie.cypher
echo "==> [init] Contraintes Neo4j appliquees."

echo "==> [init] Initialisation terminee avec succes. Le conteneur init va s'arreter."
