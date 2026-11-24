# use with https://just.systems

# ---------------------------------------------------------------------------- #
#                                 SETTINGS                                     #
# ---------------------------------------------------------------------------- #

set shell := ["bash", "-cu"]
set export
set dotenv-load
set unstable  # required for [parallel] in just/dev.just
set positional-arguments := true

export PYTHONIOENCODING := "utf8"


# ---------------------------------------------------------------------------- #
#                                  IMPORTS                                     #
# ---------------------------------------------------------------------------- #

import 'devkit.just'
import 'just/dev.just'
import 'just/qa.just'
import 'just/db.just'
import 'just/vcs.just'
import 'just/prod.just'

# Import internal extension justfiles (optional, only loaded when present)
import? 'app/extensions/example/extension.just'
import? 'app/extensions/utilities/extension.just'


# ---------------------------------------------------------------------------- #
#                               DEFAULT RECIPE                                 #
# ---------------------------------------------------------------------------- #

# Default: List available just commands
default:
    @just --list --unsorted


# ---------------------------------------------------------------------------- #
#                                 EXTENSIONS                                   #
# ---------------------------------------------------------------------------- #

# Install an extension from a local directory or Git repository
[group: "extensions"]
ext-install source_path:
    poetry run python -m app.common.extension_manager install {{source_path}}

# Uninstall an extension by name
[group: "extensions"]
ext-uninstall name:
    poetry run python -m app.common.extension_manager uninstall {{name}}

# List all installed Powercord extensions
[group: "extensions"]
ext-list:
    poetry run python -m app.common.extension_manager list


# ---------------------------------------------------------------------------- #
#                              SHARED HELPERS                                  #
# ---------------------------------------------------------------------------- #

# Status reporter for nested jobs.
[private]
_run-with-status recipe *args:
    @echo ""
    @echo '{{ CYAN }}→ Running {{ recipe }}...{{ NORMAL }}'
    @just {{ recipe }} {{ args }}
    @echo '{{ GREEN }}✓ {{ recipe }} completed{{ NORMAL }}'
alias rws := _run-with-status

# Wrap a recipe execution to print its elapsed time
[private]
_timed recipe *args:
    #!/usr/bin/env bash
    start_time=$(date +%s)
    shift
    just "{{recipe}}" "$@"
    exit_code=$?
    end_time=$(date +%s)
    elapsed=$((end_time - start_time))
    echo "Recipe '{{recipe}}' completed in ${elapsed}s with exit code ${exit_code}."
    exit ${exit_code}
