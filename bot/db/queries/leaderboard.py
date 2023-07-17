import time
import bot.db.connection
import bot.utils.bloons
from typing import List
from ..model.LeaderboardChannel import LeaderboardChannel
postgres = bot.db.connection.postgres


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
async def leaderboard_channels(conn=None) -> List[LeaderboardChannel]:
    payload = await conn.fetch("SELECT guild, channel FROM lbchannels")
    return [LeaderboardChannel(row["guild"], row["channel"]) for row in payload]
