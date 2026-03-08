# Utilities Extension

The `utilities` extension provides powerful administrative tools for server analytics and security auditing. It allows server administrators to snapshot their server's configuration and review it from the Powercord dashboard.

## Python Dependencies
- None (Standard Library)

## Database Schema Changes
- `UtilityAuditSnapshot`: Serializes and stores a snapshot of the server's roles, channels, and permission overwrites.

## Features

### Bot Features (Cogs)
- **Commands**:
  - `/audit` and `!audit`: Trigger a synchronous snapshot of the server's state.
- **Listeners**:
  - None included.
- **Tasks**:
  - None included.

### API Routes (Sprockets)
- None included.

### UI Elements (Widgets)
- `guild_admin_audit_roles_widget`: A detailed table of server roles, generating visual badges for permissions and matching the exact color of the role in Discord.
- `guild_admin_audit_channels_widget`: Displays the channel hierarchy, identifying private channels and explicitly showing how many roles/users are allowed or denied access in overwrites.
- `guild_admin_security_overview_widget`: A dashboard card summarizing total counts and highlighting specific security warnings (e.g. `@everyone has Administrator`).
- `guild_admin_audit_permissions_widget`: A matrix correlating specific permissions (like "Manage Server" or "Kick Members") directly to the roles that hold them.

---

> **Setup Note:** Ensure that the bot has `Manage Roles` and `Manage Channels` (or `Administrator`) permissions in the Discord server in order for the audit command to successfully read the server's configuration.

## Lifecycle Hooks

### Delete Server Data
The utilities extension registers a `delete_guild_data` lifecycle hook. When a server admin uses the **Delete Server Data** action (via the dashboard or `/powercord delete_server_data`), the following data is permanently removed for that guild:
- `DiscordRole` (role snapshots from audits)
- `DiscordChannel` (channel snapshots from audits)

Additionally, Powercord's core `GuildExtensionSettings` and `WidgetSettings` rows for this extension are cleaned up.
