import math
import os
from math import sqrt
from bloonspy import Client, btd6
from typing import Literal
import random
from PIL import Image, ImageDraw


TeamColor = Literal["Green", "Purple", "Red", "Yellow", "Pink", "Blue"]


BACKGROUND = "#263238"#"#707696"
PADDING = 40
MARGIN = 40

TILE_OVERLAY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin", "tile_overlays")
TILE_OVERLAY_SIZE = 120

HEX_RADIUS = 80
HEX_PADDING = 0
HEX_STROKE_W = 4
HEX_FULL_RADIUS = HEX_RADIUS + HEX_PADDING
HEX_STROKE_C = {
    "Green": "#00713a",
    "Purple": "#68049c",
    "Yellow": "#ffa300",
    "Blue": "#005cd5",
    "Pink": "#bf1c6b",
    "Red": "#bb0000",
    None: "#b0bec5",
}
HEX_FILL = {
    "Green": "#00e763",
    "Purple": "#ac2aeb",
    "Yellow": "#fad800",
    "Blue": "#00a0f9",
    "Pink": "#f769a9",
    "Red": "#ff1524",
    None: "#eceff1",
}


def sign(num: float) -> int:
    if num == 0:
        return 0
    return 1 if num > 0 else -1


def get_radius(tile_count: int) -> int:
    """
    It's just the reverse formula of the sum of numbers from 1 to n. Every time
    you increase the map radius by 1, the tiles increase by prev_radius*6. For the
    formula to work you also have to consider spawn tiles as valid tiles and also
    exclude MRX. Spawn tiles should be included in tile_count
    """
    return int((sqrt(1 + 8*(tile_count-1)/6) - 1) / 2)


def tile_to_coords(tile_code: str, map_radius: int = 7) -> tuple[int, int, int]:
    """
    First letter is which spawn the tile is closest to (A -> G counterclockwise).
    Second letter is how far horizontally it goes.
    Third letter is how far it is from MRX.

    Hexagonal grid coord reference:
    - https://www.redblobgames.com/grids/hexagons/#distances
    - https://www.redblobgames.com/grids/hexagons/#rotation
    """
    if len(tile_code) < 3:
        raise ValueError()

    tile_code = tile_code.upper()
    if tile_code == "MRX":
        return 0, 0, 0
    # FAH edge case
    if tile_code.startswith("FA") and ord(tile_code[2]) >= ord("H"):
        tile_code = tile_code[:2] + chr(ord(tile_code[2])-1)

    rotations = ord(tile_code[0])-ord("A")
    dist_from_center = map_radius - (ord(tile_code[2])-ord("A"))
    dist_from_radius = int((ord(tile_code[1])-ord("A")+1) / 2)
    qrs = (0, dist_from_center, -dist_from_center)
    if (ord(tile_code[1])-ord("A")) % 2 == 0:  # Move right
        qrs = (qrs[0]-dist_from_radius, qrs[1], qrs[2]+dist_from_radius)
    else:
        qrs = (qrs[0]+dist_from_radius, qrs[1]-dist_from_radius, qrs[2])

    for _ in range(rotations):
        qrs = (-qrs[2], -qrs[0], -qrs[1])

    return qrs


def make_map(tiles: list[btd6.CtTile], team_pov: int) -> None:
    radius = get_radius(len(tiles))
    map_size = (
        math.ceil(3/2 * HEX_FULL_RADIUS * radius + HEX_FULL_RADIUS) * 2 + (PADDING+MARGIN)*2,
        math.ceil((radius*2+1) * HEX_FULL_RADIUS*0.866*2) + (PADDING+MARGIN)*2,
    )

    img = Image.new("RGBA", map_size, color=BACKGROUND)
    canvas = ImageDraw.Draw(img)

    a = list(HEX_FILL.keys())
    for t in tiles:
        qrs = tile_to_coords(t.id, radius)
        draw_hexagon(
            qrs,
            canvas,
            map_size,
            color=random.choice(a),
            is_spawn_tile=t.tile_type == btd6.CtTileType.TEAM_START
        )
        if t.tile_type == btd6.CtTileType.RELIC:
            paste_relic(t.relic, qrs, img, map_size)
        elif t.tile_type == btd6.CtTileType.BANNER:
            paste_banner(qrs, img, map_size)

    canvas.polygon(
        [(PADDING, PADDING), (map_size[0]-PADDING, PADDING),
         (map_size[0]-PADDING, map_size[1]-PADDING), (PADDING, map_size[1]-PADDING)],
        outline="white",
        width=10,
    )
    img.show()


def qrs_to_xy(qrs: tuple[int, int, int], img_size: tuple[int, int]) -> tuple[int, int]:
    xy = (
        img_size[0]/2 + qrs[0] * HEX_FULL_RADIUS * 3/2,
        img_size[1]/2 + qrs[0] * HEX_FULL_RADIUS * 0.866,
    )
    xy = (
        xy[0],
        xy[1] + qrs[1] * HEX_FULL_RADIUS * 0.866 * 2,
    )
    return (int(xy[0]), int(xy[1]))


def draw_hexagon(
        qrs: tuple[int, int, int],
        canvas: ImageDraw,
        img_size: tuple[int, int],
        color: TeamColor or None = None,
        is_spawn_tile: bool = False) -> None:
    xy = qrs_to_xy(qrs, img_size)
    angle = 1/3 * math.pi
    points = []
    for _ in range(6):
        points.append((
            HEX_RADIUS * math.cos(angle) + xy[0],
            HEX_RADIUS * math.sin(angle) + xy[1],
        ))
        angle += 1/3 * math.pi

    fill = HEX_STROKE_C[color] if is_spawn_tile else HEX_FILL[color]
    canvas.polygon(points, fill=fill, outline=HEX_STROKE_C[color], width=HEX_STROKE_W)


def paste_relic(
        relic: btd6.Relic,
        qrs: tuple[int, int, int],
        image: Image,
        img_size: tuple[int, int]) -> None:
    xy = qrs_to_xy(qrs, img_size)
    xy = (xy[0]-int(TILE_OVERLAY_SIZE/2), xy[1]-int(TILE_OVERLAY_SIZE/2))
    relic_img = Image.open(os.path.join(TILE_OVERLAY_PATH, f"{relic.value.replace(' ', '')}.png")) \
                    .convert("RGBA") \
                    .resize((TILE_OVERLAY_SIZE, TILE_OVERLAY_SIZE))
    Image.Image.paste(image, relic_img, xy, mask=relic_img)


def paste_banner(
        qrs: tuple[int, int, int],
        image: Image,
        img_size: tuple[int, int]) -> None:
    xy = qrs_to_xy(qrs, img_size)
    xy = (xy[0]-int(TILE_OVERLAY_SIZE/2), xy[1]-int(TILE_OVERLAY_SIZE/2))
    relic_img = Image.open(os.path.join(TILE_OVERLAY_PATH, "Banner.png")) \
                    .convert("RGBA") \
                    .resize((TILE_OVERLAY_SIZE, TILE_OVERLAY_SIZE))
    Image.Image.paste(image, relic_img, xy, mask=relic_img)


if __name__ == '__main__':
    tiles = Client.contested_territories()[0].tiles()
    make_map(tiles, 5)
