import sys
from pathlib import Path


def setup_project_root():
    """Adds the project root to sys.path to ensure consistent imports."""
    # Assuming this file is at app/bootstrap.py, the project root is two levels up.
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
