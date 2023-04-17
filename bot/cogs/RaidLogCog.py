import discord
from discord.ext import commands
import bot.db.queries
from bot.classes import ErrorHandlerCog
from bot.exceptions import WrongChannelMention, MustBeForum
import bot.utils.bloons
import re
import bloonspy
from typing import List


thread_init_message = """
# How to make a good post

Other than posting the general strategy (e.g. "Sniper 025", "Gwen Solo", ...) there are other things you can say to make your report better:
* __Post the score you got.__ For Least Tiers/Least Cash, post the exact score, for Race and Boss tiles you can post an approximate time (e.g. "Sub 1:30").
* __Post the relics you used.__ It's extremely important you show what you used since some strategies are only possible with them.
* If you use Powers or Abilities, __describe the activation timing on important rounds.__ For example: "Place a Glue Trap on R63" or "Use Phoenix when you start getting overwhealmed on R77" or "Use both SMS on Tier 1" etc...

There are also extra rules specific to tile types.

## Least Tiers/Least Cash
* __Post a screenshot of the map once you win.__ Knowing tower placements can be really important!

## Boss
* __Describe the farming methods you used.__ Bloontrap? Buy farm on Round 5? Geraldo? You tell me!
* __Post a screenshot of your setup for every tier.__

## Race
You can do 2 things for race tiles, which one is up to you:
* __Post a video of your race.__ That's the simplest way to do it although kind of annoying to set up.
* __Accurately describe what to get and which rounds to send.__ For example:
 * Buy Ace 020, send R20
 * Ace 020 > 030, send R39
 * Buy Bomb 003 > 203 > 204
 * Buy another Ace 030, send R49
 * Buy another Ace 030, spam 204 Bomb.
 * Fullsend
 * Ace 030 > 040, activate, sell for 205 Sniper for clean."""[1:]


class RaidLogCog(ErrorHandlerCog):
    help_descriptions = {
        None: "Manages a forum to post tile strategies",
        "tilestratforum": {
            "create": "Creates a new Tile Strat forum. You can rename it & set the perms to whatever you want",
            "set": "Sets an existing channel as the Tile Strat forum. Using [[create]] is recommended though.",
            "unset": "Makes the bot stop tracking the current Tile Strat forum.",
        },
        "tilestrat": "Looks up a strat in the Tile Strat forum.",
    }

    group_tilestratchannel = discord.app_commands.Group(
        name="tilestratchannel",
        description="Manage the Tile Strat forum."
    )

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)

    @discord.app_commands.command(name="tilestrat", description="Get the strat thread for a tile")
    @discord.app_commands.describe(tile_code="The tile code to look up.")
    @discord.app_commands.guild_only()
    async def cmd_search(self, interaction: discord.Interaction, tile_code: str) -> None:
        forum_id = await bot.db.queries.get_tile_strat_forum(interaction.guild_id)
        if forum_id is None:
            await interaction.response.send_message(
                "You don't have a Tile Strats forum set! Run /tilestratforum create or /tilestratforum set to have one.",
                ephemeral=True
            )
            return

        tile_code = tile_code.strip().upper()
        tile_re = r"(?:M|[A-G])(?:R|[A-G])(?:X|[A-H])"
        if len(tile_code) != 3 or re.match(tile_re, tile_code) is None:
            await interaction.response.send_message(
                f"The tile {tile_code} doesn't exist!",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            forum_channel = await interaction.guild.fetch_channel(forum_id)
        except discord.errors.Forbidden:
            await interaction.edit_original_response(
                content=f"I don't have permission to see that channel!"
            )
            return
        except discord.errors.InvalidData:
            await interaction.edit_original_response(
                content=f"That channel isn't even in this server!"
            )
            return

        current_event_tag = f"Season {bot.utils.bloons.get_current_ct_number()}"
        if current_event_tag not in [tag.name for tag in forum_channel.available_tags]:
            await forum_channel.create_tag(name=current_event_tag)

        old_strats = []
        found = None
        for thread in forum_channel.threads:
            if tile_code in thread.name.upper():
                if current_event_tag in [tag.name for tag in thread.applied_tags]:
                    found = thread
                    await interaction.edit_original_response(
                        embed=self.get_raidlog_embed(thread, old_strats, loading=True)
                    )
                else:
                    old_strats.append(thread)

        async for thread in forum_channel.archived_threads(limit=None):
            if tile_code in thread.name.upper():
                if current_event_tag in [tag.name for tag in thread.applied_tags]:
                    found = thread
                    await interaction.edit_original_response(
                        embed=self.get_raidlog_embed(thread, old_strats, loading=True)
                    )
                else:
                    old_strats.append(thread)

        if not found:
            # tile_info = bloonspy.get_tile_info_somehow(tile_code)

            tags = [
                discord.utils.get(forum_channel.available_tags, name=current_event_tag)
            ]
            thread_template = "[{map}] {tile_code}"
            found = await forum_channel.create_thread(
                name=thread_template.format(map="", tile_code=tile_code),
                content=thread_init_message,
                applied_tags=tags,
            )

        await interaction.edit_original_response(
            embed=self.get_raidlog_embed(found, old_strats)
        )

    @group_tilestratchannel.command(name="create", description="Create a Tile Strats forum.")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    @discord.app_commands.guild_only()
    async def cmd_create_raidlog(self, interaction: discord.Interaction) -> None:
        forum = await interaction.guild.create_forum("tile-strats")

        await bot.db.queries.set_tile_strat_forum(interaction.guild_id, forum.id)
        await interaction.response.send_message(
            f"Done! <#{forum.id}> is now your Tile Strats forum!"
        )

    @group_tilestratchannel.command(
        name="set",
        description="Set an existing channel as the server's Tile Strats forum"
    )
    @discord.app_commands.describe(channel="The forum to set as the server's Tile Strats forum")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    @discord.app_commands.guild_only()
    async def cmd_set_raidlog(self, interaction: discord.Interaction, channel: str) -> None:
        channel = channel.strip()
        if len(channel) <= 3 or not channel[2:-1].isnumeric():
            raise WrongChannelMention()
        channel_id = int(channel[2:-1])
        print(channel_id)
        forum = discord.utils.get(interaction.guild.forums, id=channel_id)
        if not forum:
            raise WrongChannelMention()
        if not isinstance(forum, discord.ForumChannel):
            raise MustBeForum()

        await bot.db.queries.set_tile_strat_forum(interaction.guild_id, channel_id)
        await interaction.response.send_message(
            f"Done! <#{channel_id}> is now your Tile Strats forum!"
        )

    @group_tilestratchannel.command(name="unset", description="Stop tracking the current Tile Strats forum")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    @discord.app_commands.guild_only()
    async def cmd_unset_raidlog(self, interaction: discord.Interaction) -> None:
        await bot.db.queries.del_tile_strat_forum(interaction.guild_id)
        await interaction.response.send_message(
            "Done! You server no longer has a tile strat forum!"
        )

    @staticmethod
    def get_raidlog_embed(
            thread: discord.Thread,
            old_threads: List[discord.Thread],
            loading: bool = False
    ) -> discord.Embed:
        content = f"Click [HERE]({RaidLogCog.get_channel_url(thread)}) to go jump to the thread!"

        if len(old_threads) > 0:
            threads_str = []
            thread_template = "• [CT{ct_num}]({thread_url}) - {tile_type} {boss_type}"
            tile_types = ["Least Cash", "Least Tiers", "Race", "Boss"]
            bosses = ["Vortex", "Lych", "Bloonarius"]
            for old_thr in old_threads:
                ct_num = "???"
                tile_type = "Unknown Tile type"
                boss_type = ""
                for tag in old_thr.applied_tags:
                    if "Event" in tag.name:
                        ct_num = tag.name[-2:]
                    elif tag.name in tile_types:
                        tile_type = tag.name
                        if tag.emoji:
                            tile_type = f"<:{tag.emoji.name}:{tag.emoji.id}> {tile_type}"
                    elif tag.name in bosses:
                        boss_type = tag.name
                        if tag.emoji:
                            boss_type = f"<:{tag.emoji.name}:{tag.emoji.id}> {boss_type}"

                threads_str.append(thread_template.format(
                    ct_num=ct_num,
                    thread_url=RaidLogCog.get_channel_url(old_thr),
                    tile_type=tile_type,
                    boss_type=boss_type
                ))
            content += "\n\n" + "\n".join(threads_str)

        if loading:
            content += "\n\nChecking for past threads for this tile code..."

        return discord.Embed(
            title=thread.name,
            description=content,
            color=discord.Color.orange()
        )

    @staticmethod
    def get_channel_url(channel: discord.abc.MessageableChannel):
        return f"https://discord.com/channels/{channel.guild.id}/{channel.id}"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RaidLogCog(bot))
