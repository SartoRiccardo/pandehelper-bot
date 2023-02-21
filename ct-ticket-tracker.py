import discord
import ct_ticket_tracker.db.connection
from discord.ext import commands
from config import TOKEN, APP_ID


class CtTicketTracker(commands.Bot):
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
        cogs = ["OwnerCog", "TrackerCog", "LeaderboardCog"]
        for cog in cogs:
            await self.load_extension(f"ct_ticket_tracker.cogs.{cog}")


if __name__ == '__main__':
    CtTicketTracker().run(TOKEN)
