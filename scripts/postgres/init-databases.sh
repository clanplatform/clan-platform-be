#!/bin/bash
# Runs once on first volume init (postgres Docker entrypoint behaviour).
# Creates the audit_service database if it does not already exist.
# The main admin_service database is already created by POSTGRES_DB env var.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE audit_service'
    WHERE NOT EXISTS (
        SELECT FROM pg_database WHERE datname = 'audit_service'
    )\gexec

    GRANT ALL PRIVILEGES ON DATABASE audit_service TO $POSTGRES_USER;
EOSQL

echo "[init-databases] audit_service database ready."
