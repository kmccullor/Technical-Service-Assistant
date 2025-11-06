-- Migration: Consolidate RBAC permissions to match PermissionLevel enum
-- Date: 2025-11-02
-- Purpose: Ensure database permissions match the PermissionLevel enum used in code

-- Add missing permissions that are in the enum but not in DB
INSERT INTO permissions (name, resource, action, description) VALUES
    ('delete', 'general', 'delete', 'Delete access to resources')
ON CONFLICT (name) DO NOTHING;

-- Update role_permissions to include delete for admin role
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'admin' AND p.name = 'delete'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Verify all PermissionLevel enum values exist in permissions table
-- This query should return all enum values after migration
-- SELECT unnest(ARRAY['read', 'write', 'admin', 'delete', 'manage_users', 'manage_roles', 'system_config', 'export_data', 'view_analytics', 'download_documents', 'manage_documents']) as expected_permission
-- EXCEPT
-- SELECT name FROM permissions;

-- End migration
