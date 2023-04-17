import time
import datetime
import bot.db.connection
import bot.utils.bloons
from typing import List, Dict, Tuple
from .model.TileCapture import TileCapture
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
async def get_oak(user: int, conn=None) -> str or None:
    payload = await conn.fetch("SELECT oak FROM btd6players WHERE userid=$1", user)
    return payload[0]["oak"] if len(payload) > 0 else None


@postgres
async def set_oak(user: int, oak: str, conn=None) -> None:
    saved_oak = await get_oak(user)
    if saved_oak:
        await conn.execute("UPDATE btd6players SET oak=$2 WHERE userid=$1", user, oak)
    else:
        await conn.execute("INSERT INTO btd6players(userid, oak) VALUES ($1, $2)", user, oak)


@postgres
async def get_tile_strat_forum(guild_id: int, conn=None) -> int or None:
    payload = await conn.fetch("SELECT forumid FROM tilestratforums WHERE guildid=$1", guild_id)
    return payload[0]["forumid"] if len(payload) > 0 else None


@postgres
async def set_tile_strat_forum(guild_id: int, forum_id: int, conn=None) -> None:
    saved_forum_id = await get_tile_strat_forum(guild_id)
    if saved_forum_id:
        await conn.execute("UPDATE tilestratforums SET forumid=$2 WHERE guildid=$1", guild_id, forum_id)
    else:
        await conn.execute("INSERT INTO tilestratforums(guildid, forumid) VALUES ($1, $2)", guild_id, forum_id)


@postgres
async def del_tile_strat_forum(guild_id: int, conn=None) -> None:
    await conn.execute("DELETE FROM tilestratforums WHERE guildid=$1", guild_id)
