import asyncio
import os
import json
import bloonspy
import bloonspy.exceptions
import bot.utils.io
import bot.db.queries
import discord
from discord.ext import commands, tasks
from bot.classes import ErrorHandlerCog
from typing import List, Dict, Any


class UtilsCog(ErrorHandlerCog):
    help_descriptions = {
        "longestround": "Gives you info about a race's longest round, and the rounds that follow.",
        # "mintime": "Tells you what time you'll get if you pclean a race after fullsending on a certain round.",
        "tag": "Sends a pre-written message associated to a tag. Usually for FAQs.\n"
               "Type the command with no parameters to see all available tags.",
        "github": "Get a link to the bot's repo. It's open source!",
        "invite": "Invite the bot to your server!",
    }

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)
        self.tag_list: List[str] = []

    def cog_load(self) -> None:
        self.update_tag_list.start()

    def cog_unload(self) -> None:
        self.update_tag_list.cancel()

    @tasks.loop(seconds=60*60)
    async def update_tag_list(self) -> None:
        self.tag_list = await asyncio.to_thread(bot.utils.io.get_tag_list)

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
    async def cmd_send_tag(self, interaction: discord.Interaction, tag_name: str = None) -> None:
        await interaction.response.defer()
        if tag_name is None:
            tags = await asyncio.to_thread(bot.utils.io.get_tag_list)
            await interaction.edit_original_response(content=f"Tags: `{'` `'.join(tags)}`")
            return

        tag_content = await asyncio.to_thread(bot.utils.io.get_tag, tag_name.lower())
        response_content = tag_content if tag_content else "No tag with that name!"
        await interaction.edit_original_response(content=response_content)

    @cmd_send_tag.autocomplete("tag_name")
    async def autoc_tag_tag_name(self,
                                 _interaction: discord.Interaction,
                                 current: str
                                 ) -> List[discord.app_commands.Choice[str]]:
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
        url = "https://discord.com/api/oauth2/authorize?client_id=1088892665422151710&permissions=51539946512&scope=bot"
        await interaction.response.send_message(
            content=f"Wanna invite me to your server? Use [this invite link]({url})!"
        )

    @discord.app_commands.command(name="tile",
                                  description="Check a tile's challenge data")
    @discord.app_commands.describe(tile="The 3 letter tile code")
    @discord.app_commands.guild_only()
    async def cmd_tile(self, interaction: discord.Interaction, tile: str) -> None:
        # Gatekeeping the command to Pandemonium members
        has_access = False
        for role in interaction.user.roles:
            if role.id in [1005472018189271160, 1026966667345002517, 1011968628419207238, 860147253527838721, 940942269933043712]:
                has_access = True
                break
        if not has_access:
            return

        tile = tile.upper()
        embed = await self.get_tile_embed(tile)
        if embed is None:
            await interaction.response.send_message(
                content="I don't have the challenge data for that tile!"
            )
            return

        await interaction.response.send_message(
            embed=embed
        )

    @staticmethod
    async def get_tile_embed(tile: str) -> discord.Embed or None:
        path = f"bot/files/json/tiles/{tile}.json"
        if not os.path.exists(path):
            return None
        # Blocking operation ik idc
        fin = open(path)
        data = json.loads(fin.read())
        fin.close()

        tile_type = "Regular"
        if data['TileType'] == "TeamFirstCapture":
            return None
        elif data['TileType'] == "Banner":
            tile_type = "Banner"
        elif data['TileType'] == "Relic":
            tile_type = data['RelicType']
        data = data["GameData"]

        description = f"**{data['selectedMap']} - {data['selectedDifficulty']} {data['selectedMode']}**\n" \
                      f"Round {data['dcModel']['startRules']['round']}/{data['dcModel']['startRules']['endRound']} - " \
                      f"${data['dcModel']['startRules']['cash']}\n"
        if "bossData" in data:
            boss_name = "Bloonarius"
            if data['bossData']['bossBloon'] == 1:
                boss_name = "Lych"
            elif data['bossData']['bossBloon'] == 2:
                boss_name = "Vortex"
            description += f"{boss_name} {data['bossData']['TierCount']} Tiers\n"
        elif data['subGameType'] == 9:
            description += "Least Tiers\n"
        elif data['subGameType'] == 8:
            description += "Least Cash\n"
        elif data['subGameType'] == 2:
            description += "Time Attack\n"

        if data['dcModel']['maxTowers'] > -1:
            description += f"- **Max Towers:** {data['dcModel']['maxTowers']}\n"
        if data['dcModel']['disableMK']:
            description += f"- **Monkey Knowledge Disabled**\n"
        if data['dcModel']['disableSelling'] > -1:
            description += f"- **Selling Disabled**\n"
        if data['dcModel']['abilityCooldownReductionMultiplier'] != 1.0:
            description += f"- **Ability cooldown:** {int(data['dcModel']['abilityCooldownReductionMultiplier']*100)}%\n"
        if data['dcModel']['removeableCostMultiplier'] != 1.0:
            description += f"- **Removable cost:** {int(data['dcModel']['removeableCostMultiplier']*100)}%\n"
        if data['dcModel']['bloonModifiers']['speedMultiplier'] != 1.0:
            description += f"- **Bloon Speed:** {int(data['dcModel']['bloonModifiers']['speedMultiplier']*100)}%\n"
        if data['dcModel']['bloonModifiers']['moabSpeedMultiplier'] != 1.0:
            description += f"- **MOAB Speed:** {int(data['dcModel']['bloonModifiers']['moabSpeedMultiplier']*100)}%\n"
        if data['dcModel']['bloonModifiers']['healthMultipliers']['bloons'] != 1.0:
            description += f"- **Ceramic Health:** {int(data['dcModel']['bloonModifiers']['healthMultipliers']['bloons']*100)}%\n"
        if data['dcModel']['bloonModifiers']['healthMultipliers']['moabs'] != 1.0:
            description += f"- **MOAB Health:** {int(data['dcModel']['bloonModifiers']['healthMultipliers']['moabs']*100)}%\n"
        if data['dcModel']['bloonModifiers']['regrowRateMultiplier'] != 1.0:
            description += f"- **Regrow Rate:** {int(data['dcModel']['bloonModifiers']['regrowRateMultiplier']*100)}%\n"

        heroes = []
        towers = []
        for twr in data['dcModel']['towers']['_items']:
            if twr is None or twr['tower'] == "ChosenPrimaryHero" or twr['max'] == 0:
                continue
            if twr['isHero']:
                heroes.append(twr['tower'])
            else:
                towers.append((twr['tower'], twr['max']))
        towers_str = ""
        for i in range(len(towers)):
            name, max = towers[i]
            towers_str += f"{name}"
            if max > 0:
                towers_str += f" (x{max})"
            if i != len(towers)-1:
                towers_str += " - "

        embed = discord.Embed(
            title=f"{tile} - {tile_type}",
            description=description,
            color=discord.Color.orange(),
        )
        if len(heroes) > 0:
            embed.add_field(name="Heroes", value="-".join(heroes))
        embed.add_field(name="Towers", value=towers_str)
        embed.set_footer(text="Command is hastily made I'll improve sometime later")
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UtilsCog(bot))
