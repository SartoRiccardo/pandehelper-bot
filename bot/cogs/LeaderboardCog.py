from datetime import datetime, timedelta
from bloonspy import Client
import discord
from discord.ext import tasks, commands
import time
import asyncio
import bot.db.queries
import bot.utils.io
from bot.classes import ErrorHandlerCog
from typing import Dict, Any
from bot.utils.emojis import TOP_1_GLOBAL, TOP_2_GLOBAL, TOP_3_GLOBAL, TOP_25_GLOBAL, ECO, NEW_TEAM


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

        self.last_hour_score: Dict[str, int] = {}
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
    async def add_leaderboard(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await bot.db.queries.add_leaderboard_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(f"Leaderboard added to <#{channel.id}>!", ephemeral=True)

    @leaderboard_group.command(name="remove", description="Remove a leaderboard from a channel.")
    @discord.app_commands.describe(channel="The channel to remove it from.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def remove_leaderboard(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await bot.db.queries.remove_leaderboard_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(f"Leaderboard removed from <#{channel.id}>!", ephemeral=True)

    @tasks.loop(seconds=10)
    async def track_leaderboard(self) -> None:
        msg_header = "Team                                                 |    Points (Gained)" + "\n" + \
                     "------------------------------   +  ----------------------"
        placements_emojis = [TOP_1_GLOBAL, TOP_2_GLOBAL, TOP_3_GLOBAL] + [TOP_25_GLOBAL]*(25-3)
        row_template = "{} `{: <20}`    | `{: <7,}`"
        eco_template = " (" + ECO + " `{: <4}`)"

        now = datetime.now()
        if now < self.next_update:
            return
        self.next_update += timedelta(hours=1)
        current_event = (await asyncio.to_thread(Client.contested_territories))[0]
        if current_event.id != self.current_ct_id:
            self.current_ct_id = current_event.id
            self.last_hour_score = {}

        if now > current_event.end or now < current_event.start:
            return

        leaderboard = await asyncio.to_thread(current_event.leaderboard_team, pages=4)
        messages = []
        message_current = msg_header
        current_hour_score = {}
        for i in range(min(len(leaderboard), 100)):
            team = leaderboard[i]
            placement = f"`{i+1}`"
            if i < len(placements_emojis):
                placement = placements_emojis[i]
            # if team.disbanded:
            #     placement = "❌"

            team_name = team.name.split("-")[0]
            message_current += "\n" + row_template.format(placement, team_name, team.score)
            if team.id in self.last_hour_score:
                score_gained = team.score - self.last_hour_score[team.id]
                message_current += eco_template.format(score_gained)
            elif not self.first_run:
                message_current += f" {NEW_TEAM}"
            current_hour_score[team.id] = team.score

            if (i+1) % 20 == 0 or i == len(leaderboard)-1:
                messages.append(message_current)
                message_current = ""

        if len(messages) == 0:
            return
        messages[len(messages)-1] += f"\n*Last updated: <t:{int(time.mktime(now.timetuple()))}:R>*"
        self.last_hour_score = current_hour_score

        await self.send_leaderboard(messages)
        self.first_run = False

        await self.save_state()

    async def send_leaderboard(self, messages):
        channels = await bot.db.queries.leaderboard_channels()
        for guild_id, channel_id in channels:
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                try:
                    guild = await self.bot.fetch_guild(guild_id)
                except discord.NotFound:
                    await bot.db.queries.remove_leaderboard_channel(guild_id, channel_id)
                    continue

            channel = guild.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await guild.fetch_channel(channel_id)
                except discord.NotFound:
                    await bot.db.queries.remove_leaderboard_channel(guild_id, channel_id)
                    continue

            leaderboard_messages = []
            bot_messages = []
            modify = True
            async for message in channel.history(limit=25):
                if message.author == self.bot.user:
                    leaderboard_messages.insert(0, message)
                    bot_messages.append(message)
                    if len(leaderboard_messages) == len(messages):
                        break
                else:
                    leaderboard_messages = []
                    modify = False
            if len(leaderboard_messages) != len(messages):
                modify = False

            if modify:
                tasks = []
                for i in range(len(messages)):
                    tasks.append(leaderboard_messages[i].edit(content=messages[i]))
                await asyncio.gather(*tasks)
            else:
                tasks = []
                for msg in bot_messages:
                    tasks.append(msg.delete())
                await asyncio.gather(*tasks)

                for content in messages:
                    await channel.send(content)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
