import string
import discord
import asyncio
import bot.utils.io
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from bot.classes import ErrorHandlerCog


class WelcomeCog(ErrorHandlerCog):
    WAITING_ROOM_NAME = "🫵・challenger-{}"
    PANDEMONIUM_GID = 860146839181459466
    RECRUITMENT_CID = 1005681268844924958
    WELCOME_MSG = "Welcome, <@{}>! Please check out <#1102652581026725970>"
    VISITOR_ROLE_ID = 1005688667953692732
    VISITOR_AFTER = 7*24*60*60

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)
        self.waiting_rooms: dict[int, datetime] = {}

    async def cog_load(self) -> None:
        await self.load_state()
        self.check_inactive_rooms.start()

    def cog_unload(self) -> None:
        self.check_inactive_rooms.cancel()

    async def load_state(self) -> None:
        state = await asyncio.to_thread(bot.utils.io.get_cog_state, "welcome")
        if state is None:
            return

        data = state["data"]
        if "waiting_rooms" in data:
            self.waiting_rooms = {}
            for wr in data["waiting_rooms"]:
                self.waiting_rooms[wr["uid"]] = datetime.fromtimestamp(wr["expire"])

    async def save_state(self) -> None:
        data = {
            "waiting_rooms": [
                {"uid": uid, "expire": self.waiting_rooms[uid].timestamp()}
                for uid in self.waiting_rooms
            ],
        }
        await asyncio.to_thread(bot.utils.io.save_cog_state, "welcome", data)

    @tasks.loop(seconds=10)
    async def check_inactive_rooms(self) -> None:
        now = datetime.now()
        to_remove = []
        for uid in self.waiting_rooms:
            if self.waiting_rooms[uid] <= now:
                to_remove.append(uid)

        if len(to_remove) == 0:
            return

        pandemonium = await self.get_guild(self.PANDEMONIUM_GID)
        visitor_role = discord.utils.get(pandemonium.roles, id=self.VISITOR_ROLE_ID)
        for uid in to_remove:
            del self.waiting_rooms[uid]
            member = pandemonium.get_member(uid)
            if member is not None:
                await member.add_roles(visitor_role)
                try:
                    await member.send(
                        content="Hiiiii you haven't spoken in a week in the Juandemonium server (that one BTD6 team), "
                                "so it's probably safe to assume you don't really wanna join the team.\n"
                                "You've been assigned the Visitor role instead. Have fun!"
                    )
                except:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        member = message.author
        if member.id in self.waiting_rooms and message.channel.topic == str(member.id):
            self.waiting_rooms[member.id] = datetime.now() + timedelta(seconds=self.VISITOR_AFTER)

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
        self.waiting_rooms[member.id] = datetime.now() + timedelta(seconds=self.VISITOR_AFTER)
        await new_ch.send(self.WELCOME_MSG.format(member.id))

    async def remove_waiting_room(self, member: discord.Member | discord.User, guild_id: int = None) -> None:
        if member.guild.id != self.PANDEMONIUM_GID:
            return

        if isinstance(member, discord.Member):
            pandemonium = member.guild
        elif guild_id is not None:
            pandemonium = await self.get_guild(guild_id)
        else:
            return

        recruitment_category = discord.utils.get(pandemonium.categories, id=self.RECRUITMENT_CID)
        if recruitment_category is None:
            return
        for channel in recruitment_category.text_channels:
            if channel.topic == str(member.id):
                await channel.delete()
                if member.id in self.waiting_rooms:
                    del self.waiting_rooms[member.id]
                return

    async def get_guild(self, guild_id: int) -> discord.Guild:
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            guild = await self.bot.fetch_guild(guild_id)
        return guild

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
