from discord.ext import commands
import configparser
from traceback import format_exception
from sys import exc_info
import logging
import discord

cogs = [
    "cogs.gallery",
    "cogs.general",
]


class Mayushii(commands.Bot):

    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.help_command.dm_help = True
        self.logger = self.get_logger(self)
        self.logger.info('Loading config.ini')
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.load_cogs()

    @staticmethod
    def get_logger(self):
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        fh = logging.FileHandler('mayushii.log')
        ch.setLevel(logging.INFO)
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(module)s - %(levelname)s - %(message)s',datefmt='%Y-%m-%d %H:%M:%S')
        ch.setFormatter(formatter)
        fh.setFormatter(formatter)
        logger.addHandler(ch)
        logger.addHandler(fh)
        return logger

    async def on_ready(self):
        self.guild = bot.get_guild(int(self.config['Main']['guild']))
        self.logger.info(f"Initialized on {self.guild.name}")

    def load_cogs(self):
        for cog in cogs:
            try:
                self.load_extension(cog)
                self.logger.info(f'Loaded {cog}')
            except Exception as exc:
                self.logger.error(f"Encountered error while loading {cog} {''.join(format_exception(type(exc), exc, exc.__traceback__))}")

    async def on_command_error(self, ctx, exc):
        logger = self.logger if ctx.cog is None else ctx.cog.logger

        if isinstance(exc, commands.CommandNotFound):
            pass

        elif isinstance(exc, commands.NoPrivateMessage):
            await ctx.send(f'{exc}')

        elif isinstance(exc, commands.CheckFailure):
            await ctx.send(f"You cannot use {ctx.command}.")

        elif isinstance(exc, commands.BadArgument):
            await ctx.send(f"Bad argument in {ctx.command}: `{exc}`")
            await ctx.send_help(ctx.command)

        elif isinstance(exc, commands.MissingRequiredArgument):
            await ctx.send(f"Missing arguments in `{ctx.command}`")
            await ctx.send_help(ctx.command)

        elif isinstance(exc, commands.CommandInvokeError):
            if isinstance(exc.original, discord.Forbidden):
                await ctx.send("I can't do this!")
            else:
                await ctx.send(f"`{ctx.command}` caused an exception.")
                logger.error(f"Exception occurred in {ctx.command} {''.join(format_exception(type(exc), exc, exc.__traceback__))}")
        else:
            await ctx.send(f"Unhandled exception in `{ctx.command}`")
            logger.error(f"Unhandled exception occurred in {ctx.command} {''.join(format_exception(type(exc), exc, exc.__traceback__))}")

    async def on_error(self, event, *args, **kwargs):
        self.logger.error(f'Error occurred in {event}', exc_info=exc_info())


bot = Mayushii(command_prefix="$", description="A bot for Nintendo Homebrew artistic channel")
bot.run(bot.config['Main']['token'])

