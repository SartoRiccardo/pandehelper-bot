import discord
from discord.ext import commands
import ct_ticket_tracker.db.queries
import ct_ticket_tracker.utils.bloons
from ct_ticket_tracker.classes import ErrorHandlerCog


class TagCog(ErrorHandlerCog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.app_commands.command(name="tag",
                                  description="Sends a message associated with the given tag")
    @discord.app_commands.describe(tag_name="The tag to search")
    async def send_tag(self, interaction: discord.Interaction, tag_name: str) -> None:
        await interaction.response.defer()
        tag_content = await ct_ticket_tracker.db.queries.get_tag(tag_name)
        response_content = tag_content if tag_content else "No tag with that name!"
        await interaction.edit_original_response(content=response_content)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TagCog(bot))
