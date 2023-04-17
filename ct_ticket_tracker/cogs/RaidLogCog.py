import discord
from discord.ext import commands
from ct_ticket_tracker.classes import ErrorHandlerCog
import ct_ticket_tracker.utils.bloons
import re


class RaidLogCog(ErrorHandlerCog):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)

    @discord.app_commands.command(name="raidlog", description="Get a Raid Log thread")
    @discord.app_commands.describe(tile_code="The tile code to look up.")
    @discord.app_commands.guild_only()
    async def cmd_raid_log_thread(self, interaction: discord.Interaction, tile_code: str) -> None:
        forum_id = 1049000279099588719

        tile_re = r"[A-GM][A-GR][A-GX]"
        tile_code = tile_code.upper()
        if re.search(tile_re, tile_code) is None:
            await interaction.response.send_message(f"The tile {tile_code} doesn't exist!",
                                                    ephemeral=True)

        await interaction.response.defer()
        try:
            forum_channel = await interaction.guild.fetch_channel(forum_id)
        except (discord.errors.Forbidden, discord.errors.InvalidData):
            await interaction.edit_original_response(content=f"This command is only for the Pandemonium server. Sorry!")
            return

        for thread in forum_channel.threads:
            if tile_code in thread.name.upper():
                thread_url = f"https://discord.com/channels/{interaction.guild.id}/{thread.id}"
                embed = discord.Embed(title=f"Raid Log - Tile {tile_code}",
                                      colour=discord.Color.orange(),
                                      description=f"Link to the thread: <#{thread.id}>\n"
                                                  f"If it doesn't work, click [here]({thread_url}) "
                                                  f"to jump to that thread!")
                await interaction.edit_original_response(embed=embed)
                return

        async for thread in forum_channel.archived_threads(limit=200):
            if tile_code in thread.name.upper():
                thread_url = f"https://discord.com/channels/{interaction.guild.id}/{thread.id}"
                embed = discord.Embed(title=f"Raid Log - Tile {tile_code}",
                                      colour=discord.Color.orange(),
                                      description=f"Link to the thread: <#{thread.id}>\n"
                                                  f"If it doesn't work, click [here]({thread_url})"
                                                  f"to jump to that thread!")
                await interaction.edit_original_response(embed=embed)
                return

        await interaction.edit_original_response(content=f"There is no thread named {tile_code}!")

    @discord.app_commands.command(name="newraidlog", description="Mark the beginning of a new event in Raid Log")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    @discord.app_commands.guild_only()
    async def cmd_raidlog_reset(self, interaction: discord.Interaction) -> None:
        forum_id = 1049000279099588719
        tile_re = r"[A-GM][A-GR][A-GX]"

        await interaction.response.send_message(
            "Announcing a new season in Raid Log! It might take a while...",
            ephemeral=True
        )

        try:
            forum_channel = discord.utils.get(interaction.guild.channels, id=forum_id)
            if forum_channel is None:
                forum_channel = await interaction.guild.fetch_channel(forum_id)
        except (discord.errors.Forbidden, discord.errors.InvalidData):
            await interaction.edit_original_response(content=f"This command is only for the Pandemonium server. Sorry!")
            return

        for thread in forum_channel.threads:
            if re.match(tile_re, thread.name.upper()) is not None:
                await self.announce_ct_season_raidlog(thread)

        async for thread in forum_channel.archived_threads(limit=200):
            if re.match(tile_re, thread.name.upper()) is not None:
                await self.announce_ct_season_raidlog(thread)

        await interaction.edit_original_response(content="All done!")

    async def announce_ct_season_raidlog(self, channel: discord.Thread) -> None:
        ct_num = ct_ticket_tracker.utils.bloons.get_current_ct_number(breakpoint_on_event_start=False)
        season_message = f"__**— CONTESTED TERRITORY {ct_num} —**__"

        last_message = channel.last_message
        if last_message is None:
            last_message = [msg async for msg in channel.history(limit=1)][0]

        if last_message.author == self.bot.user:
            await last_message.edit(content=season_message)
        else:
            await channel.send(season_message)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RaidLogCog(bot))
