import time
import datetime
import bot.db.connection
import bot.utils.bloons
from typing import List, Dict, Tuple, Any, Literal
from .model.TileCapture import TileCapture
postgres = bot.db.connection.postgres
bloons = bot.utils.bloons

# I really need to format this into different files huh
# I'll do that... someday


@postgres
async def track_channel(channel: int, conn=None) -> None:
    await conn.execute("""
            INSERT INTO teams (channel) VALUES ($1)
                ON CONFLICT DO NOTHING
            """, channel)


@postgres
async def untrack_channel(channel: int, conn=None) -> None:
    await conn.execute("DELETE FROM teams WHERE channel=$1",
                       channel)


@postgres
async def get_ticket_overview(channel: int, event: int = 0, conn=None) -> Dict[int, List[List[TileCapture]]]:
    if event == 0:
        event = bloons.get_ct_number_during(datetime.datetime.now())
    event_start = bloons.FIRST_CT_START + datetime.timedelta(days=bloons.EVENT_DURATION*2 * (event-1))
    event_end = event_start + datetime.timedelta(days=bloons.EVENT_DURATION)
    result = await conn.fetch("""
        SELECT * FROM claims
            WHERE channel=$1
              AND claimed_at >= $2
              AND claimed_at <= $3
        """, channel, event_start, event_end)

    claims = {}
    for record in result:
        uid = record["userid"]
        if uid not in claims:
            claims[uid] = []
            for _ in range(bloons.EVENT_DURATION):
                claims[uid].append([])
        day = (record["claimed_at"] - event_start).days
        if 0 <= day < bloons.EVENT_DURATION:
            claims[uid][day].append(
                TileCapture(uid, record["tile"], channel, record["message"], record["claimed_at"])
            )
    return claims


@postgres
async def get_tickets_from(member_id: int, channel: int, event: int = 0, conn=None) -> List[List[TileCapture]]:
    if event == 0:
        event = bloons.get_ct_number_during(datetime.datetime.now())
    event_start = bloons.FIRST_CT_START + datetime.timedelta(days=bloons.EVENT_DURATION*2 * (event-1))
    event_end = event_start + datetime.timedelta(days=bloons.EVENT_DURATION)
    result = await conn.fetch("""
        SELECT * FROM claims
            WHERE channel=$1
              AND userid=$2
              AND claimed_at >= $3
              AND claimed_at <= $4
        """, channel, member_id, event_start, event_end)

    claims = []
    for _ in range(bloons.EVENT_DURATION):
        claims.append([])
    for record in result:
        day = (record["claimed_at"] - event_start).days
        if 0 <= day < bloons.EVENT_DURATION:
            claims[day].append(
                TileCapture(member_id, record["tile"], channel, record["message"], record["claimed_at"])
            )
    return claims


@postgres
async def tracked_channels(conn=None) -> List[int]:
    payload = await conn.fetch("SELECT channel FROM teams")
    channels = [row["channel"] for row in payload]
    return channels


@postgres
async def capture(channel: int, user: int, tile: str, message: int, conn=None) -> None:
    await conn.execute("""
            INSERT INTO claims (userid, tile, channel, message, claimed_at) VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT DO NOTHING
        """, user, tile, channel, message, datetime.datetime.now())


@postgres
async def uncapture(message: int, conn=None) -> None:
    await conn.execute("DELETE FROM claims WHERE message=$1", message)


@postgres
async def add_leaderboard_channel(guild: int, channel: int, conn=None) -> None:
    await conn.execute("""
                INSERT INTO lbchannels (guild, channel) VALUES ($1, $2)
                    ON CONFLICT DO NOTHING
                """, guild, channel)


@postgres
async def remove_leaderboard_channel(guild: int, channel: int, conn=None) -> None:
    await conn.execute("DELETE FROM lbchannels WHERE guild=$1 AND channel=$2",
                       guild, channel)


@postgres
async def leaderboard_channels(conn=None) -> List[Tuple[int, int]]:
    payload = await conn.fetch("SELECT guild, channel FROM lbchannels")
    return [(row["guild"], row["channel"]) for row in payload]


@postgres
async def get_oaks(user: int, conn=None) -> List[Dict[str, Any]]:
    payload = await conn.fetch("""
        SELECT oak, is_main
        FROM btd6players
        WHERE userid=$1
        ORDER BY
            is_main DESC,
            oak
    """, user)
    return payload


async def get_main_oak(user: int) -> str or None:
    oaks = await get_oaks(user)
    return oaks[0] if len(oaks) > 0 else None


@postgres
async def set_main_oak(user: int, oak: str, conn=None) -> None:
    await conn.execute("""
        UPDATE btd6players
        SET is_main=(oak=$2)
        WHERE userid=$1
    """, user, oak)


@postgres
async def is_oak_registered(oak: str, conn=None) -> bool:
    return len(await conn.fetch("SELECT * FROM btd6players WHERE oak=$1", oak)) > 0


@postgres
async def set_oak(user: int, oak: str, conn=None) -> None:
    await conn.execute("""
        INSERT INTO btd6players (userid, oak, is_main)
        VALUES (
            $1, $2,
            (SELECT COUNT(*)=0 FROM btd6players WHERE userid=$1)
        )
    """, user, oak)
    pass


@postgres
async def del_oak(user: int, oak: str, conn=None) -> None:
    await conn.execute("""
        DELETE FROM btd6players
        WHERE userid=$1
            AND oak=$2
    """, user, oak)


@postgres
async def get_planners(only_active: bool = False, conn=None) -> List[Dict[str, Any]]:
    only_active_q = " WHERE is_active" if only_active else ""
    planners = await conn.fetch("SELECT * FROM planners" + only_active_q)
    return planners


@postgres
async def get_planner(planner_id: int, conn=None) -> Dict[str, Any] or None:
    results = await conn.fetch("""
        SELECT *
        FROM planners
        WHERE planner_channel=$1
    """, planner_id)
    return results[0] if len(results) else None


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
                              conn=None) -> List[Dict[str, Any]]:
    event = bloons.get_current_ct_number()
    event_start = bloons.FIRST_CT_START + datetime.timedelta(days=bloons.EVENT_DURATION*2 * (event-1))
    banner_captures = """
        SELECT c.tile AS tile, c.claimed_at AS claimed_at, ptc.user_id AS user_id
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
        SELECT bcap.tile, bcap.claimed_at, bcap.user_id
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
    return banners


@postgres
async def get_banners_between(banner_codes: List[str],
                              expire_from: datetime.datetime,
                              expire_to: datetime.datetime,
                              conn=None) -> List[Dict[str, Any]]:
    one_day = datetime.timedelta(days=1)
    banner_captures = """
            SELECT p.planner_channel AS planner_channel, c.tile AS tile, c.claimed_at AS claimed_at,
                    ptc.user_id AS user_id, p.ping_channel as ping_channel, p.ping_role AS ping_role
            FROM (claims c
            JOIN planners p
                ON c.channel = p.claims_channel)
            LEFT JOIN plannertileclaims ptc
                ON p.planner_channel = ptc.planner_channel AND c.tile = ptc.tile
            WHERE claimed_at >= $2
                AND claimed_at < $3
                AND c.tile = ANY($1::VARCHAR(3)[])
            ORDER BY c.claimed_at ASC
        """

    banners = await conn.fetch(f"""
            SELECT bcap.planner_channel, bcap.tile, bcap.claimed_at, bcap.user_id, bcap.ping_channel,
                    bcap.ping_role
            FROM ({banner_captures}) bcap
            WHERE claimed_at = (
                SELECT MAX(claimed_at)
                FROM ({banner_captures}) bcap2
                WHERE bcap.tile = bcap2.tile
            ) AND (
                (SELECT clear_time FROM planners WHERE planner_channel = bcap.planner_channel) IS NULL
                OR claimed_at >= (SELECT clear_time FROM planners WHERE planner_channel = bcap.planner_channel)
            )
        """, banner_codes, expire_from-one_day, expire_to-one_day)
    return banners


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
async def get_planner_linked_to(tile_claim_ch: int, conn=None) -> int or None:
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
