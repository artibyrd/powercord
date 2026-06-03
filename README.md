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
- **[Python 3.12](https://docs.python.org/release/3.12.0/)** — Nextcord (bot), FastAPI (API), and FastHTML (frontend) are all Python applications.
- **[Poetry](https://python-poetry.org/)** — Python dependency management.
- **[Nextcord](https://docs.nextcord.dev/en/stable/)** — Python SDK for Discord, providing core bot functionality.
- **[FastAPI](https://fastapi.tiangolo.com/)** — REST API framework for exposing bot features as API endpoints.
- **[FastHTML](https://www.fastht.ml/)** — Python-based frontend framework for the web admin control panel.
- **[Postgresql](https://www.postgresql.org/docs/current/)** — Relational database for long-term data storage and advanced querying.
- **[Nginx](https://nginx.org/en/docs/index.html)** — Reverse proxy for the frontend and API.
- **[Docker](https://www.docker.com/)** — Single container image for local and cloud deployment.
- **[Packer](https://www.packer.io/)** — Builds GCE VM server images for containerized workloads.
- **[Just](https://just.systems/)** — Command runner for all project recipes.  Run `just` from the project root to see available commands.

## Quick Start

### Prerequisites
- [Poetry](https://python-poetry.org/docs/#installation)
- [Docker](https://docs.docker.com/get-docker/) (for local containerized run)
- [Just](https://just.systems/man/en/chapter_4.html) (optional but recommended)

### Setup
```bash
# 1. Configure environment
cp .example.env .env
# Edit .env with your Discord Token and other secrets

# 2. Install dependencies
just install

# 3. Initialize database
just db-upgrade

# 4. Add yourself as admin
just add-admin <YOUR_DISCORD_ID> "Initial Admin"

# 5. Run the stack
just dev
```

> [!TIP]
> See the [Fresh Setup Guide](docs/SETUP.md) for detailed instructions including extension installation, containerized development, and environment migration.

### Quality Assurance
```bash
just qa        # Run linting, formatting, security checks, type checks, and tests
just qa fix    # Same, but auto-fix lint and formatting issues
```

## Documentation

| Guide | Description |
|-------|-------------|
| **[Fresh Setup Guide](docs/SETUP.md)** | Clone, install extensions, and run Powercord from scratch |
| **[Extending Powercord](docs/extensions.md)** | Extension framework: creating, managing, and publishing extensions |
| **[API Security & Management](docs/api.md)** | API authentication, scopes, Swagger docs, and API key management |
| **[Database Documentation](docs/db.md)** | Database management, models, migrations, and automated backups |
| **[GCP Deployment Guide](docs/GCP.md)** | Deploying Powercord to Google Cloud Platform |
| **[Testing Guide](docs/TESTING.md)** | Test execution, coverage targets, and database provisioning |
| **[Extension Discovery](docs/discovery.md)** | How Powercord auto-discovers and loads extension components |
| **[Cog Hotloading](docs/cogs.md)** | Dynamic loading and unloading of Discord cogs |
| **[Core Utilities](docs/utilities.md)** | Reusable API, Bot, and UI components |
| **[Swagger Styling](docs/swagger_styling.md)** | Customizing the Swagger API docs with dark themes |
| **[Legacy V2 Migration](docs/LEGACY_V2_MIGRATION.md)** | Migrating from Powercord V2 to V3 |

## LLMS Files
Included are LLMS files for [Discord](docs/llms/discord-llms.txt), [FastHTML](docs/llms/fasthtml-llms.txt), and [Pydantic](docs/llms/pydantic-llms-full.txt), to give large language models better introspection for more useful code assist.
