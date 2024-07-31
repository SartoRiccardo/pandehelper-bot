import math
import os
import aiofiles
import re
import traceback
from datetime import datetime, timedelta
import discord
from discord.ext import tasks, commands
import asyncio
import bot.db.queries.leaderboard
import bot.utils.io
from bot.classes import ErrorHandlerCog
from config import EMOTE_GUILD_ID
from bot.utils.emojis import TOP_1_GLOBAL, TOP_2_GLOBAL, TOP_3_GLOBAL, TOP_25_GLOBAL, ECO, ECO_NEGATIVE, NEW_TEAM, \
    TOP_1_PERCENT, BLANK, TOP_100_GLOBAL


class LeaderboardCog(ErrorHandlerCog):
    leaderboard_group = discord.app_commands.Group(name="leaderboard", description="Various leaderboard commands")
    help_descriptions = {
        "leaderboard": {
            "add": "Sets a channel as a leaderboard channel. The Top 100 Global leaderboard will "
                   "appear there and be updated every hour.\n"
                   "__It is recommended to set it on a read-only channel.__",
            "remove": "Removes the leaderboard from a channel previously added with [[add]]. "
                      "That channel will no longer be updated."
        }
    }

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)

        self.last_hour_score: dict[str, int] = {}
        self.current_ct_id = ""
        self.first_run = True
        self.next_update = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    async def cog_load(self) -> None:
        await self.load_state()
        self.track_leaderboard.start()

    def cog_unload(self) -> None:
        self.track_leaderboard.cancel()

    async def load_state(self) -> None:
        state = await asyncio.to_thread(bot.utils.io.get_cog_state, "leaderboard")
        if state is None:
            return

        saved_at = datetime.fromtimestamp(state["saved_at"])
        if self.next_update-saved_at > timedelta(hours=1):
            return

        data = state["data"]
        if "current_ct_id" in data:
            self.current_ct_id = data["current_ct_id"]
        if "last_hour_score" in data:
            self.last_hour_score = data["last_hour_score"]
        self.first_run = False

    async def save_state(self) -> None:
        data = {
            "current_ct_id": self.current_ct_id,
            "last_hour_score": self.last_hour_score,
        }
        await asyncio.to_thread(bot.utils.io.save_cog_state, "leaderboard", data)

    @leaderboard_group.command(name="add", description="Add a leaderboard to a channel.")
    @discord.app_commands.describe(channel="The channel to add it to.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_add_leaderboard(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await bot.db.queries.leaderboard.add_leaderboard_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(
            content=f"Leaderboard added to <#{channel.id}>!\n"
                    "*It will start appearing when it gets updated next. Make sure my permissions are set correctly "
                    "and I can write, see & delete messages in that channel!*",
            ephemeral=True,
        )

    @leaderboard_group.command(name="remove", description="Remove a leaderboard from a channel.")
    @discord.app_commands.describe(channel="The channel to remove it from.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_remove_leaderboard(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await bot.db.queries.leaderboard.remove_leaderboard_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(
            content=f"Leaderboard removed from <#{channel.id}>!\n"
                    "*That channel will no longer be updated.*",
            ephemeral=True,
        )

    @tasks.loop(seconds=10)
    async def track_leaderboard(self) -> None:
        now = datetime.now()
        if now < self.next_update:
            return
        self.next_update += timedelta(hours=1)

        msg_header = ("Team                                                        |    Points\n"
                      "—————————————————   +   —————") \
                     if self.first_run else \
                     ("Team                                                        |    Points      (Gained)\n"
                      "—————————————————   +   ————————————")
        placements_emojis = {
            0: TOP_1_GLOBAL,
            1: TOP_2_GLOBAL,
            2: TOP_3_GLOBAL,
            24: TOP_25_GLOBAL,
            99: TOP_100_GLOBAL,
        }
        row_template = "{placement}{icon} `{name: <20}`    | `{score: <7,}`"
        eco_template = " ({emote} `{eco: <4}`)"

        current_event = await asyncio.to_thread(bot.utils.bloons.get_current_ct_event)
        if current_event is None:
            return

        if current_event.id != self.current_ct_id:
            self.current_ct_id = current_event.id
            self.last_hour_score = {}

        if now > current_event.end + timedelta(hours=2) or now < current_event.start:
            return

        should_skip_eco = now > current_event.end
        leaderboard = await asyncio.to_thread(current_event.leaderboard_team, pages=4)
        if len(leaderboard) == 0:
            return
        
        current_hour_score = {}
        for i in range(min(len(leaderboard), 100)):
            current_hour_score[leaderboard[i].id] = leaderboard[i].score
        
        # Load all teams 5 at a time
        for i in range(math.ceil(len(leaderboard)/5)):
            await asyncio.gather(*[
                asyncio.to_thread(team.load_resource) for team in leaderboard[i*5:(i+1)*5]
            ])
        
        # Load all team icon emotes if EMOTE_GUILD_ID is set
        team_icon_emotes = {}
        if EMOTE_GUILD_ID:
            emote_guild = self.bot.get_guild(EMOTE_GUILD_ID)
            try:
                team_icon_emotes = await asyncio.wait_for(self.load_team_icon_emotes(emote_guild, leaderboard), timeout=7*60)
            except asyncio.TimeoutError:
                pass  # If the task takes longer than 7 minutes it probably hit rate limit on the create emoji endpoint.
        
        message_full = msg_header
        for i in range(min(len(leaderboard), 100)):
            team = leaderboard[i]
            placement = f"`{i+1: <2}`"
            if i in placements_emojis:
                placement = placements_emojis[i]
            if team.is_disbanded:
                placement = "❌"

            team_name = team.name.split("-")[0]
            icon_hash = self.hash_team_icon(team)
            message_full += "\n" + row_template.format(
                placement=placement,
                icon=f" {team_icon_emotes[icon_hash]}" if icon_hash in team_icon_emotes else "",
                name=team_name,
                score=team.score
            )
            if not should_skip_eco:
                if team.id in self.last_hour_score:
                    score_gained = team.score - self.last_hour_score[team.id]
                    eco_emote = ECO if score_gained >= 0 else ECO_NEGATIVE
                    message_full += eco_template.format(emote=eco_emote, eco=score_gained)
                elif not self.first_run:
                    message_full += f" {NEW_TEAM}"
        
        self.last_hour_score = current_hour_score
        await self.save_state()

        # Misc addendums to the leaderboard
        top_1_percent_message = ""
        if current_event.total_scores_team > 10100:
            award_word = "Awarded" if should_skip_eco else "Awardable"
            top_1_percent_message += f"\n      {TOP_1_PERCENT} __Top 1% {award_word}__"

        time_remaining_message = ""
        if now < current_event.end:
            total_hours_left = math.ceil((current_event.end - now).total_seconds()/3600)
            hours_left = total_hours_left%24
            days_left = int(total_hours_left/24)
            time_left_str = ""
            if days_left > 0:
                time_left_str += f"{days_left}d"
            if hours_left > 0:
                time_left_str += f"{hours_left:0>2}h"
            time_remaining_message = f"\n*Event time left:* {time_left_str}"

        message_full += f"\n\n*Teams:* {current_event.total_scores_team:,}  " \
                        f"⸰  *Players:* {current_event.total_scores_player:,}" + \
                        top_1_percent_message + \
                        time_remaining_message + \
                        f"\n*Last updated: <t:{int(now.timestamp())}:R>*"

        # Split message
        messages = []
        message_current = ""
        for ln in message_full.split("\n"):
            if len(message_current + "\n" + ln) <= 2000:
                message_current += "\n" + ln
            else:
                messages.append(message_current[1:])  # Take out initial newline
                message_current = "\n" + ln
        if message_current != "":
            messages.append(message_current[1:])
            
        # Pad message list
        while len(messages) < 5:
            messages.append(BLANK)

        await self.send_leaderboard(messages)
        self.first_run = False
    
    async def load_team_icon_emotes(self, emote_guild: discord.Guild, teams: list["bloonspy.btd6.Team"]) -> dict[str, str]:
        emotes = {}
        to_make = []
        used = []
        for team in teams:
            icon_hash = self.hash_team_icon(team)
            if icon_hash in used:
                continue
            
            found = False
            for e in emote_guild.emojis:
                if e.name == icon_hash:
                    emotes[icon_hash] = f"<{'a' if e.animated else ''}:_:{e.id}>"
                    found = True
                    break
            if not found:
                to_make.append((team.frame, team.icon))
            used.append(icon_hash)
        
        # Remove useless slots if any
        avail_static_slots = 50
        avail_anim_slots = 50
        for e in emote_guild.emojis:
            if e.animated:
                avail_anim_slots -= 1
            else:
                avail_static_slots -= 1
        
        for e in reversed(emote_guild.emojis):
            if avail_static_slots + avail_anim_slots >= len(to_make):
                break
            if e.name not in used:
                if e.animated:
                    avail_anim_slots += 1
                else:
                    avail_static_slots += 1
                await e.delete()
        
        await self.download_team_icon_assets(to_make)
        for frame, icon in to_make:
            icon_hash = self.hash_team_icon(frame, icon)
            emotes[icon_hash] = await self.make_team_icon_emote(emote_guild, icon_hash, frame, icon, avail_static_slots == 0)
            if avail_anim_slots > 0:
                avail_anim_slots -= 1
            else:
                avail_static_slots -= 1
        
        return emotes
    
    @staticmethod
    async def download_team_icon_assets(to_make: list[tuple["bloonspy.btd6.Asset", "bloonspy.btd6.Asset"]]) -> None:
        frames, icons = [], []
        for frame, icon in to_make:
            if frame not in frames and not os.path.exists(f"tmp/{frame.name}"):
                frames.append(frame)
            if icon not in icons and not os.path.exists(f"tmp/{icon.name}"):
                icons.append(icon)
        
        await bot.utils.discordutils.download_files([f.url for f in frames], [f"tmp/{f.name}" for f in frames])
        await bot.utils.discordutils.download_files([i.url for i in icons], [f"tmp/{i.name}" for i in icons])
    
    @staticmethod
    async def make_team_icon_emote(emote_guild: discord.Guild,
                                   emote_name: str,
                                   frame: "bloonspy.btd6.Asset",
                                   icon: "bloonspy.btd6.Asset",
                                   animated: bool) -> str:
        frame_path = f"tmp/{frame.name}"
        icon_path = f"tmp/{icon.name}"
        if not os.path.exists(frame_path) or not os.path.exists(icon_path):
            return
        merged_path = f"tmp/{emote_name}.{'gif' if animated else 'png'}"
        
        await asyncio.to_thread(bot.utils.io.merge_images, frame_path, icon_path, merged_path, animated)
        async with aiofiles.open(merged_path, "rb") as fin:
            image = await fin.read()
        # Be careful with this joint the rate limit is super low and
        # if you exceed it this function will be blocking for a whole hour.
        # If it's your first time running the leaderboard it WILL exceed it.
        try:
            emote = await emote_guild.create_custom_emoji(name=emote_name, image=image)
            os.remove(merged_path)
        except discord.errors.HTTPException:
            return BLANK
        
        return f"<{'a' if animated else ''}:_:{emote.id}>"
    
    @staticmethod
    def hash_team_icon(arg0: "bloonspy.btd6.Team" or "bloonspy.btd6.Asset", arg1: "bloonspy.btd6.Asset" = None) -> str:
        frame_num = re.search('\d+', arg0.name if arg1 else arg0.frame.name).group(0)
        icon_num = re.search('\d+', arg1.name if arg1 else arg0.icon.name).group(0)
        return f"f{frame_num}i{icon_num}"

    async def send_leaderboard(self, messages: list[str]) -> None:
        channels = await bot.db.queries.leaderboard.leaderboard_channels()
        for leaderboard in channels:
            guild_id, channel_id = leaderboard.guild_id, leaderboard.channel_id
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                try:
                    guild = await self.bot.fetch_guild(guild_id)
                except discord.NotFound:
                    await bot.db.queries.leaderboard.remove_leaderboard_channel(guild_id, channel_id)
                    continue

            channel = guild.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await guild.fetch_channel(channel_id)
                except discord.NotFound:
                    await bot.db.queries.leaderboard.remove_leaderboard_channel(guild_id, channel_id)
                    continue
            try:
                await bot.utils.discordutils.update_messages(
                    self.bot.user,
                    [(x, None) for x in messages],
                    channel,
                    tolerance=0
                )
            except discord.Forbidden:
                pass
            except discord.HTTPException as exc:
                print(f"HTTPException in Leaderboard")
                traceback.print_exc()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
