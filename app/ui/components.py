from fasthtml.common import (
    H3,
    A,
    Button,
    Details,
    Div,
    Input,
    Label,
    Summary,
)
from fasthtml.svg import Circle, Svg
from fasthtml.svg import Text as SvgText


def PrimaryButton(text: str, **kwargs):
    """
    Creates a primary styled button.

    Args:
        text (str): The button text.
        **kwargs: Additional arguments for the Button component.
    """
    return Button(text, cls="btn btn-primary", **kwargs)


def SecondaryButton(text: str, **kwargs):
    """
    Creates a secondary styled button.

    Args:
        text (str): The button text.
        **kwargs: Additional arguments for the Button component.
    """
    return Button(text, cls="btn btn-secondary", **kwargs)


def DangerButton(text: str, **kwargs):
    """
    Creates a danger styled button.

    Args:
        text (str): The button text.
        **kwargs: Additional arguments for the Button component.
    """
    return Button(text, cls="btn btn-error", **kwargs)


def FormLabel(text: str, **kwargs):
    """
    Creates a styled form label.

    Args:
        text (str): The label text.
        **kwargs: Additional arguments for the Label component.
    """
    return Label(text, cls="label", **kwargs)


def FormInput(**kwargs):
    """
    Creates a styled form input.

    Args:
        **kwargs: Additional arguments for the Input component.
    """
    cls = kwargs.pop("cls", "")
    return Input(cls=f"input input-bordered w-full {cls}", **kwargs)


def Card(title, content, **kwargs):
    """
    Creates a card component with a title.

    Args:
        title (str | Component): The card title.
        content: The content of the card body.
        **kwargs: Additional arguments for the card container.
    """
    header = H3(title, cls="card-title") if isinstance(title, str) else title
    cls = kwargs.pop("cls", "")

    return Div(
        Div(header, content, cls="card-body"),
        cls=f"card bg-base-100 shadow-xl {cls}",
        **kwargs,
    )


def HealthScoreArc(score: int, alert_count: int = 0):
    """
    Standardized SVG circular progress indicator displaying score and alert counts.
    """
    if score >= 80:
        color_class = "text-success"
        stroke_class = "stroke-success"
    elif score >= 50:
        color_class = "text-warning"
        stroke_class = "stroke-warning"
    else:
        color_class = "text-error"
        stroke_class = "stroke-error"

    r = 36
    c = 226.19  # Approx 2 * pi * 36
    offset = c - (score / 100.0) * c

    return Div(
        Svg(
            Circle(cx="50", cy="50", r=str(r), stroke_width="8", cls="stroke-base-300 fill-transparent"),
            Circle(
                cx="50",
                cy="50",
                r=str(r),
                stroke_width="8",
                cls=f"{stroke_class} fill-transparent transition-all duration-500 ease-in-out",
                stroke_dasharray=str(c),
                stroke_dashoffset=f"{offset:.2f}",
                transform="rotate(-90 50 50)",
                stroke_linecap="round",
            ),
            SvgText(
                f"{score}%",
                x="50",
                y="46",
                text_anchor="middle",
                dominant_baseline="middle",
                cls=f"text-2xl font-black fill-current {color_class}",
            ),
            SvgText(
                f"{alert_count} alert{'s' if alert_count != 1 else ''}",
                x="50",
                y="64",
                text_anchor="middle",
                dominant_baseline="middle",
                cls="text-[11px] font-bold fill-base-content/70",
            ),
            viewBox="0 0 100 100",
            cls="w-32 h-32",
        ),
        cls="flex flex-col items-center justify-center",
    )


def TabGroup(tabs: list[tuple[str, str, bool]], target_id: str):
    """
    Tabbed filter component for page filtering.
    """
    target = target_id if target_id.startswith("#") else f"#{target_id}"
    tab_elements = []
    click_script = (
        "const tabs = Array.from(this.parentElement.children); "
        "tabs.forEach(t => t.classList.remove('tab-active', '!bg-primary', '!text-primary-content', 'font-bold', 'shadow-md')); "
        "this.classList.add('tab-active', '!bg-primary', '!text-primary-content', 'font-bold', 'shadow-md');"
    )
    for label, url, is_active in tabs:
        cls = "tab"
        if is_active:
            cls += " tab-active !bg-primary !text-primary-content font-bold shadow-md"
        tab_elements.append(A(label, cls=cls, hx_get=url, hx_target=target, hx_swap="innerHTML", onclick=click_script))
    return Div(*tab_elements, cls="tabs tabs-boxed")


def Accordion(title: str, *children, open: bool = False, **kwargs):
    """
    Reusable DaisyUI details/summary collapsible wrapper.
    """
    open_kwargs = {"open": "open"} if open else {}
    return Details(
        Summary(title, cls="collapse-title text-lg font-medium"),
        Div(*children, cls="collapse-content"),
        cls="collapse collapse-arrow bg-base-200 card border border-base-content/20",
        **{**open_kwargs, **kwargs},
    )
