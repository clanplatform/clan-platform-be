-- Add usersetup_basic.profile_image_url (profile image URL / file reference).
--
-- Idempotent. Run against every usersetup_basic-bearing database (master +
-- each tenant DB):
--   psql -U postgres -d clan_platform          -f add_usersetup_basic_profile_image_url.sql
--   psql -U postgres -d clan_platform_<tenant> -f add_usersetup_basic_profile_image_url.sql

ALTER TABLE IF EXISTS usersetup_basic
    ADD COLUMN IF NOT EXISTS profile_image_url VARCHAR(500);
