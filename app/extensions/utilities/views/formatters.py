# mypy: ignore-errors
"""Text formatting and badge rendering helpers for security alerts and details."""

import re

from fasthtml.common import *

from app.extensions.utilities.security_engine.constants import high_risk_perms, medium_risk_perms


def format_details(details: str) -> FT:
    """Formats raw alert details string into styled FastHTML badges and structured blocks."""
    if not details:
        return ""

    def make_perm_badge(p_name: str) -> FT:
        p_clean = p_name.strip("' ")
        if p_clean.lower() == "none":
            return Span("None", cls="text-xs opacity-50 font-mono")
        if p_clean in high_risk_perms:
            return Span(
                p_clean,
                cls="badge badge-error badge-outline badge-sm h-auto py-1 px-2.5 mr-1 mb-1 font-semibold shadow-sm",
            )
        elif p_clean in medium_risk_perms:
            return Span(
                p_clean, cls="badge badge-warning badge-outline badge-sm h-auto py-1 px-2.5 mr-1 mb-1 font-semibold"
            )
        else:
            return Span(
                p_clean, cls="badge badge-info badge-outline badge-sm h-auto py-1 px-2.5 mr-1 mb-1 font-semibold"
            )

    def group_permissions(perms_list: list[str]) -> list[str]:
        high = []
        medium = []
        low = []
        has_none = False
        for p in perms_list:
            p_clean = p.strip("' ")
            if p_clean.lower() == "none":
                has_none = True
            elif p_clean in high_risk_perms:
                high.append(p)
            elif p_clean in medium_risk_perms:
                medium.append(p)
            else:
                low.append(p)
        result = high + medium + low
        if not result and has_none:
            result = ["none"]
        return result

    # 1. Check if CategoryPermissionBaseline
    if "Leaked allows:" in details:
        parts = details.split("Leaked allows:")
        prefix = parts[0].strip()
        rest = parts[1].split("leaked denies:")
        allows_str = rest[0].strip()
        denies_str = rest[1].strip() if len(rest) > 1 else ""

        if allows_str.endswith(","):
            allows_str = allows_str[:-1]
        if denies_str.endswith("."):
            denies_str = denies_str[:-1]

        allows = group_permissions([p.strip("' ") for p in allows_str.split(",") if p.strip()])
        denies = group_permissions([p.strip("' ") for p in denies_str.split(",") if p.strip()])

        allows_badges = [make_perm_badge(p) for p in allows]
        denies_badges = [make_perm_badge(p) for p in denies]

        return Div(
            P(prefix, cls="text-sm font-semibold text-secondary/90 mb-2"),
            Div(
                Span("Leaked Allows: ", cls="text-xs font-bold text-secondary mr-2"),
                Div(*allows_badges, cls="inline-flex flex-wrap items-center"),
                cls="mb-1.5 flex flex-wrap items-center",
            ),
            Div(
                Span("Leaked Denies: ", cls="text-xs font-bold text-secondary mr-2"),
                Div(*denies_badges, cls="inline-flex flex-wrap items-center"),
                cls="flex flex-wrap items-center",
            ),
            cls="p-3 bg-black/40 rounded-md border border-neutral-700/50 mt-2",
        )

    # 2. Check other rules that contain explicit list markers
    perms_marker = None
    if "Allowed permissions:" in details:
        perms_marker = "Allowed permissions:"
    elif "sensitive permissions:" in details:
        perms_marker = "sensitive permissions:"
    elif "effective permissions" in details:
        perms_marker = "effective permissions"

    if perms_marker:
        parts = details.split(perms_marker)
        prefix = parts[0].strip()
        perms_str = parts[1].strip()
        if perms_str.endswith("."):
            perms_str = perms_str[:-1]
        if perms_str.startswith(":"):
            perms_str = perms_str[1:].strip()

        perms = group_permissions([p.strip("' ") for p in perms_str.split(",") if p.strip()])
        perms_badges = [make_perm_badge(p) for p in perms]

        return Div(
            P(prefix, cls="text-sm font-semibold text-secondary/90 mb-2"),
            Div(
                Span("Permissions: ", cls="text-xs font-bold text-secondary mr-2"),
                Div(*perms_badges, cls="inline-flex flex-wrap items-center"),
                cls="flex flex-wrap items-center",
            ),
            cls="p-3 bg-black/40 rounded-md border border-neutral-700/50 mt-2",
        )

    # 3. Highlight single-quoted terms (e.g. role names, channel names) in default text
    pattern = r"'([^']+)'"
    matches = re.findall(pattern, details)
    if matches:
        formatted_parts = []
        last_idx = 0
        for match in re.finditer(pattern, details):
            # Text before the match
            if match.start() > last_idx:
                formatted_parts.append(Span(details[last_idx : match.start()], cls="text-xs opacity-80"))
            # The matched text styled
            formatted_parts.append(
                Span(
                    match.group(1),
                    cls="text-xs text-accent font-bold bg-accent/10 px-1.5 py-0.5 rounded border border-accent/20 mx-0.5",
                )
            )
            last_idx = match.end()
        if last_idx < len(details):
            formatted_parts.append(Span(details[last_idx:], cls="text-xs opacity-80"))
        return Div(*formatted_parts, cls="p-3 bg-black/40 rounded-md border border-neutral-700/50 mt-2 leading-relaxed")

    # 4. Fallback style
    return Div(
        Span(details, cls="text-xs opacity-80"), cls="p-3 bg-black/40 rounded-md border border-neutral-700/50 mt-2"
    )


def format_message(text: str) -> FT:
    """Highlights channel references (#chan), single-quoted names, and roles in messages."""
    if not text:
        return ""

    highlights = []

    # 1. Channel names starting with #
    for m in re.finditer(r"#([a-zA-Z0-9_-]+)", text):
        highlights.append((m.start(), m.end(), m.group(0), "channel"))

    # 2. Quoted names like 'Role'
    for m in re.finditer(r"'([^']+)'", text):
        highlights.append((m.start(), m.end(), m.group(1), "quote"))

    # 3. Role name after "is visible to "
    for m in re.finditer(r"is visible to ([^.]+)", text):
        highlights.append((m.start(1), m.end(1), m.group(1), "role"))

    # 4. Category name after "compared to parent category "
    for m in re.finditer(r"compared to parent category ([^.]+)", text):
        highlights.append((m.start(1), m.end(1), m.group(1), "category"))

    # Sort highlights by starting index
    highlights = sorted(highlights, key=lambda x: x[0])

    # Resolve overlaps (keep the first one)
    non_overlapping = []
    last_end = 0
    for start, end, val, kind in highlights:
        if start >= last_end:
            non_overlapping.append((start, end, val, kind))
            last_end = end

    # Rebuild the FT components
    formatted_parts = []
    last_idx = 0
    for start, end, val, _kind in non_overlapping:
        if start > last_idx:
            formatted_parts.append(Span(text[last_idx:start]))

        formatted_parts.append(Span(val, cls="font-bold text-accent"))
        last_idx = end

    if last_idx < len(text):
        formatted_parts.append(Span(text[last_idx:]))

    return Span(*formatted_parts)
