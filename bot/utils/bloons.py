import datetime
import discord
import re
import os
import json
from typing import Tuple
from bot.utils.emojis import NO_SELLING, NO_KNOWLEDGE, CERAM_HEALTH, MOAB_HEALTH, MOAB_SPEED, BLOON_SPEED, \
    BLOONARIUS, VORTEX, LYCH, LEAST_CASH, LEAST_TIERS, TIME_ATTACK, MAX_TOWERS, REGROW_RATE, CASH
from bot.utils.images import BANNER_IMG, REGULAR_IMG, RELICS_IMG, RELIC_IMG, MAPS, IMG_BLOONARIUS, \
    IMG_LYCH, IMG_VORTEX, IMG_LEAST_CASH, IMG_LEAST_TIERS, IMG_TIME_ATTACK


EVENT_EPOCHS = [
    (0, datetime.datetime.fromtimestamp(0)),
    (1, datetime.datetime.fromtimestamp(1660075200)),
    (26, datetime.datetime.fromtimestamp(1690927200)),
]

EVENT_DURATION = 7
DEFAULT_STARTING_LIVES = {
    "Easy": 200,
    "Medium": 150,
    "Hard": 100,
    "Impoppable": 1,
}
TOWER_CATEGORY = {
    "DartMonkey": "Primary",
    "BoomerangMonkey": "Primary",
    "BombShooter": "Primary",
    "TackShooter": "Primary",
    "IceMonkey": "Primary",
    "GlueGunner": "Primary",
    "SniperMonkey": "Military",
    "MonkeySub": "Military",
    "MonkeyBuccaneer": "Military",
    "MonkeyAce": "Military",
    "HeliPilot": "Military",
    "MortarMonkey": "Military",
    "DartlingGunner": "Military",
    "WizardMonkey": "Magic",
    "SuperMonkey": "Magic",
    "NinjaMonkey": "Magic",
    "Alchemist": "Magic",
    "Druid": "Magic",
    "BananaFarm": "Support",
    "SpikeFactory": "Support",
    "MonkeyVillage": "Support",
    "EngineerMonkey": "Support",
    "BeastHandler": "Support",
}
CODE_TO_COORDS = {
    "MRX": (0, 0, 0),
}


def get_ct_number_during(time: datetime.datetime, breakpoint_on_event_start: bool = True) -> int:
    """Gets the CT number during a certain datetime.

    :param time: the time to get the number for.
    :param breakpoint_on_event_start: If `True`, a new CT "starts" only when the next event starts.
    Otherwise, it starts as soon as the current event ends. In other words, if `True`, the break period
    will count as part of the last CT, if `False` it will count as the next.
    :return:
    """
    i = 0
    while i+1 < len(EVENT_EPOCHS) and time >= EVENT_EPOCHS[i+1][1]:
        i += 1
    event_start, epoch_start = EVENT_EPOCHS[i]
    next_epoch_event_start = 1000
    if i+1 < len(EVENT_EPOCHS):
        next_epoch_event_start = EVENT_EPOCHS[i+1][0]

    if not breakpoint_on_event_start:
        epoch_start -= datetime.timedelta(days=EVENT_DURATION)
    return min(
        int((time-epoch_start).days / (EVENT_DURATION*2)) + event_start,
        next_epoch_event_start-1
    )


def get_current_ct_number(breakpoint_on_event_start: bool = True) -> int:
    return get_ct_number_during(datetime.datetime.now(), breakpoint_on_event_start)


def get_ct_period_during(time: datetime.datetime = None,
                         event: int = None) -> Tuple[datetime.datetime, datetime.datetime]:
    if time is None and event is None:
        return datetime.datetime.fromtimestamp(0), datetime.datetime.fromtimestamp(0)

    if event:
        current = event
    elif time:
        current = get_ct_number_during(time)

    i = 0
    while i+1 < len(EVENT_EPOCHS) and current >= EVENT_EPOCHS[i+1][0]:
        i += 1
    event_start, epoch_start = EVENT_EPOCHS[i]

    start = epoch_start + datetime.timedelta(days=EVENT_DURATION*(current-event_start)*2)
    return start, start+datetime.timedelta(days=EVENT_DURATION)


def get_current_ct_period() -> Tuple[datetime.datetime, datetime.datetime]:
    return get_ct_period_during(time=datetime.datetime.now())


def raw_challenge_to_embed(challenge) -> discord.Embed or None:
    event_number = challenge["EventNumber"]
    # event_number = get_current_ct_number()

    tile = challenge["Code"]
    tile_type_url = REGULAR_IMG
    # if challenge['TileType'] == "TeamFirstCapture":
    #     return None
    if challenge['TileType'] == "Banner":
        tile_type_url = BANNER_IMG
    elif challenge['TileType'] == "Relic":
        if challenge['RelicType'] in RELICS_IMG:
            tile_type_url = RELICS_IMG[challenge['RelicType']]
        else:
            tile_type_url = RELIC_IMG

    challenge = challenge["GameData"]

    if challenge["selectedMap"] == "AdorasTemple":
        challenge["selectedMap"] = "Adora'sTemple"
    elif challenge["selectedMap"] == "PatsPond":
        challenge["selectedMap"] = "Pat'sTemple"
    elif challenge["selectedMap"] == "Tutorial":
        challenge["selectedMap"] = "MonkeyMeadow"

    boss = None
    challenge_thmb = ""
    if "bossData" in challenge:
        boss = "Bloonarius"
        challenge_thmb = IMG_BLOONARIUS
        if challenge['bossData']['bossBloon'] == 1:
            boss = "Lych"
            challenge_thmb = IMG_LYCH
        elif challenge['bossData']['bossBloon'] == 2:
            boss = "Vortex"
            challenge_thmb = IMG_VORTEX

    mode = challenge['selectedMode']
    if boss:
        mode = f"{boss} {challenge['bossData']['TierCount']} Tier{'s' if challenge['bossData']['TierCount'] > 1 else ''}"

    if challenge['subGameType'] == 9:
        challenge_thmb = IMG_LEAST_TIERS
    elif challenge['subGameType'] == 8:
        challenge_thmb = IMG_LEAST_CASH
    elif challenge['subGameType'] == 2:
        challenge_thmb = IMG_TIME_ATTACK

    title = f"{add_spaces(challenge['selectedMap'])} — {challenge['selectedDifficulty']} {mode}"

    starting_lives = challenge['dcModel']['startRules']['lives']
    if starting_lives == -1:
        starting_lives = DEFAULT_STARTING_LIVES[challenge['selectedDifficulty']]
    end_round = challenge['dcModel']['startRules']['endRound']
    if end_round == -1:
        end_round = f"{challenge['bossData']['TierCount'] * 20 + 20}+"
    description = f"{CASH} ${challenge['dcModel']['startRules']['cash']} — ♥️ {starting_lives} — " \
                  f"Rounds {challenge['dcModel']['startRules']['round']}/{end_round}\n\n"

    if challenge['dcModel']['maxTowers'] > -1:
        description += f"{MAX_TOWERS} Max Towers: {challenge['dcModel']['maxTowers']}\n"
    if challenge['dcModel']['disableMK']:
        description += f"{NO_KNOWLEDGE} Knowledge Disabled\n"
    if challenge['dcModel']['disableSelling']:
        description += f"{NO_SELLING} Selling Disabled\n"
    # if challenge['dcModel']['abilityCooldownReductionMultiplier'] != 1.0:
    #     description += f"- **Ability cooldown:** {int(challenge['dcModel']['abilityCooldownReductionMultiplier']*100)}%\n"
    # if challenge['dcModel']['removeableCostMultiplier'] != 1.0:
    #     description += f"- **Removable cost:** {int(challenge['dcModel']['removeableCostMultiplier']*100)}%\n"
    bloon_modifiers = []
    if challenge['dcModel']['bloonModifiers']['speedMultiplier'] != 1.0:
        bloon_modifiers.append(f"{BLOON_SPEED} Bloon Speed: {int(challenge['dcModel']['bloonModifiers']['speedMultiplier']*100)}%\n")
    if challenge['dcModel']['bloonModifiers']['moabSpeedMultiplier'] != 1.0:
        bloon_modifiers.append(f"{MOAB_SPEED} MOAB Speed: {int(challenge['dcModel']['bloonModifiers']['moabSpeedMultiplier']*100)}%\n")
    if challenge['dcModel']['bloonModifiers']['healthMultipliers']['bloons'] != 1.0:
        bloon_modifiers.append(f"{CERAM_HEALTH} Ceramic Health: {int(challenge['dcModel']['bloonModifiers']['healthMultipliers']['bloons']*100)}%\n")
    if challenge['dcModel']['bloonModifiers']['healthMultipliers']['moabs'] != 1.0:
        bloon_modifiers.append(f"{MOAB_HEALTH} MOAB Health: {int(challenge['dcModel']['bloonModifiers']['healthMultipliers']['moabs']*100)}%\n")
    if challenge['dcModel']['bloonModifiers']['regrowRateMultiplier'] != 1.0:
        bloon_modifiers.append(f"{REGROW_RATE} Regrow Rate: {int(challenge['dcModel']['bloonModifiers']['regrowRateMultiplier']*100)}%\n")
    if len(bloon_modifiers) > 0:
        description += "Bloon modifiers:\n" + "".join(bloon_modifiers)

    heroes_excluded = []
    all_heros_enabled = False
    towers = {
        "Heroes": [],
        "Primary": [],
        "Military": [],
        "Magic": [],
        "Support": [],
    }
    for twr in challenge['dcModel']['towers']['_items']:
        if twr is None:
            continue
        if twr['tower'] == "ChosenPrimaryHero":
            if twr["max"] == 1:
                all_heros_enabled = True
            continue

        if twr["isHero"] and twr["max"] == 0:
            heroes_excluded.append(add_spaces(twr['tower']))
        if twr['max'] == 0:
            continue
        if twr['isHero']:
            towers["Heroes"].append(add_spaces(twr['tower']))
        else:
            towers[TOWER_CATEGORY[twr['tower']]].append((twr['tower'], twr['max']))

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.orange(),
    )

    embed.set_author(
        name=f"Contested Territory #{event_number} — Tile {tile}",
        icon_url=tile_type_url,
    )
    map_key = challenge["selectedMap"] if challenge["selectedMap"] in MAPS else None
    embed.set_image(url=MAPS[map_key])
    embed.set_thumbnail(url=challenge_thmb)

    if all_heros_enabled:
        embed.add_field(name="Heroes", value="All Heroes Enabled!")
    if len(towers["Heroes"]) > 0:
        content = ""
        list_heroes = towers["Heroes"]
        if len(towers["Heroes"]) > len(heroes_excluded):
            content = "All **__EXCEPT FOR:__**\n"
            list_heroes = heroes_excluded
        for i in range(len(list_heroes)):
            content += list_heroes[i]
            if i != len(list_heroes)-1:
                content += " — " if i % 2 == 0 else "\n"
        embed.add_field(name="Heroes", value=content)

    for key in towers:
        if key == "Heroes" or len(towers[key]) == 0:
            continue
        content = ""
        for i in range(len(towers[key])):
            tower, max_amount = towers[key][i]
            if max_amount > 0:
                content += f"[{max_amount}x] "
            content += add_spaces(tower)
            if i != len(towers[key])-1:
                content += " — " if i % 2 == 0 else "\n"
        embed.add_field(name=f"{key} Towers", value=content, inline=False)
    return embed


def add_spaces(text: str) -> str:
    """Adds spaces to a text in PascalCase"""
    def repl(matchobj):
        return " " + matchobj.group(0)
    return re.sub("[A-Z]", repl, text).strip()


def fetch_tile_data(tile: str):
    path = f"bot/files/json/tiles/{tile}.json"
    if not os.path.exists(path):
        return None
    fin = open(path)
    data = json.loads(fin.read())
    fin.close()
    return data


def fetch_all_tiles():
    path = f"bot/files/json/tiles"
    tiles = []
    for file in os.listdir(path):
        data = fetch_tile_data(file[:3])
        if data is not None:
            tiles.append(data)
    return tiles


def relic_to_tile_code(relic: str) -> str or None:
    relic = relic.lower()
    relics = {
        'AirAndSea': ['aas', 'airandsea', 'air_and_sea', "ans"],
        'Abilitized': ['abilitized'],
        'AlchemistTouch': ['alchtouch', 'alch', 'alchemisttouch', 'alchemist_touch', 'alch_touch'],
        'MonkeyBoost': ['boost', 'mboost', 'mb', 'monkeyboost', 'monkey_boost'],
        'MarchingBoots': ['boots', 'mboots', 'marchingboots', 'marching_boots'],
        'BoxOfMonkey': ['box', 'boxofmonkey', 'bom', 'box_of_monkey'],
        'BoxOfChocolates': ['chocobox', 'chocbox', "boxofchocolates"],
        'CamoTrap': ['ctrap', 'camotrap', 'camo_trap'],
        'DurableShots': ['dshots', 'durableshots', 'durable_shotr'],
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
        "BrokenHeart": ["brokenheart", "broken_heart"]
    }
    for key in relics:
        if relic in relics[key]:
            tiles = fetch_all_tiles()
            for tile in tiles:
                if tile["RelicType"] == key:
                    return tile["Code"]
    return None


def get_map_image(team_pov: int = 0):
    tiles = fetch_all_tiles()
    ct_num = tiles[0]["EventNumber"]
    map_path = f"files/img/map/ct{ct_num}-{team_pov}.png"
    if not os.path.exists(map_path):
        make_map(map_path, tiles)


def make_map(path, tiles):
    pass
