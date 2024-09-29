from typing import Any
from PIL import Image
from datetime import datetime, timedelta
import json
import os
from .Cache import Cache

rounds_cache = Cache.empty()

CACHE_DIR = "bot/files/cache"
if not os.path.exists(CACHE_DIR):
    os.mkdir(CACHE_DIR)


def get_race_rounds() -> list[dict[str, Any]]:
    global rounds_cache
    if not rounds_cache.valid:
        with open("bot/files/json/rounds-race.json") as fin:
            data = json.loads(fin.read())
            data.sort(key=lambda x: x["round"])
            rounds_cache = Cache(data, timedelta(days=256))
    return rounds_cache.value


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


def merge_images(img1_path: str, img2_path: str, save_path: str, gif: bool) -> None:
    img1 = Image.open(img1_path)
    img2 = Image.open(img2_path)
    img1.paste(img2, (0, 0), img2)
    
    if gif:
        frame2 = img1.copy()
        pixels = frame2.load()
        # This is so the frames are a little different but ALSO you can't add new colors
        # because for some reason sometimes GIFs flicker if you do.
        replaced = False
        for i in range(frame2.size[0]):
            for j in range(frame2.size[1]):
                if pixels[i, j] != (0, 0, 0, 0):
                    # Make a square 3 tall and 3 wide. Changing only one pixel sometimes
                    # doesnt work due to compression or... something
                    for x in range(3):
                        for y in range(3):
                            pixels[x, y] = pixels[i, j]
                    replaced = True
                    break
            if replaced:
                break
        frames = [img1, frame2]
        img1.save(save_path, format="GIF", append_images=frames, save_all=True, duration=100, loop=0)
    else:
        img1.save(save_path)
