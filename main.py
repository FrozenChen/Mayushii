import discord
import logging
import json

from discord.ext import commands
from traceback import format_exception
from sys import exc_info
from utils import exceptions

cogs = ["cogs.gallery", "cogs.general", "cogs.voting", "cogs.raffle"]


class Mayushii(commands.Bot):
    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.logger = self.get_logger(self)
        self.logger.info("Loading config.json")
        with open("config.json") as config:
            self.config = json.load(config)

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
        self.guild = bot.get_guild(self.config["guild"])
        self.load_cogs()
        self.logger.info(f"Initialized on {self.guild.name}")

    def load_cogs(self):
        for cog in cogs:
            try:
                self.load_extension(cog)
                self.logger.info(f"Loaded {cog}")
            except commands.ExtensionNotFound:
                self.logger.error(f"Extension {cog} not found")
            except commands.ExtensionFailed as exc:
                self.logger.error(f"Error occurred when loading {cog}")
                self.logger.debug(
                    f"{''.join(format_exception(type(exc), exc, exc.__traceback__))}"
                )

    async def on_command_error(self, ctx, exc):
        logger = self.logger if ctx.cog is None else ctx.cog.logger

        if isinstance(exc, commands.CommandNotFound):
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

        elif isinstance(exc, commands.CommandInvokeError):
            if isinstance(exc.original, discord.Forbidden):
                await ctx.send("I can't do this!")
            else:
                await ctx.send(f"`{ctx.command}` caused an exception.")
                logger.error(f"Exception occurred in {ctx.command}")
                logger.debug(
                    f"{''.join(format_exception(type(exc), exc, exc.__traceback__))}"
                )
        else:
            await ctx.send(f"Unhandled exception in `{ctx.command}`")
            logger.error(f"Unhandled exception occurred in {ctx.command}")
            logger.debug(
                f"{''.join(format_exception(type(exc), exc, exc.__traceback__))}"
            )

    async def on_error(self, event, *args, **kwargs):
        self.logger.error(f"Error occurred in {event}", exc_info=exc_info())


bot = Mayushii(
    command_prefix="$", max_messages=None, description="A bot for Nintendo Homebrew artistic channel"
)
bot.run(bot.config["token"])
