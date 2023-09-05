import discord
from datetime import datetime
import bot.db.connection
from bot import __version__
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
            application_id=APP_ID,
            activity=discord.Game(name="/help"),
        )
        self.remove_command("help")
        self.version = __version__
        self.last_restart = datetime.now()

    async def setup_hook(self):
        await bot.db.connection.start()
        cogs = [
            "OwnerCog",
            "TrackerCog",
            "LeaderboardCog",
            "RaidLogCog",
            "UtilsCog",
            #"VerifyCog",
            "PlannerCog",
            "WelcomeCog",
            "TilesCog",
        ]
        for cog in cogs:
            await self.load_extension(f"bot.cogs.{cog}")

    def reload_version(self):
        with open("bot/__init__.py") as fin:
            for ln in fin:
                ln = ln.strip()
                if ln.startswith("__version__ = \""):
                    self.version = ln[len("__version__ = \""):-1]
                    return


if __name__ == '__main__':
    CtTicketTracker().run(TOKEN)
