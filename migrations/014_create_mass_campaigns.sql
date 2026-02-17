-- Mass Campaign System
-- Allows admins to create mass DM/channel messages with interactive forms

-- Campaigns table - stores campaign configurations
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    message_content TEXT,
    embed_title TEXT,
    embed_description TEXT,
    embed_color INTEGER,
    embed_image_url TEXT,
    embed_thumbnail_url TEXT,
    target_type TEXT NOT NULL CHECK(target_type IN ('dm', 'channel', 'roles', 'users')),
    target_channel_id INTEGER,
    target_role_ids TEXT, -- JSON array of role IDs for 'roles' type
    target_user_ids TEXT, -- JSON array of user IDs for 'users' type
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft', 'sent', 'archived'))
);

-- Campaign buttons/forms - stores button configurations and associated forms
CREATE TABLE IF NOT EXISTS campaign_forms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    button_label TEXT NOT NULL,
    button_style TEXT DEFAULT 'primary' CHECK(button_style IN ('primary', 'secondary', 'success', 'danger', 'link')),
    button_emoji TEXT,
    button_order INTEGER DEFAULT 0,
    has_form INTEGER DEFAULT 0,
    modal_title TEXT,
    form_fields TEXT, -- JSON array of form field configurations
    response_channel_id INTEGER, -- Where to send form responses
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE
);

-- Campaign responses - stores user responses to forms
CREATE TABLE IF NOT EXISTS campaign_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    form_id INTEGER NOT NULL,
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    response_data TEXT, -- JSON object with field_name: response pairs
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (form_id) REFERENCES campaign_forms(id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_campaigns_guild ON campaigns(guild_id);
CREATE INDEX IF NOT EXISTS idx_campaign_forms_campaign ON campaign_forms(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_responses_form ON campaign_responses(form_id);
CREATE INDEX IF NOT EXISTS idx_campaign_responses_user ON campaign_responses(user_id, guild_id);
