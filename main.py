import aiohttp
import discord
import logging
import json
import sqlalchemy.orm

from discord import app_commands
from discord.ext import commands
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Optional
from traceback import format_exception
from utils.database import Guild, Base
from utils.exceptions import (
    DisabledCog,
    BotOwnerOnly,
    TooNew,
    NoOnGoingPoll,
    NoOnGoingRaffle,
    BlackListed,
    NoArtChannel,
)
from utils.utilities import create_error_embed

cogs = ["cogs.gallery", "cogs.general", "cogs.voting", "cogs.raffle", "cogs.community"]


class Mayushii(commands.Bot):
    user: discord.ClientUser
    s: sqlalchemy.orm.Session
    session: aiohttp.ClientSession
    
    setup_complete = False

    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.logger = self.get_logger(self.__class__)
        self.logger.info("Loading config.json")
        with open("data/config.json") as config:
            self.config = json.load(config)
        self.owner_id = self.config["owner"]

    async def setup_hook(self) -> None:
        engine = create_engine("sqlite:///data/mayushii.db")
        session = sessionmaker(bind=engine)
        self.s: sqlalchemy.orm.Session = session()
        Base.metadata.create_all(engine)
        self.session = aiohttp.ClientSession()

    @staticmethod
    def get_logger(object):
        logger = logging.getLogger(object.__class__.__name__)
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
        if self.setup_complete:
            return
        for guild in self.guilds:
            if not self.s.get(Guild, guild.id):
                self.s.add(Guild(id=guild.id, name=guild.name))
            self.s.commit()
        await self.load_cogs()
        self.logger.info(f"Initialized on {','.join(x.name for x in self.guilds)}")
        self.setup_complete = True

    async def load_cogs(self):
        for cog in cogs:
            try:
                await self.load_extension(cog)
                self.logger.info(f"Loaded {cog}")
            except commands.ExtensionNotFound:
                self.logger.error(f"Extension {cog} not found")

    def get_error_channel(self, interaction) -> Optional[discord.TextChannel]:
        if interaction.guild and (dbguild := self.s.get(Guild, interaction.guild.id)):
            c = interaction.guild.get_channel(dbguild.error_channel)
            if c and c.type == discord.ChannelType.text:
                return c
        return None

    async def on_command_error(self, ctx, exc):
        logger = self.logger if ctx.cog is None else ctx.cog.logger

        error_channel = self.get_error_channel(ctx)

        if isinstance(exc, (commands.CommandNotFound, DisabledCog, BotOwnerOnly)):
            return

        elif isinstance(
            exc,
            (
                commands.NoPrivateMessage,
                TooNew,
                NoOnGoingPoll,
                NoOnGoingRaffle,
            ),
        ):
            await ctx.send(exc)

        elif isinstance(exc, BlackListed):
            await ctx.author.send(exc)

        elif isinstance(exc, commands.CheckFailure):
            await ctx.send(f"You cannot use {ctx.command}.")

        elif isinstance(exc, commands.BadArgument):
            await ctx.send(f"Bad argument in {ctx.command}: `{exc}`")
            await ctx.send_help(ctx.command)

        elif isinstance(exc, commands.MissingRequiredArgument):
            await ctx.send(exc)
            await ctx.send_help(ctx.command)
        elif isinstance(exc, commands.CommandOnCooldown):
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
            logger.error(exc)
            if error_channel:
                await error_channel.send(exc)

    async def close(self) -> None:
        await self.session.close()
        self.s.close()
        await super().close()


class Mayutree(app_commands.CommandTree):
    bot: Mayushii

    def __init__(self, client):
        super().__init__(client)
        self.err_channel = None
        self.bot = client
        self.logger = logging.getLogger(__name__)

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ):
        logger = self.logger
        error_channel = self.bot.get_error_channel(interaction)
        command_name = interaction.command.name if interaction.command else "unknown"
        if isinstance(
            error,
            (
                TooNew,
                NoOnGoingPoll,
                BotOwnerOnly,
                NoOnGoingRaffle,
                BlackListed,
                NoArtChannel,
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
                    await interaction.edit_original_response(
                        content=msg, embed=None, view=None
                    )
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
            except Exception:
                pass
            exc_text = (
                f"{''.join(format_exception(type(error), error, error.__traceback__))}"
            )
            logger.error(f"Unhandled exception occurred `{command_name}`")
            logger.debug(exc_text)
            if error_channel:
                embed = create_error_embed(interaction, error)
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
