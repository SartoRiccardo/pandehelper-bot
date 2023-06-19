import discord
import bot.db.queries
from datetime import datetime
from typing import Callable, Any


class SwitchPlannerButton(discord.ui.Button):
    def __init__(self, switch_callback: Callable, is_active: bool, planner_id: int):
        self.is_active = is_active
        self.switch_callback = switch_callback
        super().__init__(
            label=f"Turn {'Off' if self.is_active else 'On'}",
            custom_id=f"planner:admin:turn:{planner_id}"[:100],
            style=discord.ButtonStyle.red if self.is_active else discord.ButtonStyle.green
        )

    async def callback(self, interaction: discord.Interaction) -> Any:
        await self.switch_callback(interaction, not self.is_active)


class ClearPlannerButton(discord.ui.Button):
    def __init__(self, clear_callback: Callable, planner_id: int):
        self.clear_callback = clear_callback
        super().__init__(
            label="Clear Planner",
            custom_id=f"planner:admin:clear:{planner_id}"[:100],
            style=discord.ButtonStyle.gray
        )

    async def callback(self, interaction: discord.Interaction) -> Any:
        await self.clear_callback(interaction)


class EditTimeButton(discord.ui.Button):
    def __init__(self, edit_time_callback: Callable, planner_id: int):
        self.edit_time_callback = edit_time_callback
        super().__init__(
            label="Edit Tile Expiry",
            custom_id=f"planner:admin:edit-time:{planner_id}"[:100],
            style=discord.ButtonStyle.gray
        )

    async def callback(self, interaction: discord.Interaction) -> Any:
        await self.edit_time_callback(interaction)


class PlannerAdminView(discord.ui.View):
    """A list of actions usable by admins in the team."""
    def __init__(self,
                 planner_channel_id: int,
                 refresh_planner: Callable,
                 planner_active: bool,
                 timeout: float = None):
        super().__init__(timeout=timeout)
        self.planner_id = planner_channel_id
        self.refresh_planner = refresh_planner
        self.add_item(
            SwitchPlannerButton(self.switch_planner, planner_active, self.planner_id)
        )
        self.add_item(
            ClearPlannerButton(self.clear_planner, self.planner_id)
        )
        self.add_item(
            EditTimeButton(self.edit_time, self.planner_id)
        )

    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def switch_planner(self, interaction: discord.Interaction, new_active: bool) -> None:
        await bot.db.queries.turn_planner(self.planner_id, new_active)
        await interaction.response.send_message(
            content=f"The planner has been turned {'on' if new_active else 'off'}!",
            ephemeral=True
        )
        await self.refresh_planner(self.planner_id)

    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def clear_planner(self, interaction: discord.Interaction):
        await bot.db.queries.set_clear_time(self.planner_id, datetime.now())
        await interaction.response.send_message(
            content=f"Cleared the planner!",
            ephemeral=True
        )
        await self.refresh_planner(self.planner_id)

    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def edit_time(self, interaction: discord.Interaction, tile: str, new_time: str):
        await interaction.response.send_message(
            content="Sorry, this doesn't work yet. It's 1AM and I'm eager to get this out.",
            ephemeral=True
        )
