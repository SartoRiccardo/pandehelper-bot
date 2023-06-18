import discord
import bot.db.queries
from datetime import datetime
from typing import Callable, Any


class SwitchPlannerButton(discord.ui.Button):
    def __init__(self, switch_callback: Callable, is_active: bool):
        self.is_active = is_active
        self.switch_callback = switch_callback
        super().__init__(
            label=f"Turn {'Off' if self.is_active else 'On'}",
            custom_id="planner:admin:turn",
            style=discord.ButtonStyle.red if self.is_active else discord.ButtonStyle.green
        )

    async def callback(self, interaction: discord.Interaction) -> Any:
        await self.switch_callback(interaction, not self.is_active)


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
        self.turn_button = SwitchPlannerButton(self.switch_planner, planner_active)
        self.add_item(self.turn_button)

    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def switch_planner(self, interaction: discord.Interaction, new_active: bool) -> None:
        await bot.db.queries.turn_planner(self.planner_id, new_active)
        await interaction.response.send_message(
            content=f"The planner has been turned {'on' if new_active else 'off'}!",
            ephemeral=True
        )
        await self.refresh_planner(self.planner_id)

    @discord.ui.button(label="Clear Planner", style=discord.ButtonStyle.gray, custom_id="planner:admin:clear")
    async def btn_clear(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await bot.db.queries.set_clear_time(self.planner_id, datetime.now())
        await interaction.response.send_message(
            content=f"Cleared the planner!",
            ephemeral=True
        )
        await self.refresh_planner(self.planner_id)

    @discord.ui.button(label="Edit Tile Time", style=discord.ButtonStyle.gray, custom_id="planner:admin:edit_time")
    async def btn_edit_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass
