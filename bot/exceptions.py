import discord


class WrongChannelMention(Exception):
    pass


class MustBeForum(Exception):
    pass


class NotACommunity(Exception):
    pass


class TilestratForumNotFound(Exception):
    pass


class Gatekept(discord.app_commands.errors.CheckFailure):
    pass


class UnknownTile(Exception):
    def __init__(self, tile: str):
        self.tile = tile

