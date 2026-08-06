-- Add usersetup_preference.text_direction ('ltr' | 'rtl').
--
-- Matches the "Language & region" screenshot: Text direction is shown next to
-- Language ("follows the language automatically"), stored so it can be
-- overridden per user rather than always recomputed.
--
-- Idempotent. Run against every usersetup_preference-bearing database
-- (master + each tenant DB):
--   psql -U postgres -d clan_platform          -f add_usersetup_preference_text_direction.sql
--   psql -U postgres -d clan_platform_<tenant> -f add_usersetup_preference_text_direction.sql

ALTER TABLE IF EXISTS usersetup_preference
    ADD COLUMN IF NOT EXISTS text_direction VARCHAR(3) NOT NULL DEFAULT 'ltr';
