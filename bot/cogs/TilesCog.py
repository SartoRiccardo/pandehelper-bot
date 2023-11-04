import asyncio
import json
import os
from bloonspy import btd6
import bot.utils.io
import bot.utils.bloons
import bot.utils.discordutils
from bot.utils.Cache import Cache
import discord
from discord.ext import commands
from bot.classes import ErrorHandlerCog
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
    help_descriptions = {
        None: "Information about the map and its tiles.",
        "tile": "Check a CT tile's information.",
        "spawnlock": "Check the 3 tiles next to a team's spawn.",
        "raceregs": "Check how many race regs are on the map, and where they are.",
    }

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)
        self.raceregs: Cache or None = None

    @discord.app_commands.command(name="tile",
                                  description="Check a tile's challenge data")
    @discord.app_commands.describe(tile="The 3 letter tile code, or a relic name.",
                                   hide="Hide the output.")
    @discord.app_commands.guild_only()
    async def cmd_tile(self, interaction: discord.Interaction, tile: str, hide: None or bool = True) -> None:
        tile = tile.upper()
        challenge_data = await asyncio.to_thread(self.fetch_challenge_data, tile)
        if challenge_data is None:
            tile = await asyncio.to_thread(bot.utils.bloons.relic_to_tile_code, tile)
            challenge_data = await asyncio.to_thread(self.fetch_challenge_data, tile)
        if challenge_data is None:
            await interaction.response.send_message(
                content="I don't have the challenge data for that tile!",
                ephemeral=hide,
            )
            return

        embed = bot.utils.bloons.raw_challenge_to_embed(challenge_data)
        await interaction.response.send_message(
            embed=embed,
            ephemeral=hide,
        )

    @discord.app_commands.command(name="raceregs",
                                  description="Get a list of all race regs.")
    async def cmd_raceregs(self, interaction: discord.Interaction) -> None:
        tiles = bot.utils.bloons.get_current_ct_tiles()
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
        embed = bot.utils.bloons.raw_challenge_to_embed(tiles_data[idx])
        view = SpawnlockPaginateView(tiles_data)
        await interaction.response.send_message(
            embed=embed,
            ephemeral=hide,
            view=view,
        )
        view.set_original_interaction(interaction)

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
