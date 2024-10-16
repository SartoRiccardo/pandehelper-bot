import time
import datetime
import bot.db.connection
import bot.utils.bloons
from ..model.TileCapture import TileCapture
postgres = bot.db.connection.postgres
bloons = bot.utils.bloons


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
async def get_ticket_overview(channel: int, event: int = 0, conn=None) -> dict[int, list[list[TileCapture]]]:
    if event == 0:
        event = bloons.get_ct_number_during(datetime.datetime.now())
    event_start, event_end = bloons.get_ct_period_during(event=event)
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
async def get_tickets_from(member_id: int, channel: int, event: int = 0, conn=None) -> list[list[TileCapture]]:
    if event == 0:
        event = bloons.get_ct_number_during(datetime.datetime.now())
    event_start, event_end = bloons.get_ct_period_during(event=event)
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
async def tracked_channels(conn=None) -> list[int]:
    payload = await conn.fetch("SELECT channel FROM teams")
    channels = [row["channel"] for row in payload]
    return channels


@postgres
async def is_channel_tracked(channel_id: int, conn=None) -> bool:
    payload = await conn.fetch("SELECT channel FROM teams WHERE channel = $1", channel_id)
    return len(payload) > 0


@postgres
async def call_tile(
        channel: int,
        tile: str,
        message: int,
        user: int = None,
        edit: bool = False,
        conn=None
) -> None:
    if not edit:
        await conn.execute(
            """
            INSERT INTO claims (userid, tile, channel, message)
            VALUES ($1, $2, $3, $4)
            """,
            user, tile, channel, message,
        )
    else:
        await conn.execute(
            """
            UPDATE claims
            SET tile=$1
            WHERE claimed_at IS NULL
                AND message = $2
            """,
            tile, message,
        )


@postgres
async def is_tile_called(
        channel: int,
        tile: str,
        ignore_user: int,
        minutes_back: int = 90,
        conn=None
) -> bool:
    result = await conn.fetchrow(
        """
        SELECT COUNT(*) > 0 AS is_called
        FROM claims
        WHERE channel = $1
            AND tile = $2
            AND claimed_at IS NULL
            AND userid != $4
            AND called_at >= CURRENT_TIMESTAMP - $3 * INTERVAL '1 minute'
        """,
        channel, tile, minutes_back, ignore_user,
    )
    return result["is_called"]


@postgres
async def delete_claim(message: int, conn=None) -> None:
    await conn.execute(
        """
        DELETE FROM claims
        WHERE message = $1
        """,
        message,
    )


@postgres
async def capture(
        message: int,
        channel: int = None,
        tile: str = None,
        user: int = None,
        conn=None
) -> None:
    if channel and tile and user:
        await conn.execute(
            """
            INSERT INTO claims (userid, tile, channel, message, claimed_at)
            VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
            """,
            user, tile, channel, message,
        )
    else:
        await conn.execute(
            """
            UPDATE claims
            SET claimed_at = NOW()
            WHERE message = $1
            """,
            message,
        )


@postgres
async def uncapture(message: int, conn=None) -> None:
    await conn.execute(
        """
        UPDATE claims
        SET claimed_at = NULL
        WHERE message = $1
        """,
        message,
    )


@postgres
async def get_capture_by_message(message: int, conn=None) -> TileCapture or None:
    payload = await conn.fetch(
        """SELECT * FROM claims WHERE message=$1""",
        message,
    )
    if len(payload) == 0:
        return None

    return TileCapture(payload[0]["userid"], payload[0]["tile"], payload[0]["channel"], payload[0]["message"],
                       payload[0]["claimed_at"])


@postgres
async def get_tile_claims(tile: str, channel: int, event: int = 0, conn=None) -> list[TileCapture]:
    if event == 0:
        event_start, event_end = bloons.get_current_ct_period()
    else:
        event_start, event_end = bloons.get_ct_period_during(event=event)
    tiles = await conn.fetch("""
        SELECT * FROM CLAIMS
        WHERE channel=$1
          AND tile=$2
          AND claimed_at >= $3
          AND claimed_at <= $4
        ORDER BY claimed_at ASC
    """, channel, tile, event_start, event_end)
    return [TileCapture(r["userid"], tile, channel, r["message"], r["claimed_at"]) for r in tiles]
