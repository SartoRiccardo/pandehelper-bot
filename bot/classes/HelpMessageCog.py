import re
from discord.ext import commands


class HelpMessageCog(commands.Cog):
    has_help_msg: bool = True
    help_descriptions: dict[str or None, str or dict[str, str]] = {}

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def help_message(self) -> str:
        message = []
        if None in self.help_descriptions.keys():
            message.append(self.help_descriptions[None])

        for cmd_name in self.help_descriptions:
            cmd = await self.bot.get_app_command(cmd_name)
            if cmd is None:
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
