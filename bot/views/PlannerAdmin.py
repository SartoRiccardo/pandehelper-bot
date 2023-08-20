import discord
import bot.db.queries.planner
from datetime import datetime, timedelta
from typing import Callable, Any


def check_manage_guild(wrapped: Callable):
    async def _wrapper(self, interaction: discord.Interaction, *args):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                content="You need *Manage Guild* permissions to use this!",
                ephemeral=True,
            )
            return
        await wrapped(self, interaction, *args)
    return _wrapper


class SwitchPlannerButton(discord.ui.Button):
    def __init__(self, switch_callback: Callable, is_active: bool, planner_id: int):
        self.is_active = is_active
        self.switch_callback = switch_callback
        super().__init__(
            label=f"Turn {'Off' if self.is_active else 'On'}",
            custom_id=f"planner:admin:turn:{planner_id}"[:100],
            style=discord.ButtonStyle.red if self.is_active else discord.ButtonStyle.green
        )

    @check_manage_guild
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

    @check_manage_guild
    async def callback(self, interaction: discord.Interaction) -> Any:
        await self.clear_callback(interaction)


class ForceUnclaimModal(discord.ui.Modal, title="Force a tile to be unclaimed"):
    tile_code = discord.ui.TextInput(label="Tile Code", min_length=3, max_length=3, placeholder="FFB", required=True)

    def __init__(self, planner_id: int, force_unclaim_callback: Callable, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.planner_id = planner_id
        self.force_unclaim_callback = force_unclaim_callback

    async def on_submit(self, interaction: discord.Interaction) -> None:
        tile_code = self.tile_code.value.upper()
        await self.force_unclaim_callback(interaction, self.planner_id, tile_code)


class ForceUnclaimButton(discord.ui.Button):
    def __init__(self, unclaim_callback: Callable, planner_id: int):
        self.unclaim_callback = unclaim_callback
        self.planner_id = planner_id
        super().__init__(
            label="Force Unclaim",
            custom_id=f"planner:admin:unclaim:{planner_id}"[:100],
            style=discord.ButtonStyle.gray
        )

    @check_manage_guild
    async def callback(self, interaction: discord.Interaction) -> Any:
        await interaction.response.send_modal(
            ForceUnclaimModal(self.planner_id, self.unclaim_callback)
        )


class TimeEditModal(discord.ui.Modal, title="Edit a Tile's Expiration Time"):
    tile_code = discord.ui.TextInput(label="Tile Code", min_length=3, max_length=3, placeholder="FFB", required=True)
    expire_time = discord.ui.TextInput(
        label="Stale in", placeholder="13:55 (exactly as seen in-game)",
        min_length=3, max_length=5, required=True
    )

    def __init__(self, planner_id: int, edit_tile_callback: Callable, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.planner_id = planner_id
        self.edit_tile_callback = edit_tile_callback

    async def on_submit(self, interaction: discord.Interaction) -> None:
        now = datetime.now()
        tile_code = self.tile_code.value.upper()
        time_parts = self.expire_time.value.split(":")
        error = False
        if len(time_parts) != 2:
            error = True
        for part in time_parts:
            if not part.isnumeric():
                error = True
                break
        hours, minutes = 0, 0
        if not error:
            hours, minutes = [int(part) for part in time_parts]
            if minutes < 0 or minutes >= 60 or hours < 0 or hours > 24:
                error = True

        if error:
            await interaction.response.send_message(
                content="Invalid format for `Stale In`! Must be `hh:mm`, it's in "
                        "how many hours and minutes the tile will go stale in!\n"
                        "For example: *13:55*."
            )
            return

        decay_time = now + timedelta(hours=hours, minutes=minutes)
        await self.edit_tile_callback(interaction, self.planner_id, tile_code, decay_time)


class EditTimeButton(discord.ui.Button):
    def __init__(self, edit_time_callback: Callable, planner_id: int):
        self.edit_time_callback = edit_time_callback
        self.planner_id = planner_id
        super().__init__(
            label="Edit Tile Expiry",
            custom_id=f"planner:admin:edit-time:{planner_id}"[:100],
            style=discord.ButtonStyle.gray
        )

    @check_manage_guild
    async def callback(self, interaction: discord.Interaction) -> Any:
        await interaction.response.send_modal(TimeEditModal(self.planner_id, self.edit_time_callback))


class AddRemoveTileModal(discord.ui.Modal, title="Add or Remove a Tile"):
    tile_code = discord.ui.TextInput(label="Tile Code", min_length=3, max_length=3, placeholder="FFB", required=True)
    recap_after = discord.ui.TextInput(
        label="Recapture After (hours)", placeholder="24 (leave blank to remove the tile)",
        min_length=0, max_length=2, required=False,
    )

    def __init__(self, planner_id: int,
                 add_callback: Callable,
                 remove_callback: Callable,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.planner_id = planner_id
        self.add_callback = add_callback
        self.remove_callback = remove_callback

    async def on_submit(self, interaction: discord.Interaction) -> None:
        tile_code = self.tile_code.value.upper()
        remove_tile = len(self.recap_after.value) == 0
        if not remove_tile and (
                not self.recap_after.value.isnumeric() or
                int(self.recap_after.value) < 4):
            await interaction.response.send_message(
                content="Invalid format for `Recapture After`! Must be a number "
                        "greater than 4!\n",
                ephemeral=True,
            )
            return

        if remove_tile:
            await self.remove_callback(interaction, self.planner_id, tile_code)
        else:
            await self.add_callback(interaction, self.planner_id, tile_code, int(self.recap_after.value))


class AddRemoveTileButton(discord.ui.Button):
    def __init__(self,
                 add_callback: Callable,
                 remove_callback: Callable,
                 planner_id: int):
        self.add_callback = add_callback
        self.remove_callback = remove_callback
        self.planner_id = planner_id
        super().__init__(
            label="Add/Remove Tile",
            custom_id=f"planner:admin:addrm-tile:{planner_id}"[:100],
            style=discord.ButtonStyle.gray
        )

    @check_manage_guild
    async def callback(self, interaction: discord.Interaction) -> Any:
        await interaction.response.send_modal(
            AddRemoveTileModal(self.planner_id, self.add_callback, self.remove_callback)
        )


class PlannerAdminView(discord.ui.View):
    """A list of actions usable by admins in the team."""
    def __init__(self,
                 planner_channel_id: int,
                 refresh_planner: Callable,
                 edit_time: Callable,
                 force_unclaim: Callable,
                 add_planner_tile: Callable,
                 remove_planner_tile: Callable,
                 planner_active: bool,
                 timeout: float = None):
        super().__init__(timeout=timeout)
        self.planner_id = planner_channel_id
        self.refresh_planner = refresh_planner
        self.add_item(
            SwitchPlannerButton(self.switch_planner, planner_active, self.planner_id)
        )
        # self.add_item(
        #     ClearPlannerButton(self.clear_planner, self.planner_id)
        # )
        self.add_item(
            EditTimeButton(edit_time, self.planner_id)
        )
        self.add_item(
            ForceUnclaimButton(force_unclaim, self.planner_id)
        )
        self.add_item(
            AddRemoveTileButton(add_planner_tile, remove_planner_tile, self.planner_id)
        )

    async def switch_planner(self, interaction: discord.Interaction, new_active: bool) -> None:
        await bot.db.queries.planner.turn_planner(self.planner_id, new_active)
        await interaction.response.send_message(
            content=f"The planner has been turned {'on' if new_active else 'off'}!",
            ephemeral=True
        )
        await self.refresh_planner(self.planner_id)

    async def clear_planner(self, interaction: discord.Interaction):
        await bot.db.queries.planner.set_clear_time(self.planner_id, datetime.now())
        await interaction.response.send_message(
            content=f"Cleared the planner!",
            ephemeral=True
        )
        await self.refresh_planner(self.planner_id)
