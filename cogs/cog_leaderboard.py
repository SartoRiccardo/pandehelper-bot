from datetime import datetime, timedelta
import time
import discord
from discord.ext import tasks
import time
import asyncio
import db.queries
import btd6.AsyncBtd6
from discord.ext import commands


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        self.last_hour_score = {}
        self.current_ct_id = ""
        self.first_run = True
        self.next_update = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    def cog_load(self) -> None:
        self.track_leaderboard.start()

    def cog_unload(self) -> None:
        self.track_leaderboard.cancel()

    @commands.command(name="addlb")
    async def add_leaderboard(self, ctx: commands.Context, channel: str) -> None:
        if not ctx.author.guild_permissions.administrator:
            return
        channel_id = int(channel[2:-1])
        if not discord.utils.get(ctx.guild.text_channels, id=channel_id):
            return

        await db.queries.add_leaderboard_channel(ctx.guild.id, channel_id)
        await ctx.message.add_reaction("✅")

    @commands.command(name="removelb")
    async def remove_leaderboard(self, ctx: commands.Context, channel: str) -> None:
        if not ctx.author.guild_permissions.administrator:
            return
        channel_id = int(channel[2:-1])
        if not discord.utils.get(ctx.guild.text_channels, id=channel_id):
            return

        await db.queries.remove_leaderboard_channel(ctx.guild.id, channel_id)
        await ctx.message.add_reaction("✅")

    @tasks.loop(seconds=10)
    async def track_leaderboard(self) -> None:
        msg_header = "Team                                                 |    Points (Gained)" + "\n" + \
                     "------------------------------   +  ----------------------"
        placements_emojis = ["🥇", "🥈", "🥉"] + ["<:top25:1072145878602760214>"]*(25-3)
        row_template = "{} `{: <20}`    | `{: <7,}`"
        eco_template = " (🔺 `{: <4}`)"

        now = datetime.now()
        if now < self.next_update:
            return
        self.next_update += timedelta(hours=1)

        now_unix = time.mktime(now.timetuple())
        current_event = (await btd6.AsyncBtd6.AsyncBtd6.ct())[0]
        if current_event.id != self.current_ct_id:
            self.current_ct_id = current_event.id
            self.last_hour_score = {}

        if now_unix > current_event.end/1000+3600 or now_unix < current_event.start/1000:
            return

        lb_coros = []
        for page in range(10):
            lb_coros.append(current_event.teams(page+1))
        try:
            lb_pages = await asyncio.gather(*lb_coros)
        except Exception as exc:
            print(exc)
            return

        lb_data = []
        for page in lb_pages:
            lb_data += page

        messages = []
        message_current = msg_header
        current_hour_score = {}
        for i in range(len(lb_data)):
            team = lb_data[i]
            placement = f"`{i+1}`"
            if i < len(placements_emojis):
                placement = placements_emojis[i]
            if team.disbanded:
                placement = "❌"

            message_current += "\n" + row_template.format(placement, team.display_name, team.score)
            if team.id in self.last_hour_score:
                score_gained = team.score - self.last_hour_score[team.id]
                message_current += eco_template.format(score_gained)
            elif not self.first_run:
                message_current += " 🆕"
            current_hour_score[team.id] = team.score

            if (i+1) % 25 == 0 or i == len(lb_data)-1:
                messages.append(message_current)
                message_current = ""
        messages[len(messages)-1] += f"\n*Last updated: <t:{int(now_unix)}:R>*"
        self.last_hour_score = current_hour_score

        await self.send_leaderboard(messages)
        self.first_run = False

    async def send_leaderboard(self, messages):
        channels = await db.queries.leaderboard_channels()
        for guild_id, channel_id in channels:
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                guild = await self.bot.fetch_guild(guild_id)
            if guild is None:
                continue

            channel = guild.get_channel(channel_id)
            if channel is None:
                channel = await guild.fetch_channel(channel_id)
            if channel is None:
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
