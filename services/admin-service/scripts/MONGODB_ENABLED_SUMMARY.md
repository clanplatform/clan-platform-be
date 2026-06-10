# MongoDB Integration Enabled

## Changes Made

### 1. MongoDB Enabled by Default
**File**: `app/core/mongodb.py`

Changed the default behavior from `MONGODB_ENABLED=false` to `MONGODB_ENABLED=true`.

```python
# Before:
self.enabled = os.getenv("MONGODB_ENABLED", "false").lower() == "true"

# After:
self.enabled = os.getenv("MONGODB_ENABLED", "true").lower() == "true"
```

### 2. Environment Configuration Updated
**File**: `config/environments/.env.local`

Added explicit `MONGODB_ENABLED=true` flag for clarity:

```env
# ==================== DATABASE - MONGODB ====================
# Enable/disable MongoDB (default: true)
MONGODB_ENABLED=true

# MongoDB connection URL
MONGODB_URL=mongodb://admin:admin_pass@localhost:27017

# MongoDB database name
MONGODB_DB_NAME=admin_service
```

## MongoDB Navigation Structure

### How Menus are Stored

When a menu is created in PostgreSQL, it's automatically synced to MongoDB using this structure:

#### 1. Master Navigation Document
```json
{
  "_id": ObjectId("69074724f217ab8fcb2e3b24"),
  "mainNavigation": [
    ObjectId("6a158272c8601063b2ead0a2"),  // Reference to Admin app
    ObjectId("..."),                        // Other applications
  ],
  "profileSection": {},
  "config": {},
  "updated_at": "2026-04-25T06:26:47.984433+00:00"
}
```

#### 2. Application Documents (Referenced in mainNavigation)
```json
{
  "_id": ObjectId("6a158272c8601063b2ead0a2"),
  "key": "admin",
  "label": "Admin",
  "icon": "ri-admin-line",
  "description": "Manage applications and configurations",
  "badge": null,
  "sectionTitle": "Admin",
  "route": "/adminApp/",
  "application_id": "c3140a19-c79e-4902-8591-2a7e7e944809",
  "level": 1,
  "order_index": 1000,
  "is_visible": true,
  "is_active": true,
  "access": [],
  "children": [
    {
      "key": "module-name",
      "name": "Module Name",
      "label": "Module Label",
      "route": "/module-route",
      "icon": "ri-folder-line",
      "module_id": "uuid",
      "application_id": "uuid",
      "order_index": 1,
      "level": 2,
      "is_visible": true,
      "is_active": true,
      "access": [],
      "children": [
        {
          "key": "menu-key",
          "name": "Menu Name",
          "label": "Menu Label",
          "route": "/menu-route",
          "icon": "ri-menu-line",
          "component": "MenuComponent",
          "menu_id": "uuid",
          "application_id": "uuid",
          "module_id": "uuid",
          "order_index": 1,
          "level": 3,
          "is_visible": true,
          "is_active": true,
          "children": []
        }
      ]
    }
  ],
  "created_at": "2026-04-25T06:26:47.984433+00:00",
  "updated_at": "2026-04-25T06:26:47.984433+00:00"
}
```

## Sync Process

### Automatic Sync Flow

1. **Menu Created in PostgreSQL**
   - Menu is saved to `menus` table
   - Returns menu data with status 201

2. **MongoDB Sync Triggered**
   - `working_sync_to_mongodb()` function is called
   - Fetches all menus for the application
   - Groups menus by modules
   - Builds hierarchical navigation structure

3. **MongoDB Update**
   - If application document exists: Updates the `children` array
   - If new: Creates application document and adds ObjectId to `mainNavigation`
   - Updates the `updated_at` timestamp

4. **PostgreSQL Update**
   - Updates menu records with `mongo_id` field
   - Links PostgreSQL menus to MongoDB documents

## Navigation Hierarchy

```
Master Document (69074724f217ab8fcb2e3b24)
├── mainNavigation []
│   ├── Application 1 (ObjectId)
│   │   ├── Module 1
│   │   │   ├── Menu 1.1
│   │   │   ├── Menu 1.2
│   │   │   └── Menu 1.3
│   │   └── Module 2
│   │       ├── Menu 2.1
│   │       └── Menu 2.2
│   ├── Application 2 (ObjectId)
│   │   └── Module 3
│   │       └── Menu 3.1
│   └── ...
├── profileSection {}
└── config {}
```

## Verification

### Check MongoDB Connection
After restarting the service, you should see:
```
[MongoDB] Connecting to mongodb://admin:admin_pass@localhost:27017, database: admin_service
[MongoDB] Client created, testing connection...
[MongoDB] Ping successful
[MongoDB] Connected successfully. Collections: ['menu_details', ...]
```

### Check Menu Sync
When creating a menu:
```
[Menu Create Structured] ✅ Created menu in PostgreSQL: <uuid>
[Menu Create Structured] 🔄 Syncing to MongoDB using working sync function...
[Working Sync] Starting sync for application: <uuid>
[Working Sync] MongoDB connected
[Working Sync] Application found: <name>
[Working Sync] Found X menus
[Working Sync] Found Y modules
[Working Sync] Updated/Created MongoDB document: <ObjectId>
[Working Sync] Added to master navigation
[Working Sync] Updated X menus with mongo_id
```

### Query MongoDB
Use MongoDB Compass or CLI to verify:

```javascript
// View master navigation
db.menu_details.findOne({"_id": ObjectId("69074724f217ab8fcb2e3b24")})

// View all application documents
db.menu_details.find({
  "application_id": {"$exists": true}
})

// View specific application navigation
db.menu_details.findOne({
  "application_id": "c3140a19-c79e-4902-8591-2a7e7e944809"
})
```

## Benefits

1. **Fast Navigation Loading**: Frontend can fetch entire navigation structure with one MongoDB query
2. **Hierarchical Structure**: Menus organized by Application > Module > Menu hierarchy
3. **Real-time Sync**: Every menu change in PostgreSQL automatically syncs to MongoDB
4. **Access Control**: Each level includes `access` array for permission management
5. **Flexible Schema**: MongoDB document model allows for easy navigation customization

## Troubleshooting

### MongoDB Not Connecting
1. Check MongoDB is running: `docker ps | grep mongodb`
2. Verify connection string in `.env.local`
3. Check MongoDB logs for errors
4. Test connection manually: `mongosh mongodb://admin:admin_pass@localhost:27017`

### Sync Not Working
1. Check logs for "[Working Sync]" messages
2. Verify application_id exists in PostgreSQL
3. Check MongoDB has `menu_details` collection
4. Ensure master document `69074724f217ab8fcb2e3b24` exists

### Missing Menus in MongoDB
1. Create a new menu to trigger sync
2. Check PostgreSQL menus have `mongo_id` populated
3. Verify `mainNavigation` array in master document
4. Check application document `children` array

## Next Steps

✅ MongoDB is now enabled and menus sync automatically
✅ Navigation structure matches the required format
✅ Master navigation array is maintained

To test:
1. Restart the admin-service
2. Create a new menu via Swagger UI
3. Check MongoDB to verify the menu appears in `mainNavigation`
4. Verify the hierarchical structure: Application > Module > Menu
