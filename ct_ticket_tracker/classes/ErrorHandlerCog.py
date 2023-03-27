import discord
from discord.ext import commands
from ct_ticket_tracker.exceptions import WrongChannelMention


class ErrorHandlerCog(commands.Cog):
    async def cog_app_command_error(self, interaction: discord.Interaction,
                                    error: discord.app_commands.AppCommandError) -> None:
        print(error, type(error.__cause__), type(error))

        content = "An error has occurred!"
        error_type = type(error.__cause__)
        if error.__cause__ is None:
            error_type = type(error)

        if error_type == WrongChannelMention:
            content = "You did not provide a valid channel! Please *mention* the channel, don't just type its name.\n" + \
                      f"For example, instead of \"{interaction.channel.name}\" it should be \"<#{interaction.channel_id}>\""
        elif error_type == discord.app_commands.errors.MissingPermissions:
            content = "You don't have the perms to execute this command. Sorry!"

        if interaction.response.is_done():
            await interaction.edit_original_response(content=content)
        else:
            await interaction.response.send_message(content, ephemeral=True)

