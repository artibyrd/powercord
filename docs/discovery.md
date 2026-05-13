# Extension Discovery Framework

## Overview
Powercord uses a pattern of "active discovery" to find and load extension components. Instead of manual registration for every file, the `GadgetInspector` (in `app/common/extension_loader.py`) scans the extensions directory and uses static analysis and dynamic imports to build the application state.

## Gadget Types
The framework recognizes three primary "gadgets":
- **Cogs**: Discord bot command modules (`cog.py`).
- **Sprockets**: FastAPI router modules (`sprocket.py`) with automatic scope-based security.
- **Widgets**: FastHTML UI component modules (`widget.py`).

## Static Analysis (AST Parsing)
To avoid side effects during discovery, the `GadgetInspector` uses the `ast` module to inspect source code before importing it.

### Discovery Logic:
1.  **Cogs**:
    - Scans `cog.py` for classes inheriting from `commands.Cog`.
    - Detects `CogContexts` classes and identifies methods starting with `cc_`.
    - Detects `CogPersists` classes and identifies subclasses of `nextcord.ui.Modal` or `nextcord.ui.View` for persistent registration.
2.  **Sprockets**:
    - Scans `sprocket.py` for assignments where `APIRouter()` is called.
    - Used to dynamically mount routes under the extension's name (e.g., `/extension_name/...`).
3.  **Widgets**:
    - Identifies renderable functions in `widget.py`.

## Runtime Loading
Once identified, gadgets are loaded into their respective containers:
- **Bot**: Loaded via `bot.load_extension()`.
- **API**: Routers are included in the FastAPI app with `api_scope_required(extension_name)` middleware automatically applied.
- **UI**: FastHTML `routes.py` are executed via a `register_routes(rt)` callback.

### Public Path Registration (`PUBLIC_PATHS`)
Extensions with public-facing UI routes (e.g., gallery pages accessible to unauthenticated users) can declare an optional `PUBLIC_PATHS` constant in their `routes.py`:

```python
# In routes.py — module level, before register_routes()
PUBLIC_PATHS: list[str] = [
    r"/midi/gallery.*",
    r"/midi/detail/.*",
]
```

At startup, `GadgetInspector.collect_public_paths()` scans all installed extensions for this constant and aggregates the regex patterns. The core framework then extends the `Beforeware.skip` list dynamically, eliminating the need to hardcode extension-specific paths in `main_ui.py`.

**Key properties:**
- **Opt-in**: Extensions without `PUBLIC_PATHS` are unaffected (no breaking changes).
- **Co-located**: Path declarations live alongside the route definitions they apply to.
- **Type-validated**: Non-list values are logged as warnings and skipped.

## Best Practices
- **Naming Conventions**: Stick to the named files (`cog.py`, `sprocket.py`, `widget.py`) for automatic discovery.
- **Avoid Side Effects**: Do not execute top-level database queries or bot initialization inside discovery files; keep logic inside classes or functions.
- **Isolation**: Use `CogContexts` for injecting logic into bot commands without modifying the core bot class.
- **Public Routes**: Use `PUBLIC_PATHS` in `routes.py` to declare unauthenticated paths — never hardcode extension paths in the core `Beforeware` skip list.
