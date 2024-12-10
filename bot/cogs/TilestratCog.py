import math
import discord
from datetime import datetime, timedelta
from discord.ext import commands, tasks
import asyncio
from typing import Any
import bot.db.queries.tilestrat
import bot.utils.discordutils
from bot.exceptions import UnknownTile
from .CogBase import CogBase
from bot.views import EmbedPaginateView
from bot.utils.bloons import (
    raw_challenge_to_embed,
    get_current_ct_number,
)
from bot.utils.misc import add_spaces
from bot.utils.bloonsdata import (
    fetch_tile_data,
    relic_to_tile_code,
    fetch_all_tiles,
)
from bot.utils.emojis import LEAST_TIERS, LEAST_CASH, BLOONARIUS, VORTEX, LYCH, TIME_ATTACK, BLANK, DREADBLOON, \
    PHAYZE
from bot.utils.images import IMG_LEAST_CASH, IMG_LEAST_TIERS, IMG_BLOONARIUS, IMG_VORTEX, IMG_LYCH, IMG_TIME_ATTACK, \
    IMG_DREADBLOON, IMG_PHAYZE
import re
from bot.exceptions import TilestratForumNotFound, NotACommunity
from config import BOT_COLOR


thread_init_message = f"""
### {BLANK}
### {BLANK}
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
TOTAL_TILES = 163


class TilestratCog(CogBase):
    help_descriptions = {
        None: "Manages a forum to post tile strategies",
        "tilestrat-forum": {
            "create": "Creates a new Tile Strat forum. You can rename it & set the perms to whatever you want",
            "set": "Sets an existing channel as the Tile Strat forum. Using [[create]] is recommended though.",
            "unset": "Makes the bot stop tracking the current Tile Strat forum.",
            "stats": "Show an overview of how many strategies have been logged so far."
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
        self.check_back: dict[int, datetime] = {}

    async def cog_load(self) -> None:
        await super().cog_load()
        self.clean_raidlog.start()

    async def cog_unload(self) -> None:
        await super().cog_unload()
        self.clean_raidlog.cancel()

    async def parse_state(self, saved_at: datetime, state: dict[str, Any]) -> None:
        if "check_back" in state:
            self.check_back = {}
            for key in state["check_back"]:
                self.check_back[int(key)] = datetime.fromtimestamp(state["check_back"][key])

    async def serialize_state(self) -> dict[str, Any]:
        data = {
            "check_back": {},
        }
        for key in self.check_back.keys():
            data["check_back"][str(key)] = self.check_back[key].timestamp()
        return data

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
                try:
                    await thread.delete()
                except discord.Forbidden:
                    pass
            to_delete.append(thr_id)

        for thr_id in to_delete:
            del self.check_back[thr_id]
        await self._save_state()

    @discord.app_commands.command(name="raidlog", description="Alias for /tilestrat")
    @discord.app_commands.describe(tile_code="The tile code to look up.")
    @discord.app_commands.guild_only()
    async def cmd_search_raidlog(self, interaction: discord.Interaction, tile_code: str) -> None:
        await self.search_tile(interaction, tile_code)

    @discord.app_commands.command(name="tilestrat", description="Get the strat thread for a tile")
    @discord.app_commands.describe(tile_code="The tile code to look up.")
    @discord.app_commands.guild_only()
    async def cmd_search(self, interaction: discord.Interaction, tile_code: str) -> None:
        await self.search_tile(interaction, tile_code)

    async def search_tile(self, interaction: discord.Interaction, tile_code: str) -> None:
        forum_id = await bot.db.queries.tilestrat.get_tile_strat_forum(interaction.guild_id)
        if forum_id is None:
            raise TilestratForumNotFound()

        tile_code = tile_code.strip().upper()
        tile_re = r"(?:M|[A-G])(?:R|[A-G])(?:X|[A-H])"
        if len(tile_code) != 3 or re.match(tile_re, tile_code) is None:
            actual_tile_code = await relic_to_tile_code(tile_code)
            if actual_tile_code is None:
                raise UnknownTile(tile_code)
            tile_code = actual_tile_code

        await interaction.response.defer()
        forum_channel = await self.fetch_forum(interaction, forum_id)
        if forum_channel is None:
            await bot.db.queries.tilestrat.del_tile_strat_forum(interaction.guild_id)
            raise TilestratForumNotFound()

        tile_info = await fetch_tile_data(tile_code)
        if tile_info is None:
            raise UnknownTile(tile_code)

        strats = await bot.db.queries.tilestrat.get_tilestrats(tile_code, forum_id)
        current = discord.utils.get(strats, event_num=tile_info["EventNumber"])
        is_just_created = current is None
        if is_just_created:
            thread = await self.create_tilestrat_thread(tile_info, forum_channel)
            strats = await bot.db.queries.tilestrat.get_tilestrats(tile_code, forum_id)
        else:
            thread = interaction.guild.get_thread(current.thread_id)
            if thread is None:
                thread = await interaction.guild.fetch_channel(current.thread_id)

        embeds = self.get_raidlog_embeds(thread, strats, is_just_created, tile_info["EventNumber"])
        await interaction.edit_original_response(
            embed=embeds[0],
            view=None if len(embeds) == 1 else EmbedPaginateView(embeds, original_interaction=interaction)
        )

    async def create_tilestrat_thread(self, tile_info: dict, forum_channel: discord.ForumChannel) -> discord.Thread:
        tile_data = tile_info["GameData"]
        tile_type = "Boss"
        if tile_data['subGameType'] == 9:
            tile_type = "Least Tiers"
        elif tile_data['subGameType'] == 8:
            tile_type = "Least Cash"
        elif tile_data['subGameType'] == 2:
            tile_type = "Race"

        tags = []
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
            elif tile_data['bossData']['bossBloon'] == 3:
                boss_name = "Dreadbloon"
            elif tile_data['bossData']['bossBloon'] == 4:
                boss_name = "Phayze"
            elif tile_data['bossData']['bossBloon'] == 5:
                boss_name = "Blastapopoulos"
            boss_name_tag = discord.utils.get(forum_channel.available_tags, name=boss_name)
            if boss_name_tag is None:
                boss_name_tag = await forum_channel.create_tag(name=boss_name)
            tags.append(boss_name_tag)

        map_name = add_spaces(tile_data["selectedMap"])
        if map_name == "Adoras Temple":
            map_name = "Adora's Temple"
        elif map_name == "Pats Pond":
            map_name = "Pat's Temple"
        elif map_name == "Tutorial":
            map_name = "Monkey Meadow"

        thread_template = "[Event {event_num}] [{map}] {tile_code}"
        thread = (await forum_channel.create_thread(
            name=thread_template.format(event_num=tile_info["EventNumber"], map=map_name, tile_code=tile_info["Code"]),
            content=thread_init_message,
            applied_tags=tags,
            embed=await raw_challenge_to_embed(tile_info),
        )).thread
        await self.on_raidlog_created(thread, tile_info, forum_channel.id)
        return thread

    @group_tilestratchannel.command(name="stats", description="Get the raid log stats of the current season!")
    @discord.app_commands.describe(season="The CT season to check stats for.")
    @discord.app_commands.guild_only()
    async def cmd_stats(self, interaction: discord.Interaction, season: None or int = None) -> None:
        forum_id = await bot.db.queries.tilestrat.get_tile_strat_forum(interaction.guild_id)
        if forum_id is None:
            raise TilestratForumNotFound()

        await interaction.response.defer()
        forum_channel = await self.fetch_forum(interaction, forum_id)
        if forum_channel is None:
            await bot.db.queries.tilestrat.del_tile_strat_forum(interaction.guild_id)
            raise TilestratForumNotFound()

        if season is None:
            season = get_current_ct_number()

        logged_count = {
            "Banner": {"race": 0, "lc": 0, "lt": 0, "boss": 0},
            "Relic": {"race": 0, "lc": 0, "lt": 0, "boss": 0},
            "Regular": {"race": 0, "lc": 0, "lt": 0},
        }
        logged_total = {
            "Banner": {"race": 0, "lc": 0, "lt": 0, "boss": 0},
            "Relic": {"race": 0, "lc": 0, "lt": 0, "boss": 0},
            "Regular": {"race": 0, "lc": 0, "lt": 0},
        }

        tiles = await fetch_all_tiles()
        logged_tiles = await bot.db.queries.tilestrat.get_tilestrats_by_season(season, forum_id)
        logged_tiles = [lt.tile_code for lt in logged_tiles]

        for tile in tiles:
            tile_type = tile["TileType"]
            tile_chal = "boss"
            if tile["GameData"]['subGameType'] == 9:
                tile_chal = "lt"
            elif tile["GameData"]['subGameType'] == 8:
                tile_chal = "lc"
            elif tile["GameData"]['subGameType'] == 2:
                tile_chal = "race"
            if tile_type in logged_count:
                logged_total[tile_type][tile_chal] += 1
                if tile["Code"] in logged_tiles:
                    logged_count[tile_type][tile_chal] += 1

        embed = discord.Embed(
            title=f"{interaction.guild.name} Tile Strats (Season #{season})",
            description=f"__**STRATS LOGGED: {len(logged_tiles)/len(tiles)*100:.1f}%**__",
            color=BOT_COLOR,
        )
        embed.add_field(name="Banners",
                        value=self.get_stat_field(logged_count["Banner"], logged_total["Banner"]),
                        inline=False)
        embed.add_field(name="Relics",
                        value=self.get_stat_field(logged_count["Relic"], logged_total["Relic"]),
                        inline=False)
        embed.add_field(name="Regulars",
                        value=self.get_stat_field(logged_count["Regular"], logged_total["Regular"]),
                        inline=False)
        await interaction.edit_original_response(
            content="",
            embed=embed,
        )

    @staticmethod
    def get_stat_field(logged, total) -> str:
        sum_logged = 0
        sum_total = 0
        for key in logged:
            sum_logged += logged[key]
            sum_total += total[key]

        tile_completions = []
        if total['lt'] > 0:
            tile_completions.append(f"{LEAST_TIERS} {logged['lt']/total['lt']*100:.1f}%")
        if total['lc'] > 0:
            tile_completions.append(f"{LEAST_CASH} {logged['lc']/total['lc']*100:.1f}%")
        if total['race'] > 0:
            tile_completions.append(f"{TIME_ATTACK} {logged['race']/total['race']*100:.1f}%")
        if "boss" in logged and total["boss"] > 0:
            tile_completions.append(f"{BLOONARIUS} {logged['boss']/total['boss']*100:.1f}%")

        amount_logged = sum_logged/sum_total*100
        emote = "💯" if amount_logged == 100 else "➡️"
        content = f"{emote} Overall: {amount_logged:.1f}%\n" + " — ".join(tile_completions)
        return content

    @staticmethod
    async def fetch_forum(interaction: discord.Interaction, forum_id: int) -> discord.ForumChannel or None:
        try:
            forum_channel = interaction.guild.get_channel(forum_id)
            if forum_channel is None:
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
        return forum_channel

    @group_tilestratchannel.command(name="create", description="Create a Tile Strats forum.")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    @discord.app_commands.guild_only()
    async def cmd_create_raidlog(self, interaction: discord.Interaction) -> None:
        if "COMMUNITY" not in interaction.guild.features:
            raise NotACommunity()
        forum = await interaction.guild.create_forum("tile-strats")
        await self.set_raidlog(interaction, forum)

    @group_tilestratchannel.command(
        name="set",
        description="Set an existing forum as the server's Tile Strats forum"
    )
    @discord.app_commands.describe(forum="The forum to set as the server's Tile Strats forum")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    @discord.app_commands.guild_only()
    async def cmd_set_raidlog(self, interaction: discord.Interaction, forum: discord.ForumChannel) -> None:
        await self.set_raidlog(interaction, forum)

    @group_tilestratchannel.command(name="unset", description="Stop tracking the current Tile Strats forum")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    @discord.app_commands.guild_only()
    async def cmd_unset_raidlog(self, interaction: discord.Interaction) -> None:
        await bot.db.queries.tilestrat.del_tile_strat_forum(interaction.guild_id)
        await interaction.response.send_message(
            "Done! You server no longer has a tile strat forum!"
        )

    @discord.ext.commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.channel.id in self.check_back:
            del self.check_back[message.channel.id]
            await self._save_state()

    @discord.ext.commands.Cog.listener()
    async def on_raw_thread_delete(self, payload: discord.RawThreadDeleteEvent) -> None:
        await self.on_raidlog_deleted(payload.thread_id)

    @discord.ext.commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        guild_forum = await bot.db.queries.tilestrat.get_tile_strat_forum(channel.guild.id)
        if guild_forum == channel.id:
            await bot.db.queries.tilestrat.del_tile_strat_forum(channel.guild.id, soft_delete=False)

    async def on_raidlog_requested(self, thread: discord.Thread) -> None:
        if thread.id in self.check_back:
            self.check_back[thread.id] = datetime.now() + timedelta(hours=3)
            await self._save_state()

    async def on_raidlog_created(self, thread: discord.Thread, tile_info: dict, forum_id: int) -> None:
        self.check_back[thread.id] = datetime.now() + timedelta(hours=3)
        await self._save_state()
        await bot.db.queries.tilestrat.create_tilestrat(
            forum_id, thread.id, tile_info["Code"], tile_info["EventNumber"], tile_info["GameData"]["subGameType"],
            tile_info["GameData"]["bossData"]["bossBloon"] if "bossData" in tile_info["GameData"] else None
        )

    async def on_raidlog_deleted(self, thread_id: int) -> None:
        await bot.db.queries.tilestrat.del_tilestrat(thread_id)

    @staticmethod
    def get_raidlog_embeds(
            thread: discord.Thread,
            strats: list[bot.db.model.Tilestrat.Tilestrat],
            is_just_created: bool,
            event_num: int
    ) -> list[discord.Embed]:
        int_to_tile_type = {8: "Least Cash", 2: "Race", 9: "Least Tiers"}
        int_to_boss = {0: "Bloonarius", 1: "Lych", 2: "Vortex", 3: "Dreadbloon", 4: "Phayze", 5: "Blastapopoulos"}
        tile_types = {
            8: {"image": IMG_LEAST_CASH, "emoji": LEAST_CASH},
            9: {"image": IMG_LEAST_TIERS, "emoji": LEAST_TIERS},
            2: {"image": IMG_TIME_ATTACK, "emoji": TIME_ATTACK},
        }
        bosses = {
            0: {"image": IMG_BLOONARIUS, "emoji": BLOONARIUS},
            1: {"image": IMG_LYCH, "emoji": LYCH},
            2: {"image": IMG_VORTEX, "emoji": VORTEX},
            3: {"image": IMG_DREADBLOON, "emoji": DREADBLOON},
            4: {"image": IMG_PHAYZE, "emoji": PHAYZE},
        }
        old_thread_template = "- [CT{ct_num}]({thread_url}) - {tile_type_emoji} {tile_type}"

        thumb_url = ""
        old_threads_str = []
        for st in strats:
            if st.event_num == event_num:
                if st.boss is not None:
                    thumb_url = bosses[st.boss]["image"]
                else:
                    thumb_url = tile_types[st.challenge_type]["image"]
                continue

            if st.boss is not None:
                tile_type_emoji = bosses[st.boss]["emoji"]
                tile_type = int_to_boss[st.boss]
            else:
                tile_type_emoji = tile_types[st.challenge_type]["emoji"]
                tile_type = int_to_tile_type[st.challenge_type]

            old_threads_str.append(old_thread_template.format(
                ct_num=st.event_num,
                thread_url=f"https://discord.com/channels/{thread.guild.id}/{st.thread_id}",
                tile_type_emoji=tile_type_emoji,
                tile_type=tile_type
            ))

        embed_template = discord.Embed(
            title=thread.name,
            color=BOT_COLOR,
            url=TilestratCog.get_channel_url(thread),
        )
        if len(thumb_url) > 0:
            embed_template.set_thumbnail(url=thumb_url)
        if is_just_created:
            embed_template.set_footer(text="⚠️ There are currently no strategies logged in the thread.")

        strats_per_page = 7
        pages = math.ceil(len(old_threads_str)/strats_per_page)
        embeds = []
        embed = embed_template.copy()
        for i in range(pages):
            embed.add_field(
                name="Previous Strats",
                value="\n".join(old_threads_str[i*strats_per_page:(i+1)*strats_per_page])
            )
            if pages > 1:
                footer_parts = [f"Page {i+1}/{pages}"]
                if embed.footer.text:
                    footer_parts.append(embed.footer.text)
                embed.set_footer(text=" • ".join(footer_parts))

            embeds.append(embed)
            embed = embed_template.copy()
        if len(old_threads_str) == 0:
            embeds.append(embed)

        return embeds

    @staticmethod
    def get_channel_url(channel: discord.Thread):
        return f"https://discord.com/channels/{channel.guild.id}/{channel.id}"

    @staticmethod
    async def set_raidlog(interaction: discord.Interaction, forum: discord.ForumChannel):
        await bot.db.queries.tilestrat.set_tile_strat_forum(interaction.guild_id, forum.id)
        await interaction.response.send_message(
            f"Done! <#{forum.id}> is now your Tile Strats forum!"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TilestratCog(bot))
