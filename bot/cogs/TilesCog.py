import asyncio
import math
from bloonspy import btd6
from bot.utils.bloons import raw_challenge_to_embed
from bot.utils.bloonsdata import (
    get_current_ct_tiles,
    get_current_ct_event,
    relic_to_tile_code,
    fetch_tile_data,
)
from bot.types import TeamColor
from bot.views import VPaginateList
from bot.utils.emojis import LEAST_TIERS, LEAST_CASH
from bot.utils.Cache import Cache
import discord
from discord.ext import commands
from .CogBase import CogBase
from datetime import datetime, timedelta
from typing import Literal
from bot.views.SpawnlockPaginate import SpawnlockPaginateView
from bot.utils.ctmap import make_map

TeamColor = Literal["Purple", "Red", "Yellow", "Pink", "Blue", "Green"]
spawn_tile_codes = {
    "Purple": ["ABA", "AAB", "ACA"],
    "Red":    ["FBA", "FAB", "FCA"],
    "Yellow": ["EBA", "EAB", "ECA"],
    "Pink":   ["BCA", "BAB", "BBA"],
    "Blue":   ["DCA", "DAB", "DBA"],
    "Green":  ["CCA", "CAB", "CBA"],
}


class TilesCog(CogBase):
    grp_regs = discord.app_commands.Group(
        name="regs",
        description="Different commands for regular tiles",
    )
    help_descriptions = {
        None: "Information about the map and its tiles.",
        "ctmap": "Renders the CT map.",
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
    async def cmd_tile(self, interaction: discord.Interaction, tile: str, hide: None or bool = True) -> None:
        tile = tile.upper()
        challenge_data = await fetch_tile_data(tile)
        if challenge_data is None:
            tile = await relic_to_tile_code(tile)
            challenge_data = await fetch_tile_data(tile)
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

    @discord.app_commands.command(
        name="ctmap",
        description="Render the current event's map",
    )
    @discord.app_commands.describe(
        hide="Hide the output",
        team_pov="The point of view of the team you wanna see",
    )
    async def cmd_ctmap(
            self,
            interaction: discord.Interaction,
            team_pov: TeamColor = "Purple",
            hide: bool = False,
    ) -> None:
        await interaction.response.defer(ephemeral=hide)

        ct = await get_current_ct_event()
        image_path = await asyncio.to_thread(
            make_map,
            await ct.tiles(),
            team_pov=["Purple", "Pink", "Green", "Blue", "Yellow", "Red"].index(team_pov),
        )

        await interaction.edit_original_response(
            attachments=[discord.File(image_path, filename=f"{ct.id}-map.png")]
        )

    @discord.app_commands.command(name="raceregs",
                                  description="Get a list of all race regs.")
    async def cmd_raceregs(self, interaction: discord.Interaction) -> None:
        tiles = await get_current_ct_tiles()
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
        tiles = await get_current_ct_tiles()
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

        tiles_data = await asyncio.gather(*[
            fetch_tile_data(tile)
            for tile in tiles
        ])

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
        rows_per_msg = 6

        await interaction.response.defer(ephemeral=hide)

        if not self.regs.valid:
            tiles = await get_current_ct_tiles()
            regs = [
                await fetch_tile_data(tile.id) for tile in tiles
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

        rounds = []
        for key in sorted(regs_by_round.keys()):
            regs_by_type = {btd6.GameType.LEAST_CASH: [], btd6.GameType.LEAST_TIERS: []}
            for code, ttype in regs_by_round[key]:
                regs_by_type[ttype].append(code)
            total_tiles = len(regs_by_type[btd6.GameType.LEAST_CASH])+len(regs_by_type[btd6.GameType.LEAST_TIERS])
            message = f"\n**Round {key}** ({total_tiles})"
            if len(regs_by_type[btd6.GameType.LEAST_CASH]):
                message += f"\n      {LEAST_CASH} `{'`, `'.join(regs_by_type[btd6.GameType.LEAST_CASH])}`"
            if len(regs_by_type[btd6.GameType.LEAST_TIERS]):
                message += f"\n      {LEAST_TIERS} `{'`, `'.join(regs_by_type[btd6.GameType.LEAST_TIERS])}`"
            rounds.append(message.strip())

        def build_msg(rows) -> str:
            return f"## Non-Race Regs ({len(self.regs.value)})\n" + \
                "\n".join(rows)

        vpages = VPaginateList(
            interaction,
            math.ceil(len(rounds)/rows_per_msg),
            1,
            {1: rounds},
            rows_per_msg,
            len(rounds),
            None,
            build_msg,
            list_key=None,
        )
        await interaction.edit_original_response(
            content=build_msg(vpages.get_needed_rows(1, vpages.pages_saved)),
            view=vpages,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TilesCog(bot))
