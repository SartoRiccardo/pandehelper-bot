import discord
from typing import Callable


class OwnerButton(discord.ui.Button):
    def __init__(
            self,
            owner: discord.User,
            callback_func: Callable,
            *args,
            **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.callback_func = callback_func

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.callback_func(interaction)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        should_handle = self.owner is None or self.owner.id == interaction.user.id
        if not should_handle:
            await interaction.response.send_message(
                content=f"The command was executed by <@{self.owner.id}>. "
                        "Run the command yourself!",
                ephemeral=True,
            )

        return should_handle
