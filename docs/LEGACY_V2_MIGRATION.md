# Legacy v2 BardBot Migration Artifacts

> **For fresh Powercord installs:** All items in this document can be safely ignored or removed.
> They exist solely to support the migration from the legacy BardBot v2 MIDI server to Powercord v3.

## Background

Powercord v3 replaced a legacy Flask/gunicorn deployment ("BardBot v2") that served a MIDI file
library at `api.bardsguild.life`.  An external client (**LuteBot3**) depends on the legacy API
format (`?key=API_KEY&find=TERM`), so a compatibility shim was added to v3 to avoid breaking
that integration during the transition period.

These artifacts should be **removed entirely** once the LuteBot maintainer has migrated to the
v3 API, or when the legacy `api.bardsguild.life` domain is decommissioned.

---

## Artifact Inventory

All legacy artifacts are marked with `BEGIN LEGACY` / `END LEGACY` comment blocks or inline
`# LEGACY:` comments for easy identification.  You can search the entire codebase with:

```bash
rg "LEGACY" --type-add 'config:*.conf' --type-add 'just:Justfile,*.just' -t py -t config -t just
```

### Framework (powercord)

| File | Marker | Description |
|---|---|---|
| [`app/main_api.py`](file:///a:/Dev/Google/powercord/app/main_api.py#L37-L49) | `BEGIN LEGACY` block | Mounts the `legacy_compat` router at `/midi_library/legacy`, bypassing the sprocket system's `api_scope_required` auth. Guarded by `try/except ImportError` so the framework works cleanly without the `midi_library` extension. |
| [`nginx.conf`](file:///a:/Dev/Google/powercord/nginx.conf#L54-L79) | `BEGIN LEGACY` block | Adds an `api.bardsguild.life` server block that rewrites root-path requests to `/midi_library/legacy/` on FastAPI. |
| [`app/db/db_tools.py`](file:///a:/Dev/Google/powercord/app/db/db_tools.py#L146) | `BEGIN LEGACY` + inline | The `is_migration` parameter on `export_database()` and its two code paths (Docker and local host). Produces data-only INSERT dumps for importing v2 data into a v3 Alembic-managed schema. Also includes the `--migration` CLI arg at the bottom of the file. |
| [`Justfile`](file:///a:/Dev/Google/powercord/Justfile#L272) | Inline comment | The `--migration` flag on the `db-export` recipe. Passes through to `db_tools.py`'s migration export mode. |
| [`.example.env`](file:///a:/Dev/Google/powercord/.example.env#L46-L48) | `BEGIN LEGACY` block | Manifest entry for `POWERCORD_LUTEBOT_LEGACY_API_KEY`. Required by `gsm_loader.py` to fetch the secret from Secret Manager at container startup. |

### Extension (midi_library)

| File | Description |
|---|---|
| `legacy_compat.py` | The compatibility shim module. Single `GET /` endpoint that accepts the legacy query format, validates the LuteBot key, queries the v3 database, and returns flat-dict JSON matching the legacy SQL row format. |
| `tests/test_legacy_compat.py` | Unit tests for the compatibility shim (17 tests). |
| `LUTEBOT_MIGRATION.md` | Developer-facing migration guide for the LuteBot maintainer. |

### Environment Variables

| Variable | Where Used | Description |
|---|---|---|
| `POWERCORD_LUTEBOT_LEGACY_API_KEY` | `legacy_compat.py` | The exact legacy API key value. If unset, all legacy requests are rejected (safe default). |

### Database Records

| Table | Record | Description |
|---|---|---|
| `api_keys` | LuteBot key entry | A third-party API key row with `global.midi_library.user` scope, inserted via `just add-api-key`. The stored `key_hash` is the SHA-256 hash of the `POWERCORD_LUTEBOT_LEGACY_API_KEY` value. |

---

## Migration Phases

### Phase 0 — Compatibility Shim (✅ Complete)
- Implemented `legacy_compat.py` in the `midi_library` extension
- Mounted the router in `main_api.py` with `ImportError` guard
- Added nginx rewrite block for `api.bardsguild.life`
- Inserted the LuteBot API key into the production database

### Phase 1 — DNS Cutover (✅ Complete)
- Pointed `api.bardsguild.life` DNS to the v3 instance IP
- Verified end-to-end: `?key=...&find=test` returns `200 OK` with results

> [!IMPORTANT]
> **Secret loader gotcha:** `gsm_loader.py` uses `.example.env` as a **manifest**.
> Only secrets listed in `.example.env` are fetched from Secret Manager.
> The `POWERCORD_` prefix is also required for `start.sh` to export the var.

### Phase 2 — Bot Identity Swap (✅ Complete)
- Swapped `POWERCORD_DISCORD_TOKEN` to the production bot token
- Re-invited the bot with `bot` + `applications.commands` OAuth2 scopes

> [!WARNING]
> **All three Discord secrets must be updated together.** They must all
> belong to the same Discord Application:
>
> | Secret | Source (Developer Portal) |
> |---|---|
> | `POWERCORD_DISCORD_TOKEN` | Bot → Token |
> | `POWERCORD_DISCORD_CLIENT_ID` | OAuth2 → Client ID |
> | `POWERCORD_DISCORD_CLIENT_SECRET` | OAuth2 → Client Secret |
>
> If only the token is swapped, the bot connects but slash commands fail
> with `403 Missing Access`, and OAuth2 web logins break.

### Phase 3 — 48-Hour Soak Period (⏳ Pending)
- Monitor API, Discord bot, and LuteBot traffic for stability
- After 48 hours with no issues, proceed to Phase 4

### Phase 4 — Legacy Decommission (⏳ Pending)
- Stop and snapshot the legacy `bardbot-2-4-10` VM
- Follow the Removal Checklist below
- Shut down the legacy VM

---

## Removal Checklist

When the LuteBot maintainer has migrated (or the legacy domain is decommissioned), follow this
checklist to cleanly remove all v2 migration artifacts:

- [ ] **`powercord/app/main_api.py`** — Delete the `BEGIN LEGACY` → `END LEGACY` block (the `try/except` that imports and mounts `legacy_compat`)
- [ ] **`powercord/nginx.conf`** — Delete the `BEGIN LEGACY` → `END LEGACY` block (the `api.bardsguild.life` server block)
- [ ] **`powercord/app/db/db_tools.py`** — Remove the `is_migration` parameter from `export_database()`, delete both `if is_migration:` branches, and remove the `--migration` CLI arg
- [ ] **`powercord/Justfile`** — Remove the `--migration` flag from `db-export` recipe and simplify the command
- [ ] **`midi_library/legacy_compat.py`** — Delete the file entirely
- [ ] **`midi_library/tests/test_legacy_compat.py`** — Delete the file entirely
- [ ] **`midi_library/LUTEBOT_MIGRATION.md`** — Delete the file entirely
- [ ] **`powercord/.example.env`** — Remove the `BEGIN LEGACY` → `END LEGACY` block (the `POWERCORD_LUTEBOT_LEGACY_API_KEY` manifest entry)
- [ ] **Environment** — Remove `POWERCORD_LUTEBOT_LEGACY_API_KEY` from `.env.prod` and Terraform secrets
- [ ] **Database** — Revoke the LuteBot API key: `just revoke-api-key <id>`
- [ ] **DNS** — Remove or redirect the `api.bardsguild.life` A record in Cloudflare
- [ ] **This document** — Delete `docs/LEGACY_V2_MIGRATION.md` itself

After completing the checklist, run `just qa` to verify nothing is broken.
