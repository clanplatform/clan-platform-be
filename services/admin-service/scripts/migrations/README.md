# MongoDB Migrations

This directory contains MongoDB migration scripts for the admin service.

## Available Migrations

### 1. Update Profile Menu Items

**Purpose:** Adds default menu items with route fields to the profileSection in the master navigation document.

**Files:**
- `update_profile_menu_items.py` - Async version (recommended)
- `update_profile_menu_items_sync.py` - Synchronous version (fallback)

**What it does:**
- Connects to MongoDB
- Finds the master navigation document (ID: `69074724f217ab8fcb2e3b24`)
- Adds/updates profileSection with default menu items including:
  - My Profile (`/profile`)
  - Account Settings (`/settings/account`)
  - Preferences (`/settings/preferences`)
  - Notifications (`/notifications`)
  - Help & Support (`/help`)
  - Logout (`/logout`)

**Menu Item Structure:**
```json
{
  "key": "my-profile",
  "route": "/profile",
  "label": "My Profile",
  "icon": "ri-user-line",
  "children": [],
  "type": null,
  "badge": null
}
```

## How to Run Migrations

### Prerequisites

1. **Set up environment variables** in your `.env` file or export them:
   ```bash
   DATABASE_URL=postgresql://postgres:root@localhost:5432/clan_platform
   MONGODB_URL=mongodb://admin:admin_pass@localhost:27017
   MONGODB_DB_NAME=clan_platform
   REDIS_URL=redis://localhost:6379/0
   SECRET_KEY=your-secret-key
   ENVIRONMENT=local
   ```

2. **Ensure MongoDB is running:**
   ```bash
   # Check if MongoDB is running
   mongosh --eval "db.adminCommand('ping')"
   ```

3. **Install dependencies:**
   ```bash
   pip install pymongo motor
   ```

### Running the Migration

#### Option 1: Async Version (Recommended)

```bash
# From the project root
cd services/admin-service
python scripts/migrations/update_profile_menu_items.py
```

#### Option 2: Synchronous Version

```bash
# From the project root
cd services/admin-service
python scripts/migrations/update_profile_menu_items_sync.py
```

### What to Expect

1. The script will connect to MongoDB
2. Display current profileSection status
3. Ask for confirmation before making changes
4. Update the document
5. Verify the changes were applied
6. Show a summary of added menu items

**Example Output:**
```
======================================================================
MongoDB Migration: Add Profile Menu Items with Routes
======================================================================

📡 Connecting to MongoDB...
✅ Connected to MongoDB successfully

🔍 Looking for master navigation document: 69074724f217ab8fcb2e3b24
✅ Found master navigation document

📊 Current profileSection status:
   - Has profileSection: True
   - Current menuItems count: 0

======================================================================

⚠️  Do you want to update profileSection with default menu items? (yes/no): yes

🔄 Updating MongoDB document...
✅ Successfully updated profileSection with menu items!

📋 Added 6 menu items:
   1. My Profile
      - Key: my-profile
      - Route: /profile
      - Icon: ri-user-line
   ...

🔍 Verifying update...
✅ Verification complete:
   - Updated menuItems count: 6

======================================================================
✅ Migration completed successfully!
======================================================================

✅ All done! The profileSection now has default menu items with routes.
   You can verify this by calling the /api/v1/menus endpoint.
```

## Customizing Menu Items

To customize the default menu items, edit the `DEFAULT_PROFILE_MENU_ITEMS` list in the migration script:

```python
DEFAULT_PROFILE_MENU_ITEMS = [
    {
        "key": "custom-item",
        "route": "/custom/route",
        "label": "Custom Item",
        "icon": "ri-custom-icon",
        "children": [],
        "type": None,
        "badge": None
    },
    # ... more items
]
```

## Verifying the Migration

After running the migration, you can verify it worked by:

1. **Using MongoDB shell:**
   ```bash
   mongosh
   use clan_platform
   db.menu_details.findOne({_id: ObjectId("69074724f217ab8fcb2e3b24")}, {profileSection: 1})
   ```

2. **Using the API:**
   ```bash
   curl -X GET "http://localhost:8000/api/v1/menus/" \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

   Check the `profileSection.menuItems` array in the response.

3. **Check the frontend:**
   - Log in to the application
   - Open the profile dropdown/menu
   - You should see the new menu items with working routes

## Troubleshooting

### Connection Error

**Error:** `ServerSelectionTimeoutError: connection refused`

**Solution:**
- Make sure MongoDB is running
- Check the MongoDB URL in your environment variables
- Verify MongoDB is listening on the correct port

### Document Not Found

**Error:** `Master navigation document not found`

**Solution:**
- Verify the document ID exists in your database
- Update the `master_doc_id` variable in the script if needed
- Create the master navigation document first if it doesn't exist

### Permission Denied

**Error:** `OperationFailure: not authorized`

**Solution:**
- Check MongoDB user credentials
- Ensure the user has write permissions on the database
- Update the MongoDB connection string with correct credentials

## Rollback

To rollback the changes:

1. **Remove menu items:**
   ```javascript
   db.menu_details.updateOne(
     {_id: ObjectId("69074724f217ab8fcb2e3b24")},
     {$set: {"profileSection.menuItems": []}}
   )
   ```

2. **Restore from backup:**
   If you have a backup, restore the original document.

## Creating New Migrations

To create a new migration:

1. Copy one of the existing migration scripts
2. Rename it with a descriptive name
3. Update the migration logic
4. Add documentation to this README
5. Test thoroughly before running in production

## Best Practices

- ✅ Always backup MongoDB before running migrations
- ✅ Test migrations in development first
- ✅ Read the script output carefully
- ✅ Verify changes after migration
- ✅ Keep a log of migrations run
- ❌ Never run migrations directly in production without testing
- ❌ Don't skip the confirmation prompt
