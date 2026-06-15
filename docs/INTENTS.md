# Discord Privileged Intents Tracking & Verification

This document tracks and justifies the use of Discord privileged gateway intents across the Powercord ecosystem. Since the bot is deployed in large servers exceeding the **10,000 user threshold**, these details are critical for the Discord Developer Portal application review process.

---

## 1. Summary Matrix

| Privileged Intent | Core Framework | Extension-Specific | Legacy / Future | Status |
| :--- | :---: | :---: | :---: | :--- |
| **Guild Members** (`intents.members`) | **Required** (RBAC / Cache) | None | None | **Enabled** |
| **Message Content** (`intents.message_content`) | None | **Required** (`midi_library`) | None | **Enabled** |
| **Guild Presences** (`intents.presences`) | None | None | **Legacy/Planned** (Game Server Scale) | **Enabled** |

---

## 2. Core Framework Requirements

### A. Guild Members Intent (`intents.members`)

*   **Primary Justification**: Core API Authorization & RBAC Synchronization.
*   **Where it is used**:
    *   [powercord/app/bot/internal_server.py](file:///home/pendragon/Projects/powercord-ecosystem/powercord/app/bot/internal_server.py)
        *   `GET /user/{user_id}/guilds/{guild_id}/roles` (via `guild.get_member(user_id)`)
        *   `GET /user/{user_id}/admin_guilds` (via `guild.get_member(user_id)`)
*   **Technical Details**:
    The Flet client communicates with the bot's internal FastAPI server to determine user permissions. To check if a user is an administrator of a guild or to retrieve their roles, the API server retrieves the cached `Member` object using `guild.get_member()`. 
    Without the `Guild Members` intent, the bot's internal member cache is empty (except for the bot itself), causing `guild.get_member()` to fail.
*   **Alternative Mitigations**:
    Replacing `guild.get_member()` with the API call `await guild.fetch_member()` would bypass cache requirements but introduces heavy REST API latency and exposes the bot to strict Discord rate limits under high user concurrency.

---

## 3. Extension-Specific Requirements

### A. Message Content Intent (`intents.message_content`)

*   **Primary Justification**: Auto-ingesting user-uploaded MIDI files and archives.
*   **Where it is used**:
    *   [powercord-extensions/midi_library/cog.py](file:///home/pendragon/Projects/powercord-ecosystem/powercord-extensions/midi_library/cog.py)
        *   `on_message` listener
*   **Technical Details**:
    The MIDI Library extension automatically processes uploads of `.mid`, `.midi`, `.zip`, `.7z`, and `.rar` attachments sent in designated channels. Under Discord API rules, the `message.attachments` field is completely stripped from payload messages unless the `Message Content` intent is enabled.

#### Note on Honeypot Extension
*   The Honeypot extension ([honeypot/cog.py](file:///home/pendragon/Projects/powercord-ecosystem/powercord-extensions/honeypot/cog.py)) listens to the `on_message` event to track user channel hopping. However, it only inspects metadata (`message.channel.id` and `message.author.id`) and **does not** read `message.content` or `message.attachments`. It does not strictly require this intent to function.

---

## 4. Legacy and Future Requirements

### A. Guild Presences Intent (`intents.presences`)

*   **Primary Justification**: Dynamic Game Server Scaling & Active Play-Status Monitoring.
*   **Status**: Currently declared but inactive in the active codebase.
*   **Background / Intent**:
    This intent was originally designated for a legacy feature designed to dynamically provision game servers based on player demand:
    1.  **Presence Monitoring**: The bot monitored player statuses (`member.activities` and `member.status`) to check if users were playing a specific game (e.g., assigning a temporary "NOW PLAYING {GAME}" role).
    2.  **Dynamic Scaling**: If the count of active players playing a specific game on the server crossed threshold \(X\), the bot automatically triggered the startup of a private game server instance.
    3.  **Automatic Shutdown**: Once the game server was empty for duration \(Y\) (monitored by the bot), the bot automatically spun down the instance to conserve hosting resources.
*   **Next Steps**:
    This feature has not yet been ported to the new Powercord cogs architecture. If this dynamic server-scaling system is slated for reimplementation, the bot must retain `intents.presences = True`. If this roadmap is abandoned, the presence intent should be set to `False` to streamline the Discord application review.
