from datetime import datetime
from utils.exceptions import TooNew, BlackListed
from utils.database import BlackList


def not_new(ctx):
    if (datetime.now() - ctx.author.joined_at).days < ctx.bot.config["min_days"]:
        raise TooNew(
            f"Only members older than {ctx.bot.config['min_days']} days can participate."
        )
    return True


async def not_blacklisted(ctx):
    if ctx.cog.s.query(BlackList).get(ctx.author.id):
        await ctx.message.delete()
        raise BlackListed("You are blacklisted and cant use this command")
    return True
