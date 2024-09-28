from datetime import datetime
import os
import asyncio
import aiofiles
import aiohttp_client_cache
from bloonspy import AsyncClient, btd6
from config import DATA_PATH
import json

bpy_client: AsyncClient


async def init_bloonspy_client() -> None:
    cache = aiohttp_client_cache.SQLiteBackend(
        cache_name=os.path.join(DATA_PATH, ".cache", "aiohttp-requests.db"),
        expire_after=60*5,
        urls_expire_after={
            "data.ninjakiwi.com": 60*30,
        },
        include_headers=True,
    )

    async def init():
        global bpy_client
        async with aiohttp_client_cache.CachedSession(cache=cache) as session:
            bpy_client = AsyncClient(session)
            while True:
                await session.delete_expired_responses()
                await asyncio.sleep(3600 * 24)
    asyncio.create_task(init())


async def get_current_ct_event() -> btd6.ContestedTerritoryEvent | None:
    now = datetime.now()
    events = await bpy_client.contested_territories()
    for ct in events:
        if ct.start <= now:
            return ct
    return None


async def get_current_ct_tiles() -> list[btd6.CtTile]:
    ct = await get_current_ct_event()
    if ct is None:
        return []
    return await ct.tiles()


async def is_tile_code_valid(tile: str) -> bool:
    return tile in [t.id for t in await get_current_ct_tiles()]


async def fetch_tile_data(tile: str) -> dict | None:
    path = f"bot/files/json/tiles/{tile}.json"
    if not os.path.exists(path):
        return None
    async with aiofiles.open(path) as fin:
        return json.loads(await fin.read())


async def fetch_all_tiles() -> list[dict]:
    path = f"bot/files/json/tiles"
    tiles = []
    for file in os.listdir(path):
        data = await fetch_tile_data(file[:3])
        if data is not None:
            tiles.append(data)
    return tiles


async def relic_to_tile_code(relic: str) -> str or None:
    relic = relic.lower().replace(" ", "_")
    relics = {
        'AirAndSea': ['aas', 'airandsea', 'air_and_sea', "ans"],
        'Abilitized': ['abilitized'],
        'AlchemistTouch': ['alchtouch', 'alch', 'alchemisttouch', 'alchemist_touch', 'alch_touch'],
        'MonkeyBoost': ['boost', 'mboost', 'mb', 'monkeyboost', 'monkey_boost'],
        'MarchingBoots': ['boots', 'mboots', 'marchingboots', 'marching_boots'],
        'BoxOfMonkey': ['box', 'boxofmonkey', 'bom', 'box_of_monkey'],
        'BoxOfChocolates': ['chocobox', 'chocbox', "boxofchocolates"],
        'CamoTrap': ['ctrap', 'camotrap', 'camo_trap'],
        'DurableShots': ['dshots', 'durableshots', 'durable_shots'],
        'ExtraEmpowered': ['eemp', 'extraemp', 'extra_empowered'],
        'FlintTips': ['flinttips', 'flint_tips', "flint", "ft"],
        'Camoflogged': ['flogged', 'cflogged', 'camo_flogged'],
        'Fortifried': ['fried', 'ffried', 'fortifried'],
        'GoingTheDistance': ['goingthedistance', 'gtd'],
        'GlueTrap': ['gtrap', 'glue', 'gluetrap', 'glue_trap'],
        'HardBaked': ['hardbaked', 'hb'],
        'HeroBoost': ['hboost', 'heroboost', 'hero_boost'],
        'ManaBulwark': ['manabulwark', "mana"],
        'MoabClash': ['mc', 'clash', 'moabclash', 'moab_clash'],
        'MoabMine': ['mine', 'moabmine'],
        'Regeneration': ['regen', 'regeneration'],
        'Restoration': ['resto', 'restoration'],
        'RoundingUp': ["rup", 'roundingup', 'rounding_up'],
        'RoyalTreatment': ['royal', 'rtreatment', 'royaltreatment', 'royal_treatment'],
        'Sharpsplosion': ['sharp', 'sharpsplosion'],
        'SuperMonkeyStorm': ['sms', 'supermonkeystorm', 'super_monkey_storm'],
        'RoadSpikes': ['spikes', 'rspikes', 'roadspikes', 'road_spikes'],
        'StartingStash': ['stash', 'startingstash', 'starting_stash'],
        'Thrive': ['thrive'],
        'ElDorado': ['eldorado', 'dorado', 'el_dorado'],
        'DeepHeat': ['dheat', 'deepheat', 'deep_heat'],
        "Techbot": ["techbot"],
        "Heartless": ["heartless"],
        "BrokenHeart": ["brokenheart", "broken_heart"],
        "BiggerBloonSabotage": ["bbs", "bigger_bloon_sabotage", "biggerbloonsabotage"],
    }
    for key in relics:
        if relic in relics[key]:
            tiles = await fetch_all_tiles()
            for tile in tiles:
                if tile["RelicType"] == key:
                    return tile["Code"]
    return None
