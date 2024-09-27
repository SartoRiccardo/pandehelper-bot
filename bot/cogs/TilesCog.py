import asyncio
import json
import os
from bloonspy import btd6
from bot.utils.bloons import (
    relic_to_tile_code,
    get_current_ct_tiles,
    raw_challenge_to_embed,
)
from bot.utils.emojis import LEAST_TIERS, LEAST_CASH
from bot.utils.Cache import Cache
import discord
from discord.ext import commands
from bot.classes import ErrorHandlerCog
from datetime import datetime, timedelta
from typing import Literal
from bot.views.SpawnlockPaginate import SpawnlockPaginateView

TeamColor = Literal["Purple", "Red", "Yellow", "Pink", "Blue", "Green"]
spawn_tile_codes = {
    "Purple": ["ABA", "AAB", "ACA"],
    "Red":    ["FBA", "FAB", "FCA"],
    "Yellow": ["EBA", "EAB", "ECA"],
    "Pink":   ["BCA", "BAB", "BBA"],
    "Blue":   ["DCA", "DAB", "DBA"],
    "Green":  ["CCA", "CAB", "CBA"],
}


class TilesCog(ErrorHandlerCog):
    grp_regs = discord.app_commands.Group(
        name="regs",
        description="Different commands for regular tiles",
    )
    help_descriptions = {
        None: "Information about the map and its tiles.",
        "tile": "Check a CT tile's information.",
        "spawnlock": "Check the 3 tiles next to a team's spawn.",
        "regs": {
            "race": "Check how many race regs are on the map, and where they are.",
            "sorted": "Sort all regular tiles by end round.",
        },
    }

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)
        self.regs = Cache(None, datetime.now())

    @discord.app_commands.command(name="tile",
                                  description="Check a tile's challenge data")
    @discord.app_commands.describe(tile="The 3 letter tile code, or a relic name.",
                                   hide="Hide the output.")
    @discord.app_commands.guild_only()
    async def cmd_tile(self, interaction: discord.Interaction, tile: str, hide: None or bool = True) -> None:
        tile = tile.upper()
        challenge_data = await asyncio.to_thread(self.fetch_challenge_data, tile)
        if challenge_data is None:
            tile = await asyncio.to_thread(relic_to_tile_code, tile)
            challenge_data = await asyncio.to_thread(self.fetch_challenge_data, tile)
        if challenge_data is None:
            await interaction.response.send_message(
                content="I don't have the challenge data for that tile!",
                ephemeral=hide,
            )
            return

        embed = raw_challenge_to_embed(challenge_data)
        await interaction.response.send_message(
            embed=embed,
            ephemeral=hide,
        )

    @discord.app_commands.command(name="raceregs",
                                  description="Get a list of all race regs.")
    async def cmd_raceregs(self, interaction: discord.Interaction) -> None:
        tiles = get_current_ct_tiles()
        race_regs = [
            tile.id for tile in tiles
            if tile.tile_type == btd6.CtTileType.REGULAR and tile.game_type == btd6.GameType.RACE
        ]

        await interaction.response.send_message(
            content=f"Note: You should use /regs race, /raceregs is deprecated.\n"
                    f"**Race Regs ({len(race_regs)}):** `{'`, `'.join(sorted(race_regs))}`"
        )

    @grp_regs.command(name="race",
                      description="Get a list of all race regs.")
    async def cmd_regs_race(self, interaction: discord.Interaction) -> None:
        tiles = get_current_ct_tiles()
        race_regs = [
            tile.id for tile in tiles
            if tile.tile_type == btd6.CtTileType.REGULAR and tile.game_type == btd6.GameType.RACE
        ]

        await interaction.response.send_message(
            content=f"**Race Regs ({len(race_regs)}):** `{'`, `'.join(sorted(race_regs))}`"
        )

    @discord.app_commands.command(name="spawnlock",
                                  description="See a team's spawnlock tiles.")
    @discord.app_commands.describe(team="The team you wanna see the spawn tiles for.",
                                   hide="Hide the output.")
    @discord.app_commands.guild_only()
    async def cmd_spawnlock(self, interaction: discord.Interaction, team: TeamColor, hide: bool = True) -> None:
        tiles = spawn_tile_codes[team]

        tiles_data = []
        for tile in tiles:
            tiles_data.append(asyncio.to_thread(self.fetch_challenge_data, tile))
        tiles_data = await asyncio.gather(*tiles_data)

        idx = 0
        embed = raw_challenge_to_embed(tiles_data[idx])
        view = SpawnlockPaginateView(tiles_data)
        await interaction.response.send_message(
            embed=embed,
            ephemeral=hide,
            view=view,
        )
        view.set_original_interaction(interaction)

    @grp_regs.command(name="sorted",
                      description="Get a sorted list of all non-race regs.")
    @discord.app_commands.describe(hide="Hide the output.")
    async def cmd_regs_sorted(
            self,
            interaction: discord.Interaction,
            hide: bool = True,
    ) -> None:
        """
        Since this command uses actual tile data NOT pulled from the API
        I have to check every single tile saved locally and cannot use the API
        for this since there might be mismatch. Please just give me API access
        bro please I am on my knees begging
        """
        await interaction.response.defer(ephemeral=hide)

        if not self.regs.valid:
            tiles = get_current_ct_tiles()
            regs = [
                self.fetch_challenge_data(tile.id) for tile in tiles
                # if tile.tile_type in [btd6.CtTileType.REGULAR, btd6.CtTileType.TEAM_START]
                #    and tile.game_type != btd6.GameType.RACE
            ]
            # Comment this later
            regs = [tl for tl in regs if tl is not None and tl["TileType"] not in ["Banner", "Relic"] and tl["GameData"]["subGameType"] in [8, 9]]
            self.regs = Cache(regs, datetime.now() + timedelta(hours=12))

        regs_by_round: dict[int, list[tuple[str, btd6.GameType]]] = {}
        for reg in self.regs.value:
            end_round = reg["GameData"]['dcModel']['startRules']['endRound']
            if end_round not in regs_by_round:
                regs_by_round[end_round] = []
            if reg["GameData"]["subGameType"] == 9:
                regs_by_round[end_round].append((reg["Code"], btd6.GameType.LEAST_TIERS))
            elif reg["GameData"]["subGameType"] == 8:
                regs_by_round[end_round].append((reg["Code"], btd6.GameType.LEAST_CASH))

        message = ""
        for key in sorted(regs_by_round.keys()):
            regs_by_type = {btd6.GameType.LEAST_CASH: [], btd6.GameType.LEAST_TIERS: []}
            for code, ttype in regs_by_round[key]:
                regs_by_type[ttype].append(code)
            total_tiles = len(regs_by_type[btd6.GameType.LEAST_CASH])+len(regs_by_type[btd6.GameType.LEAST_TIERS])
            message += f"\n**Round {key}** ({total_tiles}):"
            if len(regs_by_type[btd6.GameType.LEAST_CASH]):
                message += f"\n      {LEAST_CASH} `{'`, `'.join(regs_by_type[btd6.GameType.LEAST_CASH])}`"
            if len(regs_by_type[btd6.GameType.LEAST_TIERS]):
                message += f"\n      {LEAST_TIERS} `{'`, `'.join(regs_by_type[btd6.GameType.LEAST_TIERS])}`"

        await interaction.edit_original_response(
            content=f"## Non-Race Regs ({len(self.regs.value)}):" + message
        )

    @staticmethod
    def fetch_challenge_data(tile: str):
        path = f"bot/files/json/tiles/{tile}.json"
        if not os.path.exists(path):
            return None
        fin = open(path)
        data = json.loads(fin.read())
        fin.close()
        return data


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TilesCog(bot))
