import re
from datetime import datetime
import discord
import random
import traceback

# thanks ihaveahax
from discord import app_commands


def gen_color(seed) -> discord.Color:
    random.seed(seed)
    c_r = random.randint(0, 255)
    c_g = random.randint(0, 255)
    c_b = random.randint(0, 255)
    return discord.Color((c_r << 16) + (c_g << 8) + c_b)


class ConfirmationButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
        self.value = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        self.value = True
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def deny_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        self.value = False
        self.stop()


def create_error_embed(interaction, exc) -> discord.Embed:
    name = interaction.command.name if interaction.command else "unknown"
    embed = discord.Embed(
        title=f"Unexpected exception in command {name}",
        color=0xE50730,
    )
    trace = "".join(
        traceback.format_exception(etype=None, value=exc, tb=exc.__traceback__)
    )
    embed.description = f"```py\n{trace}```"
    embed.add_field(name="Exception Type", value=exc.__class__.__name__)
    embed.add_field(
        name="Information",
        value=f"channel: {interaction.channel.mention if isinstance(interaction.channel, discord.TextChannel) else 'Direct Message'}\ncommand: {name}\nauthor: {interaction.user.mention}",
        inline=False,
    )
    return embed


def parse_time(time_string) -> int:
    """Parses a time string in dhms format to seconds"""
    # thanks Luc#5653
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    match = re.findall(
        "([0-9]+[smhd])", time_string
    )  # Thanks to 3dshax server's former bot
    if not match:
        return -1
    return sum(int(item[:-1]) * units[item[-1]] for item in match)


class TimeTransformer(app_commands.Transformer):
    @classmethod
    async def transform(cls, interaction: discord.Interaction, value: str) -> int:
        seconds = parse_time(value)
        if seconds > 0:
            return seconds
        raise app_commands.TransformerError(
            "Invalid time format", discord.AppCommandOptionType.integer, cls
        )


class DateTransformer(app_commands.Transformer):
    @classmethod
    async def transform(cls, interaction: discord.Interaction, value: str) -> datetime:

        data = value.split(" ")
        if len(data) == 2:
            return datetime.strptime(value, "%d/%m/%y %H:%M:%S")
        elif len(data) == 1:
            return datetime.strptime(value, "%d/%m/%y")
        else:
            raise app_commands.TransformerError(
                "Invalid date format", discord.AppCommandOptionType.string, cls
            )
