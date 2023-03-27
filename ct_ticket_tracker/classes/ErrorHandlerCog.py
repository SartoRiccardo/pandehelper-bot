import discord
from discord.ext import commands
from ct_ticket_tracker.exceptions import WrongChannelMention


class ErrorHandlerCog(commands.Cog):
    async def cog_app_command_error(self, interaction: discord.Interaction,
                                    error: discord.app_commands.AppCommandError) -> None:
        error_type = type(error.__cause__)
        if error_type == WrongChannelMention:
            await interaction.response.send_message(
                "You did not provide a valid channel! Please *mention* the channel, don't just type its name.\n"
                f"For example, instead of \"{interaction.channel.name}\" it should be \"<#{interaction.channel_id}>\"",
                ephemeral=True
            )
        elif error_type == discord.app_commands.errors.MissingPermissions:
            await interaction.response.send_message(
                "You don't have the perms to execute this command. Sorry!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "An error has occurred!", ephemeral=True
            )
