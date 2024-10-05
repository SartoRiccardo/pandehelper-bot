import io
import math
import os
from math import sqrt
from bloonspy import btd6
from bot.types import TeamColor
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont
from config import DATA_PATH
from functools import wraps
from pathlib import Path
import hashlib
from datetime import datetime


@dataclass
class ColorStyle:
    hex_stroke: str
    hex_fill: str
    hex_fill_stale: str | None
    letter: str | None


# Everything is relative to this. Current resolution is 8:7
HEX_RADIUS = (80 // 1.4, 70 // 1.4)

BACKGROUND = "#263238"
PADDING = round(max(HEX_RADIUS) / 2)
MARGIN = round(max(HEX_RADIUS) / 2)

HEX_PADDING = round(max(HEX_RADIUS) / 40)
HEX_STROKE_W = round(max(HEX_RADIUS) / 20)
HEX_STROKE_W_SPAWN = round(min(HEX_RADIUS) / 10)
HEX_FULL_RADIUS = (HEX_RADIUS[0] + HEX_PADDING, HEX_RADIUS[1] + HEX_PADDING)
COLOR_STYLES = {
    "Green": ColorStyle("#00713a", "#00e763", "#c7ffdf", "C"),
    "Purple": ColorStyle("#68049c", "#ac2aeb", "#c4b7ed", "A"),
    "Yellow": ColorStyle("#ffa300", "#fad800", "#faf3ca", "E"),
    "Blue": ColorStyle("#005cd5", "#00a0f9", "#bae2f7", "D"),
    "Pink": ColorStyle("#bf1c6b", "#f769a9", "#f2cbdd", "B"),
    "Red": ColorStyle("#bb0000", "#ff1524", "#e8a5a9", "F"),
    None: ColorStyle("#b0bec5", "#eceff1", None, ""),
}

TILE_OVERLAY_PATH = os.path.join("files", "bin", "tile_overlays")
TILE_OVERLAY_SIZE = round(max(HEX_RADIUS) * 10/8)

TEXT_FONT = ImageFont.truetype(os.path.join("files", "bin", "LuckiestGuy-Regular.ttf"), (max(HEX_RADIUS) * 10) // 8)
text_margin_rel = round(max(HEX_RADIUS) * 3/8)
TEXT_MARGIN = (0, text_margin_rel, text_margin_rel, text_margin_rel)
TEXT_C = (255, 255, 255)
TEXT_STROKE_C = (0, 0, 0)
TEXT_STROKE_W = round(max(HEX_RADIUS) / 8)


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


def cache_image(cache_path: str, limit: int):
    def deco(wrapped):
        @wraps(wrapped)
        def wrapper(tiles: list[btd6.CtTile], **kwargs) -> str:
            imghash = ""
            for tl in sorted(tiles, key=lambda x: x.id):
                imghash += str(tl)
            for kw in sorted(kwargs.keys()):
                imghash += f"[{kw}]{kwargs[kw]}"
            imghash = hashlib.sha256(imghash.encode()).hexdigest()
            fpath = os.path.join(cache_path, f"{imghash}.png")

            if not os.path.exists(fpath):
                cached_imgs = sorted(Path(cache_path).iterdir(), key=os.path.getmtime, reverse=True)
                for i in range(limit-1, len(cached_imgs)):
                    os.remove(cached_imgs[i])
                wrapped(tiles, **kwargs, file_out=fpath)

            now = int(datetime.now().timestamp())
            os.utime(fpath, times=(now, now))
            return fpath

        return wrapper

    os.makedirs(cache_path, exist_ok=True)
    return deco


@cache_image(os.path.join(DATA_PATH, "tmp", "map-images"), limit=20)
def make_map(
        tiles: list[btd6.CtTile],
        team_pov: int = 0,
        title: str or None = None,
        file_out: str | None = None
) -> io.BytesIO | None:
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

    for t in tiles:
        # The max is a hack cause tile codes are not dynamic like they're supposed to
        qrs = tile_to_coords(t.id, max(radius, 7), team_pov)
        is_spawn = t.tile_type == btd6.CtTileType.TEAM_START
        color = None
        if is_spawn:
            for clr in COLOR_STYLES:
                if t.id[0] == COLOR_STYLES[clr].letter:
                    color = clr
                    break

        draw_hexagon(
            qrs,
            canvas,
            map_center,
            color=color,
            is_spawn_tile=is_spawn,
            is_stale=False,
        )
        if t.tile_type == btd6.CtTileType.RELIC:
            paste_relic(t.relic, qrs, img, map_center)
        elif t.tile_type == btd6.CtTileType.BANNER:
            paste_banner(qrs, img, map_center)

    make_border(canvas, map_size, title)

    if file_out is None:
        imgbin = io.BytesIO()
        img.save(imgbin, format="PNG")
        imgbin.seek(0)
        return imgbin
    else:
        img.save(file_out, format="PNG")


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
    return int(xy[0]), int(xy[1])


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

    style = COLOR_STYLES[color]
    fill = style.hex_fill_stale if color and is_stale else style.hex_fill #HEX_STROKE_C[color] if is_spawn_tile else HEX_FILL[color]
    outline = style.hex_stroke #HEX_FILL[color] if is_spawn_tile else HEX_STROKE_C[color]
    stroke = HEX_STROKE_W_SPAWN if is_spawn_tile else HEX_STROKE_W
    canvas.polygon(points, fill=fill, outline=outline, width=stroke)

    if is_spawn_tile and color:
        canvas.text(
            (xy[0], xy[1]+12),
            style.letter,
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
    relic_img = Image.open(os.path.join(TILE_OVERLAY_PATH, f"{relic.value.replace(' ', '')}.png").lower()) \
                     .convert("RGBA") \
                     .resize((TILE_OVERLAY_SIZE, TILE_OVERLAY_SIZE))
    Image.Image.paste(image, relic_img, xy, mask=relic_img)


def paste_banner(
        qrs: tuple[int, int, int],
        image: Image,
        map_center: tuple[int, int]) -> None:
    xy = qrs_to_xy(qrs, map_center)
    xy = (xy[0]-int(TILE_OVERLAY_SIZE/2), xy[1]-int(TILE_OVERLAY_SIZE/2))
    relic_img = Image.open(os.path.join(TILE_OVERLAY_PATH, "banner.png")) \
                    .convert("RGBA") \
                    .resize((TILE_OVERLAY_SIZE, TILE_OVERLAY_SIZE))
    Image.Image.paste(image, relic_img, xy, mask=relic_img)
