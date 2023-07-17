import time
import bot.db.connection
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
async def del_tile_strat_forum(guild_id: int, conn=None) -> None:
    await conn.execute("DELETE FROM tilestratforums WHERE guildid=$1", guild_id)
