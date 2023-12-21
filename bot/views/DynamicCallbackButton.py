import discord
from typing import Callable, Awaitable, Any


class DynamicCallbackButton(discord.ui.Button):
    def __init__(self, *args, cb: Callable[[Any], Awaitable[Any]] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cb = cb

    def set_cb(self, cb: Callable[[Any], Awaitable[Any]]) -> None:
        self.cb = cb

    async def callback(self, interaction: discord.Interaction) -> Any:
        await self.cb(interaction)
