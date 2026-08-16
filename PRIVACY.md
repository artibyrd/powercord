# Powercord Privacy Policy

**Effective Date:** August 15, 2026  
**Website:** [https://powercord.rocks/](https://powercord.rocks/)  
**Repository:** [https://github.com/artibyrd/powercord](https://github.com/artibyrd/powercord)

This Privacy Policy describes how the **Powercord** Discord application ("Powercord", "we", "us", or "our") collects, uses, processes, and protects information when you interact with our Discord bot, web dashboard at https://powercord.rocks/, and internal APIs.

Powercord is committed to upholding user privacy, adhering strictly to the Discord Developer Terms of Service and Developer Policy, and applying the **Principle of Least Privilege** and **Data Minimization** across all system components.

---

## 1. Summary of Principles

* **No General Chat Logging:** We do not collect, read, store, or monitor general text messages or chat conversations.
* **No AI/ML Training:** We do not use any user data, messages, or uploaded files to train machine learning or artificial intelligence models.
* **No Data Monetization:** We never sell, rent, license, or monetize any user or server data.
* **Per-Guild Isolation:** Extensions that process specialized data (such as music attachments) are isolated and only operate in specific servers and channels where server administrators have explicitly enabled them.

---

## 2. Information We Collect and Process

### A. Message Content & File Attachments (`intents.message_content`)
* **What We Process:** In servers where the **MIDI Library** extension is explicitly enabled, Powercord listens for user-submitted file attachments ending with `.mid`, `.midi`, `.zip`, `.7z`, or `.rar` dropped in designated channels.
* **How It Is Used:** When an attachment is detected:
  1. The bot verifies the file type and computes a cryptographic checksum (MD5).
  2. The file is parsed using deterministic audio analysis libraries (`pretty_midi`, `librosa`) to extract musical metadata (note count, instrument breakdown, track diversity, duration).
  3. A dark-mode piano-roll visual spectrogram preview is generated.
  4. The song metadata and file are indexed into the community music library so members can search, browse, and play music via slash commands and interactive select menus.
* **What We Do NOT Collect:** General text messages, user chat messages without music attachments, and private messages (DMs) are **never** read, logged, analyzed, or stored. Incoming messages on servers that do not have the music extension enabled are immediately discarded with zero processing.

### B. Server Roles, Channels & Permission Overwrites (`intents.members`)
* **What We Process:** For the **Security Auditor** and administrative features:
  * Server role names, hierarchy positions, colors, and permission bitmasks (`DiscordRole`).
  * Channel names, types, category parent IDs, and permission overwrite bitmasks (`DiscordChannel`).
* **How It Is Used:**
  * To evaluate server permission structures against 8 baseline security rules (detecting category permission leaks, exposed staff channels, and unauthorized `@everyone` mentions).
  * To synchronize role-based access control (RBAC) and verify administrator permissions when users log in to the management dashboard.
* **Storage:** Role and channel permission metadata is cached in our PostgreSQL database to render security audit scores and dashboards. Member data is kept in-memory during bot runtime and is not harvested or persisted off-platform.

### C. Web Dashboard & Discord OAuth2
* **What We Process:** When a server administrator logs in to the FastHTML web dashboard via Discord OAuth2, we receive:
  * The user's Discord Snowflake ID and username.
  * The list of mutual Discord servers where the user has administrative permissions.
* **How It Is Used:** Exclusively to verify identity and restrict dashboard access to authorized server administrators.

### D. Anti-Raid & Honeypot Monitoring
* **What We Process:** In servers with the **Honeypot** extension enabled, the bot monitors configured honeypot trap channels for user message timestamps and channel IDs.
* **How It Is Used:** To identify automated user bots hopping between trap channels within a short time window and execute automated mitigation (banning or alerting staff). Message text is not inspected or stored.

### E. User Presence & Activity Data
* **No Presence Tracking:** Powercord does **not** record, log, or persist user presence status (online/offline/idle), rich presence, or game activity off-platform.

---

## 3. Data Storage, Security & Retention

* **Databases:** Relational data (guild extension settings, permission configurations, indexed music metadata, and audit scores) is stored in a secured PostgreSQL database.
* **Storage Buckets:** User-contributed MIDI files and generated piano-roll preview images are stored in Google Cloud Storage (GCS) buckets.
* **Transient Data Cleanup:** Any temporary files extracted during archive analysis (`.zip` / `.7z`) in temporary directories are immediately deleted upon processing.
* **Access Control:** All internal APIs and dashboard routes are protected by authenticated API key middleware, session tokens, and strict network boundaries.

---

## 4. User Choices, Opt-Out & Data Deletion

* **Channel-Level Control:** Server administrators control precisely which channels the bot has access to via standard Discord channel permissions.
* **Extension Toggles:** Every extension can be toggled on or off per guild at any time via slash commands or the web dashboard.
* **Data Deletion Requests:** Server administrators or users may request the deletion of their server's cached data, indexed music uploads, or audit records at any time. To request deletion:
  * Open an issue or inquiry on our GitHub repository: [https://github.com/artibyrd/powercord/issues](https://github.com/artibyrd/powercord/issues)
  * Contact the bot administrator directly within your server.

---

## 5. Third-Party Services

Powercord interacts with the following third-party infrastructure providers:
* **Discord API / Gateway:** To send and receive events according to the Discord Developer Terms.
* **Google Cloud Platform (GCP):** For secure cloud hosting, database management, and object storage.

---

## 6. Open Source Transparency

Powercord is open-source. You can inspect the core bot logic, database models, and permission security rules directly in our public repository:
* **Repository:** [https://github.com/artibyrd/powercord](https://github.com/artibyrd/powercord)
* **Intents Architecture Documentation:** [https://github.com/artibyrd/powercord/blob/main/docs/INTENTS.md](https://github.com/artibyrd/powercord/blob/main/docs/INTENTS.md)
* **Security Auditor Documentation:** [https://github.com/artibyrd/powercord/blob/main/docs/SECURITY_AUDITOR.md](https://github.com/artibyrd/powercord/blob/main/docs/SECURITY_AUDITOR.md)

---

## 7. Updates to this Policy

We may update this Privacy Policy periodically to reflect changes in our framework or regulatory requirements. Any updates will be committed to the public repository with a revised effective date.
