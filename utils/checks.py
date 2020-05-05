from datetime import datetime
from utils.exceptions import TooNew


def not_new(ctx):
    if (datetime.now() - ctx.author.joined_at).days < int(ctx.bot.config['Vote']['min_days']):
        raise TooNew(f"Only members older than {ctx.bot.config['Vote']['min_days']} days can participate.")
    return True
