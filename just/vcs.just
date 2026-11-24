# ---------------------------------------------------------------------------- #
#                                VCS COMMANDS                                  #
# ---------------------------------------------------------------------------- #

# Inspect git status across all ecosystem repositories
[group: "vcs"]
status-all:
    #!/usr/bin/env bash
    set -euo pipefail
    for r in . ../powercord-client ../powercord-agent ../powercord-extensions/* ../powercord-client-extensions/* ../powercord-downstream-server; do
        if [ -d "$r/.git" ]; then
            echo "=== Git Status: $(basename "$(cd "$r" && pwd)") ==="
            (cd "$r" && git status -s)
        fi
    done

# Create or switch to a feature branch (never work directly on main)
[group: "vcs"]
branch name:
    git checkout -b {{name}} 2>/dev/null || git checkout {{name}}

# Incremental commit on feature branch gated by pre-commit check
[group: "vcs"]
commit msg: check
    #!/usr/bin/env bash
    current=$(git symbolic-ref --short HEAD 2>/dev/null)
    if [ "$current" = "main" ]; then
        echo "ERROR: Direct commits to main prohibited by inv-branch-pr-review-gate. Use: just branch feat/<name>"
        exit 1
    fi
    git add -A
    git commit -m "{{msg}}"

# Push feature branch and open a GitHub pull request (gated by validate_pr.py)
[group: "vcs"]
pr-create title="":
    #!/usr/bin/env bash
    set -euo pipefail
    current=$(git symbolic-ref --short HEAD 2>/dev/null || true)
    if [ -z "$current" ]; then
        echo "ERROR: Detached HEAD; checkout a feature branch before opening a PR." >&2
        exit 1
    fi
    if [ "$current" = "main" ]; then
        echo "ERROR: Cannot open PR from main branch." >&2
        exit 1
    fi
    if [ -n "{{title}}" ]; then
        python3 scripts/validate_pr.py --branch "$current" --pr-title "{{title}}"
    else
        python3 scripts/validate_pr.py --branch "$current"
    fi
    git push -u origin "$current"
    if [ -n "{{title}}" ]; then
        gh pr create --title "{{title}}" --fill
    else
        gh pr create --fill
    fi

# Check pull request status for the current branch
[group: "vcs"]
pr-status:
    gh pr status

# Release tag sequence (run on main after PR merge)
[group: "vcs"]
release version message: check
    #!/usr/bin/env bash
    current=$(git symbolic-ref --short HEAD 2>/dev/null)
    if [ "$current" != "main" ]; then
        echo "ERROR: Releases must be tagged on the main branch after PR merge."
        exit 1
    fi
    poetry version {{version}}
    git add Justfile pyproject.toml tests/governance/test_version_and_manifest_parity.py
    git commit --allow-empty -m "chore(release): bump version to {{version}}"
    git tag -a "v{{version}}" -m "{{message}}"
    git push origin main "v{{version}}"
    echo "Release v{{version}} tagged and pushed successfully."
