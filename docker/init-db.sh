#!/bin/bash
# ==============================================================================
# PostgreSQL Init Script — runs once when the container is first created.
#
# What it does:
#   1. Creates the pgvector extension in the default database
#   2. Creates two additional databases:
#      - langchain_pgvector  → stores document embeddings for RAG
#      - langchain_history   → stores LangGraph checkpoints (conversation history)
#   3. Enables pgvector in each new database
#   4. Grants full permissions to the app user
#
# This script is mounted via docker-compose.yml into
# /docker-entrypoint-initdb.d/ — PostgreSQL runs all *.sh scripts in that
# directory automatically on first startup.
# ==============================================================================

set -e

echo "🔧 [init-db.sh] Setting up databases and extensions..."

# Variables (from docker-compose environment)
PGUSER="${POSTGRES_USER:-chatbot_user}"
PGPASS="${POSTGRES_PASSWORD:-chatbot_pass}"
PGVECTOR_DB="${PGVECTOR_DB:-langchain_pgvector}"
HISTORY_DB="${HISTORY_DB:-langchain_history}"

# ---------------------------------------------------------------------------
# 1. Enable pgvector in the default Django database
# ---------------------------------------------------------------------------
echo "  → Enabling pgvector in '${POSTGRES_DB}'..."
psql -v ON_ERROR_STOP=1 --username "$PGUSER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
    GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${PGUSER};
EOSQL

# ---------------------------------------------------------------------------
# 2. Create the pgvector database (for RAG embeddings)
# ---------------------------------------------------------------------------
echo "  → Creating database '${PGVECTOR_DB}'..."
psql -v ON_ERROR_STOP=1 --username "$PGUSER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE ${PGVECTOR_DB}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${PGVECTOR_DB}')\gexec
    GRANT ALL PRIVILEGES ON DATABASE ${PGVECTOR_DB} TO ${PGUSER};
EOSQL

echo "  → Enabling pgvector in '${PGVECTOR_DB}'..."
psql -v ON_ERROR_STOP=1 --username "$PGUSER" --dbname "$PGVECTOR_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

# ---------------------------------------------------------------------------
# 3. Create the LangGraph history database (for conversation checkpoints)
# ---------------------------------------------------------------------------
echo "  → Creating database '${HISTORY_DB}'..."
psql -v ON_ERROR_STOP=1 --username "$PGUSER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE ${HISTORY_DB}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${HISTORY_DB}')\gexec
    GRANT ALL PRIVILEGES ON DATABASE ${HISTORY_DB} TO ${PGUSER};
EOSQL

echo "  → Enabling pgvector in '${HISTORY_DB}'..."
psql -v ON_ERROR_STOP=1 --username "$PGUSER" --dbname "$HISTORY_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "✅ [init-db.sh] All databases and extensions ready!"
echo ""
echo "  Databases:"
echo "    • ${POSTGRES_DB}   → Django models (users, sessions, preferences, etc.)"
echo "    • ${PGVECTOR_DB}   → pgvector embeddings for RAG"
echo "    • ${HISTORY_DB}    → LangGraph checkpoints (conversation history)"
echo ""
