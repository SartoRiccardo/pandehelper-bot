from typing import Any
from datetime import datetime
import json
import os


CACHE_DIR = "bot/files/cache"
if not os.path.exists(CACHE_DIR):
    os.mkdir(CACHE_DIR)


def get_race_rounds() -> list[dict[str, Any]]:
    fin = open("bot/files/json/rounds-race.json")
    data = json.loads(fin.read())
    fin.close()
    return data


def get_tag_list() -> list[str]:
    fin = open("bot/files/json/tags.json")
    data = json.loads(fin.read())
    fin.close()
    return data.keys()


def get_tag(tag_name: str) -> str or None:
    fin = open("bot/files/json/tags.json")
    data = json.loads(fin.read())
    if tag_name not in data.keys():
        return None
    fin.close()
    return data[tag_name]


def save_cog_state(cog_name: str, state: dict[str, Any]) -> None:
    data = json.dumps({
        "saved_at": datetime.now().timestamp(),
        "data": state,
    })
    fout = open(state_path(cog_name), "w")
    fout.write(data)
    fout.close()


def get_cog_state(cog_name: str) -> dict[str, Any] or None:
    if not os.path.exists(state_path(cog_name)):
        return None
    fin = open(state_path(cog_name))
    data = json.loads(fin.read())
    fin.close()
    return data


def state_path(cog_name: str) -> str:
    return f"{CACHE_DIR}/state-{cog_name}.json"

