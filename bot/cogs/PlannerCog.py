from datetime import datetime, timedelta
import re
import discord
from discord.ext import tasks, commands
import asyncio
import bot.db.model
import bot.db.queries.planner
import bot.db.queries.tickets
import bot.utils.io
import bot.utils.discordutils
from bot.classes import ErrorHandlerCog
from typing import List, Tuple, Union, Optional, Dict
from bot.utils.emojis import TILE_BANNER, TILE_REGULAR, TILE_RELIC, RELICS
from bot.views import PlannerUserView, PlannerAdminView
from bot.utils.Cache import Cache
from bot.utils.emojis import EXPIRE_LATER, EXPIRE_DONT_RECAP, EXPIRE_AFTER_RESET, EXPIRE_STALE, EXPIRE_2HR, \
    EXPIRE_3HR, BLANK
from bloonspy.model.btd6 import CtTileType, CtTile


CT_DATA_CACHE_HR = 12
PLANNER_ADMIN_PANEL = """
# Control Panel
- Status: {}
- Tile Claim Channel: {}
- Ping Channel: {}
- Team Role: {}
__*To configure, use `/planner config`*__

*Please don't send other messages in this channel! I'm gonna get really mad and accidentally ping everybody in an hour if you do because I should be the first thing you see in the channel.*
"""[1:-1]
PLANNER_HR = "```\n \n```"
PLANNER_TABLE_HEADER = """
# Tiles & Expiration
——————- + -——————————————
"""[1:]
PLANNER_TABLE_EMPTY = "https://cdn.discordapp.com/attachments/924255725390270474/1122521704829292555/IMG_0401.png"
PLANNER_TABLE_ROW = "{emoji_claim} {emoji_tile} `{tile}`  |  "
PLANNER_TABLE_ROW_TIME = "<t:{expire_at}:T> (<t:{expire_at}:R>){claimer}\n"
PLANNER_TABLE_ROW_STALE = "⚠️ **__STALE SINCE <t:{expire_at}:R>__** ⚠️\n"


class PlannerCog(ErrorHandlerCog):
    planner_group = discord.app_commands.Group(name="planner", description="Various CT Planner commands")
    help_descriptions = {
        None: "Please check out [the wiki](<https://github.com/SartoRiccardo/ct-ticket-tracker/wiki>) for a "
              "step-by-step setup guide!\n\n"
              "Creates a planner that tracks all banner decay times, pings when they decay, and lets users "
              "claim them beforehand. Works in tandem with the `tracker` module.",
        "planner": {
            "new": "Create a new Planner channel",
            "add": "Sets a channel as a Planner channel.\n"
                   " __It is **mandatory** to set it on a read-only channel. "
                   "**The bot should be the only account typing there**.__",
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
        self.banner_decays = []
        self.next_planner_refreshes = {}
        self.last_check_end = self.next_check
        self.ct_day = 0
        self._banner_list: Cache or None = None
        self._relic_list: Cache or None = None

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

        self.banner_decays = await bot.db.queries.planner.get_tile_closest_to_expire(datetime.now())
        self.check_decay.start()

        next_refresh = datetime.now().replace(second=0, microsecond=0, minute=0) + timedelta(hours=1)
        planners = await bot.db.queries.planner.get_planners()
        for p in planners:
            self.next_planner_refreshes[p.planner_channel] = next_refresh
        self.check_planner_refresh.start()

        self.check_reset.start()
        self.check_orphan_has_tickets_roles.start()

    def cog_unload(self) -> None:
        self.check_reminders.cancel()
        self.check_decay.cancel()
        self.check_planner_refresh.cancel()
        self.check_reset.cancel()
        self.check_orphan_has_tickets_roles.cancel()

    @tasks.loop(seconds=10)
    async def check_reminders(self) -> None:
        """
        Regularly checks for banners that expire soon and pings the appropriate
        member/role if there's any.
        """
        now = datetime.now()
        if now < self.next_check:
            return
        _cts, ct_end = bot.utils.bloons.get_current_ct_period()
        if now >= ct_end-timedelta(hours=12):
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

        _cts, ct_end = bot.utils.bloons.get_current_ct_period()
        planners = await bot.db.queries.planner.get_planners(only_active=True)
        for planner in planners:
            tile_codes = await bot.db.queries.planner.get_planner_tracked_tiles(planner.planner_channel)
            pings = await self.check_planner_reminder(
                planner.planner_channel,
                planner.ping_channel,
                tile_codes,
                check_from,
                min(check_to, ct_end-timedelta(hours=12)),
                check_to_unclaimed if check_unclaimed else None
            )
            if len(pings.keys()) > 0:
                await self.send_reminder(
                    pings,
                    planner.planner_channel,
                    planner.ping_channel,
                    planner.ping_role_with_tickets if planner.ping_role_with_tickets else planner.team_role,
                )
        await self.save_state()

    async def check_planner_reminder(self,
                                     planner_id: int,
                                     ping_ch_id: int,
                                     banner_codes: List[str],
                                     check_from: datetime,
                                     check_to: datetime,
                                     check_to_unclaimed: datetime or None) -> Dict[int or None, List[str]]:
        if ping_ch_id is None:
            return {}
        banners = await bot.db.queries.planner.get_planned_tiles(planner_id, banner_codes,
                                                                 expire_between=(check_from, check_to))
        banners_unclaimed = []
        if check_to_unclaimed is not None:
            banners_unclaimed = await bot.db.queries.planner.get_planned_tiles(planner_id, banner_codes,
                                                                               expire_between=(check_from,
                                                                                               check_to_unclaimed),
                                                                               claimed_status="UNCLAIMED")
        if len(banners) == 0 and len(banners_unclaimed) == 0:
            return {}

        pings = {}
        for b in banners:
            if b.claimed_by not in pings:
                pings[b.claimed_by] = []
            pings[b.claimed_by].append(b.tile)

        for unclaimed_b in banners_unclaimed:
            if None not in pings:
                pings[None] = []
            if unclaimed_b.tile not in pings[None]:
                pings[None].append(unclaimed_b.tile)

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
            await bot.db.queries.planner.planner_delete_config(planner_id, ping_channel=True)
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
        _cts, ct_end = bot.utils.bloons.get_current_ct_period()
        if now >= ct_end-timedelta(hours=12):
            return

        update_expire_list = False
        send_ping_coros = []
        for banner in self.banner_decays:
            tile_expire_time = banner.claimed_at + timedelta(hours=banner.expires_in_hr)
            if tile_expire_time < now:
                update_expire_list = True
                planner = await bot.db.queries.planner.get_planner(banner.planner_channel)
                if not planner.is_active:
                    continue

                tiles_tracked = await bot.db.queries.planner.get_planner_tracked_tiles(planner.planner_channel)
                tiles_expiring = await bot.db.queries.planner.get_planned_tiles(
                    planner.planner_channel,
                    tiles_tracked,
                    expire_between=(tile_expire_time, now),
                )
                for exp_tile in tiles_expiring:
                    send_ping_coros.append(
                        self.decay_ping_when_ready(exp_tile, planner)
                    )

        await asyncio.gather(*send_ping_coros)
        if update_expire_list:
            self.banner_decays = await bot.db.queries.planner.get_tile_closest_to_expire(now)

    async def decay_ping_when_ready(self,
                                    tile: "bot.db.model.PlannedTile.PlannedTile",
                                    planner: "bot.db.model.Planner.Planner") -> None:
        now = datetime.now()
        tile_data = await bot.db.queries.planner.planner_get_tile_status(tile.tile, tile.planner_channel)
        ping_role = planner.ping_role_with_tickets if planner.ping_role_with_tickets else planner.ping_role

        # This check never happens when called by check_decay since it only
        # fetches tiles whose expires_at is strictly lower than now.
        # if now < tile_data.expires_at:
        #     await asyncio.sleep((tile_data.expires_at-now).total_seconds())

        await self.send_decay_ping(tile.planner_channel, tile_data.ping_channel,
                                   tile.tile, tile_data.claimed_by, ping_role)

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
            await bot.db.queries.planner.planner_delete_config(planner_id, ping_channel=True)
            await self.send_planner_msg(planner_id)
            return

        message = f"**TILE `{tile}` HAS JUST GONE STALE**, claim it now"
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

    @tasks.loop(seconds=30)
    async def check_planner_refresh(self) -> None:
        now = datetime.now()
        for planner_channel in self.next_planner_refreshes:
            if self.next_planner_refreshes[planner_channel] > now:
                continue
            await self.send_planner_msg(planner_channel)

    @tasks.loop(seconds=60)
    async def check_reset(self) -> None:
        """Calls functions at every CT Day reset"""
        current_day = bot.utils.bloons.get_current_ct_day()
        if current_day == self.ct_day:
            return
        self.ct_day = current_day
        if self.ct_day <= 7:
            await self.reassign_has_tickets_roles()

    @tasks.loop(seconds=3600*24)
    async def check_orphan_has_tickets_roles(self) -> None:
        """
        Removes the "has tickets" role once CT is over.
        """
        if 0 <= self.ct_day <= 7:
            return
        await self.remove_has_tickets_roles()

    async def reassign_has_tickets_roles(self) -> None:
        """
        For every planner & its team, checks ticket counts and reassigns the "has tickets"
        role to whoever necessary.
        """
        planners = await bot.db.queries.planner.get_planners()
        for pln in planners:
            planner_ch = self.bot.get_channel(pln.planner_channel)
            if planner_ch is None:
                try:
                    planner_ch = await self.bot.fetch_channel(pln.planner_channel)
                except discord.NotFound:
                    continue

            role = discord.utils.get(planner_ch.guild.roles, id=pln.team_role)
            if role is None:
                roles = await planner_ch.guild.fetch_roles()
                role = discord.utils.get(roles, id=pln.team_role)

            checks = []
            for member in role.members:
                checks.append(self.check_has_tickets_role(member, pln))
            await asyncio.gather(*checks)

    async def remove_has_tickets_roles(self) -> None:
        """Removes the has tickets role from all planners."""
        # Lots of copied code with reassign_has_tickets_roles ahhhh
        planners = await bot.db.queries.planner.get_planners()
        for pln in planners:
            if pln.ping_role_with_tickets is None:
                continue

            planner_ch = self.bot.get_channel(pln.planner_channel)
            if planner_ch is None:
                try:
                    planner_ch = await self.bot.fetch_channel(pln.planner_channel)
                except discord.NotFound:
                    continue

            role = discord.utils.get(planner_ch.guild.roles, id=pln.ping_role_with_tickets)
            if role is None:
                roles = await planner_ch.guild.fetch_roles()
                role = discord.utils.get(roles, id=pln.ping_role_with_tickets)

            removals = []
            for member in role.members:
                removals.append(member.remove_roles(role))
            await asyncio.gather(*removals)

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
        if await bot.db.queries.planner.get_planner(channel.id) is None:
            await interaction.response.send_message(
                content=f"<#{channel.id}> is not even a planner!",
                ephemeral=True
            )
            return

        await bot.db.queries.planner.del_planner(channel.id)
        await interaction.response.send_message(
            content=f"<#{channel.id}> will no longer be updated as a planner!",
            ephemeral=True
        )

    @planner_group.command(name="add", description="Adds Planner to an existing channel.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(
        channel="The channel you want to add the Planner to.",
    )
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
        if await bot.db.queries.planner.get_planner(planner_channel.id) is None:
            await interaction.response.send_message(
                content="That's not a planner channel!",
                ephemeral=True,
            )
            return

        if tile_claim_channel:
            planner_linked = await bot.db.queries.planner.get_planner_linked_to(tile_claim_channel.id)
            if planner_linked is not None and planner_linked != planner_channel.id:
                await interaction.response.send_message(
                    content=f"<#{tile_claim_channel.id}> is already linked to another planner!",
                    ephemeral=True,
                )
                return
            if not await bot.db.queries.tickets.is_channel_tracked(tile_claim_channel.id):
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

        await bot.db.queries.planner.planner_update_config(
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

    @planner_group.command(
        name="overwrite",
        description="Overwrites which tiles are tracked in a Planner channel. "
                    "It will assume they all expire in 24 hours."
    )
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(
        planner_channel="The channel of the planner you want to overwrite the tiles for.",
        tiles="Comma separated value of tile codes.",
    )
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_overwrite_tiles(self, interaction: discord.Interaction, planner_channel: discord.TextChannel, tiles: str) -> None:
        tile_list = [t.upper() for t in tiles.split(",")]
        tile_re = r"(?:M|[A-G])(?:R|[A-G])(?:X|[A-H])"
        for tile in tile_list:
            if len(tile) != 3 or re.match(tile_re, tile) is None:
                await interaction.response.send_message(
                    content=f"Invalid tile: `{tile}`",
                    ephemeral=True,
                )
                return

        if await bot.db.queries.planner.get_planner(planner_channel.id) is None:
            await interaction.response.send_message(
                content="That's not a planner channel!",
                ephemeral=True,
            )
            return

        currently_tracked = await bot.db.queries.planner.get_planner_tracked_tiles(planner_channel.id)
        await asyncio.gather(*[
            bot.db.queries.planner.remove_tile_from_planner(planner_channel.id, tile)
            for tile in currently_tracked
        ])

        await asyncio.gather(*[
            bot.db.queries.planner.add_tile_to_planner(planner_channel.id, tile, 24)
            for tile in tile_list
        ])

        await interaction.response.send_message(
            content="All done! The planner message will be updated in a bit...",
            ephemeral=True,
        )
        await self.send_planner_msg(planner_channel.id)

    async def add_planner(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if await bot.db.queries.planner.get_planner(channel.id) is not None:
            await interaction.response.send_message(
                content=f"<#{channel.id}> is already a planner!",
                ephemeral=True
            )
            return

        await bot.db.queries.planner.add_planner(channel.id)
        await interaction.response.send_message(
            content=f"<#{channel.id}> is now a planner channel!\n"
                    "*Make sure my permissions are set correctly and I can write, see & delete messages in that "
                    "channel, and create & assign user roles, or it won't work!*\n"
                    "**Also make sure __NOBODY__ types there. __Not even you!__ Only I should type there. "
                    "It gets ugly if anybody else types there.",
            ephemeral=True
        )
        await self.send_planner_msg(channel.id)

    async def get_planner_msg(self, channel: int) -> List[Tuple[str, discord.ui.View or None]]:
        """Generates the message to send in planner.

        :param channel: The ID of the Planner channel.
        """
        planner = await bot.db.queries.planner.get_planner(channel)
        if planner is None:
            return []

        planner_status = "🟢 ONLINE" if planner.is_active else "🔴 OFFLINE *(won't ping)*"
        if not planner.ping_channel:
            planner_status = "⚠️ CONFIGURATION UNFINISHED *(won't work)*"

        ping_role_msg = "⚠️ None *(anyone can claim tiles & will ping `@here` instead)*"
        if planner.ping_role:
            ping_role_msg = f"<@&{planner.ping_role}>"
            if planner.ping_role_with_tickets:
                ping_role_msg += f"\n - Team Role (with tickets): <@&{planner.ping_role_with_tickets}>"

        messages = [
            (PLANNER_ADMIN_PANEL.format(
                planner_status,
                f"<#{planner.claims_channel}>" if planner.claims_channel else
                "⚠️ None *(members will have to register captures manually)*️",
                f"<#{planner.ping_channel}>" if planner.ping_channel else
                "⚠️ None *(the bot will not ping at all)*️",
                ping_role_msg
            ), PlannerAdminView(channel,
                                self.send_planner_msg,
                                self.edit_tile_time,
                                self.force_unclaim,
                                self.add_planner_tile,
                                self.remove_planner_tile,
                                planner.is_active)),
            (PLANNER_HR, None),
        ]

        now = datetime.now()
        tile_table = PLANNER_TABLE_HEADER
        banner_codes = await self.get_banner_tile_list()
        relic_tiles = await self.get_relic_tile_list()
        relic_codes = [r.id for r in relic_tiles]
        tile_list = await bot.db.queries.planner.get_planner_tracked_tiles(channel)
        ct_start, ct_end = bot.utils.bloons.get_current_ct_period()
        if now < ct_end:
            tracked_tiles = await bot.db.queries.planner.get_planned_tiles(
                channel, tile_list, expire_between=(ct_start, ct_end)
            )
        else:
            tracked_tiles = []
        next_reset_day = ct_start + timedelta(hours=((now-ct_start).days+1)*24)
        emojis_explanations = {
            EXPIRE_DONT_RECAP: None,
            EXPIRE_AFTER_RESET: None,
        }
        banner_claims = []
        for i in range(len(tracked_tiles)):
            tile = tracked_tiles[i]
            expire_at = tile.claimed_at + timedelta(hours=tile.expires_in_hr)
            emoji_claim = EXPIRE_LATER
            if expire_at >= ct_end-timedelta(hours=12):
                emoji_claim = EXPIRE_DONT_RECAP
                emojis_explanations[EXPIRE_DONT_RECAP] = "Should __not__ be refreshed"
            elif expire_at < now:
                emoji_claim = EXPIRE_STALE
            elif now < next_reset_day <= expire_at:
                emoji_claim = EXPIRE_AFTER_RESET
                emojis_explanations[EXPIRE_AFTER_RESET] = "Expires after reset"
            elif expire_at-now < timedelta(hours=2):
                emoji_claim = EXPIRE_2HR
            elif expire_at-now < timedelta(hours=3):
                emoji_claim = EXPIRE_3HR

            emoji_tile = TILE_REGULAR
            if tile.tile in banner_codes:
                emoji_tile = TILE_BANNER
            elif (r_idx := relic_codes.index(tile.tile)) > -1:
                emoji_tile = TILE_RELIC
                print(tile.tile, relic_codes, r_idx)
                relic = relic_tiles[r_idx]
                if relic.relic in RELICS.keys():
                    emoji_tile = RELICS[relic.relic]
                    print(relic.relic, emoji_tile)
            row_second_part = PLANNER_TABLE_ROW_STALE if emoji_claim == EXPIRE_STALE else PLANNER_TABLE_ROW_TIME
            new_row = PLANNER_TABLE_ROW.format(
                emoji_claim=emoji_claim,
                emoji_tile=emoji_tile,
                tile=tile.tile,
            ) + row_second_part.format(
                expire_at=int(expire_at.timestamp()),
                claimer=f"   →  <@{tile.claimed_by}>" if tile.claimed_by is not None else ""
            )

            if len(new_row) + len(tile_table) > 2000:
                messages.append((tile_table, None))
                tile_table = ""
            tile_table += new_row
            banner_claims.append((tile.tile, tile.claimed_by is not None))

        append_explanation = "\n"
        for emoji in emojis_explanations:
            if emojis_explanations[emoji] is not None:
                append_explanation += f"\nⓘ {emoji} *{emojis_explanations[emoji]}*"
        if len(append_explanation) > 1:
            if len(tile_table) + len(append_explanation) > 2000:
                messages.append((tile_table, None))
                tile_table = BLANK + append_explanation
            else:
                tile_table += append_explanation

        if len(banner_claims) == 0:
            tile_table = PLANNER_TABLE_EMPTY

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
        channels = await bot.db.queries.planner.get_planners()
        for channel in channels:
            channel_id = channel.planner_channel
            tile_codes = await bot.db.queries.planner.get_planner_tracked_tiles(channel_id)
            tiles = await bot.db.queries.planner.get_planned_tiles(channel_id, tile_codes)
            banner_claims = {}
            for banner in tile_codes:
                banner_claims[banner] = False
            for banner in tiles:
                if banner.claimed_by:
                    banner_claims[banner.tile] = True

            views.append(
                PlannerUserView([(tile, banner_claims[tile]) for tile in banner_claims], channel_id,
                                PlannerCog.switch_tile_claim, self.send_planner_msg)
            )
            views.append(
                PlannerAdminView(channel_id,
                                 self.send_planner_msg,
                                 self.edit_tile_time,
                                 self.force_unclaim,
                                 self.add_planner_tile,
                                 self.remove_planner_tile,
                                 channel.is_active)
            )

        return views

    async def get_banner_tile_list(self) -> List[str]:
        """Returns a list of banner tile codes."""
        if self._banner_list is None or not self._banner_list.valid:
            ct_event = await asyncio.to_thread(bot.utils.bloons.get_current_ct_event)
            if ct_event is None:
                return []
            banner_tile_list = await asyncio.to_thread(ct_event.tiles)
            banner_list = [
                tile.id for tile in banner_tile_list
                if tile.tile_type == CtTileType.BANNER
            ]
            self._banner_list = Cache(banner_list, datetime.now() + timedelta(hours=CT_DATA_CACHE_HR))
        return self._banner_list.value

    async def get_relic_tile_list(self) -> List[CtTile]:
        """Returns a list of relic tiles."""
        if self._relic_list is None or not self._relic_list.valid:
            ct_event = await asyncio.to_thread(bot.utils.bloons.get_current_ct_event)
            if ct_event is None:
                return []
            relics = await asyncio.to_thread(ct_event.tiles)
            relics = [r for r in relics if r.tile_type == CtTileType.RELIC]
            self._relic_list = Cache(relics, datetime.now() + timedelta(hours=CT_DATA_CACHE_HR))
        return self._relic_list.value

    async def send_planner_msg(self, channel_id: int) -> None:
        """(Re)sends the planner message.

        :param channel_id: The ID of the Planner channel.
        """
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.NotFound:
                await bot.db.queries.planner.del_planner(channel_id)
                return

        planner_content = await self.get_planner_msg(channel_id)
        self.next_planner_refreshes[channel_id] = datetime.now() + timedelta(hours=1)
        try:
            await bot.utils.discordutils.update_messages(self.bot.user, planner_content, channel, tolerance=5)
        except discord.Forbidden:
            pass

    @staticmethod
    async def switch_tile_claim(user: discord.Member, planner_channel_id: int, tile: str) -> Tuple[str, bool]:
        """Claims or unclaims a tile for an user.

        :param user: The member who wants to claim the tile.
        :param planner_channel_id: The Planner channel ID.
        :param tile: The ID of the tile.
        :return: A message to give to the user.
        """
        planner_info = await bot.db.queries.planner.get_planner(planner_channel_id)
        if planner_info is None:
            return "This channel is not a planner channel...?", False
        if planner_info.ping_role is not None and \
                discord.utils.get(user.roles, id=planner_info.ping_role) is None:
            return f"You need the <@&{planner_info.ping_role}> role to claim tiles!", False

        tile_status = await bot.db.queries.planner.planner_get_tile_status(tile, planner_channel_id)
        if tile_status is None:
            return "That tile isn't in the planner...?", False
        claimed_by_user = await bot.db.queries.planner.get_claims_by(user.id, planner_channel_id)

        response = "That tile's not claimed by you! Hands off! 💢"
        refresh = False
        if tile_status.claimed_by == user.id:
            await bot.db.queries.planner.planner_unclaim_tile(tile, planner_channel_id)
            response = f"You have unclaimed `{tile}`!"
            refresh = True
        elif len(claimed_by_user) >= 4:
            response = "You already have 4 tiles claimed. You can't claim any more."
        elif tile_status.claimed_by is None:
            await bot.db.queries.planner.planner_claim_tile(user.id, tile, planner_channel_id)
            response = f"You have claimed `{tile}`!\n*Select it again if you want to unclaim it.*"
            refresh = True

        if refresh:
            await PlannerCog.check_has_tickets_role(user, planner_info)

        return response, refresh

    async def on_tile_captured(self, tile: str, claim_channel: int, claimer: int) -> None:
        """
        Event fired when a tile gets claimed.

        :param tile: The ID of the tile.
        :param claim_channel: The ID of the Ticket Tracker channel.
        :param claimer: The ID of the user who captured it.
        """
        await self.handle_tile_capture(tile, claim_channel, claimer)

    async def on_tile_uncaptured(self, tile: str, claim_channel: int, claimer: int) -> None:
        """
        Event fired when a tile gets uncaptured.

        :param tile: The ID of the tile.
        :param claim_channel: The ID of the Ticket Tracker channel.
        :param claimer: The ID of the user who uncaptured it.
        """
        await self.handle_tile_capture(tile, claim_channel, claimer, is_capture=False)

    async def handle_tile_capture(self, tile: str, claim_channel: int, claimer: int, is_capture: bool = True) -> None:
        planner_id = await bot.db.queries.planner.get_planner_linked_to(claim_channel)
        if planner_id is None:
            return
        if is_capture:
            await bot.db.queries.planner.planner_unclaim_tile(tile, planner_id)

        # Create the "with tickets" role if it doesn't exist
        planner = await bot.db.queries.planner.get_planner(planner_id)
        if not planner.ping_role_with_tickets:
            try:
                new_ping_role = await self.create_ping_role(planner)
                await bot.db.queries.planner.planner_update_config(
                    planner.planner_channel,
                    ping_role_with_tickets=new_ping_role.id
                )
            except discord.Forbidden:
                pass
        else:
            channel = self.bot.get_channel(claim_channel)
            await self.check_has_tickets_role(channel.guild.get_member(claimer), planner)

        # Update planner if necessary
        tile_list = await bot.db.queries.planner.get_planner_tracked_tiles(planner_id)
        if tile in tile_list:
            self.banner_decays = await bot.db.queries.planner.get_tile_closest_to_expire(datetime.now())
            await self.send_planner_msg(planner_id)

    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def edit_tile_time(self,
                             interaction: discord.Interaction,
                             planner_id: int,
                             tile: str,
                             new_time: datetime) -> None:
        planner_info = await bot.db.queries.planner.get_planner(planner_id)
        if planner_info is None or planner_info.claims_channel is None:
            return
        claims_channel = planner_info.claims_channel
        tracked_tile_list = await bot.db.queries.planner.get_planner_tracked_tiles(planner_id)
        success = await bot.db.queries.planner.edit_tile_capture_time(
            claims_channel, tile, new_time - timedelta(days=1)
        )
        self.banner_decays = await bot.db.queries.planner.get_tile_closest_to_expire(datetime.now())
        message = f"Got it! `{tile}` will decay at " \
                  f"<t:{int(new_time.timestamp())}:t> (<t:{int(new_time.timestamp())}:R>)"
        if not success:
            message = f"`{tile}` doesn't seem to be a valid tile...\n"
            if tile not in tracked_tile_list:
                message += "*It's not a tracked tile!*"
            else:
                message += f"*The tile must have been captured at any point during the CT to be able to " \
                           f"have its time edited. If you want to add it to the planner, register the capture " \
                           f"yourself in <#{claims_channel}>. and __then__ edit the time.*"
        await interaction.response.send_message(
            content=message,
            ephemeral=True
        )
        await self.send_planner_msg(planner_id)

        tile_status = await bot.db.queries.planner.planner_get_tile_status(tile, planner_id)
        if tile_status and tile_status.claimed_by:
            member = interaction.guild.get_member(tile_status.claimed_by)
            await self.check_has_tickets_role(member, planner_info)

    async def force_unclaim(self, interaction: discord.Interaction, planner_id: int, tile: str) -> None:
        prev_status = await bot.db.queries.planner.planner_get_tile_status(tile, planner_id)
        await bot.db.queries.planner.planner_unclaim_tile(tile, planner_id)
        await interaction.response.send_message(
            content=f"All done! `{tile}` is now unclaimed.",
            ephemeral=True
        )
        await self.send_planner_msg(planner_id)

        if prev_status.claimed_by is None:
            return
        member = interaction.guild.get_member(prev_status.claimed_by)
        planner = await bot.db.queries.planner.get_planner(planner_id)
        await self.check_has_tickets_role(member, planner)

    async def remove_planner_tile(self, interaction: discord.Interaction, planner_id: int, tile: str) -> None:
        await bot.db.queries.planner.remove_tile_from_planner(planner_id, tile)
        overwrite_id = bot.utils.discordutils.get_slash_command_id(self.bot, "planner")
        await interaction.response.send_message(
            content=f"All done! `{tile}` will no longer appear in the planner.\n"
                    f"*Need to remove lots of tiles? Try using </planner overwrite:{overwrite_id}> instead!*",
            ephemeral=True
        )
        self.banner_decays = await bot.db.queries.planner.get_tile_closest_to_expire(datetime.now())
        await self.send_planner_msg(planner_id)

    async def add_planner_tile(self,
                               interaction: discord.Interaction,
                               planner_id: int,
                               tile: str,
                               recap_after: int) -> None:
        await bot.db.queries.planner.add_tile_to_planner(planner_id, tile, recap_after)
        overwrite_id = bot.utils.discordutils.get_slash_command_id(self.bot, "planner")
        await interaction.response.send_message(
            content=f"All done! `{tile}` will appear in the planner. If it doesn't appear, it's because it hasn't "
                    f"been claimed this event yet.\n"
                    f"*Need to add lots of tiles? Try using </planner overwrite:{overwrite_id}> instead!*",
            ephemeral=True
        )
        self.banner_decays = await bot.db.queries.planner.get_tile_closest_to_expire(datetime.now())
        await self.send_planner_msg(planner_id)

    async def create_ping_role(self, planner: bot.db.model.Planner.Planner) -> discord.Role or None:
        """
        Creates the role that will be assigned to people in the team who still have
        tickets to spend. Assigns it to the whole team, where required.
        :param planner: The planner channel's data.
        :return: The newly created role.
        """
        channel = self.bot.get_channel(planner.planner_channel)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(planner.planner_channel)
            except discord.NotFound:
                return None

        team_role = discord.utils.get(channel.guild.roles, id=planner.ping_role)
        if team_role is None:
            return None

        new_role = await channel.guild.create_role(name=f"{team_role.name} (has tickets)")

        ret = new_role
        if not planner.claims_channel:
            return ret

        checks = []
        for member in team_role.members:
            checks.append(self.check_has_tickets_role(member, planner))
        await asyncio.gather(*checks)

        return ret

    @staticmethod
    async def check_has_tickets_role(member: discord.Member, planner: bot.db.model.Planner.Planner) -> None:
        """
        Checks if the "has tickets" role should be added or removed.
        :param member: The member to check.
        :param planner: The planner to check for.
        """
        if planner.ping_role_with_tickets is None:
            return
        ping_role = member.guild.get_role(planner.ping_role_with_tickets)
        if ping_role is None:
            await bot.db.queries.planner.planner_delete_config(ping_role_with_tickets=True)
            return

        today_ticket_idx = min(bot.utils.bloons.get_current_ct_day() - 1, 6)
        tickets_used = len(
            (await bot.db.queries.tickets.get_tickets_from(member.id, planner.claims_channel))[today_ticket_idx]
        )

        member_claims = await bot.db.queries.planner.get_claims_by(member.id, planner.planner_channel)
        tile_codes = [claim["tile"] for claim in member_claims]
        tile_infos = await bot.db.queries.planner.get_planned_tiles(planner.planner_channel, tile_codes)
        today = bot.utils.bloons.get_current_ct_day()
        for ti in tile_infos:
            expire_in_day = bot.utils.bloons.get_ct_day_during(ti.claimed_at + timedelta(hours=ti.expires_in_hr))
            if expire_in_day == today:
                tickets_used += 1

        has_role = discord.utils.get(member.roles, id=planner.ping_role_with_tickets) is not None
        if has_role and tickets_used >= 4:
            await member.remove_roles(ping_role)
        elif not has_role and tickets_used < 4:
            await member.add_roles(ping_role)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PlannerCog(bot))
