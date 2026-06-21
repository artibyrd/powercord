from fasthtml.common import (
    H3,
    A,
    Button,
    Details,
    Div,
    Input,
    Label,
    Progress,
    Span,
    Summary,
)
from fasthtml.svg import Circle, Line, Svg
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


SEGMENT_MAP = {
    "0": {"a", "b", "c", "d", "e", "f"},
    "1": {"b", "c"},
    "2": {"a", "b", "g", "e", "d"},
    "3": {"a", "b", "g", "c", "d"},
    "4": {"f", "g", "b", "c"},
    "5": {"a", "f", "g", "c", "d"},
    "6": {"a", "f", "e", "d", "c", "g"},
    "7": {"a", "b", "c"},
    "8": {"a", "b", "c", "d", "e", "f", "g"},
    "9": {"a", "b", "c", "d", "f", "g"},
}


def _render_single_digit(digit_char: str, bg_color_class: str):
    active_segments = SEGMENT_MAP.get(digit_char, set())

    def seg_cls(name: str, pos_cls: str):
        is_active = name in active_segments
        if is_active:
            return Div(cls=f"absolute rounded-sm {bg_color_class} opacity-100 transition-all duration-200 {pos_cls}")
        else:
            return Div(cls=f"absolute rounded-sm bg-neutral/30 opacity-10 transition-all duration-200 {pos_cls}")

    return Div(
        seg_cls("a", "top-0 left-[3px] right-[3px] h-[3px]"),
        seg_cls("g", "top-[22px] left-[3px] right-[3px] h-[3px]"),
        seg_cls("d", "bottom-0 left-[3px] right-[3px] h-[3px]"),
        seg_cls("f", "top-[2px] left-0 w-[3px] h-[21px]"),
        seg_cls("b", "top-[2px] right-0 w-[3px] h-[21px]"),
        seg_cls("e", "bottom-[2px] left-0 w-[3px] h-[21px]"),
        seg_cls("c", "bottom-[2px] right-0 w-[3px] h-[21px]"),
        cls="w-8 h-12 relative flex-shrink-0",
    )


def SegmentedDigit(value: int, label: str, color_cls: str):
    """
    Retro digital watch 7-segment display component.
    """
    bg_color_class = color_cls.replace("text-", "bg-")

    val_str = str(value).zfill(2)
    digits_ui = [_render_single_digit(c, bg_color_class) for c in val_str]

    return Div(
        Div(
            *digits_ui,
            cls="flex gap-1.5 p-2 bg-black/60 rounded-md border border-neutral-700 shadow-inner justify-center items-center",
        ),
        Span(label, cls=f"text-xs font-bold mt-2 {color_cls} opacity-90"),
        cls="bg-base-200/30 rounded-box p-3 shadow-inner flex flex-col items-center justify-center",
    )


def ProgressBarStat(label: str, current: int, max_limit: int):
    """
    A labeled horizontal progress bar displaying current vs max limit.
    """
    percent = min(100, int((current / max_limit) * 100))
    if percent > 80:
        bar_color = "progress-error"
    elif percent > 50:
        bar_color = "progress-warning"
    else:
        bar_color = "progress-primary"

    return Div(
        Div(
            Span(label, cls="text-xs opacity-70 font-semibold"),
            Span(f"{current} / {max_limit}", cls="text-xs font-mono font-bold"),
            cls="flex justify-between items-center mb-1",
        ),
        Progress(
            value=str(current),
            max=str(max_limit),
            cls=f"progress {bar_color} w-full h-2 bg-base-300",
        ),
        cls="bg-base-200/30 rounded-box p-3 shadow-inner flex flex-col justify-center",
    )


def AlertsGauge(alert_pct: int, alert_count: int = 0):
    """
    SVG semi-circular alerts gauge with needle indicator.
    """
    if alert_pct <= 20:
        color_class = "text-success"
        stroke_class = "stroke-success"
    elif alert_pct <= 50:
        color_class = "text-warning"
        stroke_class = "stroke-warning"
    else:
        color_class = "text-error"
        stroke_class = "stroke-error"

    r = 36
    c = 226.19
    semi_c = 113.1
    offset = semi_c - (alert_pct / 100.0) * semi_c
    needle_angle = -90 + (alert_pct / 100.0) * 180

    return Div(
        Svg(
            Circle(
                cx="50",
                cy="50",
                r=str(r),
                stroke_width="8",
                cls="stroke-base-300 fill-transparent",
                stroke_dasharray=f"{semi_c} {c}",
                transform="rotate(-180 50 50)",
                stroke_linecap="round",
            ),
            Circle(
                cx="50",
                cy="50",
                r=str(r),
                stroke_width="8",
                cls=f"{stroke_class} fill-transparent transition-all duration-500 ease-in-out",
                stroke_dasharray=f"{semi_c} {c}",
                stroke_dashoffset=f"{offset:.2f}",
                transform="rotate(-180 50 50)",
                transform_origin="center",
                stroke_linecap="round",
            ),
            Line(
                x1="50",
                y1="50",
                x2="50",
                y2="22",
                stroke="currentColor",
                stroke_width="3",
                stroke_linecap="round",
                cls=f"{color_class} transition-transform duration-500 ease-in-out",
                transform=f"rotate({needle_angle} 50 50)",
            ),
            Circle(
                cx="50",
                cy="50",
                r="5",
                cls=f"fill-current {color_class}",
            ),
            SvgText(
                f"{alert_count} Alert{'s' if alert_count != 1 else ''}",
                x="50",
                y="68",
                text_anchor="middle",
                dominant_baseline="middle",
                cls="text-[12px] font-bold fill-base-content/80",
            ),
            SvgText(
                f"{alert_pct}%",
                x="50",
                y="85",
                text_anchor="middle",
                dominant_baseline="middle",
                cls="text-[10px] font-semibold fill-base-content/50",
            ),
            viewBox="0 0 100 100",
            cls="w-32 h-32",
        ),
        cls="flex flex-col items-center justify-center bg-base-200/30 rounded-box p-3 shadow-inner col-span-2",
    )
