-- This script is executed during the initial setup of the PostgreSQL database.
-- It creates the necessary tables for the Powercord application to function.

-- Table to store guild-specific settings for extensions.
-- This allows enabling or disabling cogs, sprockets, and widgets on a per-server basis.
CREATE TABLE IF NOT EXISTS guild_extension_settings (
    guild_id BIGINT NOT NULL,
    extension_name VARCHAR(255) NOT NULL,
    gadget_type VARCHAR(50) NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (guild_id, extension_name, gadget_type)
);

-- Table to store layout and display settings for widgets on the public UI.
-- A guild_id of 0 is used for the global/default public page layout.
CREATE TABLE IF NOT EXISTS widget_settings (
    guild_id BIGINT NOT NULL,
    extension_name VARCHAR(255) NOT NULL,
    widget_name VARCHAR(255) NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    display_order INT NOT NULL DEFAULT 0,
    column_span INT NOT NULL DEFAULT 4, -- Width in 12-column grid
    grid_x INT NOT NULL DEFAULT 0,      -- X position in grid (0-11)
    grid_y INT NOT NULL DEFAULT 0,      -- Y position in grid (row)
    PRIMARY KEY (guild_id, extension_name, widget_name)
);

-- Table to store Dashboard Admins
-- These users have access to the restricted /admin page
CREATE TABLE IF NOT EXISTS admin_users (
    user_id BIGINT NOT NULL PRIMARY KEY,
    comment VARCHAR(255)
);

-- You can add more tables or default data below.
