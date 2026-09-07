"""Example UI view and interactive component classes."""

import asyncio
import os
from typing import List
from urllib.parse import quote_plus

import aiohttp
import nextcord

WEBHOOK_URL = os.environ.get("POWERCORD_EXAMPLE_WEBHOOK_URL", "")


async def send_to_webhook(url: str, content: str) -> None:
    """Create a new HTTP session and use it to send content via webhook."""
    async with aiohttp.ClientSession() as session:
        webhook = nextcord.Webhook.from_url(url, session=session)
        await webhook.send(content)


if __name__ == "__main__":
    # Test the webhook directly
    asyncio.run(send_to_webhook(f"{WEBHOOK_URL}", "Hello, world!"))


# Example simple search button class
class Google(nextcord.ui.View):
    def __init__(self, query: str):
        super().__init__()
        query = quote_plus(query)
        url = f"https://www.google.com/search?q={query}"
        self.add_item(nextcord.ui.Button(label="Click Here", url=url))


# Example confirmation view class
class Confirm(nextcord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    @nextcord.ui.button(label="Confirm", style=nextcord.ButtonStyle.green)
    async def confirm(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_message("Confirming", ephemeral=True)
        self.value = True
        self.stop()

    @nextcord.ui.button(label="Cancel", style=nextcord.ButtonStyle.grey)
    async def cancel(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_message("Cancelling", ephemeral=True)
        self.value = False
        self.stop()


# Example counter button view class
class Counter(nextcord.ui.View):
    @nextcord.ui.button(label="0", style=nextcord.ButtonStyle.red)
    async def count(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        number = int(button.label) if button.label else 0
        if number + 1 >= 5:
            button.style = nextcord.ButtonStyle.green
            button.disabled = True
        button.label = str(number + 1)
        await interaction.response.edit_message(view=self)


# Example ephemeral counter button view class
class EphemeralCounter(nextcord.ui.View):
    @nextcord.ui.button(label="Click", style=nextcord.ButtonStyle.blurple)
    async def receive(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_message("Enjoy!", view=Counter(), ephemeral=True)


# Example dropdown select view classes
class Dropdown(nextcord.ui.Select):
    def __init__(self):
        options = [
            nextcord.SelectOption(label="Red", description="Your favourite colour is red", emoji="🟥"),
            nextcord.SelectOption(label="Green", description="Your favourite colour is green", emoji="🟩"),
            nextcord.SelectOption(label="Blue", description="Your favourite colour is blue", emoji="🟦"),
        ]
        super().__init__(
            placeholder="Choose your favourite colour...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: nextcord.Interaction):
        await interaction.response.send_message(f"Your favourite colour is {self.values[0]}")


class DropdownView(nextcord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(Dropdown())


# TicTacToe game logic class
class TicTacToeButton(nextcord.ui.Button["TicTacToe"]):
    def __init__(self, x: int, y: int):
        super().__init__(style=nextcord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: nextcord.Interaction):
        assert self.view is not None
        view: TicTacToe = self.view
        state = view.board[self.y][self.x]
        if state in (view.X, view.O):
            return

        if view.current_player == view.X:
            self.style = nextcord.ButtonStyle.danger
            self.label = "X"
            self.disabled = True
            view.board[self.y][self.x] = view.X
            view.current_player = view.O
            content = "It is now O's turn"
        else:
            self.style = nextcord.ButtonStyle.success
            self.label = "O"
            self.disabled = True
            view.board[self.y][self.x] = view.O
            view.current_player = view.X
            content = "It is now X's turn"

        winner = view.check_board_winner()
        if winner is not None:
            if winner == view.X:
                content = "X won!"
            elif winner == view.O:
                content = "O won!"
            else:
                content = "It's a tie!"

            for child in view.children:
                child.disabled = True

            view.stop()

        await interaction.response.edit_message(content=content, view=view)


# TicTacToe board View class
class TicTacToe(nextcord.ui.View):
    children: List[TicTacToeButton]
    X = -1
    O = 1
    Tie = 2

    def __init__(self):
        super().__init__()
        self.current_player = self.X
        self.board = [
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ]

        for x in range(3):
            for y in range(3):
                self.add_item(TicTacToeButton(x, y))

    def check_board_winner(self):
        for across in self.board:
            value = sum(across)
            if value == 3:
                return self.O
            elif value == -3:
                return self.X

        for line in range(3):
            value = self.board[0][line] + self.board[1][line] + self.board[2][line]
            if value == 3:
                return self.O
            elif value == -3:
                return self.X

        diag = self.board[0][2] + self.board[1][1] + self.board[2][0]
        if diag == 3:
            return self.O
        elif diag == -3:
            return self.X

        diag = self.board[0][0] + self.board[1][1] + self.board[2][2]
        if diag == 3:
            return self.O
        elif diag == -3:
            return self.X

        if all(i != 0 for row in self.board for i in row):
            return self.Tie

        return None
