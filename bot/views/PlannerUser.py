import discord
from typing import List, Tuple, Callable
import bloonspy
from bot.utils.emojis import X, ARROW_RIGHT


class BannerSelect(discord.ui.Select):
    def __init__(self,
                 banners: List[Tuple[str, bool]],
                 callback: Callable = None):
        banners = sorted(banners, key=lambda x: x[0])
        options = [
            discord.SelectOption(label=code, emoji=X if claimed else ARROW_RIGHT)
            for code, claimed in banners
        ]
        self.callback_func = callback
        super().__init__(
            placeholder="Claim a tile",
            options=options,
            custom_id="planner:user:bannerselect"
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.callback_func:
            await self.callback_func(interaction, self.values[0])


class PlannerUserView(discord.ui.View):
    """A list of actions usable by every user in the team."""
    def __init__(self,
                 banners: List[Tuple[str, bool]],
                 planner_channel_id: int,
                 switch_tile_callback: Callable,
                 refresh_planner: Callable,
                 timeout: float = None):
        super().__init__(timeout=timeout)
        self.banners = banners
        self.planner_channel_id = planner_channel_id
        self.refresh_planner = refresh_planner
        self.switch_tile_callback = switch_tile_callback
        self.select = BannerSelect(banners, callback=self.switch_tile)
        self.add_item(self.select)

    async def switch_tile(self, interaction: discord.Interaction, tile: str) -> None:
        response_content, should_refresh = await self.switch_tile_callback(interaction.user.id, self.planner_channel_id, tile)
        await interaction.response.send_message(
            content=response_content,
            ephemeral=True
        )
        if should_refresh:
            await self.refresh_planner(self.planner_channel_id)

    @staticmethod
    async def init_all() -> List["PlannerUserView"]:
        """Generate all views to register for the bot setup hook."""
        pass

