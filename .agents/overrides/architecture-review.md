# Architecture Review Policy for Powercord

Self-contained architecture review guide and overlay for the Powercord ecosystem (`powercord`, `powercord-client`, `powercord-extensions/*`, `powercord-client-extensions/*`).

## Overrides

- **Deep Modules & 1,000-LOC Anti-God-File Rail (`inv-500-loc-ceiling`)**: Favor Ousterhout Deep Modules (rich behavior behind small, cohesive public seams). Treat **~500 LOC** as a soft internal decomposition trigger, and enforce a hard **1,000-LOC anti-god-file safety rail** across `powercord/app`, `powercord-client`, and `powercord-extensions/*` (verified by `powercord/tests/governance/test_architecture_governance.py`). Decompose large task runners into modular `just/*.just` files rather than letting root `Justfile` grow past a concise router.
- **FastHTML Route Static Typing Exception**: FastHTML generates HTML element constructors (`Div`, `Td`, `Form`, `Table`, etc.) dynamically at runtime, which triggers false-positive `[name-defined]` errors in Mypy. Place `# mypy: ignore-errors` on line 1 of FastHTML UI route and widget modules (`routes.py`, `widget.py`) only. Pure domain models, FastAPI sprockets (`sprocket.py`), database query modules, and `compute_*` functions must never disable Mypy and must keep strict static typing.

## Extensions

1. **`compute_*` Pure Function Ontology (`inv-compute-ontology`)**:
   - Name every mathematical, statistical, bitmask, and permission calculation function with the `compute_*` prefix.
   - `calc_*` and `calculate_*` prefixes are banned and rejected by `test_compute_naming_ontology_invariant`.
   - `compute_*` helpers must remain pure with zero database, filesystem, or network side effects.
2. **Split-Stack FastHTML vs. FastAPI REST Isolation (`inv-split-stack-isolation`)**:
   - FastHTML views (`routes.py`, `widget.py`) return HTML/FT components for server-rendered UI and HTMX swaps.
   - FastAPI sprockets (`sprocket.py`) return typed JSON/Pydantic payloads for companion clients and API callers — never raw HTML strings.
   - Dashboard widgets must follow strict scope prefixes (`inv-widget-scope-namespaces`): `admin_` for `/admin`, `guild_admin_` for `/dashboard/{guild_id}`, and unprefixed names for public widgets.
3. **FastHTML `Card` Integrity & Decorator Signature Preservation (`inv-fasthtml-card-signature`)**:
   - Always invoke `Card` components as `Card(title, content, **kwargs)` (pass a `Div` as `title` when headers need inline forms or buttons).
   - Any custom decorator placed below `@rt(...)` must preserve the wrapped function's signature (`wrapper.__signature__ = inspect.signature(f)`) so FastHTML dependency and parameter injection works reliably.
4. **Client-Server Runtime Isolation (`inv-client-server-decoupling`)**:
   - Companion desktop code (`powercord-client/` and `powercord-client-extensions/*`) must never import backend modules (`app.*`, `nextcord`, `fasthtml`).
   - All client-server communication runs over asynchronous HTTP REST (`httpx.AsyncClient`) or WebSockets (`inv-flet-async-routing`).
5. **Facade-Preserving Monolith Deconstruction & Dynamic Mock Propagation**:
   - When splitting a large module into a subpackage, keep a thin facade module that re-exports public symbols (`__all__`) and exposes thin pass-through widget wrappers (e.g., `def guild_admin_*_widget(...)`) so `extension_loader.py` gadget discovery (`getattr(obj, "__module__", None) == module.__name__`) still registers them.
   - Inside decomposed submodules that query the database, resolve `Session` and `engine` dynamically from the facade (or via `sys.modules`) inside handler bodies so unit tests patching `app.extensions.<ext>.widget.Session` or `engine` continue to inject mocks cleanly without circular imports:
     ```python
     import app.extensions.<ext>.widget as facade
     session_cls = getattr(facade, "Session", Session)
     current_engine = getattr(facade, "engine", engine)
     with session_cls(current_engine) as session:
         ...
     ```
6. **Container Filesystem Isolation & Path Guards**:
   - Isolated CI and Cloud Build containers mount only a single repository (e.g., `/workspace`), where `REPO_ROOT.parent` resolves to `/`.
   - Governance tests and build scripts referencing sibling repositories or umbrella `AGENTS.md` must guard every cross-repo path with an existence check and `pytest.skip(...)` (verified by `test_container_isolated_path_guards`).
7. **Session, Media, Storage & Discord Runtime Invariants**:
   - **No Raw `get_session()` Calls**: Use `Depends(get_session)` in FastAPI routes and `with Session(engine) as session:` in Discord cogs and background jobs.
   - **Headless Matplotlib (`Agg`)**: Any module importing `matplotlib.pyplot` must call `matplotlib.use("Agg")` beforehand to prevent multi-threaded Tkinter `SIGABRT` crashes.
   - **Physical Storage Authority (`inv-omission-over-fallback-galleries`)**: Never declare derived file/cache existence columns (`has_png`, `is_cached`, etc.) in SQLModel tables; omit malformed gallery records and oversample queries instead of rendering placeholders.
   - **Discord Status Edit Sentinel**: Status edit helpers must distinguish an unset `view` (`_VIEW_UNSET = object()`) from explicit `view=None` so callers can clear interactive message buttons on completion.
   - **Core Extension Isolation (`inv-source-isolation-no-ad-hoc-cp`)**: `powercord/app/extensions/` contains only internal built-ins (`custom_content`, `example`, `utilities`); external extensions live strictly in `powercord-extensions/*` and are staged only in `powercord-downstream-server/`.

## Disabled / Not Applicable

- **Legacy `governance_ratchet.json` Probation**: Retired after all legacy monoliths graduated below 500 LOC; replaced by the 1,000-LOC anti-god-file safety rail and Deep Modules guidance above.
- **Autoscaling & Multi-Service Cloud Topologies**: Not applicable — Powercord operates on a single fixed-cost GCE VM (`inv-single-vm-cost-ceiling`).
