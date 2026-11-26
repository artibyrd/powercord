# ---------------------------------------------------------------------------- #
#                                 QA COMMANDS                                  #
# ---------------------------------------------------------------------------- #

# Quality Assurance (uses _timed wrapper). Usage: just qa [--fix]
[group: "qa"]
[arg("fix", long, value="true")]
qa fix="false": install (lint fix) (format fix) check test

# Linting. Usage: just lint [--fix] (auto-fix issues)
[group: "qa"]
[arg("fix", long, value="true")]
lint fix="false":
    poetry run ruff check . {{ if fix == "true" { "--fix" } else { "" } }}
alias lc := lint

# Formatting. Usage: just format [--fix] (apply formatting, otherwise check-only)
[group: "qa"]
[arg("fix", long, value="true")]
format fix="false":
    poetry run ruff format . {{ if fix == "false" { "--check" } else { "" } }}

# Type Checking (Mypy)
[group: "qa"]
typecheck:
    just _run-with-status _check
alias mypy := typecheck
alias tc := typecheck

[private]
_check:
    poetry run mypy .

# Fast hermetic pre-commit QA gate (lint + format + test-gov, zero DB)
[group: "qa"]
check:
    poetry run ruff check .
    poetry run ruff format --check .
    poetry run pytest tests/governance -q --no-cov

# Run shift-left governance tests (~3s, zero DB)
[group: "qa"]
test-gov:
    poetry run pytest tests/governance -v --no-cov

# Validate powercord-agent plugin layout, skills, overlays, and hooks
[group: "qa"]
agent-check:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -d "../powercord-agent" ]; then
        echo "Skipping agent-check: sibling ../powercord-agent not found."
        exit 0
    fi
    python3 ../powercord-agent/scripts/lint_skills.py
    if [ -d "../powercord-agent/tests" ]; then
        python3 -m unittest discover -s ../powercord-agent/tests -v
    fi
    if command -v agy >/dev/null 2>&1; then
        agy plugin validate --strict ../powercord-agent
    else
        echo "Note: 'agy' CLI not found on PATH; skipping 'agy plugin validate --strict'."
    fi

# Sync canonical skill overlays from sibling powercord-agent into standalone .agents/overrides/
[group: "qa"]
sync-overlays:
    #!/usr/bin/env bash
    set -euo pipefail
    src="../powercord-agent/overrides"
    dest=".agents/overrides"
    if [ ! -d "$src" ]; then
        echo "ERROR: Canonical overlays directory not found at $src" >&2
        exit 1
    fi
    mkdir -p "$dest"
    rm -f "$dest"/*.md
    cp "$src"/*.md "$dest"/
    count=$(find "$dest" -maxdepth 1 -name '*.md' | wc -l)
    echo "Synced ${count} skill overlay(s) into ${dest}/"

# Run tests. Usage: just test [--type unit|integration|all]
[group: "qa"]
[arg("type", long)]
test type="": _ensure-db lint
    just _run-with-status _test {{ if type != "" { "--type " + type } else { "" } }}
alias t := test

[private]
[arg("type", long)]
_test type="":
    #!/usr/bin/env bash
    if [ "{{type}}" = "all" ]; then
      poetry run pytest tests
    elif [ "{{type}}" != "" ]; then
      poetry run pytest tests -m "{{type}}"
    else
      poetry run pytest tests -m "not integration"
    fi

# Run tests and generate coverage report
[group: "qa"]
coverage: _ensure-db lint
    poetry run pytest --cov=app --cov-report=term-missing

# Run verification tests for the new dashboard features
[group: "qa"]
verify-dashboard: _ensure-db lint
    poetry run pytest tests/unit/test_internal_server.py tests/unit/test_ui_components.py tests/integration/test_admin_routes.py tests/integration/test_public_home.py
