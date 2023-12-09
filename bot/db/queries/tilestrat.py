import time
import bot.db.connection
from bot.db.model.Tilestrat import Tilestrat
import bot.utils.bloons
postgres = bot.db.connection.postgres


@postgres
async def get_tile_strat_forum(guild_id: int, conn=None) -> int:
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
async def del_tile_strat_forum(guild_id: int, soft_delete: bool = True, conn=None) -> None:
    if not soft_delete:
        await conn.execute(
            "DELETE FROM tilestratthreads "
            "WHERE forum_id=(SELECT forumid FROM tilestratforums WHERE guildid=$1)", guild_id)
    await conn.execute("DELETE FROM tilestratforums WHERE guildid=$1", guild_id)


@postgres
async def create_tilestrat(
        forum_id: int,
        thread_id: int,
        tile_code: str,
        event_num: int,
        challenge_type: int,
        boss: int or None,
        conn=None) -> Tilestrat:
    await conn.execute("""
        INSERT INTO tilestratthreads(forum_id, thread_id, tile_code, event_num, challenge_type, boss)
        VALUES ($1, $2, $3, $4, $5, $6)
    """, forum_id, thread_id, tile_code, event_num, challenge_type, boss)
    return Tilestrat(forum_id, thread_id, tile_code, event_num, challenge_type, boss)


@postgres
async def get_tilestrats(tile_code: str, forum_id: int, conn=None) -> list[Tilestrat]:
    results = await conn.fetch("""
        SELECT thread_id, event_num, challenge_type, boss
        FROM tilestratthreads
        WHERE forum_id=$1
            AND tile_code=$2
        ORDER BY event_num ASC
    """, forum_id, tile_code)
    return [
        Tilestrat(forum_id, r["thread_id"], tile_code, r["event_num"], r["challenge_type"], r["boss"])
        for r in results
    ]


@postgres
async def get_tilestrats_by_season(season: int, forum_id: int, conn=None) -> list[Tilestrat]:
    results = await conn.fetch("""
        SELECT thread_id, tile_code, challenge_type, boss
        FROM tilestratthreads
        WHERE forum_id=$1
            AND event_num=$2
    """, forum_id, season)
    return [
        Tilestrat(forum_id, r["thread_id"], r["tile_code"], season, r["challenge_type"], r["boss"])
        for r in results
    ]


@postgres
async def del_tilestrat(thread_id: int, conn=None) -> None:
    await conn.execute("DELETE FROM tilestratthreads WHERE thread_id=$1", thread_id)
