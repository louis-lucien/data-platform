#!/usr/bin/env bash
# =============================================================================
#  Pré-configuration Kibana : crée les "data views" (ex-index patterns)
# =============================================================================
#  Un data view dit à Kibana « voici une famille d'index que tu peux explorer »
#  (ex. releves-*). Sans lui, Kibana ne sait pas quoi afficher. On les crée via
#  l'API Kibana, une fois Kibana prêt. Idempotent : on ignore l'erreur "existe
#  déjà" (overwrite).
#
#  Pourquoi un script et pas un export NDJSON figé ? Parce qu'un NDJSON exporté
#  dépend de la version de Kibana et casse facilement. Quelques appels API sont
#  plus lisibles, plus robustes, et montrent explicitement ce qu'on crée.
# =============================================================================
set -euo pipefail

KIBANA_URL="${KIBANA_URL:-http://kibana:5601}"

echo "==> [kibana-setup] Attente de Kibana sur ${KIBANA_URL}..."
until curl -s "${KIBANA_URL}/api/status" | grep -q '"level":"available"'; do
    echo "    [kibana-setup] Kibana pas encore prêt..."
    sleep 5
done
echo "==> [kibana-setup] Kibana est prêt."

# Fonction : crée un data view (nom, motif d'index, champ temporel).
create_data_view() {
    local name="$1" pattern="$2"
    echo "==> [kibana-setup] Data view '${name}' (index ${pattern})"
    curl -s -X POST "${KIBANA_URL}/api/data_views/data_view" \
        -H 'kbn-xsrf: true' -H 'Content-Type: application/json' \
        -d "{
              \"data_view\": {
                \"name\": \"${name}\",
                \"title\": \"${pattern}\",
                \"timeFieldName\": \"@timestamp\"
              },
              \"override\": true
            }" >/dev/null && echo "    OK"
}

create_data_view "Relevés compteurs" "releves-*"
create_data_view "Alertes"           "alertes-*"

echo "==> [kibana-setup] Pré-configuration terminée."
