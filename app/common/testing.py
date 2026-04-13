import os
import sys
import types
from importlib.machinery import ModuleSpec, SourceFileLoader


def setup_extension_test_env(extension_name: str, conftest_file_path: str):
    """
    Sets up the test environment for a disconnected extension repository.
    This registers the extension into sys.modules natively so that tests and relative imports
    inside the extension can seamlessly map the namespace without structural errors.

    Args:
        extension_name: The name of the extension (e.g. 'honeypot', 'midi_library').
        conftest_file_path: The __file__ path of the local conftest.py calling this.
    """
    import app.extensions

    # Create the top-level namespace module
    ext_mod = types.ModuleType(extension_name)
    ext_mod.__package__ = f"app.extensions.{extension_name}"

    # We resolve the root directory of the extension relative to its tests/conftest.py
    root_dir = os.path.abspath(os.path.join(os.path.dirname(conftest_file_path), ".."))
    ext_mod.__path__ = [root_dir]

    # Register it into sys.modules and the app.extensions parent namespace
    sys.modules[f"app.extensions.{extension_name}"] = ext_mod
    setattr(app.extensions, extension_name, ext_mod)

    # Instead of standard __import__, evaluate the actual files directly
    # so we populate sys.modules and make relative imports from test files work.
    for file in os.listdir(root_dir):
        if file.endswith(".py") and not file.startswith("__") and file != "test.py":
            mod_name = file[:-3]
            full_name = f"app.extensions.{extension_name}.{mod_name}"

            # This loader injects `from app.extensions.<ext_name> import <file>`
            loader = SourceFileLoader(full_name, os.path.join(root_dir, file))
            spec = ModuleSpec(name=full_name, loader=loader)

            # We push the spec so relative imports inside it know their parent package
            mod = types.ModuleType(spec.name)
            mod.__file__ = loader.path
            mod.__package__ = f"app.extensions.{extension_name}"
            mod.__loader__ = loader
            mod.__spec__ = spec

            sys.modules[full_name] = mod
            setattr(ext_mod, mod_name, mod)

            loader.exec_module(mod)
