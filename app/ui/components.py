from fasthtml.common import (
    H3,
    A,
    Button,
    Details,
    Div,
    Input,
    Label,
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
        stroke_color = "var(--success)"
        color_class = "text-success"
    elif score >= 50:
        stroke_color = "var(--warning)"
        color_class = "text-warning"
    else:
        stroke_color = "var(--error)"
        color_class = "text-error"

    r = 36
    c = 226.19  # Approx 2 * pi * 36
    offset = c - (score / 100.0) * c

    return Div(
        Svg(
            Circle(
                cx="50", cy="50", r=str(r), stroke_width="8", stroke="rgba(255, 255, 255, 0.15)", fill="transparent"
            ),
            Circle(
                cx="50",
                cy="50",
                r=str(r),
                stroke_width="8",
                stroke=stroke_color,
                fill="transparent",
                cls="transition-all duration-500 ease-in-out",
                stroke_dasharray=str(c),
                stroke_dashoffset=f"{offset:.2f}",
                transform="rotate(-90 50 50)",
                stroke_linecap="round",
            ),
            SvgText(
                f"{score}%",
                x="50",
                y="45",
                text_anchor="middle",
                dominant_baseline="middle",
                fill=stroke_color,
                cls=f"font-black {color_class}",
                style="font-size: 24px; font-family: 'Orbitron', sans-serif;",
            ),
            SvgText(
                f"{alert_count} alert{'s' if alert_count != 1 else ''}",
                x="50",
                y="68",
                text_anchor="middle",
                dominant_baseline="middle",
                fill="var(--bc)",
                fill_opacity="0.7",
                style="font-size: 10px; font-family: 'Share Tech Mono', monospace;",
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
        seg_cls("a", "top-0 left-[2px] right-[2px] h-[2px]"),
        seg_cls("g", "top-[15px] left-[2px] right-[2px] h-[2px]"),
        seg_cls("d", "bottom-0 left-[2px] right-[2px] h-[2px]"),
        seg_cls("f", "top-[2px] left-0 w-[2px] h-[13px]"),
        seg_cls("b", "top-[2px] right-0 w-[2px] h-[13px]"),
        seg_cls("e", "bottom-[2px] left-0 w-[2px] h-[13px]"),
        seg_cls("c", "bottom-[2px] right-0 w-[2px] h-[13px]"),
        cls="w-5 h-8 relative flex-shrink-0",
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
            cls="flex gap-1 p-1.5 bg-black/60 rounded-md border border-neutral-700 shadow-inner justify-center items-center",
        ),
        Span(label, cls=f"text-xs font-bold tracking-wider uppercase mt-2 {color_cls} opacity-90"),
        cls="bg-black/20 rounded-md p-2 border border-white/5 flex flex-col items-center justify-center w-full",
    )


def ProgressBarStat(label: str, current: int, max_limit: int):
    """
    A labeled horizontal progress bar displaying current vs max limit.
    """
    percent = min(100, int((current / max_limit) * 100))

    return Div(
        Div(
            Span(
                label.upper(), cls="text-[10px] font-bold tracking-wider uppercase text-secondary/90 whitespace-nowrap"
            ),
            Span(f"{current} / {max_limit}", cls="text-xs font-mono font-bold text-info whitespace-nowrap"),
            cls="flex justify-between items-center mb-1.5 w-full",
        ),
        Div(
            Div(
                cls="bg-gradient-to-r from-[#e779c1] to-[#58c7f3] h-full rounded-full",
                style=f"width: {percent}%",
            ),
            cls="w-full bg-black/40 h-2.5 rounded-full overflow-hidden border border-white/5",
        ),
        cls="bg-black/20 rounded-md p-3 border border-white/5 flex flex-col justify-center w-full",
    )


def AlertsGauge(alert_pct: int, alert_count: int = 0):
    """
    SVG semi-circular alerts gauge with needle indicator.
    """
    if alert_pct <= 20:
        stroke_color = "var(--success)"
    elif alert_pct <= 50:
        stroke_color = "var(--warning)"
    else:
        stroke_color = "var(--error)"

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
                stroke="rgba(255, 255, 255, 0.15)",
                fill="transparent",
                stroke_dasharray=f"{semi_c} {c}",
                transform="rotate(-180 50 50)",
                stroke_linecap="round",
            ),
            Circle(
                cx="50",
                cy="50",
                r=str(r),
                stroke_width="8",
                stroke=stroke_color,
                fill="transparent",
                cls="transition-all duration-500 ease-in-out",
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
                stroke=stroke_color,
                stroke_width="3",
                stroke_linecap="round",
                cls="transition-transform duration-500 ease-in-out",
                transform=f"rotate({needle_angle} 50 50)",
            ),
            Circle(
                cx="50",
                cy="50",
                r="5",
                fill=stroke_color,
            ),
            SvgText(
                f"{alert_count} Alert{'s' if alert_count != 1 else ''}",
                x="50",
                y="68",
                text_anchor="middle",
                dominant_baseline="middle",
                fill="var(--bc)",
                style="font-size: 11px; font-family: 'Orbitron', sans-serif; font-weight: bold;",
            ),
            SvgText(
                f"{alert_pct}%",
                x="50",
                y="82",
                text_anchor="middle",
                dominant_baseline="middle",
                fill="var(--bc)",
                fill_opacity="0.7",
                style="font-size: 10px; font-family: 'Share Tech Mono', monospace;",
            ),
            viewBox="0 0 100 100",
            cls="w-32 h-32",
        ),
        cls="flex flex-col items-center justify-center",
    )
