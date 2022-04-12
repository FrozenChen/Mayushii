import aiohttp
import discord
import logging
import json
import sqlalchemy.orm

from discord import app_commands
from discord.app_commands import ContextMenu, Command
from discord.ext import commands
from typing import Union, Optional
from traceback import format_exception
from utils import exceptions
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from utils.database import Guild, Base
from utils.exceptions import DisabledCog, BotOwnerOnly
from utils.utilities import create_error_embed

cogs = ["cogs.gallery", "cogs.general", "cogs.voting", "cogs.raffle", "cogs.community"]


class Mayushii(commands.Bot):
    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.logger = self.get_logger(self.__class__)
        self.logger.info("Loading config.json")
        self.session: Optional[aiohttp.ClientSession] = None
        self.s: Optional[sqlalchemy.orm.Session] = None
        with open("data/config.json") as config:
            self.config = json.load(config)
        self.owner_id = self.config["owner"]

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()

    @staticmethod
    def get_logger(self):
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        fh = logging.FileHandler("mayushii.log")
        ch.setLevel(logging.INFO)
        fh.setLevel(logging.NOTSET)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(module)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        ch.setFormatter(formatter)
        fh.setFormatter(formatter)
        logger.addHandler(ch)
        logger.addHandler(fh)
        return logger

    async def on_ready(self):
        engine = create_engine("sqlite:///data/mayushii.db")
        session = sessionmaker(bind=engine)
        self.s: sqlalchemy.orm.session = session()
        Base.metadata.create_all(engine)
        for guild in self.guilds:
            if not self.s.query(Guild).get(guild.id):
                self.s.add(Guild(id=guild.id, name=guild.name))
            self.s.commit()
        await self.load_cogs()
        await self.tree.sync()
        self.logger.info(f"Initialized on {','.join(x.name for x in self.guilds)}")

    async def load_cogs(self):
        for cog in cogs:
            try:
                await self.load_extension(cog)
                self.logger.info(f"Loaded {cog}")
            except commands.ExtensionNotFound:
                self.logger.error(f"Extension {cog} not found")

    def get_error_channel(self, interaction):
        if dbguild := self.s.query(Guild).get(interaction.guild.id):
            error_channel = interaction.guild.get_channel(dbguild.error_channel)
        else:
            error_channel = None
        return error_channel

    async def on_command_error(self, ctx, exc):
        logger = self.logger if ctx.cog is None else ctx.cog.logger

        error_channel = self.get_error_channel(ctx)

        if isinstance(exc, (commands.CommandNotFound, DisabledCog, BotOwnerOnly)):
            return

        elif isinstance(
            exc,
            (
                commands.NoPrivateMessage,
                exceptions.TooNew,
                exceptions.NoOnGoingPoll,
                exceptions.NoOnGoingRaffle,
            ),
        ):
            await ctx.send(exc)

        elif isinstance(exc, exceptions.BlackListed):
            await ctx.author.send(exc)

        elif isinstance(exc, commands.CheckFailure):
            await ctx.send(f"You cannot use {ctx.command}.")

        elif isinstance(exc, commands.BadArgument):
            await ctx.send(f"Bad argument in {ctx.command}: `{exc}`")
            await ctx.send_help(ctx.command)

        elif isinstance(exc, commands.MissingRequiredArgument):
            await ctx.send(exc)
            await ctx.send_help(ctx.command)
        elif isinstance(exc, discord.ext.commands.errors.CommandOnCooldown):
            await ctx.send(
                f"This command is on cooldown, try again in {exc.retry_after:.2f}s.",
                delete_after=10,
            )

        elif isinstance(exc, commands.CommandInvokeError):
            if isinstance(exc.original, discord.Forbidden):
                await ctx.send("I can't do this!")
            else:
                await ctx.send(f"`{ctx.command}` caused an exception.")
                exc = f"{''.join(format_exception(type(exc), exc, exc.__traceback__))}"
                logger.error(f"Exception occurred in {ctx.command}")
                logger.debug(exc)
                if error_channel:
                    await error_channel.send(exc)

        else:
            await ctx.send(f"Unhandled exception in `{ctx.command}`")
            exc = f"{''.join(format_exception(type(exc), exc, exc.__traceback__))}"
            logger.error(f"Unhandled exception occurred in {ctx.command}")
            logger.debug(exc)
            if error_channel:
                await error_channel.send(exc)

    async def close(self) -> None:
        await self.session.close()
        self.s.close()
        await super().close()


class Mayutree(app_commands.CommandTree):
    def __init__(self, client):
        super().__init__(client)
        self.err_channel = None
        self.logger = logging.getLogger(__name__)

    async def on_error(
        self,
        interaction: discord.Interaction,
        command: Union[ContextMenu, Command, None],
        error: app_commands.AppCommandError,
    ):
        logger = self.logger
        error_channel = interaction.client.get_error_channel(interaction)
        command_name = interaction.command.name if interaction.command else "unknown"
        if isinstance(
            error,
            (
                exceptions.TooNew,
                exceptions.NoOnGoingPoll,
                exceptions.BotOwnerOnly,
                exceptions.NoOnGoingRaffle,
                exceptions.BlackListed,
                exceptions.NoArtChannel,
            ),
        ):
            await interaction.response.send_message(error, ephemeral=True)

        elif isinstance(error, app_commands.CommandNotFound):
            await interaction.response.send_message(
                "Command not found.", ephemeral=True
            )

        elif isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                f"You cannot use {command_name}.", ephemeral=True
            )

        elif isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"This command is on cooldown, try again in {error.retry_after:.2f}s.",
                ephemeral=True,
            )

        else:
            msg = f"Unhandled exception in `{command_name}`"
            try:
                if interaction.response.is_done():
                    await interaction.edit_original_message(
                        content=msg, embed=None, view=None
                    )
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
            except Exception:
                pass
            embed = create_error_embed(interaction, error)
            exc_text = (
                f"{''.join(format_exception(type(error), error, error.__traceback__))}"
            )
            logger.error(f"Unhandled exception occurred `{command_name}`")
            logger.debug(exc_text)
            if error_channel:
                await error_channel.send(embed=embed)


if __name__ == "__main__":
    intents = discord.Intents().all()
    bot = Mayushii(
        command_prefix="$",
        description="A bot for Nintendo Homebrew artistic channel",
        intents=intents,
        tree_cls=Mayutree,
    )
    bot.run(bot.config["token"])
