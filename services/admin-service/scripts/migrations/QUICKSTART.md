# Quick Start: Update Profile Menu Items

## 🚀 Run the Migration in 3 Steps

### Step 1: Navigate to the Project
```bash
cd c:\Users\arung\OneDrive\Documents\clan_archi\platform-domain-be\clan-platform-domain-be\services\admin-service
```

### Step 2: Run the Migration Script
```bash
# Recommended: Use the synchronous version
python scripts\migrations\update_profile_menu_items_sync.py
```

Or if you prefer async:
```bash
python scripts\migrations\update_profile_menu_items.py
```

### Step 3: Confirm When Prompted
When asked:
```
⚠️  Do you want to update profileSection with default menu items? (yes/no):
```
Type: **yes** and press Enter

## ✅ Success Output

You should see:
```
✅ Successfully updated profileSection with menu items!

📋 Added 6 menu items:
   1. My Profile
      - Key: my-profile
      - Route: /profile
      - Icon: ri-user-line
   2. Account Settings
      - Key: account-settings
      - Route: /settings/account
      - Icon: ri-settings-3-line
   3. Preferences
      - Key: preferences
      - Route: /settings/preferences
      - Icon: ri-palette-line
   4. Notifications
      - Key: notifications
      - Route: /notifications
      - Icon: ri-notification-line
   5. Help & Support
      - Key: help-support
      - Route: /help
      - Icon: ri-question-line
   6. Logout
      - Key: logout
      - Route: /logout
      - Icon: ri-logout-box-line
```

## 🔍 Verify the Changes

### Option 1: Using MongoDB Shell
```bash
mongosh
use admin_service
db.menu_details.findOne({_id: ObjectId("69074724f217ab8fcb2e3b24")}).profileSection.menuItems
```

### Option 2: Using API
Test the endpoint (requires authentication):
```bash
curl -X GET "http://localhost:8000/api/v1/menus/" -H "Authorization: Bearer YOUR_TOKEN"
```

Look for the `profileSection.menuItems` array in the response.

### Option 3: In the Frontend
1. Log in to your application
2. Click on your profile/avatar
3. You should see the new menu items with working routes

## ❌ Troubleshooting

**MongoDB not running?**
```bash
# Check MongoDB status
mongosh --eval "db.adminCommand('ping')"
```

**Connection error?**
- Make sure your `.env` file has correct MongoDB settings:
  ```
  MONGODB_URL=mongodb://admin:admin_pass@localhost:27017
  MONGODB_DB_NAME=admin_service
  ```

**Document not found?**
- The script looks for document ID: `69074724f217ab8fcb2e3b24`
- Verify this document exists in your `menu_details` collection

## 📝 What Gets Added

The migration adds these menu items to `profileSection.menuItems`:

| Label | Key | Route | Icon |
|-------|-----|-------|------|
| My Profile | my-profile | /profile | ri-user-line |
| Account Settings | account-settings | /settings/account | ri-settings-3-line |
| Preferences | preferences | /settings/preferences | ri-palette-line |
| Notifications | notifications | /notifications | ri-notification-line |
| Help & Support | help-support | /help | ri-question-line |
| Logout | logout | /logout | ri-logout-box-line |

## 🔄 Need to Run Again?

The script can be run multiple times safely. It will:
- ✅ Update existing menuItems
- ✅ Show current state before making changes
- ✅ Ask for confirmation
- ✅ Verify changes after update

## 📞 Need Help?

Check the full documentation in `README.md` for:
- Detailed explanation of each step
- Customization options
- Advanced troubleshooting
- Rollback instructions
