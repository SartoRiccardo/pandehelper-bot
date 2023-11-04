import time
import bot.db.connection
import bot.utils.bloons
from ..model.Oak import Oak
postgres = bot.db.connection.postgres


@postgres
async def get_oaks(user: int, conn=None) -> list[Oak]:
    payload = await conn.fetch("""
        SELECT oak, is_main
        FROM btd6players
        WHERE userid=$1
        ORDER BY
            is_main DESC,
            oak
    """, user)
    return [Oak(row["oak"], row["is_main"]) for row in payload]


async def get_main_oak(user: int) -> Oak:
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
