import asyncio
import ct_ticket_tracker.utils.io
import ct_ticket_tracker.db.queries
import ct_ticket_tracker.utils.bloons
import discord
from discord.ext import commands
from ct_ticket_tracker.classes import ErrorHandlerCog


class UtilsCog(ErrorHandlerCog):
    help_descriptions = {
        "longestround": "Gives you info about a race's longest round, and the rounds that follow.",
        "tag": "Sends a pre-written message associated to a tag. Usually for FAQs.\n"
               "Type the command with no parameters to see all available tags."
    }

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)

    @discord.app_commands.command(name="longestround",
                                  description="Get the longest round and its duration for races.")
    @discord.app_commands.describe(end_round="The last round of the race.")
    async def longestround(self, interaction: discord.Interaction, end_round: int) -> None:
        if end_round <= 0:
            await interaction.response.send_message(f"{end_round} is not a valid round.")
            return

        rounds = await asyncio.to_thread(ct_ticket_tracker.utils.io.get_race_rounds)
        start_round = 0
        round_checkpoints = []
        while start_round < end_round:
            check_rounds = sorted(rounds[start_round:end_round], key=lambda x: x["length"])
            longest = check_rounds[-1]
            start_round = longest["round"]
            round_checkpoints.append(longest)

        followup_rounds_template = "‣ Send **R{}** after max. **{:.2f}s**\n" \
                                   "   *({:.2f}s after R{})   (lasts {:.2f}s total)*\n\n"
        checkpoints_msg = ""
        for i in range(len(round_checkpoints)-1):
            rnd = round_checkpoints[i+1]
            prev_rnd = round_checkpoints[i]
            checkpoints_msg += followup_rounds_template.format(
                rnd["round"], round_checkpoints[0]["length"]-rnd["length"], prev_rnd["length"]-rnd["length"],
                prev_rnd["round"], rnd["length"]
            )
        reply = f"The longest round is **R{round_checkpoints[0]['round']} **" \
                f"(lasts **{round_checkpoints[0]['length']:.2f}s**).\n\n" + \
                checkpoints_msg + \
                f"The last bloon should be a **{round_checkpoints[0]['last_bloon']}** " \
                f"(or a **{round_checkpoints[0]['last_bloon_reverse']}** if the race is on Reverse)."
        await interaction.response.send_message(reply)

    @discord.app_commands.command(name="help",
                                  description="Get info about the bot's commands.")
    @discord.app_commands.describe(module="The module to get info for.")
    async def send_help_msg(self, interaction: discord.Interaction, module: str = None) -> None:
        blacklisted_cogs = ["owner", "raidlog"]
        if module is None:
            cogs = [cog.replace("Cog", "").lower() for cog in self.bot.cogs.keys()]
            for blck_cog in blacklisted_cogs:
                cogs.remove(blck_cog)
            message = "This bot has many features, organized into \"modules\"! " \
                      "If you want info about a specific module, pass its name through the `module` " \
                      "parameter the next time you use /help!\n" \
                      f"*Available modules:* `{'` `'.join(cogs)}`"
            await interaction.response.send_message(message, ephemeral=True)
            return

        module = module.lower()
        cog = None
        for cog_name in self.bot.cogs.keys():
            if cog_name.lower().replace("cog", "") == module:
                cog = self.bot.cogs[cog_name]
                break

        if cog is None:
            message = f"No module named `{module}`! Please use /help with no parameters " \
                      "to see which modules are available!"
            await interaction.response.send_message(message, ephemeral=True)
            return

        await interaction.response.send_message(await cog.help_message(), ephemeral=True)

    @discord.app_commands.command(name="tag",
                                  description="Sends a message associated with the given tag")
    @discord.app_commands.describe(tag_name="The tag to search")
    async def send_tag(self, interaction: discord.Interaction, tag_name: str) -> None:
        await interaction.response.defer()
        tag_content = await ct_ticket_tracker.db.queries.get_tag(tag_name.lower())
        response_content = tag_content if tag_content else "No tag with that name!"
        await interaction.edit_original_response(content=response_content)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UtilsCog(bot))
