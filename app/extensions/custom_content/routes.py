import re

from fasthtml.common import *
from sqlmodel import Session, select

from app.common.alchemy import init_connection_engine
from app.db.models import CustomContentItem
from app.extensions.custom_content.widget import _inject_dynamic_widget

# Fix #2: Name validation constraints
_NAME_MAX_LENGTH = 100
_NAME_PATTERN = re.compile(r"^[\w\s\-]+$")


def register_routes(rt):
    @rt("/admin/custom_content", methods=["GET"])
    def get_custom_content_list(req, sess):
        auth = sess.get("auth", {})
        if not auth:
            return "Unauthorized"

        engine = init_connection_engine()
        with Session(engine) as session:
            items = session.exec(select(CustomContentItem).order_by(CustomContentItem.id)).all()

            rows = []
            for item in items:
                rows.append(
                    Tr(
                        Td(item.name),
                        Td(item.format),
                        Td(
                            Button(
                                "Edit",
                                hx_get=f"/admin/custom_content/{item.id}/edit",
                                hx_target="#cc-editor-area",
                                cls="btn btn-sm btn-info mr-2",
                            ),
                            Button(
                                "Delete",
                                hx_delete=f"/admin/custom_content/{item.id}",
                                hx_target="closest tr",
                                hx_confirm="Are you sure?",
                                cls="btn btn-sm btn-error",
                            ),
                        ),
                    )
                )

            return Table(
                Thead(Tr(Th("Name"), Th("Format"), Th("Actions"))),
                Tbody(*rows),
                cls="table table-zebra w-full",
            )

    @rt("/admin/custom_content/new", methods=["GET"])
    def get_new_custom_content_form(req, sess):
        return _render_cc_form()

    @rt("/admin/custom_content/{item_id}/edit", methods=["GET"])
    def get_edit_custom_content_form(item_id: int, req, sess):
        engine = init_connection_engine()
        with Session(engine) as session:
            item = session.get(CustomContentItem, item_id)
            if not item:
                return "Not found"
            return _render_cc_form(item)

    @rt("/admin/custom_content", methods=["POST"])
    async def save_custom_content(req, sess):
        form = await req.form()
        item_id = form.get("id")
        name = str(form.get("name", "")).strip()
        format_type = form.get("format")
        has_frame = form.get("has_frame") == "on"
        content = form.get("content", "")

        # Fix #2: Validate name length and characters
        if not name or len(name) > _NAME_MAX_LENGTH:
            return Div(
                f"Name is required and must be {_NAME_MAX_LENGTH} characters or fewer.",
                cls="alert alert-error mt-4",
            )
        if not _NAME_PATTERN.match(name):
            return Div(
                "Name may only contain letters, numbers, spaces, underscores, and hyphens.",
                cls="alert alert-error mt-4",
            )

        engine = init_connection_engine()
        with Session(engine) as session:
            if item_id:
                item = session.get(CustomContentItem, int(item_id))
                item.name = name
                item.format = format_type
                item.has_frame = has_frame
                # Fix #4: Sanitization handled by model method
                item.set_content(content)
            else:
                item = CustomContentItem(name=name, format=format_type, has_frame=has_frame)
                item.set_content(content)
                session.add(item)
            session.commit()
            session.refresh(item)

            # Inject the widget so it's instantly available without restart
            _inject_dynamic_widget(item.id, item.name, item.content, item.format, item.has_frame)

        return Div(
            "Saved successfully!",
            cls="alert alert-success mt-4",
            hx_get="/admin/custom_content",
            hx_target="#cc-list",
            hx_trigger="load delay:1s",
        )

    @rt("/admin/custom_content/{item_id}", methods=["DELETE"])
    def delete_custom_content(item_id: int, req, sess):
        engine = init_connection_engine()
        with Session(engine) as session:
            item = session.get(CustomContentItem, item_id)
            if item:
                session.delete(item)
                session.commit()
        # Returning empty removes the row
        return ""


def _render_cc_form(item=None):
    name_val = item.name if item else ""
    format_val = item.format if item else "html"
    content_val = item.content if item else ""
    has_frame_val = item.has_frame if item else True
    item_id = item.id if item else ""

    return Form(
        # Inject Quill dependencies
        Link(rel="stylesheet", href="https://cdn.quilljs.com/1.3.6/quill.snow.css"),
        Script(src="https://cdn.quilljs.com/1.3.6/quill.js"),
        Hidden(name="id", value=item_id),
        Div(
            Label("Widget Name (Unique Identifier)", cls="label font-bold"),
            Input(type="text", name="name", value=name_val, required=True, cls="input input-bordered w-full"),
            cls="form-control mb-4",
        ),
        Div(
            Label(
                Span("Include Standard Frame/Border?", cls="label-text"),
                Input(type="checkbox", name="has_frame", checked=has_frame_val, cls="checkbox"),
                cls="label cursor-pointer justify-start gap-4",
            ),
            cls="form-control mb-4 border border-base-content/10 p-2 rounded-lg",
        ),
        Div(
            Label("Format", cls="label font-bold"),
            Select(
                Option("Rich Text (HTML)", value="html", selected=(format_val == "html")),
                Option("Markdown", value="markdown", selected=(format_val == "markdown")),
                name="format",
                cls="select select-bordered w-full",
                id="cc-format-selector",
                onchange="toggleEditorMode()",
            ),
            cls="form-control mb-4",
        ),
        Div(
            Label("Content", cls="label font-bold"),
            Div(
                id="quill-editor",
                cls="bg-base-100 text-base-content min-h-[200px]" if format_val == "html" else "hidden",
            ),
            Textarea(
                content_val,
                name="content",
                id="cc-content-input",
                cls="textarea textarea-bordered w-full min-h-[200px]" if format_val != "html" else "hidden",
            ),
            cls="form-control mb-4",
        ),
        Div(
            Button("Save Content", cls="btn btn-primary"),
            Button(
                "Cancel",
                type="button",
                cls="btn btn-ghost ml-2",
                onclick="document.getElementById('cc-editor-area').innerHTML='';",
            ),
            cls="mt-4",
        ),
        # Quill initialization script
        Script(
            """
        function initQuill() {
            if (typeof Quill === 'undefined') {
                setTimeout(initQuill, 100);
                return;
            }
            const editorEl = document.getElementById('quill-editor');
            if (!editorEl) return;
            if (editorEl.classList.contains('ql-container')) return;

            window.quill = new Quill('#quill-editor', {
                theme: 'snow',
                modules: {
                    toolbar: [
                        ['bold', 'italic', 'underline', 'strike'],
                        ['blockquote', 'code-block'],
                        [{ 'header': 1 }, { 'header': 2 }],
                        [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                        [{ 'color': [] }, { 'background': [] }],
                        [{ 'font': [] }],
                        [{ 'align': [] }],
                        ['clean'],
                        ['link', 'image', 'video']
                    ]
                }
            });
            window.quill.root.innerHTML = document.getElementById('cc-content-input').value;
            window.quill.on('text-change', function() {
                document.getElementById('cc-content-input').value = window.quill.root.innerHTML;
            });
        }

        function toggleEditorMode() {
            const format = document.getElementById('cc-format-selector').value;
            const quillContainer = document.getElementById('quill-editor');
            const textarea = document.getElementById('cc-content-input');

            let toolbar = null;
            if (quillContainer && quillContainer.previousElementSibling && quillContainer.previousElementSibling.classList.contains('ql-toolbar')) {
                toolbar = quillContainer.previousElementSibling;
            }

            if (format === 'html') {
                if (textarea) textarea.classList.add('hidden');
                if (quillContainer) quillContainer.classList.remove('hidden');
                if (toolbar) toolbar.classList.remove('hidden');
                initQuill();
            } else {
                if (textarea) textarea.classList.remove('hidden');
                if (quillContainer) quillContainer.classList.add('hidden');
                if (toolbar) toolbar.classList.add('hidden');
            }
        }

        // Wait a small bit for external script
        setTimeout(initQuill, 200);
        """
        ),
        hx_post="/admin/custom_content",
        hx_target="#cc-editor-area",
    )
