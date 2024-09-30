import asyncio
import datetime
import bot.utils.io
import bot.utils.bloons
import bot.utils.discordutils
import discord
from discord.ext import commands, tasks
from .CogBase import CogBase


class UtilsCog(CogBase):
    help_descriptions = {
        "longestround": "Gives you info about a race's longest round, and the rounds that follow.",
        # "mintime": "Tells you what time you'll get if you pclean a race after fullsending on a certain round.",
        "tag": "Sends a pre-written message associated to a tag. Usually for FAQs.\n"
               "Type the command with no parameters to see all available tags.",
        "github": "Get a link to the bot's repo. It's open source!",
        "invite": "Invite the bot to your server!",
        "now": "Now!",
        "roster-timezones": "Check the timezones for a team's roster.",
        "ct-period": "Check a CT event's start and end date by number.",
    }

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)
        self.tag_list: list[str] = []

    async def cog_load(self) -> None:
        await super().cog_load()
        self.update_tag_list.start()

    async def cog_unload(self) -> None:
        await super().cog_unload()
        self.update_tag_list.cancel()

    @tasks.loop(seconds=60*60)
    async def update_tag_list(self) -> None:
        self.tag_list = await bot.utils.io.get_tag_list()

    @discord.app_commands.command(name="ct-period",
                                  description="Check when a CT event started and ended.")
    @discord.app_commands.describe(event="The event number to check.")
    async def cmd_ct_period(self, interaction: discord.Interaction, event: int) -> None:
        if event < 0:
            await interaction.response.send_message("CT events must be positive.")
            return

        start, end = bot.utils.bloons.get_ct_period_during(event=event)
        # Event 1 lasted 12 days. get_ct_period_during treats it as it having 7 days cause it was easier to code.
        if event == 1:
            start -= datetime.timedelta(days=5)

        if start > datetime.datetime.now():
            verb_start, verb_end = "will start", "end"
        else:
            verb_start, verb_end = "started", "ended"
        await interaction.response.send_message(f"**CT #{event}** {verb_start} at <t:{int(start.timestamp())}> and {verb_end} at <t:{int(end.timestamp())}>.")

    @discord.app_commands.command(name="longestround",
                                  description="Get the longest round and its duration for races.")
    @discord.app_commands.describe(end_round="The last round of the race.")
    async def cmd_longestround(self, interaction: discord.Interaction, end_round: int) -> None:
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
    # async def cmd_mintime(self, interaction: discord.Interaction, from_round: int,
    #                       to_round: int, send_time_formatted: str) -> None:
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
    async def cmd_send_help_msg(self, interaction: discord.Interaction, module: str = None) -> None:
        help_cmd = await self.bot.get_app_command("help")

        if module is None:
            cogs = self.get_help_cogs()
            cog_list = '`\n- `'.join(cogs)
            message = "This bot has many features, organized into \"modules\"! " \
                      "If you want info about a specific module, pass its name through the `module` " \
                      f"parameter the next time you use </help:{help_cmd.id}>!\n" \
                      f"*Available modules:*\n- `{cog_list}`\n\n" \
                      "Also be sure to check out [the wiki](<https://github.com/SartoRiccardo/ct-ticket-tracker/wiki>) " \
                      "for help in setting up some of the more difficult to use modules!"
            await interaction.response.send_message(message, ephemeral=True)
            return

        module = module.lower()
        cog = None
        for cog_name in self.bot.cogs.keys():
            if cog_name.lower().replace("cog", "") == module:
                cog = self.bot.cogs[cog_name]
                break

        if cog is None:
            message = f"No module named `{module}`! Please use </help:{help_cmd.id}> with no parameters " \
                      "to see which modules are available!"
            await interaction.response.send_message(message, ephemeral=True)
            return

        await interaction.response.send_message(await cog.help_message(), ephemeral=True)

    @cmd_send_help_msg.autocomplete("module")
    async def autoc_tag_tag_name(self,
                                 _interaction: discord.Interaction,
                                 current: str
                                 ) -> list[discord.app_commands.Choice[str]]:
        return [
            discord.app_commands.Choice(name=tag, value=tag)
            for tag in self.get_help_cogs() if current.lower() in tag.lower()
        ]

    def get_help_cogs(self):
        return [
            cog.replace("Cog", "").title()
            for cog in self.bot.cogs.keys()
            if isinstance(self.bot.cogs[cog], CogBase) and self.bot.cogs[cog].has_help_msg
        ]

    @discord.app_commands.command(name="tag",
                                  description="Sends a message associated with the given tag")
    @discord.app_commands.describe(tag_name="The tag to search")
    async def cmd_send_tag(self, interaction: discord.Interaction, tag_name: str = None) -> None:
        await interaction.response.defer()
        if tag_name is None:
            tags = await bot.utils.io.get_tag_list()
            await interaction.edit_original_response(content=f"Tags: `{'` `'.join(tags)}`")
            return

        tag_content = await bot.utils.io.get_tag(tag_name.lower())
        response_content = tag_content if tag_content else "No tag with that name!"
        await interaction.edit_original_response(content=response_content)

    @cmd_send_tag.autocomplete("tag_name")
    async def autoc_tag_tag_name(self,
                                 _interaction: discord.Interaction,
                                 current: str
                                 ) -> list[discord.app_commands.Choice[str]]:
        return [
            discord.app_commands.Choice(name=tag, value=tag)
            for tag in self.tag_list if current.lower() in tag.lower()
        ]

    @discord.app_commands.command(name="github",
                                  description="Get the bot's repo")
    async def cmd_github(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("https://github.com/SartoRiccardo/ct-ticket-tracker/")

    @discord.app_commands.command(name="invite",
                                  description="Invite Pandemonium Helper to your server!")
    async def cmd_invite(self, interaction: discord.Interaction) -> None:
        perms = "51808381968"
        perms = "8"
        url = f"https://discord.com/api/oauth2/authorize?client_id=1088892665422151710&permissions={perms}&scope=bot"
        await interaction.response.send_message(
            content=f"Wanna invite me to your server? Use [this invite link]({url})!"
        )

    @discord.app_commands.command(name="now",
                                  description="Now!")
    async def cmd_now(self, interaction: discord.Interaction) -> None:
        now = datetime.datetime.now()
        await interaction.response.send_message(
            content=f"`{int(now.timestamp())}` <t:{int(now.timestamp())}>"
        )

    @discord.app_commands.command(name="team-timezones",
                                  description="Get an idea of where a team's roster lives.")
    @discord.app_commands.describe(team_role="The role that every member of the team has.")
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    @discord.app_commands.guild_only()
    @bot.utils.discordutils.gatekeep()
    async def cmd_roster_timezones(self, interaction: discord.Interaction, team_role: discord.Role) -> None:
        timezone_roles = {
            1053808789696024676: [],
            1053808801272311830: [],
            1101112063276884060: [],
        }
        timezone_unknown = []

        for member in team_role.members:
            found_timezone = False
            for role in member.roles:
                if role.id in timezone_roles:
                    timezone_roles[role.id].append(member)
                    found_timezone = True
                    break
            if not found_timezone:
                timezone_unknown.append(member)

        embed = discord.Embed(title=f"{team_role.name.title()} Team Timezones",
                              colour=discord.Colour.orange())
        for role_id in timezone_roles:
            tz_role = discord.utils.get(interaction.guild.roles, id=role_id)
            member_list = timezone_roles[role_id]
            embed.add_field(name=tz_role.name.title(), value="\n".join([m.mention for m in member_list]))
        if len(timezone_unknown) > 0:
            embed.add_field(name="Unknown", value="\n".join([m.mention for m in timezone_unknown]))
        embed.set_footer(text=f"Number of members: {len(team_role.members)}")

        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="info",
                                  description="General information about the bot.")
    async def cmd_info(self, interaction: discord.Interaction) -> None:
        lr = int(self.bot.last_restart.timestamp())
        embed = discord.Embed(
            title=f"PandeHelper v{self.bot.version}",
            description=f"- Playing **__{len(self.bot.guilds)}__** tiles (server count)\n"
                        f"- Last Restart: <t:{lr}> (<t:{lr}:R>)\n"
                        "More information and help at [pandehelper.sarto.dev](https://pandehelper.sarto.dev)"
                        "Found a bug? Yell at the maintainer or make [an issue on Github](https://github.com/SartoRiccardo/ct-ticket-tracker/issues)\n\n"
                        f"*Coded & maintained by __Chime__ (@chime.nemo) <:chimichanga:1147529275499614288>*",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UtilsCog(bot))
