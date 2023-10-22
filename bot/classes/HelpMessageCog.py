import re
from discord.ext import commands
from typing import Dict, Union


class HelpMessageCog(commands.Cog):
    has_help_msg: bool = True
    help_descriptions: Dict[str or None, Union[str, Dict[str, str]]] = {}

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def help_message(self) -> str:
        if not hasattr(self.bot, "synced_tree"):
            self.bot.synced_tree = await self.bot.tree.fetch_commands()

        message = []
        if None in self.help_descriptions.keys():
            message.append(self.help_descriptions[None])

        for cmd in self.bot.synced_tree:
            if cmd.name not in self.help_descriptions.keys():
                continue

            if isinstance(self.help_descriptions[cmd.name], str):
                message.append(f"🔸 </{cmd.name}:{cmd.id}>\n{self.help_descriptions[cmd.name]}")
            else:
                for subcommand in self.help_descriptions[cmd.name]:
                    desc = self.help_descriptions[cmd.name][subcommand]
                    desc = re.sub(r"\[\[(\w+)]]", lambda match: f"</{cmd.name} {match.group(1)}:{cmd.id}>", desc)
                    message.append(f"🔸 </{cmd.name} {subcommand}:{cmd.id}>\n{desc}")
        if len(message) == 0:
            return "No help message written for this module! Yell at the maintainer."
        return "\n\n".join(message)
