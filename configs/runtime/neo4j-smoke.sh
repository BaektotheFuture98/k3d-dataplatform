#!/usr/bin/env bash
# Feed this file to bash inside neo4j-0; credentials stay in the container.
set -euo pipefail
auth=$(cat /config/neo4j-auth/NEO4J_AUTH)
export NEO4J_USERNAME=${auth%%/*}
export NEO4J_PASSWORD=${auth#*/}
case "${1:-}" in
  write)
    query="MERGE (n:InfrastructurePersistence {id: 'finance-platform-20261018-infra'}) RETURN count(n) AS persisted;"
    ;;
  read)
    # Assert the scalar result without requiring optional plugins.
    result=$(cypher-shell -a bolt://neo4j:7687 --format plain "MATCH (n:InfrastructurePersistence {id: 'finance-platform-20261018-infra'}) RETURN count(n) AS persisted;")
    [[ "$result" == $'persisted\n1' ]] || { echo 'Neo4j persistence assertion failed' >&2; exit 1; }
    query="MATCH (n:InfrastructurePersistence {id: 'finance-platform-20261018-infra'}) DELETE n RETURN count(n) AS cleaned;"
    ;;
  *) echo 'Expected write or read' >&2; exit 2 ;;
esac
cypher-shell -a bolt://neo4j:7687 --format plain "$query"
