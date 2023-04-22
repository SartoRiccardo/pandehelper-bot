import discord
from typing import List, Tuple, Callable
import bloonspy
import bot.db.queries


class AccountSelect(discord.ui.Select):
    def __init__(self, users: List[Tuple[bloonspy.btd6.User, str]], callback: Callable = None):
        options = [
            discord.SelectOption(label=user.name)
            for user, _oak in users

        ]
        self.callback_func = callback
        super().__init__(
            placeholder="Select an account",
            options=options
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.callback_func:
            await self.callback_func(interaction, self.values[0])


class AccountUnverifyView(discord.ui.View):
    def __init__(self,
                 users: List[Tuple[bloonspy.btd6.User, str]],
                 func_delete_user: Callable,
                 timeout: float = 180):
        super().__init__(timeout=timeout)
        self.users = users
        self.func_delete_user = func_delete_user
        self.select = AccountSelect(users, callback=self.unverify_account)
        self.add_item(self.select)

    async def unverify_account(self, interaction: discord.Interaction, value: str) -> None:
        for user, oak in self.users:
            if user.name != value:
                continue
            await self.func_delete_user(interaction, user, oak)

