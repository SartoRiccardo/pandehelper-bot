import discord
from discord.ext import commands
from bot.classes import ErrorHandlerCog
import bot.utils.discordutils
import re


class RaidLogCog(ErrorHandlerCog):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)

    @discord.app_commands.command(name="raidlog", description="Alias for /tilestrat")
    @discord.app_commands.describe(tile_code="The tile code to look up.")
    @discord.app_commands.guild_only()
    @bot.utils.discordutils.gatekeep()
    async def cmd_search_raidlog(self, interaction: discord.Interaction, tile_code: str) -> None:
        await self.search_tile(interaction, tile_code)

    @discord.app_commands.command(name="tilestrat", description="Get the strat thread for a tile")
    @discord.app_commands.describe(tile_code="The tile code to look up.")
    @discord.app_commands.guild_only()
    @bot.utils.discordutils.gatekeep()
    async def cmd_search(self, interaction: discord.Interaction, tile_code: str) -> None:
        await self.search_tile(interaction, tile_code)

    async def search_tile(self, interaction: discord.Interaction, tile_code: str) -> None:
        forum_id = 1049000279099588719

        tile_re = r"[A-GM][A-GR][A-HX]"
        tile_code = tile_code.upper()
        if re.search(tile_re, tile_code) is None:
            await interaction.response.send_message(f"The tile {tile_code} doesn't exist!",
                                                    ephemeral=True)
            return

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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RaidLogCog(bot))
