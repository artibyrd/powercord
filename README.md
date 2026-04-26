# Powercord
__*Powercord is an opinionated full stack python based development framework for building and managing Discord bots with advanced functionality.*__

## Description
Powercord provides a framework for building full featured web applications with a Discord bot at its core.  Powercord is _opinionated_ and focused on _simplicity_.  It is entirely written in Python (backend _and_ frontend!) and can be run locally or deployed to a Google Compute Engine virtual machine instance with a few simple commands.

## Main Features
- **Modular Discord bot framework**
    - Bot features are contained within "cogs" that can be individually loaded or unloaded via slash commands in Discord or from the web interface, without taking the bot offline.
- **Web interface with Discord OAuth**
    - Use your Discord login to access an admin web interface for the bot.  Bot features can also include a web frontend "widget", and be made publicly available or restricted to Discord server members, specific roles, or admin only.
- **Integrated API layer**
    - Easily and securely expose Discord bot functionality to other applications with a simple REST API.  Map endpoints as "sprockets" associated with bot cogs, so when a cog is disabled, its API endpoints are also automatically disabled.
- **SQL database support**
    - An integrated Postgresql database is accessible to the bot, API, and UI components.  Easily add new tables to support your own complex relational data structures.
- **Easy deployment**
    - Powercord is built into a _single_ Docker image and can be run locally (only recommended for development/testing), or easily deployed to any Cloud hosting provider that supports containerized workloads.   Detailed configuration and instructions are provided only for deployment to a Google Compute Engine virtual machine instance.


## Components
- **[Python 3.12](https://docs.python.org/release/3.12.0/)**
    - Nextcord (bot framework), FastAPI (API framework), and FastHTML (frontend framework) are all Python applications.
- **[Poetry](https://python-poetry.org/)**
    - Poetry is used for Python dependency management.
- **[Nextcord](https://docs.nextcord.dev/en/stable/)**
    - Nextcord is a python SDK for Discord.  This provides the core Discord bot functionality for Powercord.
- **[FastAPI](https://fastapi.tiangolo.com/)**
    - FastAPI is a python framework for building REST APIs.  Powercord uses this to expose certain bot features as API endpoints.
- **[FastHTML](https://www.fastht.ml/)**
    - FastHTML is a python based frontend framework that shares similarities with FastAPI.  FastHTML is used to provide a web based admin control panel for Powercord, and can be extended to make your own Discord integrated application frontends.
- **[Postgresql](https://www.postgresql.org/docs/current/)**
    - Postgresql is a full featured relational database, providing long term data storage and advanced querying capabilities to Powercord.
- **[Nginx](https://nginx.org/en/docs/index.html)**
    - Nginx is used as a reverse proxy to serve the frontend FastHTML application and manage the backend FastAPI endpoints.
- **[Docker](https://www.docker.com/)**
    - Docker is used to package Powercord into a single container image that can be easily run locally or deployed to a cloud hosting provider.
- **[Packer](https://www.docker.com/)**
    - Packer is used to build a Google Compute Engine virtual machine server image that runs Powercord as a containerized workload.
- **[Just](https://just.systems/)**
    - Just is a command runner that makes it easy to interact with this project by running simple `just` recipes.  All commands to test, run, and deploy Powercord are located in the [Justfile](Justfile).  Install [just](https://just.systems/man/en/packages.html) and run `just` from the command line in the root folder of this project to see a list of available just recipes.


## Installation


### Prerequisites
- [Poetry](https://python-poetry.org/docs/#installation)
- [Docker](https://docs.docker.com/get-docker/) (for local containerized run)
- [Just](https://just.systems/man/en/chapter_4.html) (optional but recommended)

### Configuration
1. Copy `.example.env` to `.env`:
   ```bash
   cp .example.env .env
   ```
2. Update `.env` with your Discord Token and other secrets.

### Local Development
1. Install dependencies:
   ```bash
   just install
   ```

   > **Heads Up:** To access the restricted Admin Dashboard, you must manually add your Discord User ID as an admin.
   > ```bash
   > just add-admin <YOUR_DISCORD_ID> "Initial Admin"
   > ```
   > _Replace `<YOUR_DISCORD_ID>` with your actual Discord User ID (e.g., 1234567890)._

2. Initialize the database:
   ```bash
   just db-upgrade
   ```
3. Run the stack:
   ```bash
   just dev
   ```

### Quality Assurance
Run the QA suite (linting, formatting, security checks, type checks, and tests):
```bash
just qa
```

#### Test Coverage Profile
Certain files are explicitly omitted from standard pytest coverage tracking (configured in `pyproject.toml`). These omissions generally fall into the following categories:
- **Entry Points & Application Plumbings** (`app/main_bot.py`, `app/main_api.py`, `app/main_ui.py`): Files that predominantly bootstrap frameworks or run server loops. These are difficult to isolate with unit tests without standing up full environments and yield low value for strict coverage constraints.
- **UI Renderers & Discord Views** (`app/ui/dashboard.py`, `app/ui/helpers.py`, `app/bot/views.py`): Files purely focused on layout components and markup generation (FastHTML/Nextcord views) where coverage tracking often necessitates overly complex mocking of external state that does little to guarantee production functional correctness. End-to-end tests provide better guarantees here.
- **Reference Code** (`app/extensions/example/*`): Boilerplate template code meant solely as a reference guide rather than core functional logic.

### Running locally
Powercord provides two primary methods for running the application locally: Local Development (`just dev`) and Containerized Development (`just run`).

#### Local Development (`just dev`)
Running `just dev` starts each of the application components (Bot, API, UI) directly on your host machine.
- **Database**: Connects to the host machine's local PostgreSQL instance (typically `localhost:5433`).
- **Use Case**: Best for rapid development, testing, and debugging.
- **System Restarts**: The system restart buttons in the Admin Dashboard rely on an external process manager to restart the services gracefully. When running `just dev` without containerization, terminating a component will stop it, but not automatically restart it. To fully test restart functionality, use `just run`.

#### Containerized Development (`just run`)
Running `just run` spins up the entire application stack inside Docker containers using Docker Compose.
- **Database**: Uses a dedicated Docker-managed volume (`postgres_data`). This database is completely separate from your host machine's local database. It is exposed to the host machine on port `5433` so that local CLI commands (like `just db-upgrade`) function seamlessly using the `.env` file, while internal Dockerized applications securely resolve to the native `5432` port via an environment override.
  - *Note*: If you run `just run` for the first time, the Docker database will be empty. You will need to run the database migrations and manually add your user as an admin again inside the container environment.
- **Shared Sessions**: Because both `just dev` and `just run` use the same local `.env` file (which contains your `SESSION_KEY`), your browser session cookies remain valid across both environments. If you login during `just dev` and then switch to `just run`, the UI will still recognize your session, but since the Docker database is empty, your admin permissions will be revoked and you'll be redirected to your profile until you add yourself as an admin to the container's database.

## Deployment
_Currently, Powercord only provides complete deployment options for deploying to Google Cloud Platform as a Google Compute Engine virtual machine instance. You can also build the Powercord container image and manually deploy it to a different cloud hosting solution of your choice._

### Hosting prerequisites
- A Google Cloud Platform project
- `gcloud` CLI installed and authenticated
- Enable Compute Engine API and Cloud Build API

### Cloudflare and SSL Integration
To front your Powercord deployment with Cloudflare and properly utilize SSL (preventing `522 Connection Timed Out` errors):
1. **Cloudflare "Full" Mode**: 
   By default, Powercord auto-generates a self-signed SSL certificate at startup to serve HTTPS traffic over port 443. This requires zero configuration and perfectly satisfies Cloudflare's standard **"Full"** SSL/TLS encryption mode setting.
   
2. **Cloudflare "Full (strict)" Mode**: 
   If your deployment demands strict origin CA validation, you must configure `POWERCORD_SSL_CERT` and `POWERCORD_SSL_KEY` variables inside your Google Secret Manager environment secrets. Provide them your valid multi-line Cloudflare Origin CA certificate and private key. The deployment will deploy these instead of using the self-signed fallback.

## Extending Powercord
Powercord gives you a framework that lets you get straight to adding your own python application code within minutes.  Simply add your own extensions in the `app/extensions` folder with the following structure:
```
app
└── extensions
    └── example         # Folder with extension name
        ├── README.md       # Include documentation for your extensions!
        ├── __init__.py     # Do init stuff here if you're into that
        ├── blueprint.py    # Main functionality goes here, then imported into other files
        ├── cog.py          # Automatically loaded by bot
        ├── sprocket.py     # Automatically loaded by API
        └── widget.py       # Automatically loaded by UI
```
The `cog.py`, `sprocket.py`, and `widget.py` files for your extension will be automatically loaded by the bot, API, and UI components respectively.  If your extension doesn't need one of these components, simply don't include a file for that integration.  You can add more files, use subfolders, rename blueprint.py or even delete it entirely - you are free to otherwise organize your extension however you like.  Only `cog.py`, `sprocket.py`, and `widget.py` are required - your extension must have at least one of these three files.  See the [example extension](app/extensions/example/) for examples on how to use each of these files in more detail.

### Extension Management
Powercord extensions can be maintained in their own repositories and installed/uninstalled via the extension manager CLI.  Internal extensions (`example`, `utilities`) ship with the framework; external extensions (e.g. `honeypot`, `midi_library`) live in separate repositories.

#### Installing an Extension
```bash
just ext-install /path/to/extension
```
This copies the extension files into `app/extensions/<name>/`, installs any declared Python dependencies via Poetry, runs database migrations if needed, and reports required Discord permissions.

**Graceful Reinstalls for Development:**
During development, you can repeatedly run `just ext-install /path/to/extension` on an already installed extension to cleanly overwrite it with your newest code. The CLI will safely wipe the existing installation directory and intelligently check the manifests. If your `python_dependencies` and `latest_migration_version` haven't changed, it will completely skip the lengthy `poetry add` and `alembic upgrade head` phases, deploying your updates instantly.

#### Uninstalling an Extension
```bash
just ext-uninstall <name>
```
Removes the extension directory and any unique Python dependencies.  Warns about orphaned database tables that may need manual cleanup.

#### Listing Installed Extensions
```bash
just ext-list
```

#### Extension Manifest (`extension.json`)
Each extension includes an `extension.json` file declaring its metadata:
```json
{
    "name": "my_extension",
    "version": "1.0.0",
    "description": "What this extension does",
    "python_dependencies": ["some-pkg>=1.0"],
    "discord_permissions": ["manage_channels"],
    "has_migrations": true,
    "latest_migration_version": "1c7fc4ef8015",
    "internal": false,
    "global_only": false
}
```
**Key Flags:**
- `internal`: Tells the Extension Manager that this extension is shipped with the framework itself and should not be uninstalled.
- `global_only`: Hides the extension from individual Server (Guild) Dashboards, making its widgets configurable only from the Global Admin Dashboard.
- `has_migrations`: Identifies if the extension utilizes decoupled database tables.
- `latest_migration_version`: If `has_migrations` is true, this declares the specific independent `alembic` revision hash (e.g. `honey0001`) that models your tables. Powercord's multibase discovery natively detects isolated `alembic/versions` directories hosted inside your extension, ensuring schema decoupling.

> [!NOTE]
> Installing or uninstalling extensions that add Python packages or database tables requires rebuilding the Docker image and redeploying for production use.

### Extension Documentation
The `README.md` file located at the root of your extension folder is highly recommended. Powercord automatically parses this file and renders its markdown natively into the "Manage Extensions" section of the web dashboard via a "Details" modal using `marked.js`.

To ensure your extension looks stunning in the UI, we recommend adopting a standardized README structure:
- **Description**: 1-2 paragraphs detailing the extension's purpose.
- **Python Dependencies**: A bulleted list of PIP packages required by your extension.
- **Database Schema Changes**: A bulleted list outlining SQLModel models created in `blueprint.py`.
- **Features**: Subheadings explicitly listing **Bot Features (Cogs)** (Commands, Listeners, Tasks), **API Routes (Sprockets)**, and **UI Elements (Widgets)**.

### Extension Lifecycle Hooks
Powercord provides a lightweight lifecycle hook registry (`app/common/extension_hooks.py`) that lets extensions register callbacks for lifecycle events. Currently supported events:

| Event | Description |
|---|---|
| `delete_guild_data` | Purges all extension-specific data for a given guild. |
| `on_install` | Called after an extension is installed via the extension manager. |
| `on_uninstall` | Called before an extension is removed via the extension manager. |

#### Registering a Hook
In your extension's `__init__.py`, register a callback for the event:
```python
from app.common.extension_hooks import register_hook

def _delete_guild_data(guild_id: int) -> None:
    # Delete your extension's guild-scoped database rows here
    ...

register_hook("my_extension", "delete_guild_data", _delete_guild_data)
```

#### Delete Server Data
Server admins can trigger data deletion in two ways:
- **Dashboard UI**: A "Delete Data" button appears on each extension card in the server dashboard (only for extensions with a registered hook). A confirmation modal prevents accidental deletions.
- **Slash Command**: `/powercord delete_server_data` — presents an autocomplete dropdown of eligible extensions and a Confirm/Cancel prompt.

> [!NOTE]
> The `midi_library` extension is **excluded** from data deletion because its tables contain global data shared across all servers. See [midi_library README](app/extensions/midi_library/README.md) for details.

## API Security and Management
Powercord implements a robust security model for both its internal and external APIs:
- **Admin API**: Uses a database-backed, auto-generated secure key ensuring only trusted system components can access it. In addition, an IP restriction middleware ensures the Admin API is only accessible from local networks.
- **Sprocket API**: Secured using a unified authentication dependency supporting both API Keys and Discord OAuth tokens.
- **Granular Scopes**: API endpoints require specific scopes. For example, sprockets use scopes tied to their extension name (e.g., `honeypot`), while the internal API requires a `global` scope.
- **JSON Structured Logging**: All API access (both Admin and Sprocket) is logged in a structured JSON format to `stdout`. This captures request paths, execution times, and client identities, making it ideal for ingestion and analysis by external logging services like Google Cloud Logging.

### Viewing API Documentation
The auto-generated FastAPI Swagger documentation endpoints (`/docs` and `/openapi.json`) are secured behind the same authentication requirements as the rest of the API to prevent unauthorized configuration analysis.
- **Browser Access**: To view the interactive Swagger docs in a browser, append a valid API key using the `token` query parameter: `http://localhost:8000/docs?token=YOUR_API_KEY`
- **Postman/cURL**: To interact with the documented endpoints programmatically, set the standard `Authorization: Bearer YOUR_API_KEY` header in your requests.

### Managing Third-Party API Keys
You can generate and manage API keys for 3rd party integrations using the built-in CLI commands from your terminal:
- **Add a new key**: `just add-api-key <name> <scopes>` (e.g., `just add-api-key myapp '["global", "honeypot"]'`)
- **List all keys**: `just list-api-keys`
- **Revoke a key**: `just revoke-api-key <name>`

## Database Management
Powercord provides commands to easily export and import your Postgres database, seamlessly handling the difference between local machine instances and isolated Docker containers.

> [!NOTE]
> **Host Requirements**: If you are running `just dev` (Local Development), these commands require the PostgreSQL command-line tools (`pg_dump` and `psql`) to be installed and available in your system's `PATH`. If you are using `just run`, these tools are automatically executed inside the Docker container and do not need to be installed on your host machine.
> - **Windows**: Download the [PostgreSQL Windows Installer](https://www.postgresql.org/download/windows/), install the "Command Line Tools", and add `C:\Program Files\PostgreSQL\<version>\bin` to your system Environment Variables `PATH`.
> - **macOS**: `brew install postgresql`
> - **Linux (Ubuntu/Debian)**: `sudo apt install postgresql-client`

To create a SQL backup of your current database:
```bash
just db-export [filename.sql]
```
*(If no filename is provided, it defaults to `powercord-export.sql`. Use the `--migration` flag if exporting data to an environment that already has initialized database schema tables.)*

To manually trigger the background daily backup process (creates a timestamped backup file in `/var/lib/postgresql/data/backups`):
```bash
just db-backup
```

To restore a database back into the system from a SQL file:
```bash
just db-import <filename.sql>
```

> [!TIP]
> **Migrating between environments**: The `just dev` (Local) and `just run` (Containerized) environments use two completely different Postgres databases. If you wish to migrate your local data into the Docker container, run `just db-export my-local-db.sql` while the local environment is active, then terminate it. Start the containerized app with `just run`, let the blank database initialize, and run `just db-import my-local-db.sql` in a new terminal window to migrate your data!

## Further Reading
- **[Fresh Setup Guide](docs/SETUP.md)** - Instructions on how to clone, install extensions, and run Powercord from scratch.
- **[Google Cloud Platform Deployment Guide](docs/GCP.md)** - Guide for deploying the Powercord framework to a GCP virtual machine.
- **[About Powercord Cog Hotloading](docs/cogs.md)** - Details on the dynamic hotloading and unloading of Discord cogs.
- **[Database Documentation](docs/db.md)** - Reference for database management, models, and migrations.
- **[Core Utilities Documentation](docs/utilities.md)** - Overview of reusable components available across the API, Bot, and UI layers.
- **[Testing Guide](docs/TESTING.md)** - Comprehensive testing guide covering execution, coverage targets, and test organization.
- **[Swagger UI Styling Guide](docs/swagger_styling.md)** - Information on customizing the Swagger API docs with dark themes and CSS overrides.

## LLMS Files
Included are LLMS files for [Discord](docs/llms/discord-llms.txt), [FastHTML](docs/llms/fasthtml-llms.txt), and [Pydantic](docs/llms/pydantic-llms.txt), to give large language models better introspection for more useful code assist.


## Utilities Extension
The **Utilities Extension** includes a **Discord Permission Auditor** feature.
- **Requirements**:
    - The bot requires `Manage Roles` and `Manage Channels` permissions (or `Administrator`) to strictly read all permission overwrites.
    - The bot's role must be **higher** in the hierarchy than the roles it is auditing to view/manage them correctly in some cases.
- **Usage**:
    - Run the `$audit` or `/audit` command in your Discord server to fetch and store the latest permission data.
    - View the "Permission Auditor" widget in the Dashboard to visualize role and channel permissions, including category inheritance.
