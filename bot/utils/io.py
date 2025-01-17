from typing import Any
import PIL
from PIL import Image
import aiofiles
from datetime import timedelta
import json
import os
from .Cache import Cache

rounds_cache = Cache.empty()
files_dir = os.path.join(os.getcwd(), "files")


async def get_race_rounds() -> list[dict[str, Any]]:
    global rounds_cache
    if not rounds_cache.valid:
        async with aiofiles.open(os.path.join(files_dir, "rounds-race.json")) as fin:
            data = json.loads(await fin.read())
            data.sort(key=lambda x: x["round"])
            rounds_cache = Cache(data, timedelta(days=256))
    return rounds_cache.value


async def get_tag_list() -> list[str]:
    async with aiofiles.open(os.path.join(files_dir, "tags.json")) as fin:
        data = json.loads(await fin.read())
        return data.keys()


async def get_tag(tag_name: str) -> str or None:
    async with aiofiles.open(os.path.join(files_dir, "tags.json")) as fin:
        data = json.loads(await fin.read())
        if tag_name not in data.keys():
            return None
        return data[tag_name]


def merge_images(img1_path: str, img2_path: str, save_path: str, gif: bool) -> bool:
    try:
        img1 = Image.open(img1_path)
        img2 = Image.open(img2_path)
    except PIL.UnidentifiedImageError:
        return False

    img1.paste(img2, (0, 0), img2)
    
    if gif:
        frame2 = img1.copy()
        pixels = frame2.load()
        # This is so the frames are a little different, but ALSO you can't add new colors
        # because for some reason sometimes GIFs flicker if you do.
        replaced = False
        for i in range(frame2.size[0]):
            for j in range(frame2.size[1]):
                if pixels[i, j][3] == 255:
                    # Make a square. Changing only one pixel sometimes
                    # doesn't work due to compression or... something
                    SQUARE_SIZE = 6
                    for x in range(SQUARE_SIZE):
                        for y in range(SQUARE_SIZE):
                            pixels[x, y] = pixels[i, j]
                    replaced = True
                    break
            if replaced:
                break
        frames = [img1, frame2]
        img1.save(save_path, format="GIF", append_images=frames, save_all=True, duration=100, loop=0)
    else:
        img1.save(save_path)

    return True
