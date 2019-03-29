from discord.ext import commands
import configparser
from traceback import format_exception
from sys import exc_info
import logging

cogs = [
    "cogs.gallery",
    "cogs.voting",
    "cogs.general"
]


class Mayushii(commands.Bot):

    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.logger = self.get_logger(self)
        self.logger.info('Loading config.ini')
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')

    @staticmethod
    def get_logger(self):
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(module)s - %(levelname)s - %(message)s',datefmt='%Y-%m-%d %H:%M:%S')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        return logger

    async def on_ready(self):
        self.guild = bot.get_guild(int(self.config['Main']['guild']))
        self.load_cogs()
        self.logger.info(f"Initialized on {self.guild.name}")

    def load_cogs(self):
        for cog in cogs:
            try:
                bot.load_extension(cog)
                self.logger.info(f'Loaded {cog}')
            except Exception as exc:
                self.logger.error(f'Encountered error while loading {cog}\n {format_exception(type(exc), exc, exc.__traceback__)}')

    async def on_command_error(self, ctx, exc):
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
            await ctx.send(f"`{ctx.command}` caused an exception.")
            ctx.cog.logger.error(f"Exception occurred in {ctx.command} {''.join(format_exception(type(exc), exc, exc.__traceback__))}")

        else:
            await ctx.send(f"Unhandled exception in `{ctx.command}`")
            ctx.cog.logger.error(f"Unhandled exception occurred in {ctx.command} {''.join(format_exception(type(exc), exc, exc.__traceback__))}")

    async def on_error(self, event, *args, **kwargs):
        self.logger.error(f'Error occurred in {event}', exc_info=exc_info())


bot = Mayushii(command_prefix="$", description="A bot for Nintendo Homebrew artistic channel")
bot.run(bot.config['Main']['token'])

