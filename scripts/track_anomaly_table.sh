#!/bin/bash
# Track tower_anomaly_scores table in Hasura and set up relationships

HASURA_ENDPOINT="${HASURA_GRAPHQL_ENDPOINT:-http://localhost:8080}"
HASURA_SECRET="${HASURA_GRAPHQL_ADMIN_SECRET:-aerocell-secret}"

echo "Tracking tower_anomaly_scores table in Hasura..."

# Track the tower_anomaly_scores table
curl -X POST "$HASURA_ENDPOINT/v1/metadata" \
  -H "Content-Type: application/json" \
  -H "X-Hasura-Admin-Secret: $HASURA_SECRET" \
  -d '{
    "type": "pg_track_table",
    "args": {
      "source": "acd",
      "table": {
        "schema": "public",
        "name": "tower_anomaly_scores"
      }
    }
  }'

echo ""
echo "Creating relationship from tower_anomaly_scores to towers..."

# Create object relationship from tower_anomaly_scores -> tower
curl -X POST "$HASURA_ENDPOINT/v1/metadata" \
  -H "Content-Type: application/json" \
  -H "X-Hasura-Admin-Secret: $HASURA_SECRET" \
  -d '{
    "type": "pg_create_object_relationship",
    "args": {
      "source": "acd",
      "table": {
        "schema": "public",
        "name": "tower_anomaly_scores"
      },
      "name": "tower",
      "using": {
        "foreign_key_constraint_on": "tower_id"
      }
    }
  }'

echo ""
echo "Creating array relationship from towers to tower_anomaly_scores..."

# Create array relationship from towers -> tower_anomaly_scores
curl -X POST "$HASURA_ENDPOINT/v1/metadata" \
  -H "Content-Type: application/json" \
  -H "X-Hasura-Admin-Secret: $HASURA_SECRET" \
  -d '{
    "type": "pg_create_array_relationship",
    "args": {
      "source": "acd",
      "table": {
        "schema": "public",
        "name": "towers"
      },
      "name": "anomaly_scores",
      "using": {
        "foreign_key_constraint_on": {
          "table": {
            "schema": "public",
            "name": "tower_anomaly_scores"
          },
          "column": "tower_id"
        }
      }
    }
  }'

echo ""
echo "Done! The tower_anomaly_scores table is now tracked in Hasura."
echo "You can now query anomaly scores via GraphQL."
