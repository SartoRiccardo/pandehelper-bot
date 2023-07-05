import discord
from typing import List, Tuple, Callable
import bloonspy
from bot.utils.emojis import X, ARROW_RIGHT


class BannerSelect(discord.ui.Select):
    def __init__(self,
                 banners: List[Tuple[str, bool]],
                 planner_id: int,
                 select_idx: int = 0,
                 preview_list: bool = False,
                 callback: Callable = None):
        banners = sorted(banners, key=lambda x: x[0])
        options = [
            discord.SelectOption(label=code, emoji=X if claimed else ARROW_RIGHT)
            for code, claimed in banners
        ]
        self.callback_func = callback

        placeholder = "Claim a tile"
        if preview_list:
            if len(banners) > 1:
                placeholder = f"Claim a tile ({banners[0][0]} - {banners[len(banners)-1][0]})"
            else:
                placeholder = f"Claim {banners[0][0]}"

        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id=f"planner:user:banner-select:{planner_id}-{select_idx}"[:100]
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

        banner_idx = 0
        while banner_idx < len(banners):
            select = BannerSelect(
                banners[banner_idx:banner_idx+25],
                planner_channel_id,
                select_idx=int(banner_idx/25),
                preview_list=(len(banners) > 25),
                callback=self.switch_tile)
            self.add_item(select)
            banner_idx += 25

    async def switch_tile(self, interaction: discord.Interaction, tile: str) -> None:
        response_content, should_refresh = await self.switch_tile_callback(interaction.user.id, self.planner_channel_id, tile)
        await interaction.response.send_message(
            content=response_content,
            ephemeral=True
        )
        if should_refresh:
            await self.refresh_planner(self.planner_channel_id)