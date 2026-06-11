# Identity Database Setup Script (PowerShell)
# Automates the setup of the auth-service identity database

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Identity Database Setup Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if docker is running
try {
    docker info | Out-Null
} catch {
    Write-Host "Error: Docker is not running. Please start Docker and try again." -ForegroundColor Red
    exit 1
}

Write-Host "Step 1: Starting identity-postgres container..." -ForegroundColor Yellow
docker-compose up -d identity-postgres

Write-Host ""
Write-Host "Waiting for PostgreSQL to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Wait for PostgreSQL to be healthy
$maxAttempts = 30
$attempt = 0
$isReady = $false

while ($attempt -lt $maxAttempts) {
    try {
        docker exec clan-identity-postgres pg_isready -U postgres 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "PostgreSQL is ready!" -ForegroundColor Green
            $isReady = $true
            break
        }
    } catch {
        # Ignore errors and continue waiting
    }
    $attempt++
    Write-Host "Waiting for PostgreSQL... ($attempt/$maxAttempts)" -ForegroundColor Yellow
    Start-Sleep -Seconds 2
}

if (-not $isReady) {
    Write-Host "Error: PostgreSQL failed to start within the expected time." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 2: Creating auth_service database if it doesn't exist..." -ForegroundColor Yellow
try {
    docker exec clan-identity-postgres psql -U postgres -c "CREATE DATABASE auth_service;" 2>&1 | Out-Null
} catch {
    Write-Host "Database auth_service already exists" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Step 3: Initializing auth_users table..." -ForegroundColor Yellow
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$sqlFile = Join-Path $scriptPath "init_identity_db.sql"

Get-Content $sqlFile | docker exec -i clan-identity-postgres psql -U postgres -d auth_service

Write-Host ""
Write-Host "Step 4: Verifying table creation..." -ForegroundColor Yellow
$tableCheck = docker exec clan-identity-postgres psql -U postgres -d auth_service -c "`\dt auth_users" 2>&1

if ($tableCheck -match "auth_users") {
    Write-Host "auth_users table created successfully!" -ForegroundColor Green
} else {
    Write-Host "Failed to create auth_users table" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 5: Checking table structure..." -ForegroundColor Yellow
docker exec clan-identity-postgres psql -U postgres -d auth_service -c "`\d auth_users"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Identity Database Setup Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Restart the admin-service: docker-compose restart admin-service"
Write-Host "2. Check logs: docker logs admin-service | Select-String IDENTITY_DB"
Write-Host "3. Test user creation and verify sync"
Write-Host ""
Write-Host "For more information, see the IDENTITY_DB_SETUP.md file" -ForegroundColor Cyan
