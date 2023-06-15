from datetime import datetime, timedelta
from bloonspy import Client
import discord
from discord.ext import tasks, commands
import time
import asyncio
import bot.db.queries
import bot.utils.io
import bot.utils.discordutils
from bot.classes import ErrorHandlerCog
from typing import List, Tuple, Union
from bot.utils.emojis import BANNER
from bot.views import PlannerUserView


PLANNER_ADMIN_PANEL = """
# Admin Control Panel
- Status: {}
- Tile Claim Channel: {}
- Ping Channel: {}
- Team Role: {}
"""[1:-1]
PLANNER_HR = "```\n \n```"
PLANNER_TABLE_HEADER = """
# Tiles & Expiration
————  +  ——————————————
"""[1:]
PLANNER_TABLE_ROW = "{0} `{1}`  |  <t:{2}:t> (<t:{2}:R>){3}\n"


class PlannerCog(ErrorHandlerCog):
    planner_group = discord.app_commands.Group(name="planner", description="Various CT Planner commands")
    help_descriptions = {
        "planner": {
            "new": "Create a new Planner channel",
            "add": "Sets a channel as a Planner channel.\n"
                   "__It is recommended to set it on a read-only channel.__",
            "remove": "Removes the Planner from a channel previously added with [[add]]. "
                      "__Won't delete the channel,__ but it will no longer be updated.",
        },
    }

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)
        next_check = datetime.now().replace(second=0, microsecond=0)
        next_check = next_check.replace(minute=int(next_check.minute/30)*30) + timedelta(minutes=30)
        self.next_check = next_check

    async def load_state(self) -> None:
        state = await asyncio.to_thread(bot.utils.io.get_cog_state, "planner")
        if state is None:
            return

        saved_at = datetime.fromtimestamp(state["saved_at"])
        if self.next_check-saved_at > timedelta(minutes=30):
            return

        data = state["data"]
        if "next_check" in data:
            self.next_check = data["next_check"]

    async def save_state(self) -> None:
        data = {
            "next_check": self.next_check,
        }
        await asyncio.to_thread(bot.utils.io.save_cog_state, "planner", data)

    async def cog_load(self) -> None:
        await self.load_state()
        views = await self.get_views()
        for v in views:
            self.bot.add_view(v)
        self.check_reminders.start()

    def cog_unload(self) -> None:
        self.check_reminders.cancel()

    @tasks.loop(seconds=10)
    async def check_reminders(self) -> None:
        """
        Regularly checks for banners that expire soon and pings the appropriate
        member/role if there's any.
        """
        now = datetime.now()
        if now < self.next_check:
            return
        self.next_check += timedelta(minutes=30)

    @planner_group.command(name="new", description="Create a new Planner channel.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_create_planner(self, interaction: discord.Interaction) -> None:
        channel = await interaction.guild.create_text_channel(name="planner")
        await self.add_planner(interaction, channel)

    @planner_group.command(name="remove", description="Removes Planner from an existing channel.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_remove_planner(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if await bot.db.queries.get_planner(channel.id) is None:
            await interaction.response.send_message(
                content=f"<#{channel.id}> is not even a planner!",
                ephemeral=True
            )
            return

        await bot.db.queries.del_planner(channel.id)
        await interaction.response.send_message(
            content=f"<#{channel.id}> will no longer be updated as a planner!",
            ephemeral=True
        )

    @planner_group.command(name="add", description="Adds Planner to an existing channel.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_add_planner(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await self.add_planner(interaction, channel)

    async def add_planner(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if await bot.db.queries.get_planner(channel.id) is not None:
            await interaction.response.send_message(
                content=f"<#{channel.id}> is already a planner!",
                ephemeral=True
            )
            return

        await bot.db.queries.add_planner(channel.id)
        await interaction.response.send_message(
            content=f"<#{channel.id}> is now a planner channel!",
            ephemeral=True
        )
        await self.send_planner_msg(channel.id)

    @discord.app_commands.command(name="aaa")
    async def cmd_aaa(self, interaction: discord.Interaction) -> None:
        # await self.send_planner_msg(interaction.channel_id)

        data = await bot.db.queries.get_planned_banners(
            interaction.channel_id, ["EDD", "FEB", "EBD", "DBC", "FCE", "EBF", "DAE", "CDD", "EAF", "FBF", "CBF", "FAH", "BAG", "DEB", "CFB", "CAG", "ABD", "ACC", "ACB", "BCC", "BBC", "BFB", "BFA", "CEA"]
        )
        for datum in data:
            print(datum)
        print("\n\n\n")
        await interaction.response.send_message("OK", ephemeral=True)

    async def get_planner_msg(self, channel: int) -> List[Tuple[str, discord.ui.View or None]]:
        """Generates the message to send in planner.

        :param channel: The ID of the Planner channel.
        """
        planner = await bot.db.queries.get_planner(channel)
        if planner is None:
            return []

        planner_status = "🟢 ONLINE" if planner["is_active"] else "🔴 OFFLINE *(won't ping)*"
        if not planner['ping_channel']:
            planner_status = "⚠️ CONFIGURATION UNFINISHED *(won't work)*"

        messages = [
            (PLANNER_ADMIN_PANEL.format(
                planner_status,
                f"<#{planner['claims_channel']}>" if planner['claims_channel'] else
                    "⚠️ None *(members will have to register captures manually)*️",
                f"<#{planner['ping_channel']}>" if planner['ping_channel'] else
                    "⚠️ None *(the bot will not ping at all)*️",
                f"<@{planner['ping_role']}>" if planner['ping_role'] else
                    "⚠️ None *(will ping `@here` instead)*"
            ), None),
            (PLANNER_HR, None),
        ]

        tile_table = PLANNER_TABLE_HEADER
        banner_codes = await PlannerCog.get_banner_tile_list()
        banners = await bot.db.queries.get_planned_banners(channel, banner_codes)
        for banner in banners:
            new_row = PLANNER_TABLE_ROW.format(
                BANNER, banner["tile"], int((banner["claimed_at"] + timedelta(days=1)).timestamp()),
                f"   →  <@{banner['user_id']}>" if banner["user_id"] is not None else ""
            )
            if len(new_row) + len(tile_table) > 2000:
                messages.append((tile_table, None))
                tile_table = ""
            tile_table += new_row

        banner_claims = [(banner["tile"], banner["user_id"] is not None) for banner in banners]
        messages.append((
            tile_table,
            PlannerUserView(banner_claims, channel,
                            PlannerCog.switch_tile_claim, self.send_planner_msg)
        ))

        # messages[0][1] = PlannerAdminView()

        return messages

    async def get_views(self) -> List[Union[None, PlannerUserView]]:
        views = []
        banner_codes = await PlannerCog.get_banner_tile_list()
        channels = await bot.db.queries.get_planners()

        for channel in channels:
            banners = await bot.db.queries.get_planned_banners(channel, banner_codes)
            banner_claims = {}
            for banner in banner_codes:
                banner_claims[banner] = False
            for banner in banners:
                if banner["user_id"]:
                    banner_claims[banner["tile"]] = True

            views.append(
                PlannerUserView([(tile, banner_claims[tile]) for tile in banner_claims], channel,
                                PlannerCog.switch_tile_claim, self.send_planner_msg)
            )

        return views

    @staticmethod
    async def get_banner_tile_list() -> List[str]:
        """Returns a list of banner tile codes"""
        # Temporary hardcode
        return ["EDD", "FEB", "EBD", "DBC", "FCE", "EBF", "DAE", "CDD", "EAF", "FBF", "CBF", "FAH", "BAG", "DEB", "CFB",
                "CAG", "ABD", "ACC", "ACB", "BCC", "BBC", "BFB", "BFA", "CEA"]

    async def send_planner_msg(self, channel_id: int) -> None:
        """(Re)sends the planner message.

        :param channel_id: The ID of the Planner channel.
        """
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.NotFound:
                await bot.db.queries.del_planner(channel_id)
                return

        planner_content = await self.get_planner_msg(channel_id)
        messages = await bot.utils.discordutils.update_messages(self.bot.user, planner_content, channel)

    async def switch_planner(self, status: bool) -> None:
        """Turns the planner on or off.

        :param status: Whether the planner should be turned on or off.
        """
        pass

    async def set_planner_ping_channel(self, ping_channel: int) -> None:
        """Sets the channel where the Planner will send pings for the reminders.

        :param ping_channel: The channel ID where the pings will be sent
        """
        pass

    async def set_planner_ping_role(self, ping_role: int) -> None:
        """Sets the role that will be pinged if no specific user has a tile claimed.

        :param ping_role: The role ID that will be pinged.
        """
        pass

    @staticmethod
    async def switch_tile_claim(user: int, planner_channel_id: int, tile: str) -> Tuple[str, bool]:
        """Claims or unclaims a tile for an user.

        :param user: The ID of the user who wants to claim the tile.
        :param planner_channel_id: The Planner channel ID.
        :param tile: The ID of the tile.
        :return: A message to give to the user.
        """
        tile_status = await bot.db.queries.planner_get_tile_status(tile, planner_channel_id)
        if tile_status is None:
            return "That tile isn't in the planner...?", False
        claimed_by_user = await bot.db.queries.get_claims_by(user, planner_channel_id)

        response = "That tile's not claimed by you! Hands off! 💢"
        refresh = False
        if tile_status["user_id"] == user:
            await bot.db.queries.planner_unclaim_tile(user, tile, planner_channel_id)
            response = f"You have unclaimed `{tile}`!"
            refresh = True
        elif len(claimed_by_user) >= 4:
            response = "You already have 4 tiles claimed. You can't claim any more."
        elif tile_status["user_id"] is None:
            await bot.db.queries.planner_claim_tile(user, tile, planner_channel_id)
            response = f"You have claimed `{tile}`!\n*Select it again if you want to unclaim it.*"
            refresh = True

        return response, refresh

    async def clear_planner(self) -> None:
        """Clears the Planner."""
        pass

    async def on_tile_claimed(self, tile: str, claim_channel: int) -> None:
        """
        Event fired when a tile gets claimed.

        :param tile: The ID of the tile.
        :param claim_channel: The ID of the Ticket Tracker channel.
        """
        pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PlannerCog(bot))