import discord
import bot.db.connection
from discord.ext import commands
from config import TOKEN, APP_ID


class CtTicketTracker(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(
            command_prefix=",,,",
            intents=intents,
            application_id=APP_ID
        )

    async def setup_hook(self):
        await bot.db.connection.start()
        cogs = ["OwnerCog", "TrackerCog", "LeaderboardCog", "RaidLogCog", "UtilsCog"]
        for cog in cogs:
            await self.load_extension(f"bot.cogs.{cog}")


if __name__ == '__main__':
    CtTicketTracker().run(TOKEN)
