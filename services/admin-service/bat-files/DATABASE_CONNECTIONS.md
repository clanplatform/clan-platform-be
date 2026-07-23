# Database Connection Guide

## Overview
This project uses TWO separate PostgreSQL instances running in Docker containers.

## 1. Admin Service Database (Platform Domain)

**Purpose**: Stores user setup, roles, entities, and preferences

**Connection Details**:
- Host: `localhost`
- Port: `5432`
- Database: `clan_platform`
- Username: `postgres`
- Password: `root`

**Key Tables**:
- `user_setup` (parent table)
- `usersetup_basic` (user details)
- `usersetup_roles_entity` (role assignments)
- `usersetup_preference` (user preferences)

**Docker Container**: `admin-service-postgres`

---

## 2. Identity Service Database (Identity Domain)

**Purpose**: Stores authentication and authorization data

**Connection Details**:
- Host: `localhost`
- Port: `5433` ⚠️ **Different Port!**
- Database: `auth_service`
- Username: `postgres`
- Password: `root`

**Key Tables**:
- `auth_users` (authentication users - synced from admin service)

**Docker Container**: `clan-identity-postgres`

---

## How User Sync Works

1. User created in `clan_platform.usersetup_basic` (localhost:5432)
2. Admin service calls Identity service HTTP API
3. Identity service creates user in `auth_service.auth_users` (localhost:5433)
4. Both records have the same `id` (UUID)

---

## Connecting from Database Client

### DBeaver / pgAdmin / DataGrip

Create **TWO separate connections**:

**Connection 1: Admin Service**
```
Name: Admin Service
Host: localhost
Port: 5432
Database: clan_platform
User: postgres
Password: root
```

**Connection 2: Identity Service**
```
Name: Identity Service
Host: localhost
Port: 5433
Database: auth_service
User: postgres
Password: root
```

---

## Quick Verification

### Check Admin Service (Port 5432)
```sql
-- Connect to localhost:5432, database: clan_platform
SELECT COUNT(*) FROM usersetup_basic;
SELECT id, username, email FROM usersetup_basic ORDER BY created_at DESC LIMIT 5;
```

### Check Identity Service (Port 5433)
```sql
-- Connect to localhost:5433, database: auth_service
SELECT COUNT(*) FROM auth_users;
SELECT id, username, email FROM auth_users ORDER BY created_at DESC LIMIT 5;
```

---

## Docker Commands

### View all containers
```bash
docker ps
```

### Check Admin DB
```bash
docker exec -it admin-service-postgres psql -U postgres -d clan_platform
```

### Check Identity DB
```bash
docker exec -it clan-identity-postgres psql -U postgres -d auth_service
```

### Verify sync is working
```bash
# Check admin service logs for sync messages
docker logs admin-service 2>&1 | grep "SYNC"
```

---

## Troubleshooting

### auth_users table appears empty in local client
- ✅ Make sure you're connected to **port 5433** (not 5432)
- ✅ Make sure database is **auth_service** (not clan_platform)
- ✅ Refresh the schema/table list in your client

### Users not syncing
- Check `IDENTITY_SERVICE_URL` in `.env.local` is set to `http://localhost:8001`
- Check admin-service logs: `docker logs admin-service | grep SYNC`
- Verify auth-service is running: `docker ps | grep auth-service`

### Cannot connect to port 5433
- Check if clan-identity-postgres container is running: `docker ps`
- Check port mapping: `docker port clan-identity-postgres`
- Ensure no firewall blocking port 5433
