import datetime

from utils.exceptions import TooNew, BlackListed
from utils.database import BlackList, Guild


def not_new(interaction):
    dbguild = interaction.client.s.get(Guild, interaction.guild.id)
    if (
        datetime.datetime.now(datetime.timezone.utc) - interaction.user.joined_at
    ).days < dbguild.min_days:
        raise TooNew(
            f"Only members older than {interaction.client.config['min_days']} days can participate."
        )
    return True


def not_blacklisted(interaction):
    if interaction.client.s.get(BlackList, (interaction.user.id, interaction.guild.id)):
        raise BlackListed("You are blacklisted and can't use this command")
    return True
