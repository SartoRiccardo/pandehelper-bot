import discord
import db.connection
from discord.ext import commands
from config import TOKEN


class CtForumBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=",,,",
            intents=intents
        )

    async def setup_hook(self):
        await db.connection.start()
        await self.load_extension("cogs.owner")
        await self.load_extension("cogs.cog_tracker")
        await self.load_extension("cogs.cog_leaderboard")


if __name__ == '__main__':
    CtForumBot().run(TOKEN)
