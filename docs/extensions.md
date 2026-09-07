# Extending Powercord

Powercord gives you a framework that lets you get straight to adding your own Python application code within minutes. Simply add your own extensions in the `app/extensions` folder and Powercord handles the rest.

## Extension Structure

Every extension lives in its own subfolder under `app/extensions/`:

```
app
└── extensions
    └── example             # Folder named after the extension
        ├── README.md           # Extension documentation (rendered in the dashboard)
        ├── blueprint.py        # Shared logic, models, helpers
        ├── cog.py              # Automatically loaded by the bot
        ├── sprocket.py         # Automatically loaded by the API
        ├── widget.py           # Automatically loaded by the UI
        ├── routes.py           # Full-page FastHTML routes (optional)
        └── actions.py          # Scheduled background jobs (optional)
```

The five primary integration files — `cog.py`, `sprocket.py`, `widget.py`, `routes.py`, and `actions.py` — are automatically discovered and loaded by their respective framework subsystems. If your extension doesn't need a particular integration, simply omit that file.

Everything else is up to you: add more files, use subfolders, rename `blueprint.py`, or remove it entirely.

See the [example extension](../app/extensions/example/) for working samples of each file.

> [!NOTE]
> For a deep dive into how Powercord discovers and loads extension gadgets at startup, see [Extension Discovery Framework](discovery.md).

## Extension Manifest (`pyproject.toml` or `extension.json`)

Each extension declares its metadata using either a standard `pyproject.toml` (recommended for independent repositories) or an `extension.json` file.

### `pyproject.toml` Format (Recommended)

```toml
[tool.poetry]
name = "my_extension"
version = "1.0.0"
description = "What this extension does"

[tool.poetry.dependencies]
some-pkg = ">=1.0"

[tool.powercord]
discord_permissions = ["manage_channels"]
has_migrations = true
latest_migration_version = "honey0001"
internal = false
global_only = false
```

### Legacy `extension.json` Format

```json
{
    "name": "my_extension",
    "version": "1.0.0",
    "description": "What this extension does",
    "python_dependencies": ["some-pkg>=1.0"],
    "discord_permissions": ["manage_channels"],
    "has_migrations": true,
    "latest_migration_version": "honey0001",
    "internal": false,
    "global_only": false
}
```

### Manifest Fields

| Field | Type | Description |
|---|---|---|
| `name` | `string` | Extension identifier (must match the folder name). |
| `version` | `string` | Semantic version of the extension. |
| `description` | `string` | Short summary of what the extension does. |
| `python_dependencies` | `string[]` | PIP packages required by the extension. |
| `discord_permissions` | `string[]` | Discord permissions the bot needs for this extension. |
| `has_migrations` | `bool` | Whether the extension uses decoupled database tables. |
| `latest_migration_version` | `string` | The Alembic revision hash (e.g. `honey0001`) for the extension's schema. Required when `has_migrations` is `true`. Powercord's multibase discovery natively detects isolated `alembic/versions` directories hosted inside your extension, ensuring schema decoupling. |
| `internal` | `bool` | Marks the extension as shipped with the framework — the Extension Manager will prevent uninstallation. |
| `global_only` | `bool` | Hides the extension from individual Server (Guild) Dashboards, making its widgets configurable only from the Global Admin Dashboard. |

## Extension Management & Sovereign Isolation (`inv-source-isolation-no-ad-hoc-cp`)

Powercord enforces strict separation between the core framework and external extensions:
* **Source of Truth**: External extensions (`honeypot`, `midi_library`) reside strictly within their own independent git repositories (e.g. `powercord-extensions/`).
* **Zero Direct Installs in Core**: External extensions must **never** be installed into the core `powercord` repository. The core framework enforces an automatic safety guard (`_is_core_repository`) that aborts direct `just ext-install` commands to prevent dependency pollution and source contamination.
* **Downstream Integration Sandbox (`inv-downstream-integration-testbed`)**: All extension installations, multi-head Alembic migrations, and full-stack integrations are executed inside `powercord-downstream-server/`.

### Installing an Extension Downstream

```bash
cd powercord-downstream-server
just ext-install ../powercord-extensions/midi_library
```

This copies the extension files into downstream's `app/extensions/<name>/`, installs declared Python dependencies via Poetry, runs database migrations if declared, and reports required Discord permissions.

**Graceful Reinstalls for Development:**
During development, you can repeatedly run `just ext-install /path/to/extension` on an already-installed extension in downstream to cleanly overwrite it with your newest code. The CLI will safely wipe the existing downstream installation directory and intelligently check the manifests. If your `python_dependencies` and `latest_migration_version` haven't changed, it will completely skip the lengthy `poetry add` and `alembic upgrade head` phases, deploying your updates instantly.

### Uninstalling an Extension Downstream

```bash
cd powercord-downstream-server
just ext-uninstall <name>
```

Removes the extension directory and any unique Python dependencies from downstream. Warns about orphaned database tables that may need manual cleanup.

### Listing Installed Extensions

```bash
cd powercord-downstream-server
just ext-list
```

> [!NOTE]
> Installing or uninstalling extensions in downstream that add Python packages or database tables requires rebuilding the local container (`docker compose up -d --build`) and verifying on `http://localhost:5001/` before submitting pull requests.

## Extension Documentation

The `README.md` file at the root of your extension folder is highly recommended. Powercord automatically parses this file and renders its Markdown natively into the "Manage Extensions" section of the web dashboard via a "Details" modal using `marked.js`.

### Recommended README Structure

To ensure your extension looks polished in the UI, adopt this standardized outline:

- **Description** — 1–2 paragraphs detailing the extension's purpose.
- **Python Dependencies** — A bulleted list of PIP packages required by your extension.
- **Database Schema Changes** — A bulleted list outlining SQLModel models created in `blueprint.py`.
- **Features** — Subheadings explicitly listing:
  - **Bot Features (Cogs)** — Commands, Listeners, Tasks.
  - **API Routes (Sprockets)** — Endpoint summaries.
  - **UI Elements (Widgets)** — Dashboard components.

## Extension Lifecycle Hooks

Powercord provides a lightweight lifecycle-hook registry (`app/common/extension_hooks.py`) that lets extensions register callbacks for lifecycle events.

### Supported Events

| Event | Description |
|---|---|
| `delete_guild_data` | Purges all extension-specific data for a given guild. |
| `on_install` | Called after an extension is installed via the Extension Manager. |
| `on_uninstall` | Called before an extension is removed via the Extension Manager. |

### Registering a Hook

In your extension's `__init__.py`, register a callback for the desired event:

```python
from app.common.extension_hooks import register_hook

def _delete_guild_data(guild_id: int) -> None:
    # Delete your extension's guild-scoped database rows here
    ...

register_hook("my_extension", "delete_guild_data", _delete_guild_data)
```

### Delete Server Data

Server admins can trigger data deletion in two ways:

- **Dashboard UI** — A "Delete Data" button appears on each extension card in the server dashboard (only for extensions with a registered `delete_guild_data` hook). A confirmation modal prevents accidental deletions.
- **Slash Command** — `/powercord delete_server_data` presents an autocomplete dropdown of eligible extensions and a Confirm/Cancel prompt.

> [!NOTE]
> The `midi_library` extension is **excluded** from data deletion because its tables contain global data shared across all servers. See the [midi_library README](../app/extensions/midi_library/README.md) for details.
