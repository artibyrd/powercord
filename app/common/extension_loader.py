import ast
import importlib
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI


class GadgetType(str, Enum):
    COG = "cog"
    SPROCKET = "sprocket"
    WIDGET = "widget"


class GadgetInspector:
    def __init__(self) -> None:
        self.extensions_dir = Path(__file__).resolve().parents[1] / "extensions"

    def _get_gadgets(self, gadget_type: GadgetType) -> list[Path]:
        """Returns a list of all cogs, sprockets,
        or widgets found in installed extensions."""
        gadgets_found = []
        for extension_path in self.extensions_dir.iterdir():
            if extension_path.is_dir():
                gadget_file = extension_path / f"{gadget_type.value}.py"
                if gadget_file.is_file():
                    gadgets_found.append(gadget_file)
        return gadgets_found

    def inspect_cogs(self) -> dict[str, Any]:
        """
        Inspects all cog files for special components like custom contexts
        and persistent views/modals.
        """
        installed_cogs = self._get_gadgets(GadgetType.COG)

        all_cogs = [p.parent.name for p in installed_cogs]
        cog_custom_contexts = {}
        cog_persistent_modals: dict = {}
        cog_persistent_views: dict = {}

        cc_prefix = "cc_"

        for cog_file in installed_cogs:
            extension_name = cog_file.parent.name
            source = cog_file.read_text(encoding="utf-8")

            try:
                parsed_ast = ast.parse(source)
            except SyntaxError as e:
                logging.error(f"Could not parse {cog_file}: {e}")
                continue

            classes = [node for node in ast.walk(parsed_ast) if isinstance(node, ast.ClassDef)]
            cog_persistent_modals[extension_name] = []
            cog_persistent_views[extension_name] = []

            for cog_class in classes:
                if cog_class.name == "CogContexts":
                    methods = [n for n in cog_class.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    cog_custom_contexts[extension_name] = [
                        method.name for method in methods if method.name.startswith(cc_prefix)
                    ]
                elif cog_class.name == "CogPersists":
                    valid_modal = ("nextcord", "ui", "Modal")
                    valid_view = ("nextcord", "ui", "View")
                    subclasses = [n for n in cog_class.body if isinstance(n, ast.ClassDef)]
                    for subclass in subclasses:
                        if not subclass.bases:
                            continue
                        base = subclass.bases[0]
                        if (
                            isinstance(base, ast.Attribute)
                            and isinstance(base.value, ast.Attribute)
                            and isinstance(base.value.value, ast.Name)
                        ):
                            inheritance_tuple = (
                                base.value.value.id,
                                base.value.attr,
                                base.attr,
                            )
                            if inheritance_tuple == valid_modal:
                                cog_persistent_modals[extension_name].append(subclass.name)
                            if inheritance_tuple == valid_view:
                                cog_persistent_views[extension_name].append(subclass.name)

        return {
            "all_cogs": all_cogs,
            "cog_custom_contexts": cog_custom_contexts,
            "cog_persistent_modals": {k: v for k, v in cog_persistent_modals.items() if v},
            "cog_persistent_views": {k: v for k, v in cog_persistent_views.items() if v},
        }

    def inspect_sprockets(self) -> dict[str, list[str]]:
        installed_sprockets = self._get_gadgets(GadgetType.SPROCKET)
        sprocket_routers = {}
        for sprocket_file in installed_sprockets:
            extension_name = sprocket_file.parent.name
            source = sprocket_file.read_text(encoding="utf-8")
            parsed_ast = ast.parse(source)

            routers = []
            for node in ast.walk(parsed_ast):
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                    # This is a simple check that assumes the called function is APIRouter.
                    # It doesn't resolve imports but is sufficient for this convention.
                    call_name = getattr(node.value.func, "attr", getattr(node.value.func, "id", ""))
                    if call_name == "APIRouter":
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                routers.append(target.id)
            if routers:
                sprocket_routers[extension_name] = routers
        return sprocket_routers

    def load_sprockets(self, app: FastAPI) -> None:
        """Finds and loads all sprocket routers into the FastAPI app."""
        sprocket_routers = self.inspect_sprockets()
        for extension_name, router_names in sprocket_routers.items():
            try:
                module_path = f"app.extensions.{extension_name}.sprocket"
                module = importlib.import_module(module_path)
                for router_name in router_names:
                    router = getattr(module, router_name, None)
                    if router:
                        app.include_router(router, prefix=f"/{extension_name}", tags=[extension_name])
                        logging.info(f"Loaded router '{router_name}' from extension '{extension_name}'.")
            except ImportError as e:
                logging.error(f"Could not import sprocket for extension '{extension_name}': {e}")

    def inspect_widgets(self) -> dict[str, list[Callable]]:
        """
        Finds and imports all widget.py files, returning a dict of
        extension names to a list of their renderable widget functions.
        """
        installed_widgets = self._get_gadgets(GadgetType.WIDGET)
        widget_report = {}

        for widget_file in installed_widgets:
            extension_name = widget_file.parent.name
            module_path = f"app.extensions.{extension_name}.widget"
            try:
                module = importlib.import_module(module_path)
                # Find public, callable functions in the module.
                widgets = [
                    getattr(module, func_name)
                    for func_name in dir(module)
                    if callable(getattr(module, func_name))
                    and not func_name.startswith("_")
                    and getattr(module, func_name).__module__ == module.__name__
                ]
                if widgets:
                    widget_report[extension_name] = widgets
            except ImportError as e:
                logging.error(f"Could not import widget for extension '{extension_name}': {e}")

        return widget_report

    def inspect_extensions(self) -> dict[str, list[str]]:
        """
        Inspects all extension directories and reports which gadgets
        (cog, sprocket, widget) each one contains.
        """
        extensions_report = {}
        for extension_path in self.extensions_dir.iterdir():
            if extension_path.is_dir():
                extension_name = extension_path.name
                if extension_name.startswith(".") or extension_name == "__pycache__":
                    continue
                gadgets_found = []
                for gadget_type in GadgetType:
                    gadget_file = extension_path / f"{gadget_type.value}.py"
                    if gadget_file.is_file():
                        gadgets_found.append(gadget_type.value)
                if gadgets_found:
                    extensions_report[extension_name] = gadgets_found
        return extensions_report

    def load_routes(self, rt: Any) -> None:
        """Discover and register extension UI routes.

        Scans each installed extension for a ``routes.py`` file.  If one exists
        and exposes a ``register_routes(rt)`` function, it is called with the
        FastHTML route decorator so the extension can mount its own UI endpoints.
        """
        for extension_path in sorted(self.extensions_dir.iterdir()):
            if not extension_path.is_dir():
                continue
            routes_file = extension_path / "routes.py"
            if not routes_file.is_file():
                continue

            extension_name = extension_path.name
            module_path = f"app.extensions.{extension_name}.routes"
            try:
                module = importlib.import_module(module_path)
                register_fn = getattr(module, "register_routes", None)
                if callable(register_fn):
                    register_fn(rt)
                    logging.info(f"Loaded UI routes from extension '{extension_name}'.")
                else:
                    logging.warning(f"Extension '{extension_name}' has routes.py but no register_routes() function.")
            except ImportError as e:
                logging.error(f"Could not import routes for extension '{extension_name}': {e}")
