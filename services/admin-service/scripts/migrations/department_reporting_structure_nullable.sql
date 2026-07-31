-- Makes departments.reporting_structure ("Reports to") optional (was NOT NULL).
--
-- departments lives in every tenant DB (and the master DB), so run against:
--   1. The master DB (clan_platform)
--   2. EVERY existing tenant DB (clan_platform_<code>...)
--
-- Idempotent: DROP NOT NULL on an already-nullable column is a no-op, and
-- ALTER TABLE IF EXISTS skips databases without the table.

ALTER TABLE IF EXISTS departments ALTER COLUMN reporting_structure DROP NOT NULL;
