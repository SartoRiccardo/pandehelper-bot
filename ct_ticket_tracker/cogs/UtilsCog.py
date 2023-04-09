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
        rounds = sorted(rounds[:end_round], key=lambda x: x["length"])
        rounds.reverse()
        rounds = rounds[:3]

        reply = f"The {len(rounds)} longest rounds are:\n" + \
                "".join([f"• R{rnd['round']} - {rnd['length']:.2f}\n" for rnd in rounds]) + \
                f"The last bloon should be a **{rounds[0]['last_bloon']}**"
        await interaction.response.send_message(reply)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UtilsCog(bot))
