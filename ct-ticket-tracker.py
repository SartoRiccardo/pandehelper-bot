import discord
import ct_ticket_tracker.db.connection
from discord.ext import commands
from config import TOKEN, APP_ID


class CtForumBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=",,,",
            intents=intents,
            application_id=APP_ID
        )

    async def setup_hook(self):
        await ct_ticket_tracker.db.connection.start()
        await self.load_extension("ct_ticket_tracker.cogs.owner")
        await self.load_extension("ct_ticket_tracker.cogs.cog_tracker")
        await self.load_extension("ct_ticket_tracker.cogs.cog_leaderboard")


if __name__ == '__main__':
    CtForumBot().run(TOKEN)
