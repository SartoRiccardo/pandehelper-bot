import discord
from discord.ext import commands
from bot.cogs.OwnerCog import is_owner
import bot.db.connection
import bot.db.queries.tilestrat


SUCCESS_REACTION = '\N{THUMBS UP SIGN}'
str_to_chal_type = {"Least Cash": 8, "Least Tiers": 9, "Race": 2}
str_to_boss = {"Bloonarius": 0, "Lych": 1, "Vortex": 2, "Dreadbloon": 3, "Phayze": 4}


@bot.db.connection.postgres
async def get_all_forums(conn=None):
    return await conn.fetch("SELECT * FROM tilestratforums")


class MigrateCog(commands.Cog):
    """
    These commands are to be used by YOU, the hoster & owner of the bot, in case a bot update
    changes stuff so much that just pulling from the repo & adding some PSQL tables isn't enough.

    The cog isn't loaded by default.
    None of these are slash commands. Just run, for example, `,,,migrate_121_130` to run that function.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    @is_owner()
    async def migrate_121_130(self, ctx: discord.ext.commands.Context) -> None:
        """
        Migrates from <1.3.0 to >=1.3.0

        Previously the bot just looked at the forum channel and fetched all the threads to
        get the data for /tilestrat and similar commands. Now it uses a psql database.
        You don't HAVE to run this function, if you don't all that's gonna happen is your old
        strategy threads will be no longer visible by the bot. If you care about that, run it,
        if you don't, don't.
        """

        await ctx.send(f"Migrating threads to the PSQL tables. Check the console for more detail.")
        tilestratforums = await get_all_forums()
        print(f"START! Migrate 1.2.1 -> 1.3.0")
        for tsf in tilestratforums:
            guild = discord.utils.get(self.bot.guilds, id=tsf["guildid"])
            if guild is None:
                try:
                    guild = await self.bot.fetch_guild(tsf["guildid"])
                except (discord.NotFound, discord.Forbidden):
                    print(f"> Guild {tsf['guildid']} invalid (left server or deleted)")
                    continue

            forum = guild.get_channel(tsf["forumid"])
            if forum is None:
                try:
                    forum = await guild.fetch_channel(tsf["forumid"])
                except (discord.NotFound, discord.Forbidden):
                    print(f"> Forum {tsf['forumid']} invalid (no access or deleted)")
                    continue

            print(f"> Migrating {guild.id}-{forum.id}...")

            for t in forum.threads:
                if t.owner != self.bot.user:
                    continue
                await self.parse_thread(t, forum)

            async for t in forum.archived_threads(limit=None):
                if t.owner != self.bot.user:
                    continue
                await self.parse_thread(t, forum)

        print(f"END!   Migrate 1.2.1 -> 1.3.0")
        await ctx.send("Done!")

    async def parse_thread(self, thread: discord.Thread, forum: discord.ForumChannel) -> None:
            event_num = 0
            chal_type = 0
            boss = None
            for tag in thread.applied_tags:
                if tag.name in str_to_boss:
                    boss = str_to_boss[tag.name]
                elif tag.name in str_to_chal_type:
                    chal_type = str_to_chal_type[tag.name]
                elif tag.name.startswith("Season "):
                    event_num = int(tag.name[-2:])

            try:
                await bot.db.queries.tilestrat.create_tilestrat(
                    forum.id, thread.id, thread.name[-3:].upper(), event_num, chal_type, boss
                )
            except:
                pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MigrateCog(bot))
