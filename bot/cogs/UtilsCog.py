import asyncio
import re
import asyncpg.exceptions
import bloonspy
import bloonspy.exceptions
import bot.utils.io
import bot.db.queries
import discord
from discord.ext import commands
from bot.classes import ErrorHandlerCog


class UtilsCog(ErrorHandlerCog):
    help_descriptions = {
        "longestround": "Gives you info about a race's longest round, and the rounds that follow.",
        # "mintime": "Tells you what time you'll get if you pclean a race after fullsending on a certain round.",
        "tag": "Sends a pre-written message associated to a tag. Usually for FAQs.\n"
               "Type the command with no parameters to see all available tags.",
        "github": "Get a link to the bot's repo. It's open source!",
        "verify": "Tell the bot who you are in BTD6!",
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

        rounds = await asyncio.to_thread(bot.utils.io.get_race_rounds)
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

    # @discord.app_commands.command(name="mintime",
    #                               description="Calculate the min time you can get on races when you fullsend.")
    # @discord.app_commands.describe(from_round="The round you're fullsending from.",
    #                                to_round="The last round of the race.",
    #                                send_time_formatted="The time you fullsend at (e.g. 0:50). "
    #                                                    "Don't include milliseconds.")
    # @discord.app_commands.rename(send_time_formatted="send_time")
    # async def mintime(self, interaction: discord.Interaction, from_round: int,
    #                   to_round: int, send_time_formatted: str) -> None:
    #     if send_time_formatted.isnumeric():
    #         send_time = int(send_time_formatted)
    #     else:
    #         minutes, seconds = send_time_formatted.split(":")
    #         send_time = int(minutes)*60 + int(seconds)
    #
    #     rounds = await asyncio.to_thread(ct_ticket_tracker.utils.io.get_race_rounds)
    #     longest = sorted(rounds[from_round-1:to_round], key=lambda x: x["length"])[-1]
    #     send_delay = (longest["round"]-from_round)*0.2
    #     final_time = send_time + longest["length"] + send_delay
    #     minutes = int(final_time/60)
    #
    #     message = f"The longest round {from_round}-{to_round} is **R{longest['round']}** *({longest['length']:.2f}s)*\n" \
    #               f"With the round send delay, you'll get there in {send_delay:.2f}s\n\n" \
    #               f"**Min time: {minutes}:{final_time - minutes * 60:05.2f}** *(if fullsent from {send_time}s)*.\n"
    #
    #     # message = f"If you are at R{from_round} and you fullsend at {send_time_formatted}, the longest round is " \
    #     #           f"R{longest['round']} ({longest['length']:.2f}s), plus round send delay, if you pclean you'll get " \
    #     #           f"**{minutes}:{final_time-minutes*60:.2f}**."
    #     await interaction.response.send_message(message)

    @discord.app_commands.command(name="help",
                                  description="Get info about the bot's commands.")
    @discord.app_commands.describe(module="The module to get info for.")
    async def send_help_msg(self, interaction: discord.Interaction, module: str = None) -> None:
        blacklisted_cogs = ["owner"]
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
    async def send_tag(self, interaction: discord.Interaction, tag_name: str = None) -> None:
        await interaction.response.defer()
        if tag_name is None:
            tags = await asyncio.to_thread(bot.utils.io.get_tag_list)
            await interaction.edit_original_response(content=f"Tags: `{'` `'.join(tags)}`")
            return
        tag_content = await asyncio.to_thread(bot.utils.io.get_tag, tag_name)
        response_content = tag_content if tag_content else "No tag with that name!"
        await interaction.edit_original_response(content=response_content)

    @discord.app_commands.command(name="github",
                                  description="Get the bot's repo")
    async def github(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("https://github.com/SartoRiccardo/ct-ticket-tracker/")

    @discord.app_commands.command(name="verify",
                                  description="Verify who you are in Bloons TD 6!")
    @discord.app_commands.describe(oak="Your Open Access Key (leave blank if you don't know what that is)")
    async def verify(self, interaction: discord.Interaction, oak: str = None) -> None:
        user = interaction.user
        instructions = "__**About verification**__\n" \
                       "To know who you are, I need your **Open Access Key (OAK)**. This is a bit of text that " \
                       "allows me to see a lot of things about you in-game, like your profile, your team, and " \
                       "more. It's perfectly safe though, Ninja Kiwi takes privacy very seriously, so I can't do " \
                       "anything bad with it even if I wanted to!\n\n" \
                       "__**Generate your OAK**__\n" \
                       "🔹 Open Bloons TD6 (or Battles 2) > Settings > My Account > Open Data API (it's a small " \
                       "link in the bottom right) > Generate Key. Your OAK should look something like " \
                       "`oak_h6ea...p1hr`.\n" \
                       "🔹 Copy it (note: the \"Copy\" button doesn't work, so just manually select it and do ctrl+C) " \
                       "and, do /verify and paste your OAK as a parameter. Congrats, you have verified yourself!\n\n" \
                       "__**What if I have alts?**__\n" \
                       "Sorry, only one Discord account per OAK for this bot (too lazy to code it). :(\n\n" \
                       "__**More information**__\n" \
                       "Ninja Kiwi talking about OAKs: https://support.ninjakiwi.com/hc/en-us/articles/13438499873937\n"

        if oak is None:
            await interaction.response.defer()
            oak = await bot.db.queries.get_oak(user.id)
            bloons_user = None
            if oak:
                try:
                    bloons_user = bloonspy.Client.get_user(oak)
                except bloonspy.exceptions.NotFound:
                    pass

            if bloons_user:
                is_veteran = bloons_user.veteran_rank > 0
                await interaction.edit_original_response(
                    content=f"You are already verified as {bloons_user.name}! "
                            f"({f'Vet{bloons_user.veteran_rank}' if is_veteran else f'Lv{bloons_user.rank}'})\n\n"
                            "*Not who you are? Run the command with the correct account's OAK!*"
                )
            elif interaction.guild:
                await interaction.edit_original_response(content="Check your DMs!")
                await user.send(instructions)
            else:
                await interaction.edit_original_response(content=instructions)
            return

        if re.match(r"oak_[\da-z]{32}", oak) is None:
            await interaction.response.send_message(
                "Your OAK is not well formatted! it should be `oak_` followed by 32 numbers and/or lowercase letters!\n\n"
                "*Don't know what an OAK is? Leave the field blank to get a help message!*",
                ephemeral=True
            )
            return

        try:
            bloons_user = bloonspy.Client.get_user(oak)
            is_veteran = bloons_user.veteran_rank > 0
            await bot.db.queries.set_oak(user.id, oak)
            await interaction.response.send_message(
                f"You've verified yourself as {bloons_user.name}! "
                f"({f'Vet{bloons_user.veteran_rank}' if is_veteran else f'Lv{bloons_user.rank}'})\n\n"
                "*Not who you are? Run the command with the correct account's OAK!*",
                ephemeral=True
            )
        except bloonspy.exceptions.NotFound:
            await interaction.response.send_message(
                "Couldn't find a BTD6 user with that OAK! Are you sure it's the correct one?",
                ephemeral=True
            )
        except asyncpg.exceptions.UniqueViolationError:
            await interaction.response.send_message(
                "Someone else is already registered with that OAK!",
                ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UtilsCog(bot))
