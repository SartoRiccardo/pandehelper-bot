from typing import List, Tuple
import discord
import asyncio


async def update_messages(
        bot: discord.ClientUser,
        content: List[Tuple[str, discord.ui.View or None]],
        channel: discord.TextChannel) -> List[discord.Message]:
    """Edits a bunch of messages to reflect some new content. If other users
    sent messages in the channel in the meanwhile, it deletes its own old messages
    and send the whole thing again, to make sure it's always the newest message sent.

    :param bot: The bot user.
    :param content: A list of messages to send and possibly a View or None.
    :param channel: The channel to send the message to.
    :return: The messages sent or edited.
    """
    modify = True
    messages_to_change = []
    bot_messages = []
    async for message in channel.history(limit=25):
        if message.author == bot:
            messages_to_change.insert(0, message)
            bot_messages.append(message)
            if len(content) == len(messages_to_change):
                break
        else:
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
        return messages_to_change

    coros = []
    for msg in bot_messages:
        coros.append(msg.delete())
    await asyncio.gather(*coros)

    messages = []
    for msg, view in content:
        messages.append(await channel.send(content=msg, view=view))
    return messages
