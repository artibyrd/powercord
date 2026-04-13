---
description: Seamlessly clones the Powercord framework into a new downstream deployment, provisions the container environment, and natively configures core extensions.
---
# Fresh Install Downstream Deployment

This workflow sets up a fresh downstream deployment from the upstream core framework. 

## Pre-requisite: Teardown
If updating an existing target directory, completely wipe it first to avoid artifacts.
```powershell
// turbo
# Stop running containers and destroy the old database volume
cd "a:\Dev\Google\bards-guild-midi-project-3"
if (Test-Path "docker-compose.yml") { docker compose down -v }
cd ..
Remove-Item -Recurse -Force "a:\Dev\Google\bards-guild-midi-project-3"
```

## Steps

1. **Deploy Target:** Navigate to the upstream `powercord` repository and execute `init-target`. This safely creates a clone and disables upstream pushes to protect the core framework.
```powershell
// turbo
cd "a:\Dev\Google\powercord"
just init-target "a:\Dev\Google\bards-guild-midi-project-3"
```

2. **Migrate Secrets:** Copy your internal security profiles.
```powershell
// turbo
Copy-Item -Path "a:\Dev\Google\powercord\.env" -Destination "a:\Dev\Google\bards-guild-midi-project-3\.env" -Force
Copy-Item -Path "a:\Dev\Google\powercord\.env.prod" -Destination "a:\Dev\Google\bards-guild-midi-project-3\.env.prod" -Force
```

3. **Dependency Seeding:** Install Python requirements in the new target to generate the `.venv`.
```powershell
// turbo
cd "a:\Dev\Google\bards-guild-midi-project-3"
just install
```

4. **Containerization:** Spin up the base container and database. Wait until PostgreSQL is fully responsive.
```powershell
// turbo
cd "a:\Dev\Google\bards-guild-midi-project-3"
just rebuild-target
```

5. **Extension Injection:** Natively install domain-specific endpoints and capabilities.
```powershell
// turbo
cd "a:\Dev\Google\bards-guild-midi-project-3"
just ext-install "..\powercord-extensions\midi_library"
just ext-install "..\powercord-extensions\honeypot"
```

6. **Image Bake-in:** Execute a final rebuild to inject extension artifacts into the persistent Docker image.
```powershell
// turbo
cd "a:\Dev\Google\bards-guild-midi-project-3"
just rebuild-target
```

7. **Validation:** Ensure clean startup via `docker compose logs`. Verify that Uvicorn logs `Application startup complete.` and extension components mounted natively.
```powershell
// turbo
cd "a:\Dev\Google\bards-guild-midi-project-3"
docker compose logs --tail 30 app
```
