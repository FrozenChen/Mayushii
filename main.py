import disnake
import logging
import json

from disnake.ext import commands
from traceback import format_exception
from sys import exc_info
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
        self.logger = self.get_logger(self)
        self.logger.info("Loading config.json")
        with open("data/config.json") as config:
            self.config = json.load(config)
        self.owner_id = self.config["owner"]

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
        self.s = session()
        Base.metadata.create_all(engine)
        for guild in self.guilds:
            if not self.s.query(Guild).get(guild.id):
                self.s.add(Guild(id=guild.id, name=guild.name))
            self.s.commit()
        self.load_cogs()
        self.logger.info(f"Initialized on {','.join(x.name for x in self.guilds)}")

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

    async def on_slash_command_error(self, inter, exc):
        logger = self.logger
        if inter.guild and (dbguild := self.s.query(Guild).get(inter.guild.id)):
            error_channel = inter.guild.get_channel(dbguild.error_channel)
        else:
            error_channel = None

        if isinstance(
            exc,
            (
                commands.NoPrivateMessage,
                exceptions.TooNew,
                exceptions.NoOnGoingPoll,
                exceptions.NoOnGoingRaffle,
                exceptions.BlackListed,
            ),
        ):
            await inter.response.send_message(exc, ephemeral=True)

        elif isinstance(exc, commands.CheckFailure):
            await inter.response.send_message(
                f"You cannot use {inter.data.name}.", ephemeral=True
            )

        elif isinstance(exc, disnake.ext.commands.errors.CommandOnCooldown):
            await inter.response.send_message(
                f"This command is on cooldown, try again in {exc.retry_after:.2f}s.",
                ephemeral=True,
            )

        else:
            msg = f"Unhandled exception in `{inter.data.name}`"
            try:
                if inter.response.is_done():
                    await inter.edit_original_message(
                        content=msg, embed=None, view=None
                    )
                else:
                    await inter.response.send_message(msg, ephemeral=True)
            except Exception:
                pass
            embed = create_error_embed(inter, exc)
            exc_text = f"{''.join(format_exception(type(exc), exc, exc.__traceback__))}"
            logger.error(f"Unhandled exception occurred `{inter.data.name}`")
            logger.debug(exc_text)
            if error_channel:
                await error_channel.send(embed=embed)

    async def on_error(self, event, *args, **kwargs):
        self.logger.error(f"Error occurred in {event}", exc_info=exc_info())


intents = disnake.Intents(guilds=True, members=True, messages=True, reactions=True)
bot = Mayushii(
    command_prefix="$",
    description="A bot for Nintendo Homebrew artistic channel",
    intents=intents,
)
bot.run(bot.config["token"])
