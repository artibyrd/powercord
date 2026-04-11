---
description: Purges the bards-guild-midi-project-3 downstream mirror, resets the Docker volume, safely integrates internal extensions while bypassing Unicode crashes, and cleanly boots the loopback integration.
---
# Fresh Install Downstream Deployment

## Steps
1. Navigate to `a:\Dev\Google\bards-guild-midi-project-3` and execute `docker compose down -v` to aggressively purge all legacy Postgres database schemas from previous runs. Wait until the volume is successfully dropped.
2. Mirror the raw environment by running `robocopy a:\Dev\Google\powercord a:\Dev\Google\bards-guild-midi-project-3 /MIR /XD .git .venv __pycache__ .pytest_cache .mypy_cache /XF .env docker-compose.override.yml`. Note that an exit code of 1 implies a successful copy in PowerShell for `robocopy`.
3. Because native mirroring flags trailing extension files as `*EXTRA Dir` without properly dissolving their locked dependencies, explicitly enforce deletion by running `Remove-Item -Recurse -Force a:\Dev\Google\bards-guild-midi-project-3\app\extensions\<extension_name>` and `tests\extensions\<extension_name>` for all incoming extensions (e.g., `midi_library` and `honeypot`).
4. Initialize the overarching database layer empty prior to extensions by executing `docker compose up -d --build`. This prevents simultaneous Alembic insertions from crashing logic loops on boot.
5. In PowerShell, sequentially run the dependency installers using `$env:PYTHONIOENCODING="utf8"; just ext-install "..\powercord-extensions\<extension_name>"` for each extension required (e.g. `midi_library` and `honeypot`). Enforcing `utf8` is mandatory to avoid terminal emoji rendering faults on Windows. Confirm dependencies like `librosa` were seeded natively!
6. Validate and compress the final state by executing `just run-clean`. Tail the Uvicorn terminal logs to verify standard `Application startup complete.` and zero internal schema location failures!
