---
description: Seamlessly clones the Powercord framework into a new downstream deployment, provisions the container environment, and natively configures core extensions.
---
# Fresh Install Downstream Deployment

## Steps
1. Navigate to the upstream `powercord` repository and execute `just init-target "a:\Dev\Google\bards-guild-midi-project-3"` (or your desired target path). This creates a fresh deployment clone locally and completely disables upstream pushes to safeguard the core framework.
2. Inside your newly initialized target (`bards-guild-midi-project-3`), manually securely deposit your internal secret profiles (`.env` and `.env.prod`).
3. From the target directory, spin up the base core architecture by executing `just rebuild-target`. Wait until the container volume attaches and standardizes structurally.
4. Execute dependency builds sequentially for each tracked extension instance you require on this deployment profile: `just ext-install "..\powercord-extensions\midi_library"` and `just ext-install "..\powercord-extensions\honeypot"`.
5. Tail your Uvicorn logs (`docker compose logs -f api`) to confirm zero schema resolution failures on standard loopback boot.
