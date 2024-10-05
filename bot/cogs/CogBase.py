import re
import os
import json
import discord
import asyncio
import aiofiles
from typing import Any
from config import DATA_PATH
from datetime import datetime
from discord.ext import commands
from bot.utils.discordutils import handle_error


class CogBase(commands.Cog):
    has_help_msg: bool = True
    help_descriptions: dict[str | None, str | dict[str, str]] = {}

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

    async def cog_app_command_error(
            self,
            interaction: discord.Interaction,
            error: discord.app_commands.AppCommandError
    ) -> None:
        await handle_error(interaction, error)

    async def cog_load(self) -> None:
        await self._load_state()

    async def cog_unload(self) -> None:
        await self._save_state()

    @staticmethod
    def __state_path(cog_name):
        path = os.path.join(DATA_PATH, "cogstate")
        if not os.path.exists(path):
            os.mkdir(path)
        return os.path.join(path, f"{cog_name}.json")

    @staticmethod
    async def __save_cog_state(cog_name: str, state: dict[str, Any]) -> None:
        data = json.dumps({
            "saved_at": datetime.now().timestamp(),
            "data": state,
        })
        async with aiofiles.open(CogBase.__state_path(cog_name), "w") as fout:
            await fout.write(data)

    @staticmethod
    async def __get_cog_state(cog_name: str) -> dict[str, Any] or None:
        if not os.path.exists(CogBase.__state_path(cog_name)):
            return None
        async with aiofiles.open(CogBase.__state_path(cog_name)) as fin:
            data = json.loads(await fin.read())
            return data

    async def _save_state(self) -> None:
        await self.__save_cog_state(
            self.qualified_name,
            await self.serialize_state(),
        )

    async def _load_state(self) -> None:
        state = await self.__get_cog_state(self.qualified_name)
        if state is None:
            return
        await self.parse_state(
            datetime.fromtimestamp(state["saved_at"]),
            state["data"]
        )

    async def serialize_state(self) -> dict[str, Any]:
        """
        Override
        Turns all state variables into a valid JSON object
        """
        return {}

    async def parse_state(self, saved_at: datetime, state: dict[str, Any]) -> None:
        """
        Override
        Sets instance variables with the passed JSON object.
        """
        pass
