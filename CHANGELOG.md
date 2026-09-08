# Changelog — Powercord Server Framework

All notable changes to the Powercord Server Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.4.0] - 2026-09-07

### 🎹 MIDI Pipeline Hardening, Contributor Architecture & Ingestion Resiliency
* **Dedicated Contributor Entity & Strict Single Source of Truth (`powercord-extensions/midi_library`)**:
  - Implemented dedicated `midicontributor` entity table (`id`, `name`, `discord_id: BigInteger Nullable Unique Index`, `created_at`) via Alembic migration `midi0004_create_contributor_table`.
  - Migrated legacy `midifile.contributor` text data into `midicontributor` before safely dropping the redundant column.
  - Linked `midifile.contributor_id` as foreign key to `midicontributor.id` with eager joined loading (`sa_relationship_kwargs={"lazy": "joined"}`), preserving Python property ergonomics (`MidiFile.contributor` getter/setter) with zero detached instance errors.
  - Implemented `get_or_create_contributor` resolving identities by Discord Snowflake ID when available, with graceful username updates on display name change and fallback to name matching for non-Discord submissions.
* **Massive `/scan` Command & Background Worker Resiliency (`powercord-extensions/midi_library`)**:
  - Eliminated artificial 1-second sleep bottleneck per file in `sprocket.py` and wrapped file ingestion in `asyncio.to_thread`.
  - Added randomized temp file prefixes preventing concurrent collision, and detailed job metrics tracking (`imported`, `duplicates`, `failed`).
  - Added active channel scan concurrency lock (`_ACTIVE_SCANS`) in `scan_handler.py` preventing duplicate overlapping runs on the same channel.
  - Replaced rigid 1,000-message chunking with adaptive flushing (`len(attachments) >= 50 or chunk_count >= 500`) and cooperative event loop yielding (`await asyncio.sleep(0)` every 100 messages) preventing gateway stalls across tens of thousands of channel messages.
  - Captured original message author display name and Snowflake Discord ID per attachment during historical channel sweeps.
  - Added robust Discord message editing wrapper (`_safe_status_edit`) resilient to rate limits (`429`) and deleted status messages (`NotFound`).
* **MIDI Library Archive Ingestion & Character Limit Protection (`powercord-extensions/midi_library`)**:
  - Fixed archive import hanging bug where multi-file archives (`.zip`, `.7z`, `.rar`) exceeded Discord's 2,000-character content limit, throwing unhandled 400 Bad Request exceptions that froze the status message.
  - Implemented 5-item display cutoff with descriptive count summaries (`...and X more pieces added to the guild collection!`), hard message clamping at 1,850 characters, and try/except fallback handling for Discord edits.
  - Offloaded synchronous file ingestion and GCS uploads from Discord's main asyncio thread via `asyncio.to_thread` in `scan_handler.py`, preventing gateway heartbeat timeouts and WebSocket disconnects.
  - Optimized MIDI parsing in `midiscribe.py`: reused single `PrettyMIDI` instance across scoring and spectrogram generation, and lowered piano roll sampling rate (`fs=25`) with leak-proof figure closing (`plt.close("all")`).
  - Added `test_on_message_large_archive_truncation` to `tests/test_ingestion.py` validating 30-item batches under character limits.
* **Scoring Accuracy & Per-Instrument Duplicate Detection (`powercord-extensions/midi_library`)**:
  - Fixed duplicate note calculation bug in `_score_midi` (`midiscribe.py`): Scoped duplicate note signatures strictly per-instrument rather than globally across all tracks. Multi-track songs with unison or layered instruments (e.g. double-tracked rhythm and lead guitars) are no longer erroneously flagged as duplicates, fixing false 0/100 quality scores.
  - Added unit tests `test_score_midi_unison_not_duplicate` and `test_score_midi_same_instrument_duplicate` in `tests/test_midi_extension.py`.
  - Re-scored existing affected database records (such as `Metallica - Enter Sandman minus Lars.mid`, updating quality score from `0/100` to `88/100` with 0% duplicates).
* **Friendly Guild Librarian Persona & Visual Layout Redesign (`powercord-extensions/midi_library`)**:
  - Upgraded Discord submission feedback in `scan_handler.py` from cold/combative duplicate notices to a friendly, welcoming guild librarian tone (*"Good news! Looks like X already exists in our collection..."*).
  - Structured Markdown with clean bold identifiers and bulleted track summaries.
  - Added rich detail embeds (`_build_detail_embed`) featuring spectrogram visualizers, quality score progress meters, instrument classifications, and note counts.
  - Clean duplicate reference copy deliveries with tidy omission summaries (capped at 3).
* **Heartbeat Status Responses & Anti-Spam Condensed Bulk Reports (`powercord-extensions/midi_library`)**:
  - Added live pulsing heartbeat indicators (`💓`, `💗`, `💖`) with real-time elapsed second timers and currently processing filenames across both multi-file archive uploads and `/scan` message history sweeps, giving operators clear visual feedback that long-running operations are healthy and active.
* **PostgreSQL Word-Similarity Trigram Search Upgrade (`app/db/search.py`)**:
  - Replaced whole-string `similarity(col, search_term) >= 0.3` with `word_similarity(search_term, col)` combined with `func.greatest` and substring ILIKE fallback in `build_trigram_query`.
  - Solved search failure where exact keywords (e.g. `"sabaton"`, `"necrophagist"`) scored below the 0.3 similarity cutoff on long filenames (40+ chars), while continuing to catch minor typos with fuzzy matching.
* **Interactive Channel Scan Pause, Resume & Status Engine (`powercord-extensions/midi_library`)**:
  - Implemented interactive Discord UI buttons (`[ ⏸️ Pause Scan ]` and `[ ▶️ Resume Scan ]`) via `ScanControlView` allowing guild administrators to pause long-running channel scans cooperatively.
  - Added slash command action options to `/scan` (`start`, `pause`, `resume`, `status`) enabling command-line inspection and control.
  - Enhanced cursor persistence (`scan_cursor.json`) with checkpoint status (`running`, `paused`, `completed`) and running statistics (`scanned`, `imported`, `updated_at`).
  - Safe cooperative loop exit: gracefully yields active HTTP jobs, persists the last processed Snowflake ID, and displays resume guidance.
* **Clean Filename Isolation & Temp Scoping (`sprocket.py` & `midiscribe.py`)**:
  - Isolated background scan downloads into dedicated subdirectories (`temp/scan_{job_id}_{uuid}/{original_filename}`), preventing temporary UUID prefixes from mangling database filenames.
  - Added explicit `filename` parameter override across `process_file_import` and `_process_single_midi` ensuring pristine metadata and web gallery display.
* **Asynchronous Spectrogram Worker & Self-Healing Asset Queue (`powercord-extensions/midi_library`)**:
  - Decoupled CPU-heavy Matplotlib/Librosa spectrogram piano-roll PNG rendering into an asynchronous background queue (`SpectrogramRepairQueue` in [`spectrogram_worker.py`](spectrogram_worker.py)).
  - Single Discord drops render PNGs synchronously for instant rich embeds; bulk `/scan` sweeps and multi-file archives defer PNG generation (`generate_png=False`), accelerating batch indexing to ~15ms per file (25x–50x throughput gain).
  - Sprocket batch processing bounded by `asyncio.Semaphore(4)` with concurrent `asyncio.gather` for downloads and scoring.
  - Single Source of Truth: Physical storage is the authority for assets without database schema pollution (`no has_png column`). Missing assets discovered at runtime (telemetry 404s, `/midi` slash queries, or deferred scan imports) log `MidiHealthError(resolved=False)` to omit them from web galleries (`inv-omission-over-fallback-galleries`) and immediately enqueue them for background generation/repair.
  - Background workers automatically mark `MidiHealthError.resolved = True` upon rendering and uploading the PNG, restoring gallery eligibility automatically.
* **Archive Sub-Progress Reporting & Visibility (`sprocket.py` & `midiscribe.py`)**:
  - Implemented granular real-time sub-progress tracking during archive extraction (`on_item_progress(current, total, filename)`), updating scan status with active item details (e.g. `archive.zip (3/15: solo.mid)`) to eliminate perceived stalls on large multi-file archives.
* **Scan Completion Card Polish & Heartbeat Dismissal (`scan_handler.py` & `embeds.py`)**:
  - Cleaned up scan terminal state cards (`Complete`, `Paused`, `Error`): explicitly suppressed pulsing heartbeat text (`· *Heartbeat active*`) upon completion while preserving final elapsed time summary (`• **Elapsed Time:** 42s`).
* **High-Throughput Archive Acceleration & Parallelism (`midiscribe.py` & `sprocket.py`)**:
  - Implemented fast-path bulk duplicate detection for archive contents: computes SHA-256 checksums up-front and queries existing hashes in a single SQL `in_()` statement (~5ms) before performing expensive PrettyMIDI parsing or GCS operations.
  - Added multi-threaded archive processing using `ThreadPoolExecutor(max_workers=min(4, len(pending)))` with database `IntegrityError` deduplication guards.
  - Increased sprocket attachment concurrency semaphore from 4 to 6.
  - Throttled background spectrogram workers during active scans (`_is_scan_active()`), reserving 100% CPU and network bandwidth for real-time channel sweeps.
* **Headless Matplotlib Multi-Threading Isolation (`spectrogram_worker.py`)**:
  - Explicitly configured `matplotlib.use("Agg")` prior to importing `pyplot`, preventing Tkinter GUI backend initialization and eliminating multi-threaded aborts (`Tcl_AsyncDelete: async handler deleted by the wrong thread`).
  - Added safe event loop detection in worker threads for background spectrogram enqueueing.
* **Tier 2 Shift-Left Automated Governance Gates (`tests/governance/test_architecture_governance.py`)**:
  - Implemented `test_matplotlib_headless_backend_invariant` statically enforcing via AST that any module importing `matplotlib.pyplot` configures `matplotlib.use("Agg")` beforehand, permanently preventing Tkinter thread aborts in worker pools.
  - Implemented `test_no_derived_asset_columns_in_database_models` statically asserting that `SQLModel` schemas in `models.py` and extension `blueprint.py` never declare derived asset existence flags (`has_png`, `has_image`, `is_cached`), enforcing physical storage authority (`inv-omission-over-fallback-galleries`).
  - Implemented `test_discord_status_edit_component_sentinel_invariant` statically banning `if view is not None: kwargs["view"] = view` patterns in status edit helpers, ensuring explicit `view=None` component dismissals are forwarded to Discord.
  - Added unit tests `test_safe_status_edit_clears_components_when_explicit_none` and `test_format_scan_card_heartbeat_suppression` to `tests/test_scan_control.py`.
* **Tier 1 Progressive Skills & Knowledge Persistence (`.agents/skills/`)**:
  - Updated [`failure-patterns.md`](powercord-agent/.agents/skills/powercord-ecosystem/references/failure-patterns.md) with Failure Patterns 7–12 (stale UI components, Matplotlib worker aborts, derived asset DB desynchronization, trigram word-similarity on compound strings, unison note duplicate false positives, and download directory isolation).
  - Updated [`gadget-specs.md`](powercord-agent/.agents/skills/powercord-extension-authoring/references/gadget-specs.md) with Section 2 documenting Discord bot status lifecycle, card stabilization, and high-throughput channel sweep best practices.
* **Architecture & Database Slate Reset**:
  - Extracted attachment upload handling to [`upload_handler.py`](upload_handler.py) (293 LOC) and spectrogram generation to [`spectrogram_worker.py`](spectrogram_worker.py) (259 LOC), keeping all source files strictly under the 500 LOC ceiling (`inv-500-loc-ceiling`).
  - Wiped local test database (`TRUNCATE CASCADE` across all 6 MIDI tables) and purged scan cursors for clean operator re-testing.
  - 113 automated tests passing in `tests/extensions/midi_library`. All governance gates green (17 core, 16 downstream).

---

## [2.3.0] - 2026-09-07

### 🎓 100% Architectural Ratchet Graduation & Sovereign Hardening
* **100% Zero Debt Graduation**: Completed the multi-milestone decoupling program for the 500 LOC Ceiling Law (`inv-500-loc-ceiling`). Active debt files in [`governance_ratchet.json`](tests/governance/governance_ratchet.json) dropped from 4 to **0**. Every source file across core, extensions, and downstream strictly satisfies $\le 500$ LOC:
  - `powercord/app/extensions/example/cog.py`: 1,138 LOC $\rightarrow$ 313 LOC facade + modular `cogs/` submodules (`counter.py`, `ping.py`, `greeter.py`, `help.py`, `views.py`).
  - `powercord-extensions/midi_library/cog.py`: 748 LOC $\rightarrow$ 113 LOC facade + `embeds.py`, `ui_views.py`, `command_handlers.py`.
  - `powercord-extensions/midi_library/routes.py`: 541 LOC $\rightarrow$ 70 LOC facade + `views/` subpackage (`gallery.py`, `modal.py`, `proxy.py`, `telemetry.py`).
  - `powercord/app/common/extension_manager.py`: 524 LOC $\rightarrow$ 462 LOC facade + `extension_manifest.py` (112 LOC) and `extension_alembic.py` (33 LOC).
* **Core Extension Directory Isolation Guard (`inv-source-isolation-no-ad-hoc-cp`)**:
  - Implemented `_is_core_repository()` guard in `app/common/extension_manager.py` that refuses direct extension installation into the core framework repository with a hard error directing operators to `powercord-downstream-server/`.
  - Updated `powercord/Justfile` so `ext-install` and `ext-uninstall` fail immediately if invoked in core, protecting repository boundaries.
  - Added `test_core_extensions_directory_isolation()` to `tests/governance/test_architecture_governance.py` to permanently fail if external extensions are detected in `app/extensions/`.
  - Purged untracked `app/extensions/honeypot/` from the core repository.
* **Core Dependency Cleanliness**:
  - Pruned 7 external extension dependencies (`pretty-midi`, `librosa`, `matplotlib`, `py7zr`, `rarfile`, `google-cloud-storage`, `cryptography`) from core `pyproject.toml`.
  - Reconciled `poetry.lock`, eliminating 1,889 lines of heavy transitive scientific and audio processing libraries (`scipy`, `numba`, `llvmlite`, `soundfile`, `soxr`) from the core framework.
* **Docker Hygiene & Disk Space Reclaim (`inv-single-vm-cost-ceiling`)**:
  - Added shared `docker-clean` recipe to `devkit.just` across core and downstream for pruning dangling images and build cache (`just docker-clean all=true`).
* **Local Artifact Cleanliness**:
  - Pruned redundant root `.sql` dumps from `powercord/` (`bgml-data.sql`, `powercord-export.sql`, `bgml.dump`, `test_export.sql`), preserving canonical versions in `/backup/`.
  - Enhanced `just dev-clean` to automatically purge temporary `*.log` and `.sql` test dumps.
  - Pruned stale tracking directories from the ecosystem root.
* **Retrospective Governance & Skill Parity (`inv-changelog-session-parity`)**:
  - Established Operational Heuristic 5 and invariant `inv-changelog-session-parity` mandating changelog updates in the active session and strict forward-looking roadmap deduplication.
  - Formally codified extension isolation rules in `.agents/skills/powercord-extension-authoring/` (`powercord-extensions/<ext>` as sole source of truth, zero core installs, downstream-only staging).
  - Documented Docker hygiene lifecycle (`just docker-clean`) in `.agents/skills/powercord-deployment/` and `.agents/skills/powercord-ecosystem/`.
* **Database Session Leak Invariant & Governance Hardening (`inv-hermetic-db-testing-nullpool`)**:
  - Implemented `test_no_raw_generator_session_leak_invariant()` in `tests/governance/test_architecture_governance.py` which AST-scans all Python files across core and extensions to permanently ban naked calls to `get_session()`, mandating RAII context management (`with Session(engine) as session:`).
  - Remedied legacy generator session leak in `app/extensions/example/views_cog.py` (`db_test` slash command).
  - Corrected documentation in `docs/db.md` to recommend RAII sessions.
* **MIDI Library Ingestion & Submission Hardening (`powercord-extensions/midi_library`)**:
  - Eliminated database connection pool exhaustion in `midiscribe.py` by converting leaking generator invocations to RAII `Session(engine)` blocks.
  - Refactored `SingleMidiResult` and `ImportResult` to provide full accounting (`imported`, `duplicates`, `failed`) and detached `MidiFile` instances to avoid `DetachedInstanceError`.
  - Upgraded Discord submission feedback in `scan_handler.py` to provide clear, actionable status breakdowns, duplicate proof delivery (including rich embed and `.mid` file attachment, capped at 3 per message), and comprehensive rich metadata cards (`_build_detail_embed`) with piano-roll visualizations, quality score bars, track breakdowns, and note counts for newly imported MIDIs.
  - Added comprehensive unit and stress tests in `tests/test_ingestion.py` covering bounded connection pools (5 connections, 35 sequential operations) and full `handle_on_message` matrix.
* **MIDI Library Scoring Accuracy & Per-Instrument Duplicate Detection (`powercord-extensions/midi_library`)**:
  - Fixed duplicate note calculation bug in `_score_midi` (`midiscribe.py`): Scoped duplicate note signatures strictly per-instrument rather than globally across all tracks. Multi-track songs with unison or layered instruments (e.g. double-tracked rhythm and lead guitars) are no longer erroneously flagged as duplicates, fixing false 0/100 quality scores.
  - Added unit tests `test_score_midi_unison_not_duplicate` and `test_score_midi_same_instrument_duplicate` in `tests/test_midi_extension.py`.
  - Re-scored existing affected database records (such as `Metallica - Enter Sandman minus Lars.mid`, updating quality score from `0/100` to `88/100` with 0% duplicates).
* **MIDI Library Archive Ingestion & Performance Optimization (`powercord-extensions/midi_library`)**:
  - Fixed archive import hanging bug where multi-file archives (`.zip`, `.7z`, `.rar`) exceeded Discord's 2,000-character content limit, throwing unhandled 400 Bad Request exceptions that froze the status message.
  - Implemented 5-item display cutoff with descriptive count summaries (`...and X more pieces added to the guild collection!`), hard message clamping at 1,850 characters, and try/except fallback handling for Discord edits.
  - Offloaded synchronous file ingestion and GCS uploads from Discord's main asyncio thread via `asyncio.to_thread` in `scan_handler.py`, preventing gateway heartbeat timeouts and WebSocket disconnects.
  - Optimized MIDI parsing in `midiscribe.py`: reused single `PrettyMIDI` instance across scoring and spectrogram generation, and lowered piano roll sampling rate (`fs=25`) with leak-proof figure closing (`plt.close("all")`).
* **Contributor Entity Architecture & Strict Single Source of Truth (`powercord-extensions/midi_library`)**:
  - Implemented dedicated `midicontributor` entity table (`id`, `name`, `discord_id: BigInteger Nullable Unique Index`, `created_at`) via Alembic migration `midi0004_create_contributor_table`.
  - Migrated legacy `midifile.contributor` text data into `midicontributor` before safely dropping the redundant column.
  - Linked `midifile.contributor_id` as foreign key to `midicontributor.id` with eager joined loading (`sa_relationship_kwargs={"lazy": "joined"}`), preserving Python property ergonomics (`MidiFile.contributor` getter/setter) with zero detached instance errors.
  - Implemented `get_or_create_contributor` resolving identities by Discord Snowflake ID when available, with graceful username updates on display name change and fallback to name matching for non-Discord submissions.
* **Massive `/scan` Command & Background Worker Resiliency (`powercord-extensions/midi_library`)**:
  - Eliminated artificial 1-second sleep bottleneck per file in `sprocket.py` and wrapped file ingestion in `asyncio.to_thread`.
  - Added randomized temp file prefixes preventing concurrent collision, and detailed job metrics tracking (`imported`, `duplicates`, `failed`).
  - Added active channel scan concurrency lock (`_ACTIVE_SCANS`) in `scan_handler.py` preventing duplicate overlapping runs.
  - Replaced rigid 1,000-message chunking with adaptive flushing (`len(attachments) >= 50 or chunk_count >= 500`) and cooperative event loop yielding (`await asyncio.sleep(0)` every 100 messages) preventing gateway stalls across tens of thousands of channel messages.
  - Captured original message author display name and Snowflake Discord ID per attachment during historical channel sweeps.
  - Added robust Discord message editing wrapper (`_safe_status_edit`) resilient to rate limits (`429`) and deleted status messages (`NotFound`).
  - Local database wiped and reset for clean operator re-testing.

---

## [2.2.0] - 2026-09-06

### 🛡️ Security Auditor & Widget Engine Decoupling
* **Auditor Deconstruction**: Deconstructed the monolithic `widget.py` (2,783 LOC) in `app/extensions/utilities/` into modular single-responsibility components:
  - `security_engine/calculations.py`: Pure mathematical bitmask and permission ontology functions.
  - `security_engine/rules/`: Modular rule evaluators for channel exposure, ping abuse, role separation, and suggestive honeypot integration.
  - `security_engine/engine.py`: Core rule orchestration and state checksum caching.
  - `views/`: Reusable FastHTML components, modals, and formatters (`alerts_list.py`, `formatters.py`, `modals.py`).
  - `widgets/`: Focused card widgets (`overview.py`, `alerts.py`, `roles.py`, `channels.py`, `settings.py`, `permissions.py`, `overrides.py`, `auxiliary.py`).
  - `widget.py`: Compact 122 LOC registry and assembler facade.
* **Pure Function Ontology (`inv-compute-ontology`)**: Enforced `compute_*` prefix naming for pure mathematical and bitmask calculation functions across the codebase, backed by automated governance tests.

---

## [2.1.0] - 2026-09-05

### 🌐 FastHTML Web UI & Dashboard Deconstruction
* **Web UI Modularization**: Decoupled monolithic `app/main_ui.py` (1,398 LOC) into a compact 124 LOC application assembler and modular route handlers under `app/ui/routes/` (`admin.py`, `guild.py`, `public.py`, `admin_actions.py`, `admin_guard.py`).
* **Dashboard Engine Modularization**: Deconstructed monolithic `app/ui/dashboard.py` (2,084 LOC) into a cohesive `app/ui/dashboard/` subpackage (`layout.py`, `roles.py`, `settings.py`, `api_keys.py`, `grid.py`, `placement.py`).
* **Signature Preservation (`inv-fasthtml-card-signature`)**: Preserved the canonical `Card(title, content, **kwargs)` calling convention across all UI widget integrations.

---

## [2.0.0] - 2026-08-25

### 🧼 The Great Versioning Hygiene Reconciliation
* **Corrected True Baseline**: Officially reclaimed our rightful `v2.0.0` status, liberating the codebase from the humble `0.1.0` placeholder it had been wearing like an oversized thrift-store sweater while running full-fledged production workloads.
* **Invariant Governance**: Initialized Tier 0–2 Sovereign Invariant hierarchy, adopting shift-left governance test gates and 4-tier knowledge taxonomy cross-pollinated from the Credence ecosystem.
* **Single Fixed-Cost VM Sovereignty**: Permanently anchored architecture to a single GCP Compute Engine VM (`powercord-instance`), outlawing serverless autoscaling bill surprises for always-on Discord bot gateways.
* **Downstream Sandbox Isolation**: Formalized `powercord-downstream-server/` as the pre-commit integration testbed for multi-head Alembic migrations (`core`, `honey`, `midi`) and container verification.
* **Split-Stack Purity**: Hardened architectural boundaries between FastHTML/HTMX admin UI routes (`routes.py` / `widget.py`) and FastAPI REST sprockets (`sprocket.py`).
* **Branch & PR Review Lifecycle (`inv-branch-pr-review-gate`)**: Evolved commit governance to require dedicated feature branches (`just branch feat/<name>`), incremental local commits (`just commit <msg>`) strictly gated by `just check`, live downstream container verification (`http://localhost:5001/`), and GitHub pull request creation (`just pr-create`). Zero direct commits or pushes to `main`; human Mk1 review required for PR merges and release tagging.
