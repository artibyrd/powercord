# Security Auditor Extension

The **Security Auditor** is a core Powercord utility designed to evaluate, score, and monitor a Discord server's (guild's) security posture. By analyzing role permissions, channel overrides, and integration privileges, the Auditor provides server administrators with actionable alerts and remediation steps to secure their community.

---

## 1. System Architecture & Configuration

The Security Auditor consists of three primary layers:
1. **Database Models (`app.db.models`)**:
   - `DiscordAuditorConfig`: Stores guild-specific configuration parameters:
     - `staff_separator_role_id` (Optional[int]): The role separating privileged staff members from general users. Roles below this separator are evaluated for privilege containment.
     - `staff_channel_ids` (JSON string list): Channel IDs containing confidential or staff-only communications.
     - `announcement_channel_ids` (JSON string list): Channel IDs reserved for official announcements or server rules.
   - `DiscordRole`: Caches role details (name, position, managed, mentionable, permission bitmask).
   - `DiscordChannel`: Caches channel details (name, type, category parent ID, permission overrides bitmask).

2. **Security Rule Engine (`app.extensions.utilities.widget`)**:
   - Executes a series of predefined security rule checks (`SecurityRule`) against a guild's cached DB roles and channels.
   - Computes an overall health score starting from `100` down to `0`.
   - Generates granular security alerts categorized by risk vector.

3. **REST API Endpoints (`app.extensions.utilities.sprocket`)**:
   - Exposes HTTP routes enabling programmatic query and mutation of configurations, scores, and security alerts.

---

## 2. The 8 Security Rules

The engine implements 8 rules to identify leaks and misconfigurations:

### 1. Category Permission Baseline
- **Category**: `exposure`
- **Severity**: `Medium` (escalates to `High` if View Channel `1 << 10` is exposed; downgrades to `Low` if the leak is inert)
- **Conditions**: Compares explicit permission overrides of child channels against their parent category. An alert is raised if a target (role or member) has less restricted permissions in the child channel than in the category (e.g., additional allows or removed denies). If the leaked permissions are rendered inert because View Channel is effectively denied for the target (either at the child level or inherited from the parent category), the alert is downgraded to `Low` severity and annotated as `[INERT]`.
- **Risks**: Silent permission drift or exposure where sensitive content becomes visible or actions become possible to users restricted at the category level. Inert leaks indicate misconfigured overwrites that, while not currently exploitable, may become active if View Channel restrictions change.
- **Remediation**: Synchronize the channel's overrides to match the parent category, or remove the conflicting explicit permissions from the child channel.

### 2. Public Announcement Protection
- **Category**: `pings`
- **Severity**: `High`
- **Conditions**: Evaluates announcement/rules channels (configured via `announcement_channel_ids`, or containing "announcement" or "rules" in their name). Checks if any non-staff role (e.g. `@everyone` or roles below the staff separator) has Send Messages (`1 << 11`), Mention Everyone (`1 << 17`), or global Administrator (`1 << 3`) permissions. Alerts are only raised when the role has effective View Channel (`1 << 10`) access, including permissions inherited from the parent category.
- **Risks**: Malicious or regular users sending unauthorized messages or pinging `@everyone`/`@here`, causing server-wide disruption, announcement contamination, or mass ping spam.
- **Remediation**: Explicitly deny Send Messages and Mention Everyone permissions in the announcement channel for `@everyone` and any non-staff roles.

### 3. Exposed Staff Channels
- **Category**: `exposure`
- **Severity**: `High`
- **Conditions**: Checks channels designated as staff channels (configured via `staff_channel_ids`, or containing "staff", "admin", or "moderator" in their name). An alert is triggered if any non-staff role (e.g. `@everyone` or roles below the staff separator) has View Channel (`1 << 10`) permission. Effective permissions are computed using the shared permission computation function, which accounts for parent category overwrite inheritance.
- **Risks**: Leakage of confidential moderation logs, internal discussions, bot commands, or security procedures to general members.
- **Remediation**: Edit the channel permissions to ensure the `@everyone` role and all non-staff roles are explicitly denied the View Channel permission.

### 4. Unauthorized Chat Pings in Non-Text Locations
- **Category**: `pings`
- **Severity**: `Medium`
- **Conditions**: Scans non-text locations (Voice channels, Stage channels, Threads, and Forums). Triggers an alert if any non-staff role (e.g. `@everyone` or roles below the staff separator) has Send Messages (`1 << 11`), Mention Everyone (`1 << 17`), or global Administrator (`1 << 3`) permissions. Alerts are only raised when the role has effective View Channel (`1 << 10`) access, including permissions inherited from the parent category.
- **Risks**: Spamming text messages, triggering push notifications, or sending mass pings inside voice chats or forum threads, bypassing standard text-channel moderation structures.
- **Remediation**: Revoke the Send Messages / Send Messages in Threads and Mention Everyone permissions for low-tier roles in these channels.

### 5. Low-Tier Role Privileges
- **Category**: `roles`
- **Severity**: `High`
- **Conditions**: Triggered if any role positioned below the configured staff separator role has any of the following sensitive permissions enabled in its global bitmask:
  - Administrator (`1 << 3`)
  - Manage Server (`1 << 5`)
  - Manage Roles (`1 << 28`)
  - Manage Channels (`1 << 4`)
  - Kick Members (`1 << 1`)
  - Ban Members (`1 << 2`)
  - Mention Everyone (`1 << 17`)
- **Risks**: Users with low-tier roles gaining moderation or administrative access. If a low-tier role is compromised, rogue users can ban members, delete channels, or compromise the entire server configuration.
- **Remediation**: Strip administrative, management, and moderation permissions from all roles located below the staff separator role.

### 6. General Role Mentionability
- **Category**: `pings`
- **Severity**: `Low`
- **Conditions**: Checks if any role below the staff separator role is unmanaged (not a bot/integration role) and is set to mentionable (`is_mentionable=True`).
- **Risks**: Mass ping raids where bad actors ping general member roles to spam large groups of users.
- **Remediation**: Uncheck the "Allow anyone to @mention this role" setting for all non-staff/general roles in Discord settings.

### 7. Suggestive Honeypot Integration
- **Category**: `integrations`
- **Severity**: `Medium` (drops to `Low` if the Honeypot extension is completely disabled)
- **Conditions**: Checks if public "discovery" channels (channels containing "discovery" in the name with public view enabled) lack Honeypot decoy protection, or if the Honeypot extension itself is not enabled.
- **Risks**: Public channels being targeted by scrapers, self-bots, or raid invites without decoy/honeypot channels to detect, catch, and automatically ban malicious bots.
- **Remediation**: Enable the Honeypot extension and configure decoy channels, or register the public discovery channels under Honeypot protection.

### 8. Over-privileged Bot Integrations
- **Category**: `integrations`
- **Severity**: `Medium`
- **Conditions**: Analyzes managed integration roles (bot roles). Triggers an alert if any bot role holds high-level permissions such as Administrator (`1 << 3`), Manage Server (`1 << 5`), Manage Roles (`1 << 28`), or Manage Channels (`1 << 4`).
- **Risks**: Bot compromise or token leakage. If an over-privileged bot is hacked, attackers gain full access to modify or destroy the server.
- **Remediation**: Strip excessive administrative permissions from bot roles and follow the principle of least privilege.

---

## 3. Scoring Mechanism

The Security Auditor evaluates the server's security health with a numeric score ranging from **0** to **100**. 

1. **Initial Score**: The audit begins with a baseline score of **100**.
2. **Deductions**: The score is reduced by a fixed amount for each unique security alert generated during evaluation, based on the alert's severity:
   - **High Severity Alert**: `-15` points
   - **Medium Severity Alert**: `-10` points
   - **Low Severity Alert**: `-5` points
3. **Bounding**: The score is bounded to a minimum of **0** (i.e., the score cannot be negative).

$$\text{Health Score} = \max(0, 100 - (15 \times N_{\text{high}} + 10 \times N_{\text{medium}} + 5 \times N_{\text{low}}))$$

---

## 4. Sprocket API Routes

The REST API exposes four endpoints for auditing and configuring the guild security status:

### 1. Get Audit Score
- **URL**: `GET /api/guild/{guild_id}/audit/score`
- **Response**:
  ```json
  {
    "score": 85,
    "severities": {
      "high": 1,
      "medium": 0,
      "low": 0
    }
  }
  ```
- **Description**: Calculates the overall health score and counts the number of alerts by severity.

### 2. Get Audit Alerts
- **URL**: `GET /api/guild/{guild_id}/audit/alerts`
- **Query Parameters**:
  - `category` (Optional[str]): Filter alerts by category (e.g. `exposure`, `pings`, `roles`, `integrations`).
- **Response**:
  ```json
  [
    {
      "rule": "Exposed Staff Channels",
      "category": "exposure",
      "severity": "high",
      "message": "Staff channel #moderators is visible to @everyone.",
      "details": "Role '@everyone' (position 0) has View Channel (1 << 10) permission in staff channel.",
      "action_buttons": []
    }
  ]
  ```
- **Description**: Retrieves the list of active security alerts, with optional category filtering.

### 3. Get Auditor Config
- **URL**: `GET /api/guild/{guild_id}/audit/config`
- **Response**:
  ```json
  {
    "staff_separator_role_id": 1234567890,
    "staff_channel_ids": [11111111, 22222222],
    "announcement_channel_ids": [33333333]
  }
  ```
- **Description**: Returns the current auditor configuration for the specified guild.

### 4. Post Auditor Config (Update)
- **URL**: `POST /api/guild/{guild_id}/audit/config`
- **Request Body**:
  ```json
  {
    "staff_separator_role_id": 1234567890,
    "staff_channel_ids": [11111111, 22222222],
    "announcement_channel_ids": [33333333]
  }
  ```
- **Response**:
  ```json
  {
    "staff_separator_role_id": 1234567890,
    "staff_channel_ids": [11111111, 22222222],
    "announcement_channel_ids": [33333333]
  }
  ```
- **Description**: Updates the guild auditor configuration. If a field (e.g. `staff_separator_role_id`) is omitted from the JSON request payload, the existing database value is preserved and not reset to `None`.
