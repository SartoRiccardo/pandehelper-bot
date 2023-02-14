import discord
import importlib
from discord.ext import commands
from typing import Optional, Literal


SUCCESS_REACTION = '\N{THUMBS UP SIGN}'


class OwnerCog(commands.Cog):
    ERROR_MESSAGE = "**ERROR:** {} - {}"

    def __init__(self, bot):
        self.bot = bot

    def cog_unload(self):
        pass

    @commands.command()
    @commands.is_owner()
    async def sync(self, ctx, where: Optional[Literal["."]] = None):
        if where == ".":
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        else:
            synced = await ctx.bot.tree.sync()
        await ctx.send(f"Synced {len(synced)} commands ({'globally' if where is None else 'here'}).")

    @commands.group()
    @commands.is_owner()
    async def cog(self, ctx):
        if ctx.invoked_subcommand is None:
            pass

    @cog.command(aliases=["add"])
    @commands.is_owner()
    async def load(self, ctx, name):
        try:
            await self.bot.load_extension(f"ct_ticket_tracker.cogs.{name}Cog")
            await ctx.message.add_reaction(SUCCESS_REACTION)
        except Exception as e:
            await ctx.send(self.ERROR_MESSAGE.format(type(e).__name__, e))

    @cog.command(aliases=["remove"])
    @commands.is_owner()
    async def unload(self, ctx, name):
        try:
            if f"ct_ticket_tracker.cogs.{name}Cog" != __name__:
                await self.bot.unload_extension(f"ct_ticket_tracker.cogs.{name}Cog")
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
            await self.bot.unload_extension(f"ct_ticket_tracker.cogs.{name}Cog")
            await self.bot.load_extension(f"ct_ticket_tracker.cogs.{name}Cog")
            await ctx.message.add_reaction(SUCCESS_REACTION)
        except Exception as e:
            await ctx.send(self.ERROR_MESSAGE.format(type(e).__name__, e))

    @cog.command(alias=["list"])
    @commands.is_owner()
    async def list(self, ctx):
        cogs = [str_cog for str_cog in self.bot.cogs]
        await ctx.send("Loaded cogs: " + ", ".join(cogs))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OwnerCog(bot))