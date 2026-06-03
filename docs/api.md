# API Security and Management

Powercord implements a robust security model for both its internal and external APIs. This document covers the high-level security architecture, how to access the auto-generated documentation, and how to manage third-party API keys.

> [!NOTE]
> For implementation details on the authentication dependencies (`get_current_api_user` and `api_scope_required`), see [utilities.md](utilities.md#dependencies-apapidependencies).

## Security Model

### Admin API

The Admin API uses a database-backed, auto-generated secure key ensuring only trusted system components can access it. An IP restriction middleware further limits access to local networks only.

### Sprocket API

The Sprocket API is secured using a unified authentication dependency that supports both **API Keys** and **Discord OAuth tokens**. See [utilities.md](utilities.md#get_current_api_user) for the dependency signature and usage examples.

### Granular Scopes

API endpoints require specific scopes to control access:

| Context | Required Scope | Example |
|---|---|---|
| Sprocket extension | Extension name | `honeypot` |
| Internal / global API | `global` | — |

Scopes are enforced via the `api_scope_required` dependency generator documented in [utilities.md](utilities.md#api_scope_required).

### JSON Structured Logging

All API access — both Admin and Sprocket — is logged in structured JSON format to `stdout`. Each log entry captures:

- Request path
- Execution time
- Client identity

This format is designed for ingestion by external logging services such as Google Cloud Logging.

## Viewing API Documentation

The auto-generated FastAPI Swagger endpoints (`/docs` and `/openapi.json`) are secured behind the same authentication requirements as the rest of the API to prevent unauthorized configuration analysis.

### Browser Access

Append a valid API key using the `token` query parameter:

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

## Managing Third-Party API Keys

Generate and manage API keys for third-party integrations using the built-in CLI commands:

### Add a New Key

```bash
just add-api-key <name> <scopes>
```

Example:

```bash
just add-api-key myapp '["global", "honeypot"]'
```

### List All Keys

```bash
just list-api-keys
```

### Revoke a Key

```bash
just revoke-api-key <name>
```
