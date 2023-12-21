import discord
from typing import Any, Callable, Awaitable
from .DynamicCallbackButton import DynamicCallbackButton


SelectPageCallback = Callable[[discord.Interaction, int], Awaitable[None]]


class EmbedPaginateView(discord.ui.View):
    """A way to paginate embeds."""
    def __init__(self,
                 embeds: list[discord.Embed],
                 original_interaction: discord.Interaction = None,
                 timeout: float = 180,
                 current: int = 0):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.current = current
        self.original_interaction = original_interaction

        self.btn_prev = DynamicCallbackButton(
            label="Previous",
            emoji="◀️",
            cb=self.prev_page,
            disabled=True
        )
        self.add_item(self.btn_prev)
        self.btn_next = DynamicCallbackButton(
            label="Next",
            emoji="▶️",
            cb=self.next_page
        )
        self.add_item(self.btn_next)

    async def prev_page(self, interaction: discord.Interaction) -> None:
        await self.edit_embed(interaction, max(0, self.current-1))

    async def next_page(self, interaction: discord.Interaction) -> None:
        await self.edit_embed(interaction, min(len(self.embeds)-1, self.current+1))

    async def edit_embed(self, interaction: discord.Interaction, idx: int) -> None:
        if self.original_interaction.user != interaction.user:
            await interaction.response.send_message(
                content="💢 You can't click this embed! **Run the command yourself!**",
                ephemeral=True,
            )
            return

        if idx == self.current:
            await interaction.response.send_message(
                content="ⓘ You have already selected that page!",
                ephemeral=True,
            )
            return
        self.current = idx
        self.btn_prev.disabled = self.current == 0
        self.btn_next.disabled = self.current == len(self.embeds)-1

        await interaction.response.send_message(
            content=f"ⓘ Showing page **{idx+1}**!",
            ephemeral=True,
        )

        await self.original_interaction.edit_original_response(
            embed=self.embeds[idx],
            view=self
        )
