# =============================================================================
#  Image du conteneur jetable `init`
# =============================================================================
#  Problème : aucun image officielle ne contient À LA FOIS les deux clients
#  dont on a besoin — `cqlsh` (Cassandra) et `cypher-shell` (Neo4j).
#  Solution : un build MULTI-STAGE. On récupère `cypher-shell` (et sa JVM)
#  depuis l'image officielle Neo4j, et on part de l'image Cassandra qui, elle,
#  embarque déjà `cqlsh`. On obtient une seule image avec les deux outils.
#
#  Avantage : 100 % reproductible, aucun téléchargement externe fragile au
#  build (on ne tire que des images officielles déjà épinglées).
# =============================================================================

# --- Étape de récupération : on ne garde que ce qu'il faut de Neo4j ----------
FROM neo4j:5 AS neo4j-tools
# (rien à faire : on copiera les fichiers depuis cette couche plus bas)

# --- Image finale : base Cassandra (fournit cqlsh + une JVM) ------------------
FROM cassandra:5.0

#  cypher-shell est un lanceur shell + un JAR. On copie le binaire et les libs.
#  L'image Cassandra a déjà un Java ; cypher-shell s'appuiera dessus.
COPY --from=neo4j-tools /var/lib/neo4j/bin/cypher-shell /usr/local/bin/cypher-shell
COPY --from=neo4j-tools /var/lib/neo4j/lib               /opt/cypher-shell/lib

#  Le lanceur cypher-shell cherche ses libs via CYPHER_SHELL_HOME.
ENV CYPHER_SHELL_HOME=/opt/cypher-shell
RUN chmod +x /usr/local/bin/cypher-shell

#  Le script d'orchestration est monté en volume au runtime (voir compose),
#  on définit juste l'entrée par défaut.
ENTRYPOINT ["bash", "/scripts/run_init.sh"]
