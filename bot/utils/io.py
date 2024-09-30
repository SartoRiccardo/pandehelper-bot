from typing import Any
from PIL import Image
import aiofiles
from datetime import timedelta
import json
import os
from .Cache import Cache

rounds_cache = Cache.empty()


async def get_race_rounds() -> list[dict[str, Any]]:
    global rounds_cache
    if not rounds_cache.valid:
        async with aiofiles.open(os.path.join("files", "rounds-race.json")) as fin:
            data = json.loads(await fin.read())
            data.sort(key=lambda x: x["round"])
            rounds_cache = Cache(data, timedelta(days=256))
    return rounds_cache.value


async def get_tag_list() -> list[str]:
    async with aiofiles.open(os.path.join("files", "tags.json")) as fin:
        data = json.loads(await fin.read())
        return data.keys()


async def get_tag(tag_name: str) -> str or None:
    async with aiofiles.open(os.path.join("files", "tags.json")) as fin:
        data = json.loads(await fin.read())
        if tag_name not in data.keys():
            return None
        return data[tag_name]


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
