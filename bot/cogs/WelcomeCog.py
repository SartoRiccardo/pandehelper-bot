import string
import discord
from discord.ext import commands
from bot.classes import ErrorHandlerCog


class WelcomeCog(ErrorHandlerCog):
    WAITING_ROOM_NAME = "🫵・challenger-{}"
    PANDEMONIUM_GID = 860146839181459466
    RECRUITMENT_CID = 1005681268844924958
    WELCOME_MSG = "Welcome, <@{}>! Please check out <#1102652581026725970>"

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await self.create_waiting_room(member)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if len(before.roles) == 1 and len(after.roles) > 1:
            await self.remove_waiting_room(after)
        elif len(before.roles) > 1 and len(after.roles) == 1:
            await self.create_waiting_room(after)

    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent) -> None:
        if payload.guild_id != self.PANDEMONIUM_GID:
            return
        await self.remove_waiting_room(payload.user, guild_id=payload.guild_id)

    async def create_waiting_room(self, member: discord.Member) -> None:
        if member.guild.id != self.PANDEMONIUM_GID:
            return
        pandemonium = member.guild
        recruitment_category = discord.utils.get(pandemonium.categories, id=self.RECRUITMENT_CID)
        if recruitment_category is None:
            return

        new_ch = await recruitment_category.create_text_channel(
            self.WAITING_ROOM_NAME.format(self.username_to_text_channel(member.name)),
            topic=str(member.id),
            overwrites={
                **recruitment_category.overwrites,
                pandemonium.default_role: discord.PermissionOverwrite(read_messages=False),
                member: discord.PermissionOverwrite(read_messages=True),
            }
        )
        await new_ch.send(self.WELCOME_MSG.format(member.id))

    async def remove_waiting_room(self, member: discord.Member | discord.User, guild_id: int = None) -> None:
        if member.guild.id != PANDEMONIUM_GID:
            return

        if isinstance(member, discord.Member):
            pandemonium = member.guild
        elif guild_id is not None:
            pandemonium = self.bot.get_guild(guild_id)
            if pandemonium is None:
                pandemonium = self.bot.fetch_guild(guild_id)
        else:
            return

        recruitment_category = discord.utils.get(pandemonium.categories, id=RECRUITMENT_CID)
        if recruitment_category is None:
            return
        for channel in recruitment_category.text_channels:
            if channel.topic == str(member.id):
                await channel.delete()
                return

    @staticmethod
    def username_to_text_channel(username: str) -> str:
        username = username.lower()
        filtered = ""
        keep = string.ascii_lowercase + string.digits
        for letter in username:
            if letter in keep:
                filtered += letter
        return filtered


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeCog(bot))
