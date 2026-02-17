-- Add targeting columns to campaigns table for role/user specific targeting

ALTER TABLE campaigns ADD COLUMN target_role_ids TEXT; -- JSON array of role IDs for 'roles' type
ALTER TABLE campaigns ADD COLUMN target_user_ids TEXT; -- JSON array of user IDs for 'users' type
