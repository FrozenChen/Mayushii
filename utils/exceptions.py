from discord.app_commands import CheckFailure


class NoOnGoingPoll(CheckFailure):
    pass


class NoOnGoingRaffle(CheckFailure):
    pass


class TooNew(CheckFailure):
    pass


class BlackListed(CheckFailure):
    pass


class DisabledCog(CheckFailure):
    pass


class BotOwnerOnly(CheckFailure):
    pass


class NoArtChannel(CheckFailure):
    pass
