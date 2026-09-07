"""Modal and Dialog UI helpers for Powercord FastHTML dashboard.

Governed by:
- inv-500-loc-ceiling: 500 LOC module ceiling
- inv-split-stack-isolation: FastHTML returns FT components
"""

from __future__ import annotations

import json
import logging

from fasthtml.common import FT, H3, A, Button, Dialog, Div, Form, I, P, Script, Span

from app.common.extension_loader import GadgetInspector


def get_extension_details_modal(extension_name: str, access_token: str | None = None) -> FT:
    """Generates a modal containing the extension's README and functionality breakdown."""
    inspector = GadgetInspector()
    extensions_report = inspector.inspect_extensions()
    gadgets = extensions_report.get(extension_name, [])

    # Badges for functionality
    badges = []
    if "cog" in gadgets:
        badges.append(Span("Cog", cls="badge badge-primary badge-sm font-bold shadow-md"))
    if "sprocket" in gadgets:
        badges.append(Span("Sprocket", cls="badge badge-secondary badge-sm font-bold shadow-md"))
    if "widget" in gadgets:
        badges.append(Span("Widget", cls="badge badge-accent badge-sm font-bold shadow-md"))

    # Load README if it exists
    readme_path = inspector.extensions_dir / extension_name / "README.md"
    readme_content = ""

    if readme_path.is_file():
        try:
            readme_content = readme_path.read_text(encoding="utf-8")
            # Escape newlines and quotes for JS injection
            readme_content = json.dumps(readme_content)
        except Exception as e:
            logging.error(f"Failed to read README for {extension_name}: {e}")
            readme_content = json.dumps("*Failed to load README.*")
    else:
        readme_content = json.dumps("*No README.md found for this extension.*")

    modal_id = f"modal-{extension_name}-details"

    close_button = Form(
        Button(I(cls="fa-solid fa-xmark"), cls="btn btn-sm btn-circle btn-ghost absolute right-2 top-2"),
        method="dialog",
    )

    header_elements = [H3(f"{extension_name.capitalize()} Details", cls="font-bold text-2xl flex-grow")]

    if "sprocket" in gadgets:
        href_url = f"http://localhost:8000/docs#/{extension_name}"
        if access_token:
            href_url = f"http://localhost:8000/docs?token={access_token}#/{extension_name}"

        docs_link = A(
            I(cls="fa-solid fa-book"),
            " API Docs",
            href=href_url,
            target="_blank",
            cls="btn btn-ghost btn-outline btn-sm text-info ml-4",
            title="API Docs",
        )
        header_elements.append(docs_link)

    modal_content = Div(
        close_button,
        Div(*header_elements, cls="flex items-center w-full pr-8 mb-2"),
        Div(*badges, cls="flex gap-2 mb-6")
        if badges
        else P("No explicit gadgets loaded.", cls="text-sm opacity-50 mb-6"),
        Div(
            Div(id=f"readme-{extension_name}", cls="prose prose-sm prose-invert max-w-none"),
            cls="bg-base-300 p-4 rounded-lg border border-base-content/10 shadow-inner max-h-[60vh] overflow-y-auto",
        ),
        # Use marked.js to render the markdown
        Script(f"document.getElementById('readme-{extension_name}').innerHTML = marked.parse({readme_content});"),
        cls="modal-box w-11/12 max-w-3xl bg-base-100 shadow-2xl border border-secondary/20",
    )

    return Dialog(
        modal_content,
        Form(method="dialog", cls="modal-backdrop", children=[Button("close")]),
        id=modal_id,
        cls="modal modal-bottom sm:modal-middle",
        # Auto-open when injected
        open=True,
    )
