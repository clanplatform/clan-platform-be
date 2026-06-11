# ============================================================
# Identity Database Setup for Standalone PostgreSQL
# Creates auth_service database on existing PostgreSQL server
# ============================================================

param(
    [string]$DbHost = "localhost",
    [int]$DbPort = 5433,
    [string]$DbUser = "postgres",
    [string]$DbPassword = "root"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Identity Database Setup" -ForegroundColor Cyan
Write-Host "PostgreSQL Standalone Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Target Server:" -ForegroundColor Yellow
Write-Host "  Host: $DbHost"
Write-Host "  Port: $DbPort"
Write-Host "  User: $DbUser"
Write-Host ""

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$sqlFile = Join-Path $scriptPath "create_identity_database.sql"

# Set PGPASSWORD environment variable to avoid password prompt
$env:PGPASSWORD = $DbPassword

try {
    Write-Host "Step 1: Testing PostgreSQL connection..." -ForegroundColor Yellow
    
    # Test connection
    $testResult = psql -h $DbHost -p $DbPort -U $DbUser -d postgres -c "SELECT version();" 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to connect to PostgreSQL server!" -ForegroundColor Red
        Write-Host "Error: $testResult" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please verify:" -ForegroundColor Yellow
        Write-Host "1. PostgreSQL is running on ${DbHost}:${DbPort}"
        Write-Host "2. User '$DbUser' has correct password"
        Write-Host "3. PostgreSQL accepts connections from localhost"
        exit 1
    }
    
    Write-Host "Connection successful!" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "Step 2: Checking if auth_service database exists..." -ForegroundColor Yellow
    
    $dbExists = psql -h $DbHost -p $DbPort -U $DbUser -d postgres -t -c "SELECT 1 FROM pg_database WHERE datname='auth_service';" 2>&1
    
    if ($dbExists -match "1") {
        Write-Host "Database 'auth_service' already exists" -ForegroundColor Yellow
        $response = Read-Host "Do you want to continue? This will add/update the auth_users table. (Y/N)"
        if ($response -ne "Y" -and $response -ne "y") {
            Write-Host "Setup cancelled by user" -ForegroundColor Yellow
            exit 0
        }
    } else {
        Write-Host "Database 'auth_service' does not exist, will create it" -ForegroundColor Green
    }
    Write-Host ""
    
    Write-Host "Step 3: Creating/updating database and tables..." -ForegroundColor Yellow
    Write-Host "Executing SQL script: $sqlFile" -ForegroundColor Gray
    Write-Host ""
    
    # Execute the SQL script
    # First ensure database exists (ignore error if already exists)
    $null = psql -h $DbHost -p $DbPort -U $DbUser -d postgres -c "CREATE DATABASE auth_service;" 2>&1
    
    # Then run the full setup script on auth_service database
    Get-Content $sqlFile | psql -h $DbHost -p $DbPort -U $DbUser -d auth_service 2>&1 | Where-Object { $_ -notmatch "already exists" -and $_ -notmatch "NOTICE" }
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to execute SQL script!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host ""
    Write-Host "Step 4: Verifying table creation..." -ForegroundColor Yellow
    
    $tableExists = psql -h $DbHost -p $DbPort -U $DbUser -d auth_service -t -c "SELECT 1 FROM information_schema.tables WHERE table_name='auth_users';" 2>&1
    
    if ($tableExists -match "1") {
        Write-Host "Table 'auth_users' created successfully!" -ForegroundColor Green
    } else {
        Write-Host "Failed to create 'auth_users' table!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host ""
    Write-Host "Step 5: Checking table structure..." -ForegroundColor Yellow
    psql -h $DbHost -p $DbPort -U $DbUser -d auth_service -c "\d auth_users"
    
    Write-Host ""
    Write-Host "Step 6: Checking current data..." -ForegroundColor Yellow
    psql -h $DbHost -p $DbPort -U $DbUser -d auth_service -c "SELECT COUNT(*) as total_users FROM auth_users;"
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Setup Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Database Information:" -ForegroundColor Yellow
    Write-Host "  Host: $DbHost"
    Write-Host "  Port: $DbPort"
    Write-Host "  Database: auth_service"
    Write-Host "  Table: auth_users"
    Write-Host ""
    Write-Host "Connection String:" -ForegroundColor Yellow
    Write-Host "  postgresql://${DbUser}:${DbPassword}@${DbHost}:${DbPort}/auth_service" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor Yellow
    Write-Host "1. Update your .env.local or environment variables:"
    Write-Host "   IDENTITY_DATABASE_URL=postgresql://${DbUser}:${DbPassword}@${DbHost}:${DbPort}/auth_service"
    Write-Host ""
    Write-Host "2. Restart your admin-service application"
    Write-Host ""
    Write-Host "3. Create a test user via API to verify sync is working"
    Write-Host ""
    Write-Host "4. Use check_databases.ps1 script to verify sync"
    Write-Host ""
    
} catch {
    Write-Host "Error occurred during setup!" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
} finally {
    # Clear password from environment
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}
