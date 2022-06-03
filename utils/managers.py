from __future__ import annotations

import discord
import random

from datetime import datetime
from main import Mayushii
from typing import Optional, Literal, TYPE_CHECKING
from utils.database import Poll, Voter, Giveaway, GiveawayEntry, GiveawayRole
from utils.exceptions import NoOnGoingPoll
from utils.utilities import gen_color

if TYPE_CHECKING:
    from utils.views import RaffleView


class VoteManager:
    def __init__(self, bot: Mayushii):
        self.bot = bot
        self.polls: dict[int, Poll] = {
            poll.guild_id: poll
            for poll in self.bot.s.query(Poll).filter_by(active=True).all()
        }

    def get_voter(self, member: discord.Member):
        return self.bot.s.query(Voter).get((member.id, self.polls[member.guild.id].id))

    @staticmethod
    def parse_options(options: str):
        return options.split("|")

    def create_poll(
        self,
        name: str,
        guild_id: int,
        message_id: int,
        author_id: int,
        url: Optional[str],
        channel_id: int,
        custom_id: int,
        description: str,
        options: str,
        start: datetime,
        end: Optional[datetime] = None,
    ):
        poll = Poll(
            name=name,
            guild_id=guild_id,
            description=description,
            options=options,
            url=url,
            message_id=message_id,
            author_id=author_id,
            channel_id=channel_id,
            custom_id=custom_id,
            start=start,
            end=end,
        )
        self.bot.s.add(poll)
        self.bot.s.commit()
        return poll

    def count_votes(self, poll: Poll) -> dict[str, int]:
        result = {}
        for option in self.parse_options(poll.options):  # type: ignore
            c = (
                self.bot.s.query(Voter)
                .filter_by(poll_id=poll.id, option=option)
                .count()
            )
            result[option] = c
        return result

    def get_ongoing_poll(self, guild_id) -> Optional[Poll]:
        return self.polls.get(guild_id)

    def ongoing_poll(self, guild_id) -> Literal[True]:
        if self.get_ongoing_poll(guild_id) is None:
            raise NoOnGoingPoll("There is no ongoing poll")
        return True

    def get_poll(self, poll_id: int, guild_id):
        return (
            self.bot.s.query(Poll)
            .filter(Poll.id == poll_id, Poll.guild_id == guild_id)
            .one_or_none()
        )

    async def end_poll(self, poll: Poll, view, announce: bool):

        await view.stop()

        if announce:
            result = self.count_votes(poll)
            embed = discord.Embed(
                title=f"The {poll.name} has ended!",
                description="Congratulations to the winner!",
            )
            msg = ""
            for x in result.keys():
                msg += f"{x}: {result[x]}   "
            embed.add_field(name="Votes", value=msg, inline=False)

            try:
                await view.messageable.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass

        del self.polls[poll.guild_id]
        poll.active = False  # type: ignore
        self.bot.s.commit()

    async def process_vote(self, interaction: discord.Interaction, option: str):
        assert interaction.guild is not None
        assert isinstance(interaction.user, discord.Member)
        voter = self.get_voter(interaction.user)
        poll = self.get_ongoing_poll(interaction.guild.id)
        if poll is None:  # Could this happen?
            return
        if voter is None:
            voter = Voter(userid=interaction.user.id, poll_id=poll.id, option=option)
            self.bot.s.add(voter)
            await interaction.response.send_message(
                f"Voted for {option} successfully!", ephemeral=True
            )
        else:
            old_vote = voter.option
            if voter.option == option:
                await interaction.response.send_message(
                    "No change in your vote!", ephemeral=True
                )
            else:
                voter.option = option
                await interaction.response.send_message(
                    f"Vote changed from {old_vote} to {voter.option}!", ephemeral=True
                )
        self.bot.s.commit()

    @staticmethod
    def create_embed(poll: Poll, description=""):
        return discord.Embed(
            title=poll.name,
            description=description,
            colour=gen_color(poll.id),
        )


class RaffleManager:
    def __init__(self, bot: Mayushii):
        self.bot = bot
        self.raffles: dict[int, Giveaway] = {
            raffle.guild_id: raffle
            for raffle in self.bot.s.query(Giveaway).filter_by(ongoing=True).all()
        }

    def create_raffle(
        self,
        name: str,
        description: str,
        url: Optional[str],
        win_count: int,
        max_participants: Optional[int],
        roles: list[discord.Role],
        guild_id: int,
        channel_id: int,
        message_id: int,
        author_id: int,
        custom_id: int,
        start_date: datetime,
        end_date: Optional[datetime],
    ):
        raffle = Giveaway(
            name=name,
            description=description,
            url=url,
            win_count=win_count,
            max_participants=max_participants,
            ongoing=True,
            author_id=author_id,
            custom_id=custom_id,
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            start_date=start_date,
            end_date=end_date,
        )
        self.bot.s.add(raffle)

        if roles:
            self.bot.s.add_all(
                [GiveawayRole(id=role.id, giveaway_id=raffle.id) for role in roles]
            )
        self.bot.s.commit()
        return raffle

    def get_raffle(self, guild_id: int) -> Optional[Giveaway]:
        return self.raffles.get(guild_id)

    def get_winners(self, guild_id: int) -> list[discord.Member]:
        raffle = self.raffles[guild_id]
        guild = self.bot.get_guild(guild_id)
        winners = []

        if len(raffle.entries) >= raffle.win_count:
            while len(winners) != raffle.win_count:
                entry: GiveawayEntry = random.choice(raffle.entries)
                if (winner := guild.get_member(entry.user_id)) is not None:  # type: ignore
                    entry.winner = True  # type: ignore
                    self.bot.s.commit()
                    winners.append(winner)
                else:
                    self.bot.s.delete(entry)
        return winners

    async def process_entry(self, interaction: discord.Interaction):
        assert interaction.guild is not None
        assert isinstance(interaction.user, discord.Member)
        raffle = self.get_raffle(interaction.guild.id)
        if not raffle or not raffle.ongoing:
            return await interaction.response.send_message(
                "The raffle has ended", ephemeral=True
            )
        if raffle.roles:
            for role in raffle.roles:
                if not discord.utils.get(interaction.user.roles, id=role.id):
                    return await interaction.response.send_message(
                        "You are not allowed to participate!", ephemeral=True
                    )
        user_id = interaction.user.id
        entry = self.bot.s.query(GiveawayEntry).get((user_id, raffle.id))
        if entry:
            return await interaction.response.send_message(
                "You are already participating!", ephemeral=True
            )
        self.bot.s.add(GiveawayEntry(user_id=user_id, giveaway_id=raffle.id))
        self.bot.s.commit()

        await interaction.response.send_message(
            f"{interaction.user.mention} now you are participating in the raffle!",
            ephemeral=True,
        )
        if raffle.max_participants and len(raffle.entries) >= raffle.max_participants:
            await self.stop_raffle(interaction.guild.id)

    def get_view(self, guild_id: int) -> Optional[RaffleView]:
        raffle = self.get_raffle(guild_id)
        if not raffle:
            return None
        view = discord.utils.get(self.bot.persistent_views, custom_id=raffle.custom_id)
        return view if isinstance(view, RaffleView) else None

    async def stop_raffle(self, guild_id: int):
        view = self.get_view(guild_id)
        raffle = self.raffles[guild_id]
        raffle.ongoing = False  # type: ignore
        self.bot.s.commit()
        if view is not None:
            await view.stop()
            result = self.get_winners(guild_id)
            embed = discord.Embed(
                title=f"The {raffle.name} raffle has ended!",
                description="Congratulation to the winner(s)!",
            )
            msg = ""
            for winner in result:
                msg += f"{winner.mention} "
            embed.add_field(name="Winners", value=msg, inline=False)
            try:
                await view.messageable.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass
            del self.raffles[guild_id]

    @staticmethod
    def create_embed(raffle: Giveaway, description="") -> discord.Embed:
        return discord.Embed(
            title=raffle.name,
            description=description,
            colour=gen_color(raffle.id),
        )
