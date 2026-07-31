-- Removes the entities.description column (dropped by request).
--
-- entities lives in every tenant DB (and the master DB), so run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: DROP COLUMN IF EXISTS, and ALTER TABLE IF EXISTS skips databases
-- without the table.

ALTER TABLE IF EXISTS entities DROP COLUMN IF EXISTS description;
