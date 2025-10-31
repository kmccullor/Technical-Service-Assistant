-- Migration: Align users table with AuthManager expectations (password hashing & verification fields)
-- Date: 2025-10-06
-- Purpose: Fix registration failures caused by missing columns referenced in utils/auth_system.py

-- Add new columns if they do not already exist
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS role_id integer REFERENCES roles(id);
ALTER TABLE users ADD COLUMN IF NOT EXISTS verified boolean DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login timestamptz;
ALTER TABLE users ADD COLUMN IF NOT EXISTS login_attempts integer DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until timestamptz;
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences jsonb DEFAULT '{}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

-- Ensure status column matches expected semantics (pending_verification default)
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='status') THEN
        EXECUTE 'ALTER TABLE users ALTER COLUMN status SET DEFAULT '||quote_literal('pending_verification');
    END IF;
END $$;

-- Backfill role_id from user_roles junction table if role_id is null
UPDATE users u SET role_id = sub.role_id
FROM (
    SELECT ur.user_id, ur.role_id
    FROM user_roles ur
    JOIN roles r ON ur.role_id = r.id
    WHERE ur.user_id IN (SELECT id FROM users WHERE role_id IS NULL)
    ORDER BY ur.user_id, ur.role_id
) sub
WHERE u.id = sub.user_id AND u.role_id IS NULL;

-- If any users still lack role_id assign them to 'employee' if exists, else first role
WITH default_role AS (
    SELECT id FROM roles WHERE name='employee' LIMIT 1
), chosen AS (
    SELECT id FROM roles ORDER BY id LIMIT 1
)
UPDATE users SET role_id = COALESCE((SELECT id FROM default_role),(SELECT id FROM chosen)) WHERE role_id IS NULL;

-- For legacy rows without password_hash set a non-null placeholder (forces reset if ever used)
UPDATE users SET password_hash = '$2b$12$LegacyPlaceholderHashxxxxxxxxxxxxxxxxyyyyyyyyyyyyyyyyyyyyyy' WHERE password_hash IS NULL;

-- Indexes to support lookups
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id);
CREATE INDEX IF NOT EXISTS idx_users_verified ON users(verified);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

-- Trigger to maintain updated_at
CREATE OR REPLACE FUNCTION update_users_timestamp() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_users_timestamp();

-- End migration
