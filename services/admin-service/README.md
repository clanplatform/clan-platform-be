# Admin Service

Platform Admin Service for managing domains and applications with PostgreSQL, MongoDB, and Redis.

## Feature's

- **Domain Management**: Create, read, update, and soft-delete domains
- **Application Management**: Manage applications within domains
- **Caching**: Redis-based caching with automatic invalidation
- **Authentication**: JWT-based authentication
- **MongoDB Integration**: Navigation/menu document storage
- **Soft Delete**: Cascade soft-delete from domains to applications
- **OpenAPI Documentation**: Auto-generated Swagger UI

## Architecture

```
┌─────────────┐
│   FastAPI   │
│  Admin API  │
└──────┬──────┘
       │
   ┌───┴───┬──────────┬─────────┐
   │       │          │         │
┌──▼──┐ ┌──▼───┐  ┌───▼───┐ ┌──▼────┐
│ PG  │ │Redis │  │MongoDB│ │  JWT  │
└─────┘ └──────┘  └───────┘ └───────┘
```

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- MongoDB 7+
- Docker & Docker Compose (for containerized setup)

## Quick Start

### Using Docker Compose (Recommended)

1. **Clone the repository and navigate to the project root**

2. **Start all services**:
   ```bash
   docker-compose up -d
   ```

3. **Access the API**:
   - API: http://localhost:8000
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

### Local Development Setup

1. **Create and activate virtual environment**:
   ```bash
   cd services/admin-service
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Setup environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start required services** (PostgreSQL, Redis, MongoDB):
   ```bash
   # Using Docker for dependencies only
   docker-compose up -d postgres redis mongodb
   ```

5. **Run the application**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Environment Configuration

Copy the appropriate environment file:

- **Local Development**: `config/environments/.env.local`
- **Development**: `config/environments/.env.dev`
- **UAT/Staging**: `config/environments/.env.uat`
- **Production**: `config/environments/.env.prod`

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/admin_db
REDIS_URL=redis://localhost:6379/0
MONGODB_URL=mongodb://localhost:27017

# Security
SECRET_KEY=your-secret-key-min-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Cache
CACHE_DEFAULT_TTL=1800
```

## API Endpoints

### Health Check
- `GET /health` - Service health check

### Domains
- `GET /api/v1/domains` - List domains (with pagination)
- `GET /api/v1/domains/{domain_id}` - Get domain by ID
- `POST /api/v1/domains` - Create domain
- `PUT /api/v1/domains/{domain_id}` - Update domain
- `DELETE /api/v1/domains/{domain_id}` - Soft delete domain (cascades to applications)

### Applications
- `GET /api/v1/applications` - List applications
- `GET /api/v1/applications/{app_id}` - Get application by ID
- `POST /api/v1/applications` - Create application
- `PUT /api/v1/applications/{app_id}` - Update application
- `DELETE /api/v1/applications/{app_id}` - Soft delete application

## Authentication

All endpoints (except `/health`) require authentication using JWT Bearer tokens.

### Example Request

```bash
curl -X GET "http://localhost:8000/api/v1/domains" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Generate Test Token

For local development, you can generate a test token:

```python
from app.core.security import create_access_token
token = create_access_token({"sub": "user123", "username": "testuser"})
print(token)
```

## Database Migrations

Using Alembic for database migrations:

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1
```

## Development

### Project Structure

```
services/admin-service/
├── app/
│   ├── api/                    # API routes
│   │   └── v1/
│   │       └── routes/
│   │           ├── domains/    # Domain endpoints
│   │           └── applications/
│   ├── core/                   # Core functionality
│   │   ├── config.py          # Configuration
│   │   ├── security.py        # Authentication
│   │   ├── logging.py         # Logging setup
│   │   └── middleware.py      # Middleware
│   ├── domain_controls/        # Business logic
│   │   ├── models/            # SQLAlchemy models
│   │   ├── services/          # Business services
│   │   └── repositories/      # Data access
│   ├── infrastructure/         # Infrastructure layer
│   │   ├── database/          # Database config
│   │   ├── cache/             # Redis cache
│   │   └── mongodb/           # MongoDB client
│   ├── schemas/               # Pydantic schemas
│   └── main.py                # Application entry point
├── deploy/
│   └── Dockerfile
├── requirements.txt
└── README.md
```

### Running Tests

```bash
pytest tests/ -v
```

### Code Quality

```bash
# Format code
black app/

# Lint
flake8 app/

# Type checking
mypy app/
```

## Caching Strategy

- **Domain List**: Cached by query parameters (skip, limit, search, is_active)
- **Single Domain**: Cached by domain ID
- **TTL**: Configurable via `CACHE_DEFAULT_TTL` (default: 1800 seconds)
- **Invalidation**:
  - Create: Invalidates list cache
  - Update: Invalidates specific domain and list cache
  - Delete: Invalidates specific domain, list cache, and domain applications

## Soft Delete

When a domain is deleted:
1. Domain is marked as deleted (`is_deleted=true`, `is_active=false`, `deleted_at=timestamp`)
2. All related applications are automatically soft-deleted (cascade)
3. Soft-deleted records are excluded from queries
4. Cache is invalidated for affected resources

## Monitoring & Logging

- **Structured JSON Logging**: All logs are in JSON format
- **Correlation IDs**: Each request gets a unique correlation ID
- **Health Check**: `/health` endpoint for liveness probes
- **Metrics**: Request duration, status codes

## Production Deployment

### Using Docker

```bash
docker build -f deploy/Dockerfile -t admin-service:latest .
docker run -p 8000:8000 --env-file .env admin-service:latest
```

### Using Kubernetes

See `deploy/helm/` for Helm charts.

## Troubleshooting

### Database Connection Failed
- Verify DATABASE_URL is correct
- Ensure PostgreSQL is running
- Check firewall/security groups

### Redis Connection Failed
- Verify REDIS_URL is correct
- Ensure Redis is running
- Check authentication if required

### MongoDB Connection Failed
- Verify MONGODB_URL is correct
- Ensure MongoDB is running
- Check authentication settings

### Import Errors
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt`
- Check Python version (3.11+)

## Contributing

1. Create a feature branch
2. Make your changes
3. Write/update tests
4. Run code quality checks
5. Submit a pull request

## License

Copyright © 2024
