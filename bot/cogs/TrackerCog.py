import asyncio
import datetime
import discord
from discord.ext import commands
import re
import bot.db.queries.tickets
import bot.utils.bloons
from bot.classes import ErrorHandlerCog


tracked_emojis = ["🟩", "👌", "🟢", "✅", "👍"]


class TrackerCog(ErrorHandlerCog):
    help_descriptions = {
        None: "Please check out [the wiki](<https://github.com/SartoRiccardo/ct-ticket-tracker/wiki>) for a "
              "step-by-step setup guide!",
        "tickets": {
            "track": "Starts tracking a channel for tile captures. A tile is considered captured when an user reacts "
                     "to a message with ✅ in that channel, and the message they reacted to contains a valid "
                     "tile code. It also assumes everyone's reset is at the same time, which is the case for "
                     "Competitive.\n"
                     "Tile captures are only tracked during CT days. If you try to register a capture while a "
                     "CT event is not active, the bot will just ignore it.",
            "untrack": "Stop tracking a channel for tile claims.",
            "view": "A table containing number of tickets used by each member on each day.",
            "member": "Detailed information about a specific member, showing which tiles were claimed and when.",
            "tile": "Detailed information about a tile, showing how many times it was captured, by whom, and when."
        }
    }

    tickets_group = discord.app_commands.Group(name="tickets", description="Various ticket tracking commands.")

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)

    @tickets_group.command(name="track", description="Track a channel.")
    @discord.app_commands.describe(channel="The channel to start tracking.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_track(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await bot.db.queries.tickets.track_channel(channel.id)
        await interaction.response.send_message(f"I am now tracking <#{channel.id}>", ephemeral=True)

    @tickets_group.command(name="untrack", description="Stop tracking a channel.")
    @discord.app_commands.describe(channel="The channel to stop tracking.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_untrack(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await bot.db.queries.tickets.untrack_channel(channel.id)
        await interaction.response.send_message(f"I am no longer tracking <#{channel.id}>", ephemeral=True)

    @tickets_group.command(name="view", description="See how many tickets each member used.")
    @discord.app_commands.describe(channel="The channel to check.",
                                   season="The CT season to check. Defaults to the current one.")
    @discord.app_commands.guild_only()
    # @discord.app_commands.default_permissions(administrator=True)
    # @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_tickets_list(self,
                               interaction: discord.Interaction,
                               channel: discord.TextChannel,
                               season: None or int = 0,
                               hide: None or bool = False) -> None:
        if channel.id not in (await bot.db.queries.tickets.tracked_channels()):
            await interaction.response.send_message("That channel is not being tracked!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=hide)

        message = "`Member    ` | `D1` | `D2` | `D3` | `D4` | `D5` | `D6` | `D7`\n"
        # separator = "------------- + --- + --  + --  + --  + --- + --  + ---\n"
        row = "`{:10.10}` | `{:<2}` | `{:<2}` | `{:<2}` | `{:<2}` | `{:<2}` | `{:<2}` | `{:<2}`\n"

        claims = await bot.db.queries.tickets.get_ticket_overview(channel.id, season)

        async def get_member(uid: int) -> discord.Member:
            member = interaction.guild.get_member(uid)
            if member is None:
                member = await interaction.guild.fetch_member(uid)
            return member

        members = await asyncio.gather(*[
            get_member(uid) for uid in claims
        ], return_exceptions=True)
        total_claims = [0] * 7
        for member in members:
            if type(member) is discord.NotFound:
                continue
            message += row.format(
                member.display_name if member else str(member.id),
                *[len(day_claims) for day_claims in claims[member.id]]
            )
            for i in range(len(claims[member.id])):
                total_claims[i] += len(claims[member.id][i])
        message += row.format("Total", *total_claims)

        await interaction.edit_original_response(content=message)

    @tickets_group.command(name="member", description="In-depth view of a member's used tickets.")
    @discord.app_commands.describe(member="The member to check.",
                                   channel="The channel to check.",
                                   season="The CT season to check. Defaults to the current one.")
    @discord.app_commands.guild_only()
    # @discord.app_commands.default_permissions(administrator=True)
    # @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_member_tickets(self, interaction: discord.Interaction, channel: discord.TextChannel,
                                 member: discord.Member, season: None or int = 0,
                                 hide: None or bool = False) -> None:
        if channel.id not in (await bot.db.queries.tickets.tracked_channels()):
            await interaction.response.send_message("That channel is not being tracked!", ephemeral=True)
            return

        await interaction.response.send_message("Just a moment...", ephemeral=hide)
        if season == 0:
            season = bot.utils.bloons.get_ct_number_during(datetime.datetime.now())
        member_activity = await bot.db.queries.tickets.get_tickets_from(member.id, channel.id, season)

        embed = discord.Embed(
            title=f"{member.display_name}'s Tickets (CT {season})",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        for i in range(len(member_activity)):
            claims_message = ""
            for claim in member_activity[i]:
                # TODO Adding the message URL makes the field hit character limit if you claim more than 9 tiles a day. Add pagination.
                # message_url = f"https://discord.com/channels/{interaction.guild.id}/{channel_id}/{claim.message_id}"
                # claims_message += f"• `{claim.tile}` <t:{int(claim.claimed_at.timestamp())}:t> ([jump]({message_url}))\n"
                claims_message += f"- `{claim.tile}` <t:{int(claim.claimed_at.timestamp())}:t>\n"
            if len(claims_message) > 0:
                embed.add_field(name=f"Day {i+1}", value=claims_message, inline=False)
        await interaction.edit_original_response(content="", embed=embed)

    @tickets_group.command(name="tile", description="In-depth view of a tile's capture history.")
    @discord.app_commands.describe(tile="The tile to check.",
                                   channel="The channel to check.",
                                   season="The CT season to check. Defaults to the current one.",
                                   hide="If True, the message will be ephemeral.")
    @discord.app_commands.guild_only()
    # @discord.app_commands.default_permissions(administrator=True)
    # @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_tile_history(self, interaction: discord.InteractionResponse,
                               channel: discord.TextChannel,
                               tile: str,
                               season: None or int = 0,
                               hide: None or bool = False) -> None:
        if channel.id not in (await bot.db.queries.tickets.tracked_channels()):
            await interaction.response.send_message("That channel is not being tracked!", ephemeral=True)
            return

        tile = tile.upper()
        tile_re = r"(?:[a-gA-G][a-gA-G][a-hA-H]|[Mm][Rr][Xx]|[Zz]{3})"
        if re.search(tile_re, tile) is None or not bot.utils.bloons.is_tile_code_valid(tile):
            await interaction.response.send_message(f"`{tile}` is not a valid tile code!", ephemeral=True)
            return

        await interaction.response.send_message("Just a moment...", ephemeral=hide)
        if season == 0:
            season = bot.utils.bloons.get_ct_number_during(datetime.datetime.now())
        tile_claims = await bot.db.queries.tickets.get_tile_claims(tile, channel.id, season)

        content_template = "- <t:{tile_timestamp}> <@{user_id}>"
        content_parts = []
        for tc in tile_claims:
            content_parts.append(content_template.format(
                tile_timestamp=int(tc.claimed_at.timestamp()),
                user_id=tc.user_id,
            ))

        diff_template = " `+{days}{hours:>02}:{minutes:>02}:{seconds:>02}`"
        for i in range(1, len(content_parts)):
            cap_diff = tile_claims[i].claimed_at - tile_claims[i-1].claimed_at
            days = "" if cap_diff.days == 0 else f"{cap_diff.days}d "
            content_parts[i] += diff_template.format(
                days=days, hours=int(cap_diff.seconds/3600),
                minutes=int(cap_diff.seconds/60) % 60, seconds=cap_diff.seconds % 60
            )

        if len(tile_claims) == 0:
            content = f"*This tile wasn't captured in CT {season}!*"
        else:
            content = "\n".join(content_parts)

        await interaction.edit_original_response(
            content="",
            embed=discord.Embed(
                title=f"{tile} Capture History (CT {season})",
                description=content,
                color=discord.Color.orange(),
            ),
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if str(payload.emoji) not in tracked_emojis or \
                payload.channel_id not in (await bot.db.queries.tickets.tracked_channels()):
            return

        tile_re = r"(?:[a-gA-G][a-gA-G][a-hA-H]|[Mm][Rr][Xx]|[Zz]{3})"
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        match = re.search(tile_re, message.content)
        if match is None:
            return

        tile = match.group(0).upper()
        if not bot.utils.bloons.is_tile_code_valid(tile):
            return

        await bot.db.queries.tickets.capture(payload.channel_id, message.author.id, tile, payload.message_id)

        # Forward event to those who are listening
        for cog_name in self.bot.cogs:
            cog = self.bot.cogs[cog_name]
            if hasattr(cog, "on_tile_captured"):
                await cog.on_tile_captured(tile, payload.channel_id, message.author.id)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if str(payload.emoji) not in tracked_emojis or \
                payload.channel_id not in (await bot.db.queries.tickets.tracked_channels()):
            return

        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        for reaction in message.reactions:
            if reaction.emoji in tracked_emojis:
                return
        capture = await bot.db.queries.tickets.get_capture_by_message(payload.message_id)
        await bot.db.queries.tickets.uncapture(payload.message_id)

        # Forward event to those who are listening
        for cog_name in self.bot.cogs:
            cog = self.bot.cogs[cog_name]
            if hasattr(cog, "on_tile_uncaptured"):
                await cog.on_tile_uncaptured(capture.tile, capture.channel_id, capture.user_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TrackerCog(bot))
