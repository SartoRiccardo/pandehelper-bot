import asyncio
import datetime
import discord
from discord.ext import commands
import re
import ct_ticket_tracker.db.queries
import ct_ticket_tracker.utils.bloons
from typing import Optional


class RaidLogCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.app_commands.command(name="raidlog", description="Get a Raid Log thread")
    @discord.app_commands.describe(tile_code="The tile code to look up.")
    @discord.app_commands.guild_only()
    async def cmd_raid_log_thread(self, interaction: discord.Interaction, tile_code: str) -> None:
        forum_id = 1049000279099588719

        tile_re = r"[A-GM][A-GR][A-HX]"
        tile_code = tile_code.upper()
        if re.search(tile_re, tile_code) is None:
            await interaction.response.send_message(f"The tile {tile_code} doesn't exist!",
                                                    ephemeral=True)

        await interaction.response.defer()
        try:
            forum_channel = await interaction.guild.fetch_channel(forum_id)
        except discord.app_commands.errors.CommandInvokeError:
            await interaction.response.send_message(f"Channel not found in the current guild!",
                                                    ephemeral=True)
            return

        for thread in forum_channel.threads:
            if tile_code in thread.name.upper():
                thread_url = f"https://discord.com/channels/{interaction.guild.id}/{forum_channel.id}"
                embed = discord.Embed(title=f"Raid Log - Tile {tile_code}",
                                      colour=discord.Color.orange(),
                                      description=f"Link to the thread: <#{thread.id}>\n"
                                                  f"If it doesn't work, click [here]({thread_url}) "
                                                  f"to jump to that thread!")
                await interaction.edit_original_response(embed=embed)
                return

        async for thread in forum_channel.archived_threads(limit=200):
            if tile_code in thread.name.upper():
                thread_url = f"https://discord.com/channels/{interaction.guild.id}/{forum_channel.id}"
                embed = discord.Embed(title=f"Raid Log - Tile {tile_code}",
                                      colour=discord.Color.orange(),
                                      description=f"Link to the thread: <#{thread.id}>\n"
                                                  f"If it doesn't work, click [here]({thread_url})"
                                                  f"to jump to that thread!")
                await interaction.edit_original_response(embed=embed)
                return

        await interaction.edit_original_response(content=f"There is no thread named {tile_code}!")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RaidLogCog(bot))
