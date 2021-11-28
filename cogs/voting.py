import asyncio
import disnake

from disnake.ext import commands
from disnake.ext.commands import Param
from utils.database import Poll, Voter, Guild
from utils.exceptions import NoOnGoingPoll, DisabledCog, TooNew, BlackListed
from utils.checks import not_new, not_blacklisted
from utils.utilities import ConfirmationButtons
from typing import Union


class Voting(commands.Cog):
    """Commands for managing a poll."""

    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        self.polls = {
            poll.guild: poll
            for poll in self.bot.s.query(Poll).filter_by(active=True).all()
        }

        self.queue = asyncio.Queue()

    @staticmethod
    def is_enabled(ctx):
        dbguild = ctx.bot.s.query(Guild).get(ctx.guild.id)
        return dbguild.flags & 0b1000

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if not self.is_enabled(ctx):
            raise DisabledCog()
        return True

    # Checks
    def ongoing_poll(inter):
        cog = inter.application_command.cog
        if cog is None or cog.polls.get(inter.guild.id) is None:
            raise NoOnGoingPoll(f"There is no ongoing poll")
        return True

    # Internal functions
    def get_voter(self, member: disnake.Member):
        return self.bot.s.query(Voter).get((member.id, self.polls[member.guild.id].id))

    @staticmethod
    def get_current_poll(inter):
        return inter.application_command.cog.polls.get(inter.guild.id)

    @staticmethod
    def get_poll(inter, poll_id: str):
        return (
            inter.bot.s.query(Poll)
            .filter(Poll.id == poll_id, Poll.guild == inter.guild.id)
            .one_or_none()
        )

    def delete_vote(self, member: disnake.Member):
        voter = self.get_voter(member)
        if voter is not None:
            self.bot.s.delete(voter)
            self.bot.s.commit()

    async def process_vote(self):
        inter, option = await self.queue.get()
        voter = self.get_voter(inter.author)
        poll = self.polls.get(inter.guild_id)
        if voter is None:
            voter = Voter(userid=inter.author.id, poll_id=poll.id, option=option)
            self.bot.s.add(voter)
            await inter.response.send_message(
                f"Voted for {option} successfully!", ephemeral=True
            )
        else:
            old_vote = voter.option
            voter.option = option
            await inter.response.send_message(
                f"Vote changed from {old_vote} to {voter.option}!", ephemeral=True
            )
        self.bot.s.commit()
        self.queue.task_done()

    def count_votes(self, poll: Poll):
        result = {}
        for option in self.parse_options(poll.options):
            c = (
                self.bot.s.query(Voter)
                .filter_by(poll_id=poll.id, option=option)
                .count()
            )
            result[option] = c
        return result

    def create_poll(self, name, guild: int, link: str, options: str):
        poll = Poll(name=name, guild=guild, link=link, options=options)
        self.bot.s.add(poll)
        self.bot.s.commit()
        return poll

    @staticmethod
    def parse_options(options: str):
        return options.split(" | ")

    @commands.guild_only()
    @commands.slash_command()
    async def poll(self, inter):
        """Poll related commands."""
        pass

    @commands.check(not_new)
    @commands.check(not_blacklisted)
    @commands.check(ongoing_poll)
    @commands.guild_only()
    @poll.sub_command()
    async def vote(
        self,
        inter: disnake.ApplicationCommandInteraction,
        vote: str = Param(description="Your vote"),
    ):
        """Vote for the option you like"""
        if vote not in self.parse_options(self.polls.get(inter.guild_id).options):
            await inter.response.send_message(
                f"Invalid option. Valid options: {' '.join(self.parse_options(self.polls.get(inter.guild_id).options))}",
                ephemeral=True,
            )
            return
        await self.queue.put((inter, vote))
        await self.process_vote()

    @commands.has_guild_permissions(manage_channels=True)
    @poll.sub_command()
    async def create(
        self,
        inter,
        name: str = Param(description="Name of the new poll"),
        link: str = Param(description="Link to the relevant image to the poll"),
        options: str = Param(description="Options for the poll. Example A | B | C"),
    ):
        """Creates a poll"""
        embed = disnake.Embed(title="Proposed Poll", color=disnake.Color.green())
        embed.add_field(name="Name", value=name, inline=False)
        embed.add_field(name="Link", value=link, inline=False)
        embed.add_field(
            name="Options", value=" ".join(self.parse_options(options)), inline=False
        )
        view = ConfirmationButtons()
        await inter.response.send_message(
            "Is this poll correct?", view=view, embed=embed
        )
        await view.wait()
        current_poll = self.get_current_poll(inter)
        if view.value:
            poll = self.create_poll(name, inter.guild.id, link, options)
            view = ConfirmationButtons()
            msg = await inter.edit_original_message(
                content=f"Poll created successfully with id {poll.id}\nDo you want to activate it now?",
                view=view,
                embed=None,
            )
            await view.wait()
            if view.value:
                if current_poll:
                    current_poll.active = False
                poll.active = True
                self.bot.s.commit()
                self.logger.info(f"Enabled poll {poll.name}")
                self.polls[inter.guild.id] = poll
                await inter.edit_original_message(content="Poll activated!", view=None)
        else:
            await inter.edit_original_message(
                content="Alright then.", view=None, embed=None
            )

    @commands.has_guild_permissions(manage_channels=True)
    @poll.sub_command()
    async def activate(
        self, inter, poll_id: int = Param(description="ID of the poll to activate")
    ):
        """Activates a poll"""
        poll = (
            self.bot.s.query(Poll)
            .filter(Poll.guild == inter.guild.id, Poll.id == poll_id)
            .one_or_none()
        )
        if poll is None:
            return await inter.response.send_message("No poll with the provided id")
        current_poll = self.get_current_poll(inter)
        if self.get_current_poll(inter) is not None:
            current_poll.active = False
        poll.active = True
        self.bot.s.commit()
        self.logger.info(f"Enabled poll {poll.name}")
        await inter.response.send_message(f"Enabled poll {poll.name}")
        self.polls[inter.guild.id] = poll

    @commands.has_guild_permissions(manage_channels=True)
    @poll.sub_command()
    async def close(self, inter):
        """Closes a poll"""
        if (poll := self.get_current_poll(inter)) is None:
            return await inter.response.send_message("No ongoing poll")
        poll.active = False
        self.bot.s.commit()
        del self.polls[inter.guild.id]
        await inter.response.send_message("Poll closed successfully")

    @commands.has_guild_permissions(manage_nicknames=True)
    @poll.sub_command()
    async def tally(self, inter):
        """Show the current state of the poll"""
        if self.get_current_poll(inter) is None:
            return await inter.response.send_message("No ongoing poll")
        result = self.count_votes(self.get_current_poll(inter))
        embed = disnake.Embed()
        msg = ""
        for x in result.keys():
            msg += f"{x}: {result[x]}   "
        embed.add_field(name="Votes", value=msg, inline=False)
        await inter.response.send_message(embed=embed)

    @commands.has_guild_permissions(manage_channels=True)
    @poll.sub_command()
    async def list(self, inter):
        """Shows a list with current and past polls"""
        polls = self.bot.s.query(Poll).filter(Poll.guild == inter.guild.id).all()
        if polls:
            embed = disnake.Embed(title="Poll List")
            for poll in polls:
                msg = (
                    f"id={poll.id}\n"
                    f"link={poll.link}\n"
                    f"option={poll.options}\n"
                    f"active={poll.active}\n"
                    f"votes={len(poll.voters)}\n"
                )
                embed.add_field(name=poll.name, value=msg)
            await inter.response.send_message(embed=embed)
        else:
            await inter.response.send_message("No polls to show!")

    @commands.has_guild_permissions(manage_guild=True)
    @poll.sub_command()
    async def delete(
        self, inter, poll_id: int = Param(description="ID of the poll to delete")
    ):
        """Deletes a poll"""
        poll = (
            self.bot.s.query(Poll)
            .filter(Poll.id == poll_id, Poll.guild == inter.guild.id)
            .first()
        )
        if not poll:
            await inter.response.send_message("No poll associated with provided ID")
        else:
            if poll == self.get_current_poll(inter):
                del self.polls[inter.guild.id]
            self.bot.s.delete(poll)
            self.bot.s.commit()
            await inter.response.send_message("Poll deleted successfully")

    @commands.has_guild_permissions(manage_nicknames=True)
    @poll.sub_command()
    async def info(
        self, inter, poll_id: int = Param(default=None, description="ID of the poll")
    ):
        """Shows info about current poll or provided poll id"""
        if poll_id is None:
            if self.get_current_poll(inter) is None:
                await inter.response.send_message(
                    "There is ongoing poll", ephemeral=True
                )
                return
            else:
                poll_id = self.get_current_poll(inter).id
        poll = self.get_poll(inter, poll_id)
        embed = disnake.Embed(title=poll.name, color=disnake.Color.blurple())
        embed.add_field(name="ID", value=poll.id, inline=False)
        embed.add_field(name="Link", value=poll.link, inline=False)
        embed.add_field(
            name="Options",
            value=" ".join(self.parse_options(poll.options)),
            inline=False,
        )
        result = self.count_votes(poll)
        msg = ""
        for x in result.keys():
            msg += f"{x}: {result[x]}   "
        embed.add_field(name="Votes", value=msg, inline=False)
        await inter.response.send_message(embed=embed)

    async def cog_command_error(self, ctx, exc):
        self.logger.debug(f"{ctx.command}: {type(exc).__name__}: {exc}")


def setup(bot):
    bot.add_cog(Voting(bot))
