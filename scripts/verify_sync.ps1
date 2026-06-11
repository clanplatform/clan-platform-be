# ============================================================
# Identity Sync Verification Script (PowerShell)
# Verifies that user data is syncing between databases
# ============================================================

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Identity Sync Verification" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Test parameters
$username = "testuser_" + (Get-Date -Format "yyyyMMddHHmmss")
$email = "test_" + (Get-Date -Format "yyyyMMddHHmmss") + "@example.com"
$employeeId = "EMP" + (Get-Date -Format "yyyyMMddHHmmss")

Write-Host "Step 1: Creating test user via API..." -ForegroundColor Yellow
Write-Host "Username: $username" -ForegroundColor Gray
Write-Host "Email: $email" -ForegroundColor Gray
Write-Host "Employee ID: $employeeId" -ForegroundColor Gray
Write-Host ""

$body = @{
    basic = @{
        firstname = "Test"
        lastname = "User"
        employee_id = $employeeId
        username = $username
        email = $email
        password = "Test@123"
        phone_number = "+1234567890"
        status = "active"
    }
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/access-control/user-setup/with-details" `
        -Method Post `
        -ContentType "application/json" `
        -Body $body
    
    Write-Host "✓ User created successfully!" -ForegroundColor Green
    Write-Host "User ID: $($response.basic.id)" -ForegroundColor Gray
    Write-Host ""
} catch {
    Write-Host "✗ Failed to create user via API" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

Start-Sleep -Seconds 2

Write-Host "Step 2: Checking admin-service database (port 5432)..." -ForegroundColor Yellow
$adminDbResult = docker exec admin-service-postgres psql -U postgres -d admin_service `
    -c "SELECT id, username, email FROM usersetup_basic WHERE username='$username';" 2>&1

if ($adminDbResult -match $username) {
    Write-Host "✓ User found in admin-service database!" -ForegroundColor Green
    Write-Host $adminDbResult
} else {
    Write-Host "✗ User NOT found in admin-service database" -ForegroundColor Red
    Write-Host $adminDbResult
}
Write-Host ""

Write-Host "Step 3: Checking identity database (port 5433)..." -ForegroundColor Yellow
$identityDbResult = docker exec clan-identity-postgres psql -U postgres -d auth_service `
    -c "SELECT id, username, email, user_setup_id FROM auth_users WHERE username='$username';" 2>&1

if ($identityDbResult -match $username) {
    Write-Host "✓ User found in identity database! SYNC SUCCESSFUL!" -ForegroundColor Green
    Write-Host $identityDbResult
} else {
    Write-Host "✗ User NOT found in identity database - SYNC FAILED" -ForegroundColor Red
    Write-Host $identityDbResult
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "1. Check admin-service logs: docker logs admin-service | Select-String IDENTITY_DB"
    Write-Host "2. Verify IDENTITY_DATABASE_URL is set correctly in .env.local"
    Write-Host "3. Ensure identity-postgres container is running: docker ps | Select-String identity"
}
Write-Host ""

Write-Host "Step 4: Checking application logs..." -ForegroundColor Yellow
$logs = docker logs admin-service --tail 50 2>&1 | Select-String "IDENTITY_DB"
if ($logs) {
    Write-Host "Recent identity DB logs:" -ForegroundColor Gray
    $logs | ForEach-Object { Write-Host $_ -ForegroundColor Gray }
} else {
    Write-Host "No identity DB logs found in recent output" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Verification Complete" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
