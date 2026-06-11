# Database Verification Script
# This script shows data in both databases to help identify the sync issue

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Database Verification Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Step 1: Checking Docker containers..." -ForegroundColor Yellow
Write-Host ""
docker ps --filter "name=postgres" --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}"
Write-Host ""

Write-Host "Step 2: Checking admin-service database (localhost:5432/admin_service)..." -ForegroundColor Yellow
Write-Host "Container: admin-service-postgres" -ForegroundColor Gray
Write-Host ""
docker exec admin-service-postgres psql -U postgres -d admin_service -c "SELECT COUNT(*) as user_count FROM usersetup_basic;"
Write-Host ""
docker exec admin-service-postgres psql -U postgres -d admin_service -c "SELECT id, username, email, employee_id, created_at FROM usersetup_basic ORDER BY created_at DESC LIMIT 5;"
Write-Host ""

Write-Host "Step 3: Checking identity database (localhost:5433/auth_service)..." -ForegroundColor Yellow
Write-Host "Container: clan-identity-postgres" -ForegroundColor Gray
Write-Host ""
docker exec clan-identity-postgres psql -U postgres -d auth_service -c "SELECT COUNT(*) as user_count FROM auth_users;"
Write-Host ""
docker exec clan-identity-postgres psql -U postgres -d auth_service -c "SELECT id, username, email, employee_id, created_at FROM auth_users ORDER BY created_at DESC LIMIT 5;"
Write-Host ""

Write-Host "Step 4: Checking if latest user from admin DB exists in identity DB..." -ForegroundColor Yellow
$latestUser = docker exec admin-service-postgres psql -U postgres -d admin_service -t -c "SELECT username FROM usersetup_basic ORDER BY created_at DESC LIMIT 1;" | ForEach-Object { $_.Trim() }
if ($latestUser) {
    Write-Host "Latest user in admin DB: $latestUser" -ForegroundColor Gray
    Write-Host "Searching for this user in identity DB..." -ForegroundColor Gray
    Write-Host ""
    docker exec clan-identity-postgres psql -U postgres -d auth_service -c "SELECT id, username, email FROM auth_users WHERE username='$latestUser';"
} else {
    Write-Host "No users found in admin database" -ForegroundColor Red
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Database Connection Information" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Admin Database (usersetup_basic):" -ForegroundColor Yellow
Write-Host "  Host: localhost" -ForegroundColor Gray
Write-Host "  Port: 5432" -ForegroundColor Gray
Write-Host "  Database: admin_service" -ForegroundColor Gray
Write-Host "  Container: admin-service-postgres" -ForegroundColor Gray
Write-Host ""
Write-Host "Identity Database (auth_users):" -ForegroundColor Yellow
Write-Host "  Host: localhost" -ForegroundColor Gray
Write-Host "  Port: 5433 (IMPORTANT!)" -ForegroundColor Green
Write-Host "  Database: auth_service" -ForegroundColor Gray
Write-Host "  Container: clan-identity-postgres" -ForegroundColor Gray
Write-Host ""
Write-Host "Make sure you're connected to PORT 5433, not 5432!" -ForegroundColor Cyan
Write-Host ""
