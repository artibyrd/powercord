from fasthtml.common import (
    H3,
    Button,
    Div,
    Input,
    Label,
)


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
