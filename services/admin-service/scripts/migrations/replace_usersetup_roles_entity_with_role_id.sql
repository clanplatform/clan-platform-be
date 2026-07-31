-- Replace the usersetup_roles_entity table with a single role_id column on
-- usersetup_basic.
--
-- A user's role assignment was previously a separate table holding an ARRAY of
-- user_role.id (assigned_roles), plus a redundant assigned_entities array that
-- duplicated usersetup_basic.default_entity. This collapses that to a single
-- role_id column directly on usersetup_basic (the source of truth read
-- directly by the auth-service and by menu/permission resolution).
--
-- Steps (idempotent, safe to re-run):
--   1. Add usersetup_basic.role_id (FK -> user_role.id).
--   2. Backfill role_id from any existing usersetup_roles_entity.assigned_roles
--      (first element) — a no-op if that table is empty/absent.
--   3. Drop usersetup_preference.usersetup_roles_entity_id (FK + column) —
--      preferences no longer need a roles_entity row to exist.
--   4. Drop the usersetup_roles_entity table.
--
-- Run against every usersetup_basic-bearing database (master + each tenant DB):
--   psql -U postgres -d clan_platform          -f replace_usersetup_roles_entity_with_role_id.sql
--   psql -U postgres -d clan_platform_<tenant> -f replace_usersetup_roles_entity_with_role_id.sql

-- 1. Add role_id
ALTER TABLE IF EXISTS usersetup_basic
    ADD COLUMN IF NOT EXISTS role_id UUID;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'usersetup_basic_role_id_fkey'
    ) THEN
        ALTER TABLE usersetup_basic
            ADD CONSTRAINT usersetup_basic_role_id_fkey
            FOREIGN KEY (role_id) REFERENCES user_role(id);
    END IF;
END $$;

-- 2. Backfill from usersetup_roles_entity (if it still exists and has rows)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'usersetup_roles_entity'
    ) THEN
        UPDATE usersetup_basic ub
        SET role_id = re.assigned_roles[1]
        FROM usersetup_roles_entity re
        WHERE re.usersetup_basic_id = ub.id
          AND ub.role_id IS NULL
          AND re.assigned_roles IS NOT NULL
          AND array_length(re.assigned_roles, 1) > 0;
    END IF;
END $$;

-- 3. Drop the preference table's FK to usersetup_roles_entity
ALTER TABLE IF EXISTS usersetup_preference DROP COLUMN IF EXISTS usersetup_roles_entity_id;

-- 4. Drop the now-unused table
DROP TABLE IF EXISTS usersetup_roles_entity CASCADE;
