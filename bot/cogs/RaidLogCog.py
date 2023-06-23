import discord
from datetime import datetime, timedelta
from discord.ext import commands, tasks
import asyncio
import bot.db.queries
import bot.utils.discordutils
from bot.exceptions import UnknownTile
from bot.classes import ErrorHandlerCog
import bot.utils.bloons
from bot.utils.emojis import LEAST_TIERS, LEAST_CASH, BLOONARIUS, VORTEX, LYCH, TIME_ATTACK
from bot.utils.images import IMG_LEAST_CASH, IMG_LEAST_TIERS, IMG_BLOONARIUS, IMG_VORTEX, IMG_LYCH, IMG_TIME_ATTACK
import re
from typing import List, Dict, Optional


thread_init_message = f"""
# How to make a good post

Other than posting the general strategy (e.g. "Sniper 025", "Gwen Solo", ...) there are other things you can say to make your report better:
* **__Post the score you got.__**
* **__Post the relics you used.__**
* **__Write ability/power activation timing on important rounds__**, if any.

## {LEAST_TIERS} Least Tiers / {LEAST_CASH} Least Cash
* __Post a screenshot of the map once you win.__ Knowing tower placements can be really important!
## {BLOONARIUS} Boss
* __Describe the farming methods you used__, if any. Bloontrap? Buy farm on Round 5? Geraldo? You tell me!
* __Post a screenshot of your setup for every tier.__ Briefly describe any micro involved if any.
## {TIME_ATTACK} Race
You can do one of 2 things for race tiles, which one is up to you:
* __Post a video of your race.__ That's the simplest way to do it although kind of annoying to set up.
* __Accurately describe what to get and which rounds to send.__ For example:
>  1. Buy Ace 020, send R20
>  2. Ace 020 > 030, send R39
>  3. Buy Bomb 003 > 203 > 204
>  4. Buy another Ace 030, send R49
>  5. Buy another Ace 030, spam 204 Bomb.
>  6. Fullsend
>  7. Ace 030 > 040, activate, sell for 205 Sniper for clean."""[1:]


class RaidLogCog(ErrorHandlerCog):
    help_descriptions = {
        None: "Manages a forum to post tile strategies",
        "tilestrat-forum": {
            "create": "Creates a new Tile Strat forum. You can rename it & set the perms to whatever you want",
            "set": "Sets an existing channel as the Tile Strat forum. Using [[create]] is recommended though.",
            "unset": "Makes the bot stop tracking the current Tile Strat forum.",
        },
        "tilestrat": "Looks up a strat in the Tile Strat forum. If there isn't a thread for it, it "
                     "creates a new one, and deletes it if no messages are posted in it for 3 hours.",
    }

    group_tilestratchannel = discord.app_commands.Group(
        name="tilestrat-forum",
        description="Manage the Tile Strat forum."
    )

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)
        self.check_back: Dict[int, datetime] = {}

    async def cog_load(self) -> None:
        await self.load_state()
        self.clean_raidlog.start()

    async def cog_unload(self) -> None:
        await self.load_state()
        self.clean_raidlog.cancel()

    async def load_state(self) -> None:
        state = await asyncio.to_thread(bot.utils.io.get_cog_state, "raidlog")
        if state is None:
            return

        data = state["data"]
        if "check_back" in data:
            self.check_back = {}
            for key in data["check_back"]:
                self.check_back[int(key)] = datetime.fromtimestamp(data["check_back"][key])

    async def save_state(self) -> None:
        data = {
            "check_back": {},
        }
        for key in self.check_back.keys():
            data["check_back"][str(key)] = self.check_back[key].timestamp()
        await asyncio.to_thread(bot.utils.io.save_cog_state, "raidlog", data)

    @tasks.loop(seconds=3600)
    async def clean_raidlog(self) -> None:
        now = datetime.now()
        thread_ids = self.check_back.keys()
        to_delete = []
        for thr_id in thread_ids:
            delete_at = self.check_back[thr_id]
            if delete_at > now:
                continue
            thread = self.bot.get_channel(thr_id)
            if thread is None:
                try:
                    thread = await self.bot.fetch_channel(thr_id)
                except discord.NotFound:
                    thread = None
            if thread is not None:
                await thread.delete()
            to_delete.append(thr_id)

        for thr_id in to_delete:
            del self.check_back[thr_id]

    @discord.app_commands.command(name="tilestrat", description="Get the strat thread for a tile")
    @discord.app_commands.describe(tile_code="The tile code to look up.")
    @discord.app_commands.guild_only()
    @bot.utils.discordutils.gatekeep()
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
            raise UnknownTile(tile_code)

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

        tile_info = await asyncio.to_thread(bot.utils.bloons.fetch_tile_data, tile_code)
        if tile_info is None:
            raise UnknownTile(tile_code)

        current_event_tag = f"Season {tile_info['EventNumber']}"
        new_tag = None
        if current_event_tag not in [tag.name for tag in forum_channel.available_tags]:
            new_tag = await forum_channel.create_tag(name=current_event_tag)

        old_strats = []
        found = None
        for thread in forum_channel.threads:
            if tile_code in thread.name.upper():
                if current_event_tag in [tag.name for tag in thread.applied_tags]:
                    found = thread
                    await interaction.edit_original_response(
                        embed=self.get_raidlog_embed(thread, old_strats, loading=True)
                    )
                    await self.on_raidlog_requested(found)
                else:
                    old_strats.append(thread)

        async for thread in forum_channel.archived_threads(limit=None):
            if tile_code in thread.name.upper():
                if current_event_tag in [tag.name for tag in thread.applied_tags]:
                    found = thread
                    await interaction.edit_original_response(
                        embed=self.get_raidlog_embed(thread, old_strats, loading=True)
                    )
                    await self.on_raidlog_requested(found)
                else:
                    old_strats.append(thread)

        if not found:
            tile_data = tile_info["GameData"]
            tile_type = "Boss"
            if tile_data['subGameType'] == 9:
                tile_type = "Least Tiers"
            elif tile_data['subGameType'] == 8:
                tile_type = "Least Cash"
            elif tile_data['subGameType'] == 2:
                tile_type = "Race"

            tags = [
                new_tag if new_tag is not None else
                discord.utils.get(forum_channel.available_tags, name=current_event_tag),
            ]
            tile_type_tag = discord.utils.get(forum_channel.available_tags, name=tile_type)
            if tile_type_tag is None:
                tile_type_tag = await forum_channel.create_tag(name=tile_type)
            tags.append(tile_type_tag)
            if tile_type == "Boss":
                boss_name = "Bloonarius"
                if tile_data['bossData']['bossBloon'] == 1:
                    boss_name = "Lych"
                elif tile_data['bossData']['bossBloon'] == 2:
                    boss_name = "Vortex"
                boss_name_tag = discord.utils.get(forum_channel.available_tags, name=boss_name)
                if boss_name_tag is None:
                    boss_name_tag = await forum_channel.create_tag(name=boss_name)
                tags.append(boss_name_tag)

            map_name = bot.utils.bloons.add_spaces(tile_data["selectedMap"])
            if map_name == "Adoras Temple":
                map_name = "Adora's Temple"
            elif map_name == "Pats Pond":
                map_name = "Pat's Temple"
            elif map_name == "Tutorial":
                map_name = "Monkey Meadow"

            thread_template = "[{map}] {tile_code}"
            found = (await forum_channel.create_thread(
                name=thread_template.format(map=map_name, tile_code=tile_code),
                content=thread_init_message,
                applied_tags=tags,
                embed=bot.utils.bloons.raw_challenge_to_embed(tile_info),
            )).thread
            await self.on_raidlog_created(found)

        await interaction.edit_original_response(
            embed=self.get_raidlog_embed(found, old_strats)
        )

    @group_tilestratchannel.command(name="create", description="Create a Tile Strats forum.")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    @discord.app_commands.guild_only()
    @bot.utils.discordutils.gatekeep()
    async def cmd_create_raidlog(self, interaction: discord.Interaction) -> None:
        forum = await interaction.guild.create_forum("tile-strats")
        await self.set_raidlog(interaction, forum)

    @group_tilestratchannel.command(
        name="set",
        description="Set an existing forum as the server's Tile Strats forum"
    )
    @discord.app_commands.describe(forum="The forum to set as the server's Tile Strats forum")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    @discord.app_commands.guild_only()
    @bot.utils.discordutils.gatekeep()
    async def cmd_set_raidlog(self, interaction: discord.Interaction, forum: discord.ForumChannel) -> None:
        await self.set_raidlog(interaction, forum)

    @group_tilestratchannel.command(name="unset", description="Stop tracking the current Tile Strats forum")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    @discord.app_commands.guild_only()
    @bot.utils.discordutils.gatekeep()
    async def cmd_unset_raidlog(self, interaction: discord.Interaction) -> None:
        await bot.db.queries.del_tile_strat_forum(interaction.guild_id)
        await interaction.response.send_message(
            "Done! You server no longer has a tile strat forum!"
        )

    @discord.ext.commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.channel.id in self.check_back:
            del self.check_back[message.channel.id]
            await self.save_state()

    async def on_raidlog_requested(self, thread: discord.Thread) -> None:
        if thread.id in self.check_back:
            self.check_back[thread.id] = datetime.now() + timedelta(hours=3)
            await self.save_state()

    async def on_raidlog_created(self, thread: discord.Thread) -> None:
        self.check_back[thread.id] = datetime.now() + timedelta(hours=3)
        await self.save_state()

    @staticmethod
    def get_raidlog_embed(
            thread: discord.Thread,
            old_threads: List[discord.Thread],
            loading: bool = False
    ) -> discord.Embed:
        content = f"Click [HERE]({RaidLogCog.get_channel_url(thread)}) to go jump to the thread!"

        tile_types = {
            "Least Cash": {"image": IMG_LEAST_CASH, "emoji": LEAST_CASH},
            "Least Tiers": {"image": IMG_LEAST_TIERS, "emoji": LEAST_TIERS},
            "Race": {"image": IMG_TIME_ATTACK, "emoji": TIME_ATTACK},
        }
        bosses = {
            "Vortex": {"image": IMG_VORTEX, "emoji": VORTEX},
            "Lych": {"image": IMG_LYCH, "emoji": LYCH},
            "Bloonarius": {"image": IMG_BLOONARIUS, "emoji": BLOONARIUS},
        }

        thumb_url = ""
        for tag in thread.applied_tags:
            if tag.name in tile_types and tag.name != "Boss":
                thumb_url = tile_types[tag.name]["image"] + " "
            elif tag.name in bosses.keys():
                thumb_url = bosses[tag.name]["image"] + " "

        prev_strats = ""
        if len(old_threads) > 0:
            threads_str = []
            thread_template = "- [CT{ct_num}]({thread_url}) - {tile_type}"
            for old_thr in old_threads:
                ct_num = "???"
                tile_type = "Unknown Tile type"
                for tag in old_thr.applied_tags:
                    if "Season" in tag.name:
                        ct_num = tag.name[-2:]
                    elif tag.name in tile_types and tag.name != "Boss":
                        tile_type = f"{tile_types[tag.name]['emoji']} {tag.name}"
                    elif tag.name in bosses.keys():
                        tile_type = f"{bosses[tag.name]['emoji']} {tag.name}"

                threads_str.append(thread_template.format(
                    ct_num=ct_num,
                    thread_url=RaidLogCog.get_channel_url(old_thr),
                    tile_type=tile_type
                ))
            prev_strats = "\n".join(threads_str)

        if loading:
            content += "\n\nChecking for past threads for this tile code..."

        embed = discord.Embed(
            title=thread.name,
            description=content,
            color=discord.Color.orange()
        )
        if len(thumb_url) > 0:
            embed.set_thumbnail(url=thumb_url)
        if len(prev_strats) > 0:
            embed.add_field(name="Previous Strats", value=prev_strats)
        return embed

    @staticmethod
    def get_channel_url(channel: discord.Thread):
        return f"https://discord.com/channels/{channel.guild.id}/{channel.id}"

    @staticmethod
    async def set_raidlog(interaction: discord.Interaction, forum: discord.ForumChannel):
        await bot.db.queries.set_tile_strat_forum(interaction.guild_id, forum.id)
        await interaction.response.send_message(
            f"Done! <#{forum.id}> is now your Tile Strats forum!"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RaidLogCog(bot))
