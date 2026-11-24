# Command Approval Bootstrapping Policy for Powercord

Self-contained safe command approval guide for priming read-only developer checks in a fresh Powercord workspace.

## Overrides

- **Safe Read-Only Powercord Recipe Set**: Present a confirmation table first, then invoke each safe read-only command as its own discrete top-level shell call so the operator can selectively choose "Always Allow":
  1. `just check` — Hermetic `<3s` lint, format check, and Tier 2 governance suite (in `powercord/`).
  2. `just typecheck` — Mypy static type analysis (in `powercord/`).
  3. `just test-gov` — Tier 2 governance test suite (in `powercord/`).
  4. `just status-all` — Multi-repo git status inspection across the ecosystem (in `powercord/`).
  5. `just ext-list` — List installed server or client extensions.
  6. `just prod-status` — Read-only GCP VM, container tag, and backup status inspection.
  7. `git status -s` — Fast local working tree inspection.
- **Strict No-Spicy-Prefixes & Production Exclusion Rule**:
  - Never prime or ask to "Always Allow" broad wrapper prefixes (`poetry run`, `python3`, `bash`, `sh`, `docker`, `gcloud`, `gh`, `rm`) that could approve arbitrary commands.
  - Never prime destructive or production-mutating recipes (`just gcp-build`, `just prod-deploy`, `just prod-rollback`, `just prod-db-restore`, `just tf-apply`, `just tf-destroy`, `terraform apply`, `terraform destroy`). These remain explicitly gated per invocation (`inv-no-unauthorized-gcp-deploy`).

## Extensions

- **Optional Read-Only Agent Validation Commands**: When actively working on `powercord-agent/`, you may also include these read-only commands in the confirmation table:
  - `just agent-check` (from `powercord/`).
  - `agy plugin validate --strict powercord-agent/` (when the `agy` CLI is installed).
- **Subprocess Isolation Enforcement**: Always issue one discrete command per tool call; never batch approvals behind a wrapper script or shell chain (`&&` / `;`), because chaining breaks prefix-based approval matching.

## Disabled / Not Applicable

- **Retired Global Justfile Commands (`just -g status`, `just -g normalize-all`)**: Permanently disabled; user-level dotfile Justfiles violate `inv-repo-bound-task-runners`.
- **Removed `just bootstrap-approvals` Recipe**: Removed from `powercord/Justfile` because wrapping approvals inside a single `just` recipe violates subprocess isolation. Do not recreate it.
