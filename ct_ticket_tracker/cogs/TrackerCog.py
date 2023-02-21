import datetime
import discord
from discord.ext import commands
import re
import ct_ticket_tracker.db.queries
import ct_ticket_tracker.utils.bloons
from typing import Optional


class TrackerCog(commands.Cog):
    tickets_group = discord.app_commands.Group(name="tickets", description="Various ticket tracking commands.")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @tickets_group.command(name="track", description="Track a channel.")
    @discord.app_commands.describe(channel="The channel to start tracking.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def track(self, interaction: discord.Interaction, channel: str) -> None:
        channel_id = int(channel[2:-1])
        if not discord.utils.get(interaction.guild.text_channels, id=channel_id):
            return

        await ct_ticket_tracker.db.queries.track_channel(channel_id)
        await interaction.response.send_message(f"I am now tracking <#{channel_id}>", ephemeral=True)

    @tickets_group.command(name="untrack", description="Stop tracking a channel.")
    @discord.app_commands.describe(channel="The channel to stop tracking.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def untrack(self, interaction: discord.Interaction, channel: str) -> None:
        channel_id = int(channel[2:-1])
        if not discord.utils.get(interaction.guild.text_channels, id=channel_id):
            return

        await ct_ticket_tracker.db.queries.untrack_channel(channel_id)
        await interaction.response.send_message(f"I am no longer tracking <#{channel_id}>", ephemeral=True)

    @tickets_group.command(name="view", description="See how many tickets each member used.")
    @discord.app_commands.describe(channel="The channel to check.",
                                   season="The CT season to check. Defaults to the current one.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def tickets_list(self, interaction: discord.Interaction, channel: str, season: Optional[int] = 0) -> None:
        channel_id = int(channel[2:-1])
        if not discord.utils.get(interaction.guild.text_channels, id=channel_id):
            return
        if channel_id not in (await ct_ticket_tracker.db.queries.tracked_channels()):
            await interaction.response.send_message("That channel is not being tracked!", ephemeral=True)
            return

        await interaction.response.send_message("Just a moment...", ephemeral=True)
        message = "`Member    ` | `D1` | `D2` | `D3` | `D4` | `D5` | `D6` | `D7`\n"
        claims = await ct_ticket_tracker.db.queries.get_ticket_overview(channel_id, season)
        row = "`{:10.10}` | `{:<2}` | `{:<2}` | `{:<2}` | `{:<2}` | `{:<2}` | `{:<2}` | `{:<2}`\n"
        for uid in claims:
            user = await self.bot.fetch_user(uid)
            message += row.format(user.name if user else str(uid), *[len(day_claims) for day_claims in claims[uid]])
        await interaction.edit_original_response(content=message)

    @tickets_group.command(name="member", description="In-depth view of a member's used tickets.")
    @discord.app_commands.describe()
    @discord.app_commands.describe(member="The member to check.",
                                   channel="The channel to check.",
                                   season="The CT season to check. Defaults to the current one.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def member_tickets(self, interaction: discord.Interaction, channel: str,
                             member: discord.Member, season: Optional[int] = 0) -> None:
        channel_id = int(channel[2:-1])
        if not discord.utils.get(interaction.guild.text_channels, id=channel_id):
            return
        if channel_id not in (await ct_ticket_tracker.db.queries.tracked_channels()):
            await interaction.response.send_message("That channel is not being tracked!", ephemeral=True)
            return

        await interaction.response.send_message("Just a moment...", ephemeral=True)
        if season == 0:
            season = ct_ticket_tracker.utils.bloons.get_ct_number_during(datetime.datetime.now())
        member_activity = await ct_ticket_tracker.db.queries.get_tickets_from(member.id, channel_id, season)

        embed = discord.Embed(
            title=f"{member.display_name}'s Tickets (CT {season})",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        for i in range(len(member_activity)):
            claims_message = ""
            for claim in member_activity[i]:
                message_url = f"https://discord.com/channels/{interaction.guild.id}/{channel_id}/{claim.message_id}"
                claims_message += f"• `{claim.tile}` <t:{int(claim.claimed_at.timestamp())}:t> ([jump]({message_url}))\n"
            if len(claims_message) > 0:
                embed.add_field(name=f"Day {i+1}", value=claims_message, inline=False)
        await interaction.edit_original_response(embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if str(payload.emoji) not in ["✅", "👍"] or \
                payload.channel_id not in (await ct_ticket_tracker.db.queries.tracked_channels()):
            return

        tile_re = r"[a-gA-GMm][a-gA-GRr][a-hA-HXx]"
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        match = re.search(tile_re, message.content)
        if match is None:
            return
        tile = match.group(0).upper()
        await ct_ticket_tracker.db.queries.capture(payload.channel_id, payload.user_id, tile, payload.message_id)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if str(payload.emoji) not in ["✅", "👍"] or \
                payload.channel_id not in (await ct_ticket_tracker.db.queries.tracked_channels()):
            return

        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        for reaction in message.reactions:
            if reaction.emoji in ["✅", "👍"]:
                return
        await ct_ticket_tracker.db.queries.uncapture(payload.message_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TrackerCog(bot))
