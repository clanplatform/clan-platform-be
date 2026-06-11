#!/bin/bash

# ================================================
# Database Setup Script for Admin Service
# ================================================
# This script automates the database setup process
# Usage: ./setup_database.sh [options]
# Options:
#   --help          Show this help message
#   --seed          Seed sample data after creating tables
#   --reset         Drop existing tables and recreate
#   --sql           Use SQL migrations instead of Python
# ================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
SEED=false
RESET=false
USE_SQL=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help)
            echo "Database Setup Script for Admin Service"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --help          Show this help message"
            echo "  --seed          Seed sample data after creating tables"
            echo "  --reset         Drop existing tables and recreate"
            echo "  --sql           Use SQL migrations instead of Python"
            echo ""
            echo "Examples:"
            echo "  $0 --seed                # Create tables and add sample data"
            echo "  $0 --reset --seed        # Reset database and add sample data"
            echo "  $0 --sql                 # Use SQL migration files"
            exit 0
            ;;
        --seed)
            SEED=true
            shift
            ;;
        --reset)
            RESET=true
            shift
            ;;
        --sql)
            USE_SQL=true
            shift
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Print header
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🗄️  Admin Service Database Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    if [ -f .env.example ]; then
        echo -e "${BLUE}📝 Creating .env from .env.example...${NC}"
        cp .env.example .env
        echo -e "${GREEN}✅ .env file created${NC}"
        echo -e "${YELLOW}⚠️  Please update .env with your database credentials${NC}"
        echo ""
    else
        echo -e "${RED}❌ .env.example not found${NC}"
        exit 1
    fi
fi

# Check if Python is available
if ! command -v python &> /dev/null; then
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python not found${NC}"
        echo "Please install Python 3.11 or higher"
        exit 1
    fi
    PYTHON_CMD=python3
else
    PYTHON_CMD=python
fi

echo -e "${GREEN}✅ Python found: $($PYTHON_CMD --version)${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found${NC}"
    echo -e "${BLUE}📦 Creating virtual environment...${NC}"
    $PYTHON_CMD -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
    echo ""
fi

# Activate virtual environment
echo -e "${BLUE}🔌 Activating virtual environment...${NC}"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
else
    echo -e "${RED}❌ Could not find activation script${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Virtual environment activated${NC}"
echo ""

# Install dependencies
echo -e "${BLUE}📦 Checking dependencies...${NC}"
if ! $PYTHON_CMD -c "import fastapi" &> /dev/null; then
    echo -e "${YELLOW}⚠️  Dependencies not installed${NC}"
    echo -e "${BLUE}📥 Installing dependencies...${NC}"
    pip install -q -r requirements.txt
    echo -e "${GREEN}✅ Dependencies installed${NC}"
else
    echo -e "${GREEN}✅ Dependencies already installed${NC}"
fi
echo ""

# Check database connection
echo -e "${BLUE}🔍 Checking database connection...${NC}"
if ! $PYTHON_CMD -c "
import sys
sys.path.insert(0, '.')
from app.infrastructure.database.session import check_db_connection
if not check_db_connection():
    sys.exit(1)
" &> /dev/null; then
    echo -e "${RED}❌ Database connection failed${NC}"
    echo -e "${YELLOW}💡 Tips:${NC}"
    echo "  1. Check DATABASE_URL in .env file"
    echo "  2. Ensure PostgreSQL is running"
    echo "  3. Verify database credentials"
    echo ""
    echo -e "${BLUE}🐳 To start PostgreSQL with Docker:${NC}"
    echo "  docker-compose up -d postgres"
    exit 1
fi
echo -e "${GREEN}✅ Database connection successful${NC}"
echo ""

# Execute database setup based on options
if [ "$USE_SQL" = true ]; then
    # Use SQL migrations
    echo -e "${BLUE}📄 Using SQL migration files...${NC}"
    echo ""
    $PYTHON_CMD scripts/run_migrations.py
else
    # Use Python scripts
    if [ "$RESET" = true ]; then
        echo -e "${YELLOW}⚠️  Reset mode: This will drop all existing tables!${NC}"
        echo -e "${YELLOW}Press Ctrl+C to cancel or Enter to continue...${NC}"
        read
        echo ""
        
        if [ "$SEED" = true ]; then
            $PYTHON_CMD scripts/init_db.py --drop --seed
        else
            $PYTHON_CMD scripts/init_db.py --drop
        fi
    else
        if [ "$SEED" = true ]; then
            $PYTHON_CMD scripts/init_db.py --seed
        else
            $PYTHON_CMD scripts/init_db.py
        fi
    fi
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}🎉 Database setup completed!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Start the application:"
echo "     uvicorn app.main:app --reload"
echo ""
echo "  2. Access API documentation:"
echo "     http://localhost:8000/docs"
echo ""
echo "  3. Test health endpoint:"
echo "     curl http://localhost:8000/health"
echo ""
echo -e "${GREEN}✨ Happy coding!${NC}"
