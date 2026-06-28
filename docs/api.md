# API Security and Management

Powercord implements a robust security model for both its internal and external REST APIs. This document covers the security architecture, scope hierarchy, cryptographic hashing of API keys, auto-generated documentation access, and API key management.

> [!NOTE]
> For implementation details on the authentication dependencies (`get_current_api_user` and `api_scope_required`), see [utilities.md](utilities.md#dependencies-appapidependencies).

## Security Model & Cryptographic Key Hashing

To protect credentials in the event of a database compromise, all database API keys are stored as **SHA-256 hashes** (`key_hash`). 
* **Authentication Flow**: When a client sends a token via the `Authorization: Bearer <token>` header (or `token` query parameter), the API middleware hashes the incoming token and queries the database using the hash.
* **One-Time Display**: Raw plaintext keys are shown **only once** at the time of generation (via UIs or CLI) and cannot be recovered or displayed again. Tables and list commands only display key hashes or metadata.
* **Internal System Key Bypass**: The bot-to-API key (`system_internal`) bypasses the hashing flow and database queries via a plaintext fast-path comparison within the middleware memory, and is mapped to `global.admin` permissions.

## Scope Hierarchy

Powercord uses a structured, segment-based scope system. Scopes are evaluated from most-privileged to least-privileged:

| Scope Format | Category | Description | Example |
|---|---|---|---|
| `global.admin` | Super-scope (Admin) | Global write access across core and all extensions/guilds | Admin dashboard |
| `global.user` | Super-scope (User) | Global read access across core and all extensions/guilds | Global monitor key |
| `core.admin` | Core-scope (Admin) | Write access to core endpoints (reloads, restarts) | Operational scripts |
| `core.user` | Core-scope (User) | Read access to core settings and guild metadata | Desktop client key |
| `global.{extension}.admin` | Extension-wide (Admin) | Write access to a single extension across all guilds | N/A (reserved) |
| `global.{extension}.user` | Extension-wide (User) | Read access to a single extension across all guilds | Lutebot searching MIDI library |
| `{guild_id}.{extension}.admin` | Guild-specific (Admin) | Full access to a single extension on a specific guild | Honeypot configuration |
| `{guild_id}.{extension}.user` | Guild-specific (User) | Read access to a single extension on a specific guild | Member viewing audit score |

> [!IMPORTANT]
> **Extension-wide scopes (`global.{extension}.user`)** allow integrations (such as Lutebot querying the `midi_library` database) to access resources across all guilds without requiring a `X-Guild-Id` header context, while preventing them from accessing sensitive guild configurations or other extensions.
>
> **Guild-specific scopes** require the client to supply the target context using either the path parameter (if present) or the `X-Guild-Id` header.

## Viewing API Documentation

The auto-generated FastAPI Swagger endpoints (`/docs` and `/openapi.json`) are secured behind the same scope check dependencies as the rest of the API to prevent unauthorized configuration analysis.

### Browser Access

Append a valid API key (possessing `core.user` or higher) using the `token` query parameter:

```
http://localhost:8000/docs?token=YOUR_API_KEY
```

### Postman / cURL

Set the standard `Authorization` header:

```
Authorization: Bearer YOUR_API_KEY
```

> [!TIP]
> For details on customizing the Swagger UI appearance, see [swagger_styling.md](swagger_styling.md).

## Managing Third-Party API Keys (CLI)

Powercord provides CLI utilities via `Justfile` recipes to generate, list, and revoke API keys:

### Add a New Key

Generate a secure key with the specified scopes:
```bash
just add-api-key <name> --scopes '["global.midi_library.user"]'
```

To pre-seed a partner key (e.g. legacy key format):
```bash
just add-api-key <name> --scopes '["global.midi_library.user"]' --key "custom_secret_key"
```
*(Note: The CLI tool hashes the key before saving it to the database and prints the raw key exactly once.)*

### List All Keys

Displays active/inactive keys, their scopes, key types, and creation dates (raw keys or hashes are NOT displayed):
```bash
just list-api-keys
```

### Revoke a Key

Revoke a key by its database ID (retrieved from `list-api-keys`):
```bash
just revoke-api-key <id>
```

