from datetime import datetime, timedelta
import json
import discord
from discord.ext import tasks, commands
import asyncio
import bot.db.queries
import bot.utils.io
import bot.utils.discordutils
from bot.classes import ErrorHandlerCog
from typing import List, Tuple, Union, Optional, Dict
from bot.utils.emojis import BANNER, BLANK
from bot.views import PlannerUserView, PlannerAdminView
from bot.utils.Cache import Cache


PLANNER_ADMIN_PANEL = """
# Control Panel
- Status: {}
- Tile Claim Channel: {}
- Ping Channel: {}
- Team Role: {}
*To configure, use `/planner config`*
"""[1:-1]
PLANNER_HR = "```\n \n```"
PLANNER_TABLE_HEADER = """
# Tiles & Expiration
————  +  ——————————————
"""[1:]
PLANNER_TABLE_EMPTY = "https://cdn.discordapp.com/attachments/924255725390270474/1122521704829292555/IMG_0401.png"
PLANNER_TABLE_ROW = "{0} `{1}`  |  <t:{2}:t> (<t:{2}:R>){3}\n"


class PlannerCog(ErrorHandlerCog):
    planner_group = discord.app_commands.Group(name="planner", description="Various CT Planner commands")
    help_descriptions = {
        None: "Creates a planner that tracks all banner decay times, pings when they decay, and lets users "
              "claim them beforehand. Works in tandem with the `tracker` module.",
        "planner": {
            "new": "Create a new Planner channel",
            "add": "Sets a channel as a Planner channel.\n"
                   "__It is recommended to set it on a read-only channel.__",
            "remove": "Removes the Planner from a channel previously added with [[add]].\n"
                      "__Won't delete the channel,__ but it will no longer be updated.",
            "config": "Configure the planner to make sure it works properly!",
        },
    }
    CHECK_EVERY = 30
    CHECK_EVERY_UNCLAIMED = 60

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)
        next_check = datetime.now().replace(second=0, microsecond=0)
        next_check = next_check.replace(minute=int(next_check.minute/PlannerCog.CHECK_EVERY)*PlannerCog.CHECK_EVERY) \
                     + timedelta(minutes=PlannerCog.CHECK_EVERY)
        self.next_check = next_check
        self.next_check_unclaimed = next_check
        self.banner_decays = {}
        self.last_check_end = self.next_check
        self._banner_list: Cache or None = None

    async def load_state(self) -> None:
        state = await asyncio.to_thread(bot.utils.io.get_cog_state, "planner")
        if state is None:
            return

        saved_at = datetime.fromtimestamp(state["saved_at"])
        if self.next_check-saved_at > timedelta(minutes=PlannerCog.CHECK_EVERY):
            return

        data = state["data"]
        if "next_check" in data:
            self.next_check = datetime.fromtimestamp(data["next_check"])
        if "last_check_end" in data:
            self.last_check_end = datetime.fromtimestamp(data["last_check_end"])

    async def save_state(self) -> None:
        data = {
            "next_check": self.next_check.timestamp(),
            "last_check_end": self.last_check_end.timestamp(),
        }
        await asyncio.to_thread(bot.utils.io.save_cog_state, "planner", data)

    async def cog_load(self) -> None:
        await self.load_state()
        views = await self.get_views()
        for v in views:
            self.bot.add_view(v)
        self.check_reminders.start()
        banner_list = await self.get_banner_tile_list()
        self.banner_decays = await bot.db.queries.get_banner_closest_to_expire(banner_list,
                                                                               datetime.now())
        self.check_decay.start()

    def cog_unload(self) -> None:
        self.check_reminders.cancel()
        self.check_decay.cancel()

    @tasks.loop(seconds=10)
    async def check_reminders(self) -> None:
        """
        Regularly checks for banners that expire soon and pings the appropriate
        member/role if there's any.
        """
        now = datetime.now()
        if now < self.next_check:
            return
        check_from = max(self.next_check, self.last_check_end)
        check_to = self.next_check + timedelta(minutes=PlannerCog.CHECK_EVERY*2)
        check_to_unclaimed = self.next_check_unclaimed + timedelta(minutes=PlannerCog.CHECK_EVERY_UNCLAIMED*2)
        self.next_check += timedelta(minutes=PlannerCog.CHECK_EVERY)
        self.last_check_end = check_to
        check_unclaimed = False
        if now >= self.next_check_unclaimed:
            check_unclaimed = True
            self.next_check_unclaimed += timedelta(minutes=PlannerCog.CHECK_EVERY_UNCLAIMED)

        banner_codes = await self.get_banner_tile_list()
        planners = await bot.db.queries.get_planners(only_active=True)
        for planner in planners:
            pings = await self.check_planner_reminder(
                planner["planner_channel"],
                planner["ping_channel"],
                banner_codes,
                check_from,
                check_to,
                check_to_unclaimed if check_unclaimed else None
            )
            if len(pings.keys()) > 0:
                await self.send_reminder(
                    pings,
                    planner["planner_channel"],
                    planner["ping_channel"],
                    planner["ping_role"],
                )
        await self.save_state()

    async def check_planner_reminder(self,
                                     planner_id: int,
                                     ping_ch_id: int,
                                     banner_codes: List[str],
                                     check_from: datetime,
                                     check_to: datetime,
                                     check_to_unclaimed: datetime or None) -> Dict[int or None, str]:
        if ping_ch_id is None:
            return {}
        banners = await bot.db.queries.get_planned_banners(planner_id, banner_codes,
                                                           expire_between=(check_from, check_to))
        banners_unclaimed = []
        if check_to_unclaimed is not None:
            banners_unclaimed = await bot.db.queries.get_planned_banners(planner_id, banner_codes,
                                                                         expire_between=(check_from,
                                                                                         check_to_unclaimed),
                                                                         claimed_status="UNCLAIMED")
        if len(banners) == 0 and len(banners_unclaimed) == 0:
            return {}

        pings = {}
        for b in banners:
            if b["user_id"] not in pings:
                pings[b["user_id"]] = []
            pings[b["user_id"]].append(b["tile"])
        for unclaimed_b in banners_unclaimed:
            if None not in pings:
                pings[None] = []
            if unclaimed_b["tile"] not in pings[None]:
                pings[None].append(unclaimed_b["tile"])
        return pings

    async def send_reminder(self,
                            pings: Dict[int or None, List[str]],
                            planner_id: int,
                            ping_channel_id: int,
                            ping_role: int) -> None:
        message = "**Tiles that will expire soon:**\n"
        pinged_someone = False
        for uid in pings:
            if uid is None:
                continue
            pinged_someone = True
            message += f"- <@{uid}>: "
            for i in range(len(pings[uid])):
                message += f"`{pings[uid][i]}`"
                if i == len(pings[uid]) - 1:
                    message += ".\n"
                elif i == len(pings[uid]) - 2:
                    message += " and "
                else:
                    message += ", "

        if None in pings and len(pings[None]) > 0:
            ping = f"<@&{ping_role}>" if ping_role is not None else "@here"
            if pinged_someone:
                message += f"Also, {ping} these tiles haven't been claimed and will expire somewhat soon: "
            else:
                message = f"{ping} these tiles haven't been claimed and will expire somewhat soon: "
            for i in range(len(pings[None])):
                message += f"`{pings[None][i]}`"
                if i == len(pings[None]) - 1:
                    message += "."
                elif i == len(pings[None]) - 2:
                    message += " and "
                else:
                    message += ", "
            message += f""

        ping_channel = self.bot.get_channel(ping_channel_id)
        if ping_channel is None:
            ping_channel = await self.bot.fetch_channel(ping_channel_id)
        if ping_channel is None:
            await bot.db.queries.planner_delete_config(planner_id, ping_channel=True)
            await self.send_planner_msg(planner_id)
            return

        await ping_channel.send(
            content=message
        )

    @tasks.loop(seconds=5)
    async def check_decay(self) -> None:
        """
        Checks if a banner has just decayed and pings the team in the appropriate channel.
        """
        now = datetime.now()
        one_day = timedelta(days=1)
        update_expire_list = False
        for banner in self.banner_decays:
            if banner["claimed_at"] + one_day < now:
                update_expire_list = True
                planner = await bot.db.queries.get_planner(banner["planner_channel"])
                if not planner["is_active"]:
                    continue
                banner_data = await bot.db.queries.planner_get_tile_status(banner["tile"], banner["planner_channel"])
                await self.send_decay_ping(banner["planner_channel"], banner_data["ping_channel"],
                                           banner["tile"], banner_data["user_id"], banner_data["ping_role"])

        if update_expire_list:
            banner_list = await self.get_banner_tile_list()
            self.banner_decays = await bot.db.queries.get_banner_closest_to_expire(banner_list, now)

    async def send_decay_ping(self,
                              planner_id: int,
                              ping_channel_id: int,
                              tile: str,
                              user_id: int or None,
                              role_id: int or None) -> None:
        ping_channel = self.bot.get_channel(ping_channel_id)
        if ping_channel is None:
            ping_channel = await self.bot.fetch_channel(ping_channel_id)
        if ping_channel is None:
            await bot.db.queries.planner_delete_config(planner_id, ping_channel=True)
            await self.send_planner_msg(planner_id)
            return

        message = f"**BANNER `{tile}` HAS JUST GONE STALE**, claim it now"
        if user_id:
            message += f" <@{user_id}>"
        elif role_id:
            message += f" <@&{role_id}>"
        else:
            message += " @here"
        message += "!"

        await ping_channel.send(
            content=message
        )

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

    @planner_group.command(name="config", description="Configure the planner.")
    @discord.app_commands.rename(ping_role="team_role")
    @discord.app_commands.describe(
        planner_channel="The channel of the planner you want to change.",
        ping_channel="The channel where the bot will ping users to remind them of banner decays.",
        ping_role="The role that will get pinged if a banner is unclaimed.",
        tile_claim_channel="The channel where members log tile captures.",
    )
    @discord.app_commands.guild_only()
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_configure_planner(self,
                                    interaction: discord.Interaction,
                                    planner_channel: discord.TextChannel,
                                    ping_channel: Optional[discord.TextChannel] = None,
                                    ping_role: Optional[discord.Role] = None,
                                    tile_claim_channel: Optional[discord.TextChannel] = None) -> None:
        if await bot.db.queries.get_planner(planner_channel.id) is None:
            await interaction.response.send_message(
                content="That's not a planner channel!",
                ephemeral=True,
            )
            return

        if tile_claim_channel:
            planner_linked = await bot.db.queries.get_planner_linked_to(tile_claim_channel.id)
            if planner_linked is not None and planner_linked != planner_channel.id:
                await interaction.response.send_message(
                    content=f"<#{tile_claim_channel.id}> is already linked to another planner!",
                    ephemeral=True,
                )
                return
            if not await bot.db.queries.is_channel_tracked(tile_claim_channel.id):
                await interaction.response.send_message(
                    content="That channel is not tracked as a tile claim channel!\n"
                            "To make the bot track it, please check out `/help module:tracker` and it will "
                            "tell you all you need to know. Then try this command again!",
                    ephemeral=True,
                )
                return

        if ping_channel is ping_role is tile_claim_channel:
            await interaction.response.send_message(
                content="You must modify at least ONE value! Check the optional parameters!",
                ephemeral=True,
            )
            return

        await bot.db.queries.planner_update_config(
            planner_channel.id,
            ping_ch=ping_channel.id if ping_channel else None,
            ping_role=ping_role.id if ping_role else None,
            tile_claim_ch=tile_claim_channel.id if tile_claim_channel else None,
        )
        await interaction.response.send_message(
            content="All done! Check the planner's control panel!",
            ephemeral=True
        )
        await self.send_planner_msg(planner_channel.id)

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
                f"<@&{planner['ping_role']}>" if planner['ping_role'] else
                    "⚠️ None *(will ping `@here` instead)*"
            ), PlannerAdminView(channel,
                                self.send_planner_msg,
                                self.edit_tile_time,
                                self.force_unclaim,
                                planner["is_active"])),
            (PLANNER_HR, None),
        ]

        tile_table = PLANNER_TABLE_HEADER
        banner_codes = await self.get_banner_tile_list()
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

        if len(banners) == 0:
            tile_table = PLANNER_TABLE_EMPTY

        banner_claims = [(banner["tile"], banner["user_id"] is not None) for banner in banners]
        messages.append((
            tile_table,
            PlannerUserView(banner_claims, channel,
                            PlannerCog.switch_tile_claim, self.send_planner_msg)
        ))

        # Makes the message always minimum 4 messages long
        for _ in range(4-len(messages)):
            messages.insert(2, (PLANNER_HR, None))

        return messages

    async def get_views(self) -> List[Union[None, PlannerUserView]]:
        views = []
        banner_codes = await self.get_banner_tile_list()
        channels = await bot.db.queries.get_planners()

        for channel in channels:
            channel_id = channel["planner_channel"]
            banners = await bot.db.queries.get_planned_banners(channel_id, banner_codes)
            banner_claims = {}
            for banner in banner_codes:
                banner_claims[banner] = False
            for banner in banners:
                if banner["user_id"]:
                    banner_claims[banner["tile"]] = True

            views.append(
                PlannerUserView([(tile, banner_claims[tile]) for tile in banner_claims], channel_id,
                                PlannerCog.switch_tile_claim, self.send_planner_msg)
            )
            views.append(
                PlannerAdminView(channel_id,
                                 self.send_planner_msg,
                                 self.edit_tile_time,
                                 self.force_unclaim,
                                 channel["is_active"])
            )

        return views

    async def get_banner_tile_list(self) -> List[str]:
        """Returns a list of banner tile codes."""
        if self._banner_list is None or not self._banner_list.valid:
            banner_list = await asyncio.to_thread(self.fetch_banner_tile_list)
            self._banner_list = Cache(banner_list, datetime.now() + timedelta(days=5))
        return self._banner_list.value

    @staticmethod
    def fetch_banner_tile_list() -> List[str]:
        fin = open("bot/files/json/banners.json")
        banners = json.loads(fin.read())
        fin.close()
        return banners

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
        await bot.utils.discordutils.update_messages(self.bot.user, planner_content, channel)

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
            await bot.db.queries.planner_unclaim_tile(tile, planner_channel_id)
            response = f"You have unclaimed `{tile}`!"
            refresh = True
        elif len(claimed_by_user) >= 4:
            response = "You already have 4 tiles claimed. You can't claim any more."
        elif tile_status["user_id"] is None:
            await bot.db.queries.planner_claim_tile(user, tile, planner_channel_id)
            response = f"You have claimed `{tile}`!\n*Select it again if you want to unclaim it.*"
            refresh = True

        return response, refresh

    async def on_tile_claimed(self, tile: str, claim_channel: int, _claimer: int) -> None:
        """
        Event fired when a tile gets claimed.

        :param tile: The ID of the tile.
        :param claim_channel: The ID of the Ticket Tracker channel.
        :param _claimer: The ID of the user who claimed it.
        """
        if tile not in await self.get_banner_tile_list():
            return
        planner_id = await bot.db.queries.get_planner_linked_to(claim_channel)
        if planner_id is None:
            return
        await bot.db.queries.planner_unclaim_tile(tile, planner_id)
        await self.send_planner_msg(planner_id)

    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def edit_tile_time(self,
                             interaction: discord.Interaction,
                             planner_id: int,
                             tile: str,
                             new_time: datetime) -> None:
        planner_info = await bot.db.queries.get_planner(planner_id)
        if planner_info is None or planner_info["claims_channel"] is None:
            return
        claims_channel = planner_info["claims_channel"]
        banner_list = await self.get_banner_tile_list()
        self.banner_decays = await bot.db.queries.get_banner_closest_to_expire(banner_list, datetime.now())
        success = await bot.db.queries.edit_tile_capture_time(claims_channel, tile, new_time-timedelta(days=1))
        message = f"Got it! `{tile}` will decay at " \
                  f"<t:{int(new_time.timestamp())}:t> (<t:{int(new_time.timestamp())}:R>)"
        if not success:
            message = f"`{tile}` doesn't seem to be a valid tile...\n"
            if tile not in banner_list:
                message += "*It's not a banner!*"
            else:
                message += f"*The banner must have been captured at any point during the CT to be able to " \
                           f"have its time edited. If you want to add it to the planner, register the capture " \
                           f"yourself in <#{claims_channel}>. and __then__ edit the time.*"
        await interaction.response.send_message(
            content=message,
            ephemeral=True
        )
        await self.send_planner_msg(planner_id)

    async def force_unclaim(self, interaction: discord.Interaction, planner_id: int, tile: str) -> None:
        await bot.db.queries.planner_unclaim_tile(tile, planner_id)
        await interaction.response.send_message(
            content=f"All done! `{tile}` is now unclaimed.",
            ephemeral=True
        )
        await self.send_planner_msg(planner_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PlannerCog(bot))
