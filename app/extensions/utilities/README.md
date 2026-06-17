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
The extension exposes the following Sprocket API routes for programmatic access to the Security Auditor:
- `GET /api/guild/{guild_id}/audit/score`: Returns the overall security health score (starting from 100) and warning counts by severity.
- `GET /api/guild/{guild_id}/audit/alerts`: Retrieves the list of active security alerts (filterable by category).
- `GET /api/guild/{guild_id}/audit/config`: Returns the current Auditor configuration settings.
- `POST /api/guild/{guild_id}/audit/config`: Updates the Auditor configuration. Omitted fields in the request body preserve their existing database values rather than resetting to `None`.

For a comprehensive guide on the Security Auditor rules, scoring, and architecture, see [SECURITY_AUDITOR.md](../../../docs/SECURITY_AUDITOR.md).

### UI Elements (Widgets)
The extension registers 8 default widgets under the following configurations:

1. `guild_admin_security_overview`:
   - **Type**: Grid layout
   - **Column Span**: 4
   - **Display Order**: 1
   - **Description**: A dashboard card summarizing total counts and highlighting specific security warnings (e.g., `@everyone has Administrator`).
2. `guild_admin_alerts`:
   - **Type**: Grid layout
   - **Column Span**: 8
   - **Display Order**: 2
   - **Description**: An alert panel displaying active security alerts.
3. `guild_admin_auditor_settings`:
   - **Type**: Grid layout
   - **Column Span**: 12
   - **Display Order**: 3
   - **Description**: Auditor settings configuration widget.
4. `guild_admin_audit_roles`:
   - **Type**: Grid layout
   - **Column Span**: 12
   - **Display Order**: 4
   - **Description**: A detailed table of server roles, generating visual badges for permissions and matching the exact color of the role in Discord.
5. `guild_admin_audit_channels`:
   - **Type**: Grid layout
   - **Column Span**: 12
   - **Display Order**: 5
   - **Description**: Displays the channel hierarchy, identifying private channels and explicitly showing how many roles/users are allowed or denied access in overwrites.
6. `guild_admin_audit_permissions`:
   - **Type**: Grid layout
   - **Column Span**: 12
   - **Display Order**: 6
   - **Description**: A matrix correlating specific permissions (like "Manage Server" or "Kick Members") directly to the roles that hold them.
7. `guild_admin_utilities_sidebar`:
   - **Type**: Fixed layout
   - **Position**: `"left"` (Left Sidebar)
   - **Column Span**: 12
   - **Display Order**: 7
   - **Description**: A sidebar widget containing the security health score, quick statistics, quick navigation links, and a button to trigger a scan.
8. `guild_admin_utilities_help_bubble`:
   - **Type**: Floating layout
   - **Position**: `"bottom-right"` (Bottom-Right Corner)
   - **Column Span**: 12
   - **Display Order**: 8
   - **Description**: A bubble widget providing details on available slash commands and bot connection status.

### UI Dashboard Endpoints
- `POST /dashboard/{guild_id}/scan`: Triggers the bot permission scan and refreshes the dashboard page.
- `GET /dashboard/{guild_id}/ping-bot`: Verifies bot connectivity and displays the current latency.

### Bot Internal API Routes
- `POST /guilds/{guild_id}/scan`: Bot-side internal API endpoint to trigger a server audit scan.

---

> **Setup Note:** Ensure that the bot has `Manage Roles` and `Manage Channels` (or `Administrator`) permissions in the Discord server in order for the audit command to successfully read the server's configuration.

## Lifecycle Hooks

### Delete Server Data
The utilities extension registers a `delete_guild_data` lifecycle hook. When a server admin uses the **Delete Server Data** action (via the dashboard or `/powercord delete_server_data`), the following data is permanently removed for that guild:
- `DiscordRole` (role snapshots from audits)
- `DiscordChannel` (channel snapshots from audits)

Additionally, Powercord's core `GuildExtensionSettings` and `WidgetSettings` rows for this extension are cleaned up.
