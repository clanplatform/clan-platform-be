@echo off
REM ================================================
REM Database Setup Script for Admin Service (Windows)
REM ================================================
REM This script automates the database setup process
REM Usage: setup_database.bat [options]
REM Options:
REM   --help          Show this help message
REM   --seed          Seed sample data after creating tables
REM   --reset         Drop existing tables and recreate
REM   --sql           Use SQL migrations instead of Python
REM ================================================

setlocal enabledelayedexpansion

REM Default options
set SEED=false
set RESET=false
set USE_SQL=false

REM Parse arguments
:parse_args
if "%~1"=="" goto end_parse_args
if /i "%~1"=="--help" goto show_help
if /i "%~1"=="--seed" set SEED=true
if /i "%~1"=="--reset" set RESET=true
if /i "%~1"=="--sql" set USE_SQL=true
shift
goto parse_args

:show_help
echo Database Setup Script for Admin Service
echo.
echo Usage: %~nx0 [options]
echo.
echo Options:
echo   --help          Show this help message
echo   --seed          Seed sample data after creating tables
echo   --reset         Drop existing tables and recreate
echo   --sql           Use SQL migrations instead of Python
echo.
echo Examples:
echo   %~nx0 --seed                # Create tables and add sample data
echo   %~nx0 --reset --seed        # Reset database and add sample data
echo   %~nx0 --sql                 # Use SQL migration files
exit /b 0

:end_parse_args

REM Print header
echo ========================================
echo Database Setup - Admin Service
echo ========================================
echo.

REM Check if .env file exists
if not exist .env (
    echo [WARNING] .env file not found
    if exist .env.example (
        echo [INFO] Creating .env from .env.example...
        copy .env.example .env >nul
        echo [SUCCESS] .env file created
        echo [WARNING] Please update .env with your database credentials
        echo.
    ) else (
        echo [ERROR] .env.example not found
        exit /b 1
    )
)

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    echo Please install Python 3.11 or higher
    exit /b 1
)
echo [SUCCESS] Python found
echo.

REM Check virtual environment
if not exist venv (
    echo [WARNING] Virtual environment not found
    echo [INFO] Creating virtual environment...
    python -m venv venv
    echo [SUCCESS] Virtual environment created
    echo.
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo [ERROR] Could not find activation script
    exit /b 1
)
echo [SUCCESS] Virtual environment activated
echo.

REM Install dependencies
echo [INFO] Checking dependencies...
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Dependencies not installed
    echo [INFO] Installing dependencies...
    pip install -q -r requirements.txt
    echo [SUCCESS] Dependencies installed
) else (
    echo [SUCCESS] Dependencies already installed
)
echo.

REM Check database connection
echo [INFO] Checking database connection...
python -c "import sys; sys.path.insert(0, '.'); from app.infrastructure.database.session import check_db_connection; sys.exit(0 if check_db_connection() else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Database connection failed
    echo.
    echo Tips:
    echo   1. Check DATABASE_URL in .env file
    echo   2. Ensure PostgreSQL is running
    echo   3. Verify database credentials
    echo.
    echo To start PostgreSQL with Docker:
    echo   docker-compose up -d postgres
    exit /b 1
)
echo [SUCCESS] Database connection successful
echo.

REM Execute database setup
if "%USE_SQL%"=="true" (
    echo [INFO] Using SQL migration files...
    echo.
    python scripts/run_migrations.py
) else (
    if "%RESET%"=="true" (
        echo [WARNING] Reset mode: This will drop all existing tables!
        echo Press Ctrl+C to cancel or any key to continue...
        pause >nul
        echo.
        
        if "%SEED%"=="true" (
            python scripts/init_db.py --drop --seed
        ) else (
            python scripts/init_db.py --drop
        )
    ) else (
        if "%SEED%"=="true" (
            python scripts/init_db.py --seed
        ) else (
            python scripts/init_db.py
        )
    )
)

echo.
echo ========================================
echo [SUCCESS] Database setup completed!
echo ========================================
echo.
echo Next steps:
echo   1. Start the application:
echo      uvicorn app.main:app --reload
echo.
echo   2. Access API documentation:
echo      http://localhost:8000/docs
echo.
echo   3. Test health endpoint:
echo      curl http://localhost:8000/health
echo.
echo Happy coding!

endlocal
