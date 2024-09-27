import time
import datetime
import bot.db.connection
import bot.utils.bloons
from typing import Any, Literal
from ..model.Planner import Planner
from ..model.PlannedTile import PlannedTile
postgres = bot.db.connection.postgres
bloons = bot.utils.bloons


@postgres
async def get_planners(only_active: bool = False, conn=None) -> list[Planner]:
    only_active_q = " WHERE is_active" if only_active else ""
    planners = await conn.fetch("SELECT * FROM planners" + only_active_q)
    return [Planner(row["planner_channel"], row["claims_channel"], row["ping_role"], row["ping_role_with_tickets"],
                    row["ping_channel"], row["clear_time"], row["is_active"])
            for row in planners]


@postgres
async def get_planner(planner_id: int, conn=None) -> Planner or None:
    results = await conn.fetch("""
        SELECT *
        FROM planners
        WHERE planner_channel=$1
    """, planner_id)
    return Planner(results[0]["planner_channel"], results[0]["claims_channel"], results[0]["ping_role"],
                   results[0]["ping_role_with_tickets"], results[0]["ping_channel"], results[0]["clear_time"],
                   results[0]["is_active"]) \
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
async def get_planned_tiles(planner_channel: int,
                            tile_codes: list[str],
                            expire_between: tuple[datetime.datetime, datetime.datetime] = None,
                            claimed_status: Literal["UNCLAIMED", "CLAIMED", "ANY"] = "ANY",
                            conn=None) -> list[PlannedTile]:
    event_start, _event_end = bloons.get_current_ct_period()
    tile_captures = """
        SELECT c.tile, c.claimed_at, ptc.user_id, p.claims_channel, p.ping_role, p.ping_channel, p.planner_channel,
            ptt.expires_after_hr, c.claimed_at + MAKE_INTERVAL(hours => ptt.expires_after_hr) AS expires_at
        FROM (
            claims c JOIN planners p ON c.channel = p.claims_channel
            JOIN plannertrackedtiles ptt
                ON ptt.planner_channel = p.planner_channel
                    AND ptt.tile = c.tile
            ) LEFT JOIN plannertileclaims ptc
                ON p.planner_channel = ptc.planner_channel AND c.tile = ptc.tile
        WHERE p.planner_channel = $3
            AND c.claimed_at >= $1
            AND c.tile = ANY($2::VARCHAR(3)[])
        ORDER BY expires_at ASC
    """

    extra_args = []
    q_between = ""
    if expire_between is not None:
        q_between = f"""
            AND expires_at >= ${len(extra_args) + 4}
            AND expires_at < ${len(extra_args) + 5}
        """
        extra_args.append(expire_between[0])
        extra_args.append(expire_between[1])
    q_claim = ""
    if claimed_status == "UNCLAIMED":
        q_claim = "AND tcap.user_id IS NULL"
    elif claimed_status == "CLAIMED":
        q_claim = "AND tcap.user_id IS NOT NULL"

    banners = await conn.fetch(f"""
        SELECT *
        FROM ({tile_captures}) tcap
        WHERE claimed_at = (
            SELECT MAX(claimed_at)
            FROM ({tile_captures}) tcap2
            WHERE tcap.tile = tcap2.tile
        ) AND (
            (SELECT clear_time FROM planners WHERE planner_channel = $3) IS NULL
            OR claimed_at >= (SELECT clear_time FROM planners WHERE planner_channel = $3)
        )
        {q_between}
        {q_claim}
    """, event_start, tile_codes, planner_channel, *extra_args)
    return [PlannedTile(row["tile"], row["claimed_at"], row["user_id"], row["planner_channel"], row["claims_channel"],
                        row["ping_role"], row["ping_channel"], row["expires_after_hr"])
            for row in banners]


@postgres
async def get_tile_closest_to_expire(from_date: datetime.datetime,
                                     conn=None) -> list[PlannedTile]:
    # Latest expire for every tile for every claim channel
    latest_expire = f"""
        SELECT channel, tile, MAX(claimed_at) as claimed_at
        FROM claims
        GROUP BY (channel, tile)
    """

    # Earliest expire for each planner
    earliest_expire = f"""
        SELECT p.planner_channel, MIN(c.claimed_at + MAKE_INTERVAL(hours => ptt.expires_after_hr)) AS expires_at
        FROM (
            ({latest_expire}) c JOIN planners p ON c.channel = p.claims_channel
            JOIN plannertrackedtiles ptt
                ON ptt.planner_channel = p.planner_channel
                    AND ptt.tile = c.tile
            )
            LEFT JOIN plannertileclaims ptc
                ON p.planner_channel = ptc.planner_channel AND c.tile = ptc.tile
        WHERE c.claimed_at + MAKE_INTERVAL(hours => ptt.expires_after_hr) >= $1
        GROUP BY(p.planner_channel)
    """

    latest_tile_captures = f"""
        SELECT eexp.expires_at, p.planner_channel, c.tile, p.claims_channel, ptc.user_id, p.ping_channel, p.ping_role,
            c.claimed_at, ptt.expires_after_hr
        FROM ({earliest_expire}) AS eexp JOIN (
            claims c JOIN planners p ON c.channel = p.claims_channel
            JOIN plannertrackedtiles ptt
                ON ptt.planner_channel = p.planner_channel
                    AND ptt.tile = c.tile
            )
            LEFT JOIN plannertileclaims ptc
                ON p.planner_channel = ptc.planner_channel AND c.tile = ptc.tile
        ON eexp.expires_at = c.claimed_at + MAKE_INTERVAL(hours => ptt.expires_after_hr)
    """

    tiles = await conn.fetch(latest_tile_captures, from_date)
    return [PlannedTile(row["tile"], row["claimed_at"], row["user_id"], row["planner_channel"], row["claims_channel"],
                        row["ping_channel"], row["ping_role"], row["expires_after_hr"])
            for row in tiles]


@postgres
async def planner_claim_tile(user: int, tile: str, planner_channel: int, conn=None) -> None:
    await conn.execute("""
        INSERT INTO plannertileclaims(user_id, planner_channel, tile, claimed_at)
        VALUES($1, $2, $3, $4)
    """, user, planner_channel, tile, datetime.datetime.now())


@postgres
async def planner_unclaim_tile(tile: str, planner_channel: int, conn=None) -> None:
    await conn.execute("""
        DELETE FROM plannertileclaims WHERE planner_channel = $1 AND tile = $2
    """, planner_channel, tile)


async def planner_get_tile_status(tile: str, planner_channel: int) -> PlannedTile or None:
    tiles = await get_planned_tiles(planner_channel, [tile])
    return tiles[0] if len(tiles) else None


@postgres
async def planner_update_config(
        planner: int,
        ping_ch: int or None = None,
        ping_role: int or None = None,
        ping_role_with_tickets: int or None = None,
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
    if ping_role_with_tickets is not None:
        values.append(ping_role_with_tickets)
        fields.append(f"ping_role_with_tickets=${len(values)+1}")

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
        ping_role_with_tickets: bool = False,
        tile_claim_ch: bool = False,
        conn=None) -> None:
    fields = []
    if ping_ch is not None:
        fields.append(f"ping_channel=$2")
    if ping_role is not None:
        fields.append(f"ping_role=$2")
    if tile_claim_ch is not None:
        fields.append(f"claims_channel=$2")
    if ping_role_with_tickets is not None:
        fields.append(f"ping_role_with_tickets=$2")

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
async def get_claims_by(user: int, planner_channel: int, conn=None) -> list[dict[str, Any]]:
    event_start, _ee = bot.utils.bloons.get_current_ct_period()
    return await conn.fetch("""
        SELECT *
        FROM plannertileclaims
        WHERE user_id = $1
            AND planner_channel = $2
            AND claimed_at >= $3
            AND (
                (SELECT clear_time FROM planners WHERE planner_channel = $2) IS NULL OR
                claimed_at >= (SELECT clear_time FROM planners WHERE planner_channel = $2)
            )
    """, user, planner_channel, event_start)


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
    event_start, _event_end = bloons.get_current_ct_period()
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


@postgres
async def remove_tile_from_planner(planner_id: int, tile: str, conn=None) -> None:
    await conn.execute("""
        DELETE FROM plannertrackedtiles WHERE planner_channel=$2 AND tile=$1
    """, tile, planner_id)


@postgres
async def add_tile_to_planner(planner_id: int, tile: str, recap_after: int, conn=None) -> None:
    await remove_tile_from_planner(planner_id, tile)
    await conn.execute("""
        INSERT INTO plannertrackedtiles (tile, expires_after_hr, registered_at, planner_channel)
        VALUES ($1, $2, $3, $4)
    """, tile, recap_after, datetime.datetime.now(), planner_id)


@postgres
async def get_planner_tracked_tiles(planner_id: int, conn=None) -> list[str]:
    result = await conn.fetch("""
        SELECT tile FROM plannertrackedtiles WHERE planner_channel=$1
    """, planner_id)
    return [r["tile"] for r in result]


@postgres
async def overwrite_planner_tiles(planner_id: int, tiles: list[tuple[str, int]], conn=None) -> None:
    async with conn.transaction():
        await conn.execute(
            """
            DELETE FROM plannertrackedtiles
            WHERE planner_channel=$1
            """,
            planner_id,
        )
        await conn.executemany(
            """
            INSERT INTO plannertrackedtiles
                (tile, expires_after_hr, registered_at, planner_channel)
            VALUES ($1, $2, CURRENT_TIMESTAMP, $3)
            """,
            [(tile, expire, planner_id) for tile, expire in tiles]
        )
