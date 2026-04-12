---
description: Seamlessly clones the Powercord framework into a new downstream deployment, provisions the container environment, and natively configures core extensions.
---
# Fresh Install Downstream Deployment

## Steps
1. Navigate to the upstream `powercord` repository and execute `just init-target "a:\Dev\Google\bards-guild-midi-project-3"` (or your desired target path). This creates a fresh deployment clone locally and completely disables upstream pushes to safeguard the core framework.
2. Inside your newly initialized target, manually deposit your internal secret profiles (`.env` and `.env.prod`).
3. From the target directory, install Python dependencies: `just install`. This creates the local `.venv` and seeds all framework dependencies.
4. Spin up the base container and database: `just rebuild-target`. Wait until the container starts and database volume initializes.
5. Install extensions sequentially (on Windows, prefix with `$env:PYTHONIOENCODING="utf8"` to avoid terminal emoji rendering faults):
   - `just ext-install "..\powercord-extensions\midi_library"`
   - `just ext-install "..\powercord-extensions\honeypot"`
6. Run `just rebuild-target` once more to bake the installed extension code into the Docker image.
7. Tail your Uvicorn logs (`docker compose logs -f app`) to confirm `Application startup complete.` and zero schema resolution failures.
