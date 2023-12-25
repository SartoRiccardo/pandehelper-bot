import math
import os
from math import sqrt
from bloonspy import Client, btd6
from typing import Literal
import random
from PIL import Image, ImageDraw, ImageFont


TeamColor = Literal["Green", "Purple", "Red", "Yellow", "Pink", "Blue"]


BACKGROUND = "#263238"#"#707696"
PADDING = 40
MARGIN = 40

TILE_OVERLAY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin", "tile_overlays")
TILE_OVERLAY_SIZE = 100

HEX_RADIUS = (80, 70)
HEX_PADDING = 2
HEX_STROKE_W = 4
HEX_STROKE_W_SPAWN = 7
HEX_FULL_RADIUS = (HEX_RADIUS[0] + HEX_PADDING, HEX_RADIUS[1] + HEX_PADDING)
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
HEX_FILL_STALE = {
    "Green": "#c7ffdf",
    "Purple": "#c4b7ed",
    "Yellow": "#faf3ca",
    "Blue": "#bae2f7",
    "Pink": "#f2cbdd",
    "Red": "#e8a5a9",
}
HEX_LETTER = {
    "Green": "C",
    "Purple": "A",
    "Yellow": "E",
    "Blue": "D",
    "Pink": "B",
    "Red": "F",
}

TEXT_FONT = ImageFont.truetype(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin", "LuckiestGuy-Regular.ttf"), 100)
TEXT_MARGIN = (0, 30, 30, 30)
TEXT_C = (255, 255, 255)
TEXT_STROKE_C = (0, 0, 0)
TEXT_STROKE_W = 10


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


def tile_to_coords(tile_code: str, map_radius: int = 7, team_pov: int = 0) -> tuple[int, int, int]:
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

    rotations = (ord(tile_code[0])-ord("A")-team_pov) % 6
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


def make_map(tiles: list[btd6.CtTile], team_pov: int = 0, title: str or None = None) -> None:
    radius = get_radius(len(tiles))

    width = math.ceil(3/2 * HEX_FULL_RADIUS[0] * radius + HEX_FULL_RADIUS[0]) * 2
    width += (PADDING+MARGIN)*2

    height = math.ceil((radius*2+1) * HEX_FULL_RADIUS[1]*0.866*2)
    height += (PADDING+MARGIN)*2
    height += TEXT_MARGIN[0] + TEXT_MARGIN[2]

    map_size = (width, height)

    img = Image.new("RGBA", map_size, color=BACKGROUND)
    canvas = ImageDraw.Draw(img)

    title_bbox = (0, 0)
    if title is not None:
        title = title.upper()
        title_bbox = canvas.textbbox((0, 0), title, font=TEXT_FONT, stroke_width=TEXT_STROKE_W)
        map_size = (map_size[0], map_size[1] + (title_bbox[3]-title_bbox[1]))
        img = img.resize(map_size)
        canvas = ImageDraw.Draw(img)

    map_center = (
        map_size[0]/2,
        map_size[1]/2,
    )
    if title is not None:
        map_center = (map_center[0], map_center[1] + TEXT_MARGIN[0] + TEXT_MARGIN[1])

    # Test cases
    special = {
        "AAA": "Purple", "BAA": "Pink", "CAA": "Green", "DAA": "Blue", "EAA": "Yellow", "FAA": "Red",
        "ABA": "Purple", "BBA": "Pink", "CBA": "Green", "DBA": "Blue", "EBA": "Yellow", "FBA": "Red",
        "ACA": "Purple", "BCA": "Pink", "CCA": "Green", "DCA": "Blue", "ECA": "Yellow", "FCA": "Red",
        "AAB": "Purple", "BAB": "Pink", "CAB": "Green", "DAB": "Blue", "EAB": "Yellow", "FAB": "Red",
        "AAC": "Purple", "BAC": "Pink", "CAC": "Green", "DAC": "Blue", "EAC": "Yellow", "FAC": "Red",
    }
    special_stale = [
        "AAB", "BAB", "CAB", "DAB", "EAB", "FAB",
        "AAC", "BAC", "CAC", "DAC", "EAC", "FAC",
    ]

    for t in tiles:
        qrs = tile_to_coords(t.id, max(radius, 7), team_pov)  # The max is a hack cause tile codes are not dynamic like they're supposed to
        color = None if t.id not in special else special[t.id]
        is_stale = t.id in special_stale
        draw_hexagon(
            qrs,
            canvas,
            map_center,
            color=color,
            is_spawn_tile=t.tile_type == btd6.CtTileType.TEAM_START,
            is_stale=is_stale,
        )
        if t.tile_type == btd6.CtTileType.RELIC:
            paste_relic(t.relic, qrs, img, map_center)
        elif t.tile_type == btd6.CtTileType.BANNER:
            paste_banner(qrs, img, map_center)

    make_border(canvas, map_size, title)

    return img


def make_border(
        canvas: ImageDraw,
        map_size: tuple[int, int],
        title: str or None
    ) -> None:
    border_points = [
        (PADDING, PADDING),
        (PADDING, map_size[1]-PADDING),
        (map_size[0]-PADDING, map_size[1]-PADDING),
        (map_size[0]-PADDING, PADDING),
        (PADDING, PADDING)
    ]

    if title is not None:
        title = title.upper()
        title_bbox = canvas.textbbox((0, 0), title, font=TEXT_FONT, stroke_width=TEXT_STROKE_W)
        title_size = (title_bbox[2]-title_bbox[0], title_bbox[3]-title_bbox[1])
        canvas.text(
            ((map_size[0]-title_size[0])/2, TEXT_MARGIN[0] + MARGIN),
            title,
            font=TEXT_FONT,
            fill=TEXT_C,
            stroke_width=TEXT_STROKE_W,
            stroke_fill=TEXT_STROKE_C,
        )
        border_points.insert(0, (
            (map_size[0]-title_size[0])/2 - TEXT_MARGIN[3],
            PADDING + TEXT_MARGIN[0] + title_size[1]/2 - 10,
        ))
        border_points[-1] = (
            (map_size[0]+title_size[0])/2 + TEXT_MARGIN[1],
            PADDING + TEXT_MARGIN[0] + title_size[1]/2 - 10,
        )
        border_points[1] = (border_points[1][0], border_points[1][1] + TEXT_MARGIN[0] + title_size[1]/2 - 10)
        border_points[-2] = (border_points[-2][0], border_points[-2][1] + TEXT_MARGIN[0] + title_size[1]/2 - 10)

    for i in range(len(border_points)-1):
        canvas.line(
            [border_points[i], border_points[i+1]],
            fill="white",
            width=10
        )


def qrs_to_xy(
        qrs: tuple[int, int, int],
        map_center: tuple[int, int]) -> tuple[int, int]:
    xy = (
        map_center[0] + qrs[0] * HEX_FULL_RADIUS[0] * 3/2,
        map_center[1] + qrs[0] * HEX_FULL_RADIUS[1] * 0.866,
    )
    xy = (
        xy[0],
        xy[1] + qrs[1] * HEX_FULL_RADIUS[1] * 0.866 * 2,
    )
    return (int(xy[0]), int(xy[1]))


def draw_hexagon(
        qrs: tuple[int, int, int],
        canvas: ImageDraw,
        map_center: tuple[int, int],
        color: TeamColor or None = None,
        is_spawn_tile: bool = False,
        is_stale: bool = False) -> None:
    xy = qrs_to_xy(qrs, map_center)
    angle = 1/3 * math.pi
    points = []
    for _ in range(6):
        points.append((
            HEX_RADIUS[0] * math.cos(angle) + xy[0],
            HEX_RADIUS[1] * math.sin(angle) + xy[1],
        ))
        angle += 1/3 * math.pi

    fill = HEX_FILL_STALE[color] if color and is_stale else HEX_FILL[color] #HEX_STROKE_C[color] if is_spawn_tile else HEX_FILL[color]
    outline = HEX_STROKE_C[color] #HEX_FILL[color] if is_spawn_tile else HEX_STROKE_C[color]
    stroke = HEX_STROKE_W #HEX_STROKE_W_SPAWN if is_spawn_tile else HEX_STROKE_W
    canvas.polygon(points, fill=fill, outline=outline, width=stroke)

    if is_spawn_tile and color:
        canvas.text(
            (xy[0], xy[1]+12),
            HEX_LETTER[color],
            font=TEXT_FONT,
            fill=TEXT_C,
            stroke_width=TEXT_STROKE_W,
            stroke_fill=TEXT_STROKE_C,
            anchor="mm",
        )


def paste_relic(
        relic: btd6.Relic,
        qrs: tuple[int, int, int],
        image: Image,
        map_center: tuple[int, int]) -> None:
    xy = qrs_to_xy(qrs, map_center)
    xy = (xy[0]-int(TILE_OVERLAY_SIZE/2), xy[1]-int(TILE_OVERLAY_SIZE/2))
    relic_img = Image.open(os.path.join(TILE_OVERLAY_PATH, f"{relic.value.replace(' ', '')}.png")) \
                    .convert("RGBA") \
                    .resize((TILE_OVERLAY_SIZE, TILE_OVERLAY_SIZE))
    Image.Image.paste(image, relic_img, xy, mask=relic_img)


def paste_banner(
        qrs: tuple[int, int, int],
        image: Image,
        map_center: tuple[int, int]) -> None:
    xy = qrs_to_xy(qrs, map_center)
    xy = (xy[0]-int(TILE_OVERLAY_SIZE/2), xy[1]-int(TILE_OVERLAY_SIZE/2))
    relic_img = Image.open(os.path.join(TILE_OVERLAY_PATH, "Banner.png")) \
                    .convert("RGBA") \
                    .resize((TILE_OVERLAY_SIZE, TILE_OVERLAY_SIZE))
    Image.Image.paste(image, relic_img, xy, mask=relic_img)


if __name__ == '__main__':
    tiles = Client.contested_territories()[0].tiles()
    make_map(tiles, title="Pandemonium CT Map", team_pov=2).show()
    #make_map(tiles).show()

    #for ct in Client.contested_territories():
    #    make_map(ct.tiles(), 1)

    #tiles = Client.contested_territories()[0].tiles()
    #for pov in range(6):
    #    make_map(tiles, pov)
