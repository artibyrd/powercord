# Powercord Development Kit - Shared Recipes
# Import this file to access common development utilities.
# Usage: import 'devkit.just' (from powercord) or import? '../../powercord/devkit.just' (from extensions)

# Ensures the database service is running via Docker
[private]
_ensure-db:
    #!powershell
    $portInUse = Get-NetTCPConnection -LocalPort 5433 -State Listen -ErrorAction SilentlyContinue
    if (-not $portInUse) {
        Write-Host "Starting local dev database container..."
        docker rm -f powercord-pg-dev 2>$null | Out-Null
        docker run -d --name powercord-pg-dev -p 5433:5432 `
            -e POSTGRES_USER=$env:POWERCORD_POSTGRES_USER `
            -e POSTGRES_PASSWORD=$env:POWERCORD_POSTGRES_PASSWORD `
            -e POSTGRES_DB=$env:POWERCORD_POSTGRES_DB `
            -v powercord_pg_dev_data:/var/lib/postgresql/data `
            postgres:15 | Out-Null
        Write-Host "Waiting for database to be ready..."
        Start-Sleep -Seconds 5
    }

# Stops the standalone local dev database container if it's running
[private]
[no-exit-message]
_teardown-dev-db:
    #!powershell
    docker rm -f powercord-pg-dev 2>$null | Out-Null
    exit 0
