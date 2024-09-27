import asyncpg
import config
from bot.utils.colors import red, purple
from functools import wraps

pool: asyncpg.Pool | None


async def start():
    global pool
    try:
        pool = await asyncpg.create_pool(
            user=config.DB_USER, password=config.DB_PSWD,
            database=config.DB_NAME, host=config.DB_HOST
        )
        print(f"{purple('[PSQL]')} Connected")
    except:
        print(f"{purple('[PSQL]')} {red('Error connecting to Postgres database')}")


def postgres(wrapped):
    @wraps(wrapped)
    async def wrapper(*args, **kwargs):
        if "conn" in kwargs:
            return await wrapped(*args, **kwargs)

        if pool is None:
            return
        async with pool.acquire() as conn:
            return await wrapped(*args, **kwargs, conn=conn)
    return wrapper


