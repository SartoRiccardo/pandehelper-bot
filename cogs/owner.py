import discord
import importlib
from discord.ext import commands


SUCCESS_REACTION = '\N{THUMBS UP SIGN}'


class Owner(commands.Cog):
    ERROR_MESSAGE = "**ERROR:** {} - {}"

    def __init__(self, bot):
        self.bot = bot

    def cog_unload(self):
        pass

    @commands.group()
    @commands.is_owner()
    async def cog(self, ctx):
        if ctx.invoked_subcommand is None:
            pass

    @cog.command(aliases=["add"])
    @commands.is_owner()
    async def load(self, ctx, name):
        try:
            await self.bot.load_extension(f"cogs.cog_{name}")
            await ctx.message.add_reaction(SUCCESS_REACTION)
        except Exception as e:
            await ctx.send(self.ERROR_MESSAGE.format(type(e).__name__, e))

    @cog.command(aliases=["remove"])
    @commands.is_owner()
    async def unload(self, ctx, name):
        try:
            if f"cogs.cog_{name}" != __name__:
                await self.bot.unload_extension(f"cogs.cog_{name}")
                await ctx.message.add_reaction(SUCCESS_REACTION)
            else:
                await ctx.send(
                    f"You cannot unload the `{name}` cog. Did you mean `,cog reload {name}`?"
                )
        except Exception as e:
            await ctx.send(self.ERROR_MESSAGE.format(type(e).__name__, e))

    @cog.command()
    @commands.is_owner()
    async def reload(self, ctx, name):
        try:
            await self.bot.unload_extension(f"cogs.cog_{name}")
            await self.bot.load_extension(f"cogs.cog_{name}")
            await ctx.message.add_reaction(SUCCESS_REACTION)
        except Exception as e:
            await ctx.send(self.ERROR_MESSAGE.format(type(e).__name__, e))

    @cog.command(alias=["list"])
    @commands.is_owner()
    async def list(self, ctx):
        cogs = [str_cog for str_cog in self.bot.cogs]
        await ctx.send("Loaded cogs: " + ", ".join(cogs))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Owner(bot))