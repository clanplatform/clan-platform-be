-- ================================================
-- Migration: 004_seed_initial_data.sql
-- Description: Seed initial data for testing and development
-- Author: Admin Service Team
-- Date: 2024
-- ================================================

-- Insert sample domains
INSERT INTO domains (id, code, name, description, domain_metadata, is_active)
VALUES 
    ('11111111-1111-1111-1111-111111111111', 'PLATFORM', 'Platform Services', 'Core platform infrastructure services', '{"category": "infrastructure", "priority": "critical"}'::jsonb, TRUE),
    ('22222222-2222-2222-2222-222222222222', 'COMMERCE', 'Commerce Services', 'E-commerce and payment services', '{"category": "business", "priority": "high"}'::jsonb, TRUE),
    ('33333333-3333-3333-3333-333333333333', 'ANALYTICS', 'Analytics Services', 'Data analytics and reporting services', '{"category": "analytics", "priority": "medium"}'::jsonb, TRUE)
ON CONFLICT (code) DO NOTHING;

-- Insert sample applications
INSERT INTO applications (id, domain_id, name, description, version, status, key, label, route, level, icon, order_index)
VALUES
    -- Platform applications
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111', 'Admin Console', 'Platform administration console', '1.0.0', 'active', 'admin-console', 'Admin', '/admin', 1, 'settings', 1),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '11111111-1111-1111-1111-111111111111', 'User Management', 'User and access management', '1.0.0', 'active', 'user-mgmt', 'Users', '/users', 1, 'users', 2),
    
    -- Commerce applications
    ('cccccccc-cccc-cccc-cccc-cccccccccccc', '22222222-2222-2222-2222-222222222222', 'Product Catalog', 'Product and inventory management', '1.0.0', 'active', 'products', 'Products', '/products', 1, 'shopping-cart', 1),
    ('dddddddd-dddd-dddd-dddd-dddddddddddd', '22222222-2222-2222-2222-222222222222', 'Order Management', 'Order processing and fulfillment', '1.0.0', 'active', 'orders', 'Orders', '/orders', 1, 'package', 2),
    
    -- Analytics applications
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', '33333333-3333-3333-3333-333333333333', 'Reports', 'Business intelligence and reports', '1.0.0', 'active', 'reports', 'Reports', '/reports', 1, 'bar-chart', 1)
ON CONFLICT (id) DO NOTHING;

-- Insert sample menus
INSERT INTO menus (id, application_id, parent_menu_id, name, key, label, route, level, icon, order_index)
VALUES
    -- Admin Console menus
    ('11110000-0000-0000-0000-000000000001', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', NULL, 'Dashboard', 'dashboard', 'Dashboard', '/admin/dashboard', 1, 'home', 1),
    ('11110000-0000-0000-0000-000000000002', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', NULL, 'Settings', 'settings', 'Settings', '/admin/settings', 1, 'cog', 2),
    ('11110000-0000-0000-0000-000000000003', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11110000-0000-0000-0000-000000000002', 'General', 'settings-general', 'General', '/admin/settings/general', 2, NULL, 1),
    ('11110000-0000-0000-0000-000000000004', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11110000-0000-0000-0000-000000000002', 'Security', 'settings-security', 'Security', '/admin/settings/security', 2, NULL, 2),
    
    -- User Management menus
    ('22220000-0000-0000-0000-000000000001', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', NULL, 'Users', 'users-list', 'All Users', '/users/list', 1, 'users', 1),
    ('22220000-0000-0000-0000-000000000002', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', NULL, 'Roles', 'roles', 'Roles', '/users/roles', 1, 'shield', 2),
    
    -- Product Catalog menus
    ('33330000-0000-0000-0000-000000000001', 'cccccccc-cccc-cccc-cccc-cccccccccccc', NULL, 'Products', 'products-list', 'All Products', '/products/list', 1, 'box', 1),
    ('33330000-0000-0000-0000-000000000002', 'cccccccc-cccc-cccc-cccc-cccccccccccc', NULL, 'Categories', 'categories', 'Categories', '/products/categories', 1, 'folder', 2)
ON CONFLICT (id) DO NOTHING;

-- Display summary
DO $$
DECLARE
    domain_count INT;
    app_count INT;
    menu_count INT;
BEGIN
    SELECT COUNT(*) INTO domain_count FROM domains WHERE is_deleted = FALSE;
    SELECT COUNT(*) INTO app_count FROM applications WHERE is_deleted = FALSE;
    SELECT COUNT(*) INTO menu_count FROM menus WHERE deleted_at IS NULL;
    
    RAISE NOTICE 'Seed data summary:';
    RAISE NOTICE '  Domains: %', domain_count;
    RAISE NOTICE '  Applications: %', app_count;
    RAISE NOTICE '  Menus: %', menu_count;
END $$;
