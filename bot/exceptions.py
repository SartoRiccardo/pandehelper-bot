import discord


class MustBeForum(Exception):
    def formatted_exc(self) -> str:
        return "The channel must be a forum!"


class NotACommunity(Exception):
    def formatted_exc(self) -> str:
        return "You need to enable Community on your server to run this command!"


class TilestratForumNotFound(Exception):
    def formatted_exc(self) -> str:
        return "You don't have a Tile Strats forum set! " \
               "Run /tilestratforum create or /tilestratforum set to have one."


class Gatekept(discord.app_commands.errors.CheckFailure):
    def formatted_exc(self) -> str:
        return "<:hehe:1111026798210326719>"


class UnknownTile(Exception):
    def __init__(self, tile: str):
        self.tile = tile

    def formatted_exc(self) -> str:
        return f"Tile {self.tile} doesn't exist!"

