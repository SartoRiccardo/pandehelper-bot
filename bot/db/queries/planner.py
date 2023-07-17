import time
import datetime
import bot.db.connection
import bot.utils.bloons
from typing import List, Dict, Tuple, Any, Literal
from ..model.Planner import Planner
from ..model.PlannedTile import PlannedTile
postgres = bot.db.connection.postgres
bloons = bot.utils.bloons


@postgres
async def get_planners(only_active: bool = False, conn=None) -> List[Planner]:
    only_active_q = " WHERE is_active" if only_active else ""
    planners = await conn.fetch("SELECT * FROM planners" + only_active_q)
    return [Planner(row["planner_channel"], row["claims_channel"], row["ping_role"], row["ping_channel"],
                    row["clear_time"], row["is_active"])
            for row in planners]


@postgres
async def get_planner(planner_id: int, conn=None) -> Planner or None:
    results = await conn.fetch("""
        SELECT *
        FROM planners
        WHERE planner_channel=$1
    """, planner_id)
    return Planner(results[0]["planner_channel"], results[0]["claims_channel"], results[0]["ping_role"],
                   results[0]["ping_channel"], results[0]["clear_time"], results[0]["is_active"]) \
        if len(results) else None


@postgres
async def add_planner(planner_id: int, conn=None) -> None:
    await conn.execute("""
        INSERT INTO planners(planner_channel) VALUES($1)
    """, planner_id)


@postgres
async def del_planner(planner_id: int, conn=None) -> None:
    await conn.execute("""
        DELETE FROM planners WHERE planner_channel=$1
    """, planner_id)


@postgres
async def change_planner(
        planner_id: int,
        clear_time: datetime.datetime = None,
        ping_channel: int = None,
        ping_role: int = None,
        claims_channel: int = None,
        is_active: bool = None,
        conn=None) -> None:
    fields = [
        ("clear_time", clear_time),
        ("ping_channel", ping_channel),
        ("ping_role", ping_role),
        ("claims_channel", claims_channel),
        ("is_active", is_active),
    ]
    fields_query = []
    for i in range(len(fields)):
        var_name, var_value = fields[i]
        if var_value is None:
            continue
        fields_query.append((f"{var_name}=${i+2}", var_value))
    if len(fields_query) == 0:
        return

    q = f"UPDATE planners SET {', '.join([x for x, _ in fields_query])} WHERE planner_id=$1"
    await conn.execute(q, planner_id, *[x for _, x in fields_query])


@postgres
async def get_planned_banners(planner_channel: int,
                              banner_codes: List[str],
                              expire_between: Tuple[datetime.datetime, datetime.datetime] or None = None,
                              claimed_status: Literal["UNCLAIMED", "CLAIMED", "ANY"] = "ANY",
                              conn=None) -> List[PlannedTile]:
    event = bloons.get_current_ct_number()
    event_start = bloons.FIRST_CT_START + datetime.timedelta(days=bloons.EVENT_DURATION*2 * (event-1))
    banner_captures = """
        SELECT c.tile AS tile, c.claimed_at AS claimed_at, ptc.user_id AS user_id,
            p.claims_channel, p.ping_role, p.ping_channel, p.planner_channel
        FROM (claims c
        JOIN planners p
            ON c.channel = p.claims_channel)
        LEFT JOIN plannertileclaims ptc
            ON p.planner_channel = ptc.planner_channel AND c.tile = ptc.tile
        WHERE p.planner_channel = $3
            AND c.claimed_at >= $1
            AND c.tile = ANY($2::VARCHAR(3)[])
        ORDER BY c.claimed_at ASC
    """

    extra_args = []
    between_q = ""
    if expire_between is not None:
        extra_args.append(expire_between[0] - datetime.timedelta(days=1))
        extra_args.append(expire_between[1] - datetime.timedelta(days=1))
        between_q = """
            AND claimed_at >= $4
            AND claimed_at < $5
        """
    claim_q = ""
    if claimed_status == "UNCLAIMED":
        claim_q = "AND bcap.user_id IS NULL"
    elif claimed_status == "CLAIMED":
        claim_q = "AND bcap.user_id IS NOT NULL"

    banners = await conn.fetch(f"""
        SELECT bcap.tile, bcap.claimed_at, bcap.user_id, claims_channel, ping_role, ping_channel, planner_channel
        FROM ({banner_captures}) bcap
        WHERE claimed_at = (
            SELECT MAX(claimed_at)
            FROM ({banner_captures}) bcap2
            WHERE bcap.tile = bcap2.tile
        ) AND (
            (SELECT clear_time FROM planners WHERE planner_channel = $3) IS NULL
            OR claimed_at >= (SELECT clear_time FROM planners WHERE planner_channel = $3)
        )
    """ + between_q + claim_q, event_start, banner_codes, planner_channel, *extra_args)
    return [PlannedTile(row["tile"], row["claimed_at"], row["user_id"], row["planner_channel"], row["claims_channel"], row["ping_role"],
                        row["ping_channel"])
            for row in banners]


@postgres
async def get_banner_closest_to_expire(banner_codes: List[str],
                                       from_date: datetime.datetime,
                                       conn=None) -> List[PlannedTile]:
    one_day = datetime.timedelta(days=1)
    banner_captures = """
            SELECT p.planner_channel AS planner_channel, c.tile AS tile, c.claimed_at AS claimed_at,
                    ptc.user_id AS user_id, p.ping_channel as ping_channel, p.ping_role AS ping_role,
                    p.claims_channel AS claims_channel
            FROM (claims c
            JOIN planners p
                ON c.channel = p.claims_channel)
            LEFT JOIN plannertileclaims ptc
                ON p.planner_channel = ptc.planner_channel AND c.tile = ptc.tile
            WHERE claimed_at >= $2
                AND c.tile = ANY($1::VARCHAR(3)[])
            ORDER BY c.claimed_at ASC
        """
    banner_claims = f"""
            SELECT bcap.planner_channel, bcap.tile, bcap.claimed_at, bcap.user_id, bcap.ping_channel,
                    bcap.ping_role, bcap.claims_channel
            FROM ({banner_captures}) bcap
            WHERE claimed_at = (
                SELECT MAX(claimed_at)
                FROM ({banner_captures}) bcap2
                WHERE bcap.tile = bcap2.tile
                    AND bcap.planner_channel = bcap2.planner_channel
            ) AND (
                (SELECT clear_time FROM planners WHERE planner_channel = bcap.planner_channel) IS NULL
                OR claimed_at >= (SELECT clear_time FROM planners WHERE planner_channel = bcap.planner_channel)
            )
        """
    banners = await conn.fetch(f"""
            SELECT *
            FROM ({banner_claims}) bclaim
            WHERE bclaim.claimed_at = (
                SELECT MIN(bclaims2.claimed_at)
                FROM ({banner_claims}) bclaims2
                WHERE bclaim.planner_channel = bclaims2.planner_channel
            )
        """, banner_codes, from_date-one_day)
    return [PlannedTile(row["tile"], row["claimed_at"], row["user_id"], row["planner_channel"], row["claims_channel"],
                        row["ping_channel"], row["ping_role"])
            for row in banners]


@postgres
async def planner_claim_tile(user: int, tile: str, planner_channel: int, conn=None) -> None:
    await conn.execute("""
        INSERT INTO plannertileclaims(user_id, planner_channel, tile)
        VALUES($1, $2, $3)
    """, user, planner_channel, tile)


@postgres
async def planner_unclaim_tile(tile: str, planner_channel: int, conn=None) -> None:
    await conn.execute("""
        DELETE FROM plannertileclaims WHERE planner_channel = $1 AND tile = $2
    """, planner_channel, tile)


async def planner_get_tile_status(tile: str, planner_channel: int) -> Dict[str, Any] or None:
    tiles = await get_planned_banners(planner_channel, [tile])
    return tiles[0] if len(tiles) else None


@postgres
async def planner_update_config(
        planner: int,
        ping_ch: int or None = None,
        ping_role: int or None = None,
        tile_claim_ch: int or None = None,
        conn=None) -> None:
    fields = []
    values = []
    if ping_ch is not None:
        values.append(ping_ch)
        fields.append(f"ping_channel=${len(values)+1}")
    if ping_role is not None:
        values.append(ping_role)
        fields.append(f"ping_role=${len(values)+1}")
    if tile_claim_ch is not None:
        values.append(tile_claim_ch)
        fields.append(f"claims_channel=${len(values)+1}")

    if len(fields) == 0:
        return
    await conn.execute(f"""
        UPDATE planners SET {', '.join(fields)} WHERE planner_channel = $1
    """, planner, *values)


@postgres
async def planner_delete_config(
        planner: int,
        ping_ch: bool = False,
        ping_role: bool = False,
        tile_claim_ch: bool = False,
        conn=None) -> None:
    fields = []
    if ping_ch is not None:
        fields.append(f"ping_channel=$2")
    if ping_role is not None:
        fields.append(f"ping_role=$2")
    if tile_claim_ch is not None:
        fields.append(f"claims_channel=$2")

    if len(fields) == 0:
        return
    await conn.execute(f"""
        UPDATE planners SET {', '.join(fields)} WHERE planner_channel = $1
    """, planner, None)


@postgres
async def get_planner_linked_to(tile_claim_ch: int, conn=None) -> int:
    channel = await conn.fetch("""
        SELECT planner_channel
        FROM planners
        WHERE claims_channel = $1
    """, tile_claim_ch)
    return channel[0]["planner_channel"] if len(channel) > 0 else None


@postgres
async def get_claims_by(user: int, planner_channel: int, conn=None) -> List[Dict[str, Any]]:
    return await conn.fetch("""
        SELECT *
        FROM plannertileclaims
        WHERE user_id = $1
            AND planner_channel = $2
    """, user, planner_channel)


@postgres
async def turn_planner(planner: int, active: bool, conn=None) -> None:
    await conn.execute("UPDATE planners SET is_active=$1 WHERE planner_channel=$2", active, planner)


@postgres
async def set_clear_time(planner: int, clear_time: datetime.datetime, conn=None) -> None:
    await conn.execute("UPDATE planners SET clear_time=$1 WHERE planner_channel=$2", clear_time, planner)


@postgres
async def edit_tile_capture_time(channel_id: int,
                                 tile: str,
                                 new_time: datetime.datetime,
                                 planner_clear_time: datetime.datetime or None = None,
                                 conn=None) -> bool:
    event = bloons.get_current_ct_number()
    event_start = bloons.FIRST_CT_START + datetime.timedelta(days=bloons.EVENT_DURATION * 2 * (event - 1))
    min_time_to_edit = event_start if planner_clear_time is None else max(event_start, planner_clear_time)
    updated = await conn.execute("""
        UPDATE claims
        SET claimed_at = $1
        WHERE tile = $2
            AND channel = $3
            AND claimed_at = (
                SELECT MAX(claimed_at)
                FROM claims
                WHERE tile = $2
                    AND channel = $3
            )
            AND claimed_at >= $4
    """, new_time, tile, channel_id, min_time_to_edit)
    updated_rows = int(updated[7:])
    return updated_rows > 0
