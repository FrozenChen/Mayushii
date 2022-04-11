import discord
import utils

from datetime import datetime
from typing import Optional, Literal
from main import Mayushii
from utils.database import Poll, Voter, Giveaway
from utils.exceptions import NoOnGoingPoll


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
        for option in self.parse_options(poll.options):
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

    async def end_poll(self, poll: Poll, view):
        await view.stop_vote()
        result = self.count_votes(poll)
        embed = discord.Embed(
            title=f"The {poll.name} has ended!",
            description="Congratulation to the winner!",
        )
        msg = ""
        for x in result.keys():
            msg += f"{x}: {result[x]}   "
        embed.add_field(name="Votes", value=msg, inline=False)

        if guild := self.bot.get_guild(view.guild_id):

            channel = guild.get_channel(view.channel_id)
            if channel:
                await channel.send(embed=embed)
        del self.polls[poll.guild_id]
        poll.active = False
        self.bot.s.commit()

    async def process_vote(self, interaction: discord.Interaction, option: str):
        voter = self.get_voter(interaction.user)
        poll = self.get_ongoing_poll(interaction.guild_id)
        if voter is None:
            voter = Voter(userid=interaction.user.id, poll_id=poll.id, option=option)
            self.bot.s.add(voter)
            await interaction.response.send_message(
                f"Voted for {option} successfully!", ephemeral=True
            )
        else:
            old_vote = voter.option
            if voter.option == option:
                await interaction.response.send_message("No change in your vote!")
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
            colour=utils.utilities.gen_color(poll.id),
        )


class RaffleManager:
    def __init__(self, bot: Mayushii):
        self.bot = bot
        self.raffles: dict[int, Giveaway] = {
            raffle.guild: raffle
            for raffle in self.bot.s.query(Giveaway).filter_by(ongoing=True).all()
        }

    def get_raffle(self, interaction):
        return self.raffles.get(interaction.guild.id)
