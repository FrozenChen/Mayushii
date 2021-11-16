from disnake.ext import commands


class NoOnGoingPoll(commands.CheckFailure):
    pass


class NoOnGoingRaffle(commands.CheckFailure):
    pass


class TooNew(commands.CheckFailure):
    pass


class BlackListed(commands.CheckFailure):
    pass


class DisabledCog(commands.CheckFailure):
    pass


class BotOwnerOnly(commands.CheckFailure):
    pass


class NoArtChannel(commands.CheckFailure):
    pass
