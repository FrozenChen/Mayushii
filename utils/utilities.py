import discord
import random
import re
import traceback

from datetime import datetime
from discord import app_commands
from typing import Optional


# thanks ihaveahax
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
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.value = True
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def deny_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.value = False
        self.stop()


def create_error_embed(interaction, exc) -> discord.Embed:
    name = interaction.command.name if interaction.command else "unknown"
    embed = discord.Embed(
        title=f"Unexpected exception in command {name}",
        color=0xE50730,
    )
    trace = "".join(traceback.format_exception(exc))
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


def parse_date(date_string: str) -> Optional[datetime]:
    date_lst = date_string.split(' ')

    if len(date_lst) == 1:
        date_lst.append('00:00')
    elif len(date_lst) != 2:
        return None
    try:
        datetime_obj = datetime.strptime(' '.join(date_lst), "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return datetime_obj


class TimeTransformer(app_commands.Transformer):
    async def transform(self, interaction: discord.Interaction, value: str) -> int:
        seconds = parse_time(value)
        if seconds > 0:
            return seconds
        raise app_commands.TransformerError("Invalid time format", discord.AppCommandOptionType.string, self)


class DateTransformer(app_commands.Transformer):
    async def transform(self, interaction: discord.Interaction, value: str) -> datetime:
        if (datetime_obj := parse_date(value)) is not None:
            return datetime_obj
        raise app_commands.TransformerError("Invalid time format", discord.AppCommandOptionType.string, self)


class GreedyRoleTransformer(app_commands.Transformer):
    async def transform(
        self, interaction: discord.Interaction, value: str
    ) -> list[discord.Role]:
        data = value.split(",")
        roles = []
        if not interaction.guild:
            raise app_commands.NoPrivateMessage()
        for role_id in data:
            try:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    roles.append(role)
            except (discord.NotFound, ValueError):
                raise app_commands.TransformerError(
                    "Invalid date format", discord.AppCommandOptionType.role, self
                )
        return roles
