from typing import List, Tuple
import bot.exceptions
import discord
import asyncio
from discord.ext import commands


async def update_messages(
        bot: discord.ClientUser,
        content: List[Tuple[str, discord.ui.View or None]],
        channel: discord.TextChannel) -> None:
    """Edits a bunch of messages to reflect some new content. If other users
    sent messages in the channel in the meanwhile, it deletes its own old messages
    and send the whole thing again, to make sure it's always the newest message sent.

    :param bot: The bot user.
    :param content: A list of messages to send and possibly a View or None.
    :param channel: The channel to send the message to.
    """
    messages_to_change = []
    bot_messages = []
    modify = True
    async for message in channel.history(limit=25):
        if message.author == bot:
            if modify:
                messages_to_change.insert(0, message)
            bot_messages.append(message)
            if len(content) < len(messages_to_change):
                modify = False
                messages_to_change = []
        elif len(content) != len(messages_to_change):
            messages_to_change = []
            modify = False
    if len(messages_to_change) != len(content):
        modify = False

    if modify:
        coros = []
        for i in range(len(content)):
            new_content, new_view = content[i]
            if new_view is None:
                new_view = discord.ui.View()
            if messages_to_change[i].content != new_content or not \
                    (len(messages_to_change[i].components) == len(new_view.to_components()) == 0):
                coros.append(messages_to_change[i].edit(content=new_content, view=new_view))
        await asyncio.gather(*coros)
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
