import discord
from typing import Any, Callable
import bot.utils.bloons


class TileButton(discord.ui.Button):
    def __init__(self, tile_name: str, idx: int, sup_callback: Callable):
        self.idx = idx
        self.sup_callback = sup_callback
        super().__init__(
            label=tile_name,
            style=discord.ButtonStyle.blurple
        )

    async def callback(self, interaction: discord.Interaction) -> Any:
        await self.sup_callback(interaction, self.idx)


class SpawnlockPaginateView(discord.ui.View):
    """A list of actions usable by every user in the team."""
    def __init__(self,
                 tile_data: list[dict[str, Any]],
                 original_interaction: discord.Interaction = None,
                 timeout: float = 180):
        super().__init__(timeout=timeout)
        self.tile_data = tile_data
        self.current = 0
        self.original_interaction = original_interaction

        for i in range(len(tile_data)):
            self.add_item(TileButton(tile_data[i]["Code"], i, self.edit_embed))

    def set_original_interaction(self, original_interaction: discord.Interaction) -> None:
        self.original_interaction = original_interaction

    async def edit_embed(self, interaction: discord.Interaction, tile_idx: int) -> None:
        if self.original_interaction.user != interaction.user:
            await interaction.response.send_message(
                content="💢 Hands off!",
                ephemeral=True,
            )
            return

        if tile_idx == self.current:
            await interaction.response.send_message(
                content="ⓘ You have already selected that tile!",
                ephemeral=True,
            )
            return

        self.current = tile_idx
        await interaction.response.send_message(
            content=f"ⓘ Showing tile **{self.tile_data[tile_idx]['Code']}**!",
            ephemeral=True,
        )

        embed = bot.utils.bloons.raw_challenge_to_embed(self.tile_data[tile_idx])
        await self.original_interaction.edit_original_response(
            embed=embed,
        )
