import asyncio
import re
import bloonspy
import bloonspy.exceptions
import bot.utils.io
import bot.db.queries
import discord
from discord.ext import commands
from bot.classes import ErrorHandlerCog
from typing import List
from bot.views import AccountUnverifyView


class VerifyCog(ErrorHandlerCog):
    verify_group = discord.app_commands.Group(name="verify", description="Tell the bot who you are in BTD6")
    help_descriptions = {
        "verify": {
            "account": "Tell the bot who you are in BTD6!",
            "main": "Choose one of your accounts as your main account for the bot, if "
                    "you have many.",
        },
        "unverify": "Remove one or more accounts from the bot."
    }

    def __init__(self, bot):
        super().__init__(bot)

    @verify_group.command(name="account",
                          description="Verify who you are in Bloons TD 6!")
    @discord.app_commands.describe(oak="Your OAK (leave blank if you don't know what that is)")
    async def cmd_verify(self, interaction: discord.Interaction, oak: str = None) -> None:
        user = interaction.user
        instructions = "__**About verification**__\n" \
                       "To know who you are, I need your **Open Access Key (OAK)**. This is a bit of text that " \
                       "allows me to see a lot of things about you in-game, like your profile, your team, and " \
                       "more. It's perfectly safe though, Ninja Kiwi takes privacy very seriously, so I can't do " \
                       "anything bad with it even if I wanted to!\n\n" \
                       "__**Generate your OAK**__\n" \
                       "🔹 Open Bloons TD6 (or Battles 2) > Settings > My Account > Open Data API (it's a small " \
                       "link in the bottom right) > Generate Key. Your OAK should look something like " \
                       "`oak_h6ea...p1hr`.\n" \
                       "🔹 Copy it (note: the \"Copy\" button doesn't work, so just manually select it and do ctrl+C) " \
                       "and, do /verify and paste your OAK as a parameter. Congrats, you have verified yourself!\n\n" \
                       "__**What if I have alts?**__\n" \
                       "One Discord account can have multiple OAKs, but an OAK can only be associated to one Discord " \
                       "account (for now). One of these OAKs will be your \"main one\" (you can choose which one).\n\n" \
                       "__**More information**__\n" \
                       "Ninja Kiwi talking about OAKs: https://support.ninjakiwi.com/hc/en-us/articles/13438499873937\n"

        await interaction.response.defer(ephemeral=oak is not None)

        if oak is None:
            oak = await bot.db.queries.get_main_oak(user.id)
            bloons_user = None
            if oak:
                try:
                    bloons_user = bloonspy.Client.get_user(oak)
                except bloonspy.exceptions.NotFound:
                    pass

            if bloons_user:
                is_veteran = bloons_user.veteran_rank > 0
                await interaction.edit_original_response(
                    content=f"You are already verified as {bloons_user.name}! "
                            f"({f'Vet{bloons_user.veteran_rank}' if is_veteran else f'Lv{bloons_user.rank}'})\n\n"
                            "*Not who you are? Run the command with the correct account's OAK!*"
                )
            elif interaction.guild:
                await interaction.edit_original_response(content="Check your DMs!")
                await user.send(instructions)
            else:
                await interaction.edit_original_response(content=instructions)
            return

        if re.match(r"oak_[\da-z]{32}", oak) is None:
            await interaction.edit_original_response(
                content="Your OAK is not well formatted! it should be `oak_` followed by 32 numbers and/or lowercase "
                        "letters!\n\n"
                        "*Don't know what an OAK is? Leave the field blank to get a help message!*",
            )
            return

        if await bot.db.queries.is_oak_registered(oak):
            await interaction.edit_original_response(
                content="That OAK is already registered!",
            )

        try:
            bloons_user = bloonspy.Client.get_user(oak)
            is_veteran = bloons_user.veteran_rank > 0
            await bot.db.queries.set_oak(user.id, oak)
            await interaction.edit_original_response(
                content=f"You've verified yourself as {bloons_user.name}! "
                        f"({f'Vet{bloons_user.veteran_rank}' if is_veteran else f'Lv{bloons_user.rank}'})\n\n"
                        "*Not who you are? Run the command with the correct account's OAK!*",
            )
        except bloonspy.exceptions.NotFound:
            await interaction.edit_original_response(
                content="Couldn't find a BTD6 user with that OAK! Are you sure it's the correct one?",
            )

    @verify_group.command(name="main",
                          description="Choose one of your accounts as your main one")
    async def cmd_set_main(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(content="Under construction!",
                                                ephemeral=True)

    @discord.app_commands.command(name="unverify",
                                  description="Remove one or more accounts from the bot")
    async def cmd_unverify(self, interaction: discord.Interaction) -> None:
        oaks = await bot.db.queries.get_oaks(interaction.user.id)
        users = await asyncio.gather(*[
            self.get_user(oak["oak"])
            for oak in oaks
        ])
        users = [
            u for u in users
            if u is not None
        ]

        if len(users) == 0:
            await interaction.response.send_message(
                content="You have no accounts connected to this bot!",
                ephemeral=True
            )
        elif len(users) == 1:
            await self.unverify_user(interaction, users[0], users[0].id, edit=False)
        else:
            await interaction.response.send_message(
                content="Select which account you'd like to unverify.",
                view=AccountUnverifyView([
                    (user, user.id) for user in users
                ], self.unverify_user),
                ephemeral=True
            )

    @staticmethod
    async def get_user(oak: str) -> bloonspy.User or None:
        try:
            user = await asyncio.to_thread(bloonspy.Client.get_user, oak)
            return user
        except bloonspy.exceptions.NotFound:
            return None

    @staticmethod
    async def unverify_user(interaction: discord.Interaction,
                            user: bloonspy.User,
                            oak: str,
                            edit: bool = True) -> None:
        await bot.db.queries.del_oak(interaction.user.id, oak)
        content = f"Your account is no longer associated to **{user.name}**"
        if edit:
            await interaction.response.edit_message(content=content, view=None)
        else:
            await interaction.response.send_message(content=content, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VerifyCog(bot))
