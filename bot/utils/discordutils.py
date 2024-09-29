import bot.exceptions
import discord
import aiohttp
import aiofiles
import asyncio
from discord.ext import commands


async def update_messages(
        bot: discord.ClientUser,
        content: list[tuple[str, discord.ui.View or None]],
        channel: discord.TextChannel,
        tolerance: int = 10,
        delete_user_messages: bool = True) -> None:
    """Edits a bunch of messages to reflect some new content. If other users
    sent messages in the channel in the meanwhile, it deletes its own old messages
    and send the whole thing again, to make sure it's always the newest message sent.

    :param bot: The bot user.
    :param content: A list of messages to send and possibly a View or None.
    :param channel: The channel to send the message to.
    :param tolerance: How many non-bot messages it will tolerate before it decides to resend the whole thing.
    :param delete_user_messages: If True, it will delete user messages in the way. Only does so if it updates
                                 (so NOT if it resends) and will only delete the messages it "tolerated". So setting
                                 tolerance=0 turns this off as well.
    """
    messages_to_change = []
    bot_messages = []
    user_messages_delete = []
    modify = True
    tolerance_used = 0
    async for message in channel.history(limit=25):
        if message.author == bot:
            tolerance_used = tolerance+1  # If there's any more user messages after this, break.
            if modify:
                messages_to_change.insert(0, message)
            bot_messages.append(message)
            if len(content) < len(messages_to_change):
                modify = False
                messages_to_change = []
        else:
            if modify:
                tolerance_used += 1
            if delete_user_messages and tolerance_used <= tolerance:
                user_messages_delete.append(message)
            if len(content) != len(messages_to_change) and tolerance_used > tolerance:
                messages_to_change = []
                modify = False

    if len(messages_to_change) != len(content):
        modify = False

    if modify:
        coros = [m.delete() for m in user_messages_delete]
        for i in range(len(content)):
            new_content, new_view = content[i]
            if new_view is None:
                new_view = discord.ui.View()
            if messages_to_change[i].content != new_content or not \
                    (len(messages_to_change[i].components) == len(new_view.to_components()) == 0):
                await messages_to_change[i].edit(content=new_content, view=new_view)
                #coros.append(messages_to_change[i].edit(content=new_content, view=new_view))

        # Either the library doesnt handle 429s as it should or it doesn't work with asyncio.gather for some reason
        # await asyncio.gather(*coros)
        return

    coros = []
    for msg in bot_messages:
        coros.append(msg.delete())
    await asyncio.gather(*coros)

    for msg, view in content:
        await channel.send(content=msg, view=view)


def gatekeep():
    async def check(interaction: discord.Interaction) -> bool:
        has_access = False
        for role in interaction.user.roles:
            if role.id in [1005472018189271160,
                           1026966667345002517,
                           1011968628419207238,
                           860147253527838721,
                           940942269933043712]:
                has_access = True
                break
        if not has_access:
            raise bot.exceptions.Gatekept()
        return has_access
    return discord.app_commands.check(check)


def get_slash_command_id(bot: commands.Bot, command: str) -> int:
    if not hasattr(bot, "synced_tree"):
        return -1

    for cmd in bot.synced_tree:
        if cmd.name == command:
            return cmd.id
    return -1


async def download_file(session: aiohttp.ClientSession, url: str, path: str) -> None:
    async with session.get(url) as response:
        content = await response.read()
    async with aiofiles.open(path, mode="wb") as fout:
        await fout.write(content)


async def download_files(urls: list[str], paths: list[str]) -> None:
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*[download_file(session, url, paths[i]) for i, url in enumerate(urls)])


def composite_views(*views: discord.ui.View):
    new_view = discord.ui.View()
    for i, vw in enumerate(views):
        for item in vw.children:
            item.row = i
            new_view.add_item(item)
    return new_view
