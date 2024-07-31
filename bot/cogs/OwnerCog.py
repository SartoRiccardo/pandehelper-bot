import discord
from discord.ext import commands
from typing import Literal
import config


SUCCESS_REACTION = '\N{THUMBS UP SIGN}'


def is_owner():
    async def predicate(ctx: discord.ext.commands.Context):
        return ctx.author.id in config.CO_OWNER_IDS or await ctx.bot.is_owner(ctx.author)

    return discord.ext.commands.check(predicate)


class OwnerCog(commands.Cog):
    ERROR_MESSAGE = "**ERROR:** {} - {}"
    COG_PATH_TEMPLATE = "bot.cogs.{}Cog"

    def __init__(self, bot):
        self.bot = bot

    def cog_unload(self) -> None:
        pass

    @commands.command()
    @is_owner()
    async def tasks(self, ctx: discord.ext.commands.Context) -> None:
        tasks = {}
        for cog_name in self.bot.cogs:
            for vname in vars(self.bot.cogs[cog_name]):
                task = getattr(self.bot.cogs[cog_name], vname)
                if not isinstance(task, discord.ext.tasks.Loop):
                    continue
                if cog_name not in tasks:
                    tasks[cog_name] = {}
                tasks[cog_name][vname] = task.is_running()
        msg = "**__Bot tasks:__**\n"
        for cog_name in tasks:
            msg += f"- **{cog_name}:**\n"
            for tname in tasks[cog_name]:
                msg += f"  - {'🟢' if tasks[cog_name][tname] else '🔴'} {tname}\n"
        await ctx.send(msg)

    @commands.command()
    @is_owner()
    async def sync(self, ctx: discord.ext.commands.Context, where: None or [Literal["."]] = None) -> None:
        if where == ".":
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        else:
            synced = await ctx.bot.tree.sync()
            self.bot.synced_tree = synced
        await ctx.send(f"Synced {len(synced)} commands ({'globally' if where is None else 'here'}).")

    @commands.group(aliases=["cogs"])
    @is_owner()
    async def cog(self, ctx: discord.ext.commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            cogs = [str_cog for str_cog in self.bot.cogs]
            await ctx.send("Loaded cogs: `" + "`, `".join(cogs) + "`")

    @cog.command(aliases=["add"])
    @is_owner()
    async def load(self, ctx: discord.ext.commands.Context, name: str) -> None:
        try:
            name = name[0].upper() + name[1:]
            cog_name = OwnerCog.COG_PATH_TEMPLATE.format(name)
            await self.bot.load_extension(cog_name)
            await ctx.message.add_reaction(SUCCESS_REACTION)
            self.bot.reload_version()
        except Exception as e:
            await ctx.send(self.ERROR_MESSAGE.format(type(e).__name__, e))

    @cog.command(aliases=["remove"])
    @is_owner()
    async def unload(self, ctx: discord.ext.commands.Context, name: str) -> None:
        try:
            name = name[0].upper() + name[1:]
            cog_name = OwnerCog.COG_PATH_TEMPLATE.format(name)
            if cog_name != __name__:
                await self.bot.unload_extension(cog_name)
                await ctx.message.add_reaction(SUCCESS_REACTION)
                self.bot.reload_version()
            else:
                await ctx.send(
                    f"You cannot unload the `{name}` cog. Did you mean `cog reload {name}`?"
                )
        except Exception as e:
            await ctx.send(self.ERROR_MESSAGE.format(type(e).__name__, e))

    @cog.command()
    @is_owner()
    async def reload(self, ctx: discord.ext.commands.Context, name: str) -> None:
        try:
            name = name[0].upper() + name[1:]
            cog_name = OwnerCog.COG_PATH_TEMPLATE.format(name)
            await self.bot.reload_extension(cog_name)
            await ctx.message.add_reaction(SUCCESS_REACTION)
            self.bot.reload_version()
        except Exception as e:
            await ctx.send(self.ERROR_MESSAGE.format(type(e).__name__, e))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OwnerCog(bot))
