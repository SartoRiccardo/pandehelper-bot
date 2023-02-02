import discord
import re
import asyncio
import db.queries
from discord.ext import commands


class TrackerCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="track")
    async def track(self, ctx: commands.Context, channel: str) -> None:
        """
        Starts tracking tile claim messages in that channel.
        :param channel: A channel mention to be tracked.
        """
        if not ctx.author.guild_permissions.administrator:
            return
        channel_id = int(channel[2:-1])
        if not discord.utils.get(ctx.guild.text_channels, id=channel_id):
            return

        await db.queries.track_channel(channel_id)
        await ctx.message.add_reaction("✅")

    @commands.command(name="untrack")
    async def untrack(self, ctx: commands.Context, channel: str) -> None:
        """
        Stops tracking tile claim messages in that channel.
        :param channel: A channel mention to be tracked.
        """
        if not ctx.author.guild_permissions.administrator:
            return
        channel_id = int(channel[2:-1])
        if not discord.utils.get(ctx.guild.text_channels, id=channel_id):
            return

        await db.queries.untrack_channel(channel_id)
        await ctx.message.add_reaction("✅")

    @commands.command(name="tickets")
    async def tickets(self, ctx: commands.Context, channel: str, season: int = 0) -> None:
        """
        Checks how many tickets have been used for a CT season.
        :param channel: A channel mention to be checked.
        :param season: The season to check the tickets for. If none, it's the current one.
        """
        if not ctx.author.guild_permissions.administrator:
            return
        channel_id = int(channel[2:-1])
        if not discord.utils.get(ctx.guild.text_channels, id=channel_id):
            return

        message = "```\n   Member  | D1 | D2 | D3 | D4 | D5 | D6 | D7\n"
        claims = await db.queries.get_ticket_overview(channel_id, season)
        row = "{:10.10} | {:<2} | {:<2} | {:<2} | {:<2} | {:<2} | {:<2} | {:<2}\n"
        for uid in claims:
            user = await self.bot.fetch_user(uid)
            message += row.format(user.name if user else str(uid), *claims[uid])
        await ctx.author.send(message + "```")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if str(payload.emoji) not in ["✅", "👍"] or \
                payload.channel_id not in (await db.queries.tracked_channels()):
            return

        tile_re = r"[a-gA-GMm][a-gA-GRr][a-hA-HXx]"
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        match = re.search(tile_re, message.content)
        if match is None:
            return
        tile = match.group(0).upper()
        await db.queries.capture(payload.channel_id, payload.user_id, tile, payload.message_id)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if str(payload.emoji) not in ["✅", "👍"] or \
                payload.channel_id not in (await db.queries.tracked_channels()):
            return

        tile_re = r"[a-gA-GMm][a-gA-GRr][a-hA-HXx]"
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        for reaction in message.reactions:
            if reaction.emoji in ["✅", "👍"]:
                return
        await db.queries.uncapture(payload.message_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TrackerCog(bot))
