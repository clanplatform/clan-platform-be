-- Check PostgreSQL data before syncing to MongoDB
-- Run this in your PostgreSQL client (pgAdmin, DBeaver, etc.)

-- 1. Check active applications
SELECT 
    id,
    name,
    is_active,
    is_deleted,
    created_at
FROM applications 
WHERE is_active = true AND is_deleted = false
ORDER BY name;

-- 2. Check modules
SELECT 
    m.id,
    m.name,
    m.label,
    m.application_id,
    a.name as application_name,
    m.order_index,
    m.is_active,
    m.is_deleted
FROM modules m
LEFT JOIN applications a ON m.application_id = a.id
WHERE m.is_deleted = false
ORDER BY a.name, m.order_index;

-- 3. Check menus with their relationships
SELECT 
    me.id,
    me.name,
    me.label,
    me.level,
    me.order_index,
    me.application_id,
    a.name as application_name,
    me.module_id,
    mo.name as module_name,
    me.parent_menu_id,
    me.is_active,
    me.deleted_at
FROM menus me
LEFT JOIN applications a ON me.application_id = a.id
LEFT JOIN modules mo ON me.module_id = mo.id
WHERE me.deleted_at IS NULL
ORDER BY a.name, me.level, me.order_index;

-- 4. Count summary
SELECT 
    'Applications' as entity_type,
    COUNT(*) as count
FROM applications 
WHERE is_active = true AND is_deleted = false

UNION ALL

SELECT 
    'Modules' as entity_type,
    COUNT(*) as count
FROM modules 
WHERE is_deleted = false

UNION ALL

SELECT 
    'Menus' as entity_type,
    COUNT(*) as count
FROM menus 
WHERE deleted_at IS NULL;
