import time
import pytz
import datetime
import db.connection
from typing import List, Dict
postgres = db.connection.postgres


FIRST_CT_START = datetime.datetime.strptime('2022-08-10 10', '%Y-%m-%d %H')
EVENT_DURATION = 7


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
async def get_ticket_overview(channel: int, event: int = 0, conn=None):
    if event > 0:
        event_start = FIRST_CT_START + datetime.timedelta(days=14*(event-1))
    else:  # Current or last event
        event_start = FIRST_CT_START
        now = datetime.datetime.now()
        while event_start + datetime.timedelta(days=14) < now:
            event_start += datetime.timedelta(days=14)
    event_end = event_start + datetime.timedelta(days=EVENT_DURATION)
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
            claims[uid] = [0] * EVENT_DURATION
        day = (record["claimed_at"] - event_start).days
        if 0 <= day < EVENT_DURATION:
            claims[uid][day] += 1
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
