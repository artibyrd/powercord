# mypy: ignore-errors
from __future__ import annotations

from typing import Any

VALID_FIXED_POSITIONS = ("left", "right")
VALID_FLOATING_POSITIONS = ("bottom-right", "bottom-left", "top-right", "top-left")


def normalize_position_config(pos_cfg: str | None, default_pos: str | None) -> str | None:
    """Normalize position config based on default position classification."""
    if default_pos in VALID_FIXED_POSITIONS:
        return "right" if pos_cfg == "right" else "left"
    if default_pos in VALID_FLOATING_POSITIONS:
        return pos_cfg if pos_cfg in VALID_FLOATING_POSITIONS else "bottom-right"
    return pos_cfg


def classify_widget_placement(
    pos_cfg: str | None,
) -> str:
    """Classify a position config as 'fixed', 'floating', or 'grid'."""
    if pos_cfg in VALID_FIXED_POSITIONS:
        return "fixed"
    if pos_cfg in VALID_FLOATING_POSITIONS:
        return "floating"
    return "grid"


def check_position_collisions(widgets: list[dict[str, Any]]) -> dict[str, str]:
    """Check for position collisions among enabled sidebar/floating widgets.

    Returns a mapping of widget name -> error message for colliding widgets.
    """
    active_positions: dict[str, str] = {}
    collisions: dict[str, str] = {}

    for w in widgets:
        if not w.get("enabled"):
            continue

        wname = w["widget"]
        default_pos = w.get("default_pos")
        pos_cfg = w.get("position_config")

        if default_pos in VALID_FIXED_POSITIONS or default_pos in VALID_FLOATING_POSITIONS:
            norm_pos = normalize_position_config(pos_cfg, default_pos)
            if norm_pos in active_positions:
                existing = active_positions[norm_pos]
                collisions[wname] = f"Collision with {existing} at {norm_pos}"
            else:
                active_positions[norm_pos] = wname

    return collisions
