from discord.ext import commands


class NoOnGoingPoll(commands.CheckFailure):
    pass


class TooNew(commands.CheckFailure):
    pass


class BlackListed(commands.CheckFailure):
    pass