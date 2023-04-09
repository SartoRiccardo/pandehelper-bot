import asyncio
import ct_ticket_tracker.utils.io
import discord
from discord.ext import commands
from ct_ticket_tracker.classes import ErrorHandlerCog


class UtilsCog(ErrorHandlerCog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UtilsCog(bot))
