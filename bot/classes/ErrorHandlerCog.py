import discord
import traceback
from discord.ext import commands
from .HelpMessageCog import HelpMessageCog
from bot.exceptions import WrongChannelMention, MustBeForum, Gatekept, UnknownTile


class ErrorHandlerCog(HelpMessageCog):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)

    async def cog_app_command_error(self, interaction: discord.Interaction,
                                    error: discord.app_commands.AppCommandError) -> None:
        print(error, type(error.__cause__), type(error))
        traceback.print_exc()

        content = "An error has occurred!"
        thrown_error = error.__cause__
        error_type = type(error.__cause__)
        if error.__cause__ is None:
            error_type = type(error)
            thrown_error = error

        if error_type == WrongChannelMention:
            content = "You did not provide a valid channel! Please *mention* the channel, don't just type its name.\n" + \
                      f"For example, instead of \"{interaction.channel.name}\" it should be \"<#{interaction.channel_id}>\""
        elif error_type == discord.app_commands.errors.MissingPermissions:
            content = "You don't have the perms to execute this command. Sorry!\n" \
                      f"*Needs permissions: {', '.join(thrown_error.missing_permissions)}*"
        elif error_type == MustBeForum:
            content = "The channel must be a forum!"
        elif error_type == Gatekept:
            content = "<:hehe:1111026798210326719>"
        elif error_type == UnknownTile:
            content = f"Tile {thrown_error.tile} doesn't exist!"
        elif error_type == discord.errors.Forbidden:
            content = f"I don't have the perms to do that!"

        if interaction.response.is_done():
            await interaction.edit_original_response(content=content)
        else:
            await interaction.response.send_message(content, ephemeral=True)

