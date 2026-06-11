#!/bin/bash

# ============================================================
# Identity Database Setup Script
# Automates the setup of the auth-service identity database
# ============================================================

set -e  # Exit on error

echo "=========================================="
echo "Identity Database Setup Script"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

echo "Step 1: Starting identity-postgres container..."
docker-compose up -d identity-postgres

echo ""
echo "Waiting for PostgreSQL to be ready..."
sleep 5

# Wait for PostgreSQL to be healthy
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker exec clan-identity-postgres pg_isready -U postgres > /dev/null 2>&1; then
        echo -e "${GREEN}PostgreSQL is ready!${NC}"
        break
    fi
    attempt=$((attempt + 1))
    echo "Waiting for PostgreSQL... ($attempt/$max_attempts)"
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}Error: PostgreSQL failed to start within the expected time.${NC}"
    exit 1
fi

echo ""
echo "Step 2: Creating auth_service database if it doesn't exist..."
docker exec -i clan-identity-postgres psql -U postgres -c "CREATE DATABASE auth_service;" 2>/dev/null || echo "Database auth_service already exists"

echo ""
echo "Step 3: Initializing auth_users table..."
docker exec -i clan-identity-postgres psql -U postgres -d auth_service < "$(dirname "$0")/init_identity_db.sql"

echo ""
echo "Step 4: Verifying table creation..."
if docker exec clan-identity-postgres psql -U postgres -d auth_service -c "\dt auth_users" | grep -q "auth_users"; then
    echo -e "${GREEN}✓ auth_users table created successfully!${NC}"
else
    echo -e "${RED}✗ Failed to create auth_users table${NC}"
    exit 1
fi

echo ""
echo "Step 5: Checking table structure..."
docker exec clan-identity-postgres psql -U postgres -d auth_service -c "\d auth_users"

echo ""
echo "=========================================="
echo -e "${GREEN}Identity Database Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Restart the admin-service: docker-compose restart admin-service"
echo "2. Check logs: docker logs admin-service | grep IDENTITY_DB"
echo "3. Test user creation and verify sync"
echo ""
echo "For more information, see: scripts/IDENTITY_DB_SETUP.md"
