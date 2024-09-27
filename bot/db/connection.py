import asyncpg
import config
from bot.utils.colors import red, purple

connection = None


async def start():
    global connection
    try:
        connection = await asyncpg.create_pool(
            user=config.DB_USER, password=config.DB_PSWD,
            database=config.DB_NAME, host=config.DB_HOST
        )
        print(f"{purple('[Postgres]')} Connected")
    except:
        print(f"{red('[Postgres]')} Error connecting")


def postgres(func):
    async def inner(*args, **kwargs):
        if connection is None:
            return
        return await func(*args, **kwargs, conn=connection)
    return inner


