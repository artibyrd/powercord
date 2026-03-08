from typing import Callable, Coroutine

import nextcord
from nextcord.ui import Button, View


class ConfirmationView(View):
    """
    A view with Confirm and Cancel buttons.
    """

    value: bool | None

    def __init__(
        self,
        timeout: float = 60.0,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        on_confirm: Callable[[nextcord.Interaction], Coroutine] | None = None,
        on_cancel: Callable[[nextcord.Interaction], Coroutine] | None = None,
    ):
        """
        Initializes the ConfirmationView.

        Args:
            timeout (float): The timeout for the view in seconds.
            confirm_label (str): Label for the confirm button.
            cancel_label (str): Label for the cancel button.
            on_confirm (Callable): Async callback for confirmation.
            on_cancel (Callable): Async callback for cancellation.
        """
        super().__init__(timeout=timeout)
        self.value = None
        self.on_confirm_callback = on_confirm
        self.on_cancel_callback = on_cancel

        self.confirm_button: Button = Button(style=nextcord.ButtonStyle.green, label=confirm_label)
        self.confirm_button.callback = self.confirm  # type: ignore[method-assign]
        self.add_item(self.confirm_button)

        self.cancel_button: Button = Button(style=nextcord.ButtonStyle.red, label=cancel_label)
        self.cancel_button.callback = self.cancel  # type: ignore[method-assign]
        self.add_item(self.cancel_button)

    async def confirm(self, interaction: nextcord.Interaction):
        """Standard confirm callback."""
        self.value = True
        self.stop()
        if self.on_confirm_callback:
            await self.on_confirm_callback(interaction)
        else:
            await interaction.response.defer()

    async def cancel(self, interaction: nextcord.Interaction):
        """Standard cancel callback."""
        self.value = False
        self.stop()
        if self.on_cancel_callback:
            await self.on_cancel_callback(interaction)
        else:
            await interaction.response.defer()
