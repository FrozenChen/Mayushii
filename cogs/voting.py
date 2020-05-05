import asyncio
import discord
from discord.ext import commands
from sqlalchemy import create_engine, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from utils.database import Poll, Voter, Vote, BlackList
from utils.exceptions import NoOnGoingPoll, BlackListed
from utils.checks import not_new

Base = declarative_base()


class Voting(commands.Cog):
    """Commands for managing a poll."""
    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        engine = create_engine('sqlite:///vote.db')
        session = sessionmaker(bind=engine)
        self.s = session()
        Base.metadata.create_all(engine, tables=[Poll.__table__, Voter.__table__, Vote.__table__, BlackList.__table__])
        self.s.commit()
        self.current_poll = self.s.query(Poll).filter_by(active=True).scalar()
        self.logger.info(f"Loaded poll {self.current_poll.name}" if self.current_poll else "No poll loaded")
        self.queue = asyncio.Queue()

    # Checks
    def ongoing_poll(ctx):
        if ctx.cog.current_poll is None:
            raise NoOnGoingPoll(f"There is no ongoing poll")
        return True

    def not_blacklisted(ctx):
        if ctx.cog.s.query(BlackList).get(ctx.author.id):
            ctx.message.delete()
            raise BlackListed("You are blacklisted and cant use this command")
        return True

    # Internal functions
    def delete_vote(self, user):
        vote = self.s.query(Vote).get((user.id, self.current_poll.id))
        if vote is not None:
            self.s.delete(vote)
            self.s.commit()

    async def process_vote(self):
        ctx, option = await self.queue.get()
        voterid = ctx.author.id
        voter = self.s.query(Voter).get(voterid)
        if voter is None:
            voter = Voter(userid=voterid)
            self.s.add(voter)
        vote = self.s.query(Vote).filter(and_(Vote.voter_id == voter.userid, Vote.poll_id == self.current_poll.id)).scalar()
        if vote is None:
            self.logger.debug(f"Added vote")
            await ctx.send("Vote added successfully!", delete_after=10)
            self.s.add(Vote(voter_id=voter.userid, poll_id=self.current_poll.id, option=option))
        else:
            self.logger.debug(f"Modified vote")
            await ctx.send("Vote modified successfully!", delete_after=10)
            vote.option = option
        self.s.commit()
        self.queue.task_done()

    def count_votes(self, poll: Poll):
        result = {}
        for option in self.parse_options(poll.options):
            c = self.s.query(Vote).filter(and_(Vote.poll_id == poll.id, Vote.option == option)).count()
            result[option] = c
        return result

    def create_poll(self, name, link, options: str):
        poll = Poll(name=name, link=link, options=options)
        self.s.add(poll)
        self.s.commit()
        return poll

    def add_blacklisted(self, user: discord.Member):
        self.s.add(BlackList(userid=user.id))
        self.s.commit()

    def remove_blacklisted(self, user: discord.Member):
        blacklisted = self.s.query(BlackList).get(user.id)
        self.s.delete(blacklisted)
        self.s.commit()

    @staticmethod
    def parse_options(options: str):
        return options.split(" | ")

    @commands.check(not_new)
    @commands.check(not_blacklisted)
    @commands.check(ongoing_poll)
    @commands.guild_only()
    @commands.command()
    async def vote(self, ctx, option: str):
        """Votes for a option in the current poll."""
        await ctx.message.delete()
        if option not in self.parse_options(self.current_poll.options):
            await ctx.send("Invalid option")
            return
        await self.queue.put((ctx, option))
        await self.process_vote()

    @commands.guild_only()
    @commands.group()
    async def poll(self, ctx):
        """Poll related commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    async def wait_for_answer(self, ctx):
        try:
            msg = await self.bot.wait_for('message', timeout=15, check=lambda message: message.author == ctx.author
                                          and ('yes' in message.content or 'no' in message.content))
        except asyncio.TimeoutError:
            await ctx.send("You took too long 🐢")
            return None
        return 'yes' in msg.content

    @commands.has_permissions(manage_channels=True)
    @poll.command()
    async def create(self, ctx, name, link, *, options):
        """Creates a poll"""
        embed = discord.Embed(title="Proposed Poll", color=discord.Color.green())
        embed.add_field(name="Name", value=name, inline=False)
        embed.add_field(name="Link", value=link, inline=False)
        embed.add_field(name="Options", value=' '.join(self.parse_options(options)), inline=False)
        await ctx.send("Say `yes` to confirm poll creation, `no` to cancel", embed=embed)

        if await self.wait_for_answer(ctx):
            poll = self.create_poll(name, link, options)
            await ctx.send(f"Poll created successfully with id {poll.id}\nDo you want to activate it now?")
            if await self.wait_for_answer(ctx):
                if self.current_poll:
                    self.current_poll.active = False
                poll.active = True
                self.s.commit()
                self.logger.info(f"Enabled poll {poll.name}")
                self.current_poll = poll
                await ctx.send("Poll activated!")
        else:
            await ctx.send("Alright then.")

    @commands.has_permissions(manage_channels=True)
    @poll.command()
    async def activate(self, ctx, poll_id: int):
        """Activates a poll"""
        poll = self.s.query(Poll).get(poll_id)
        if poll is None:
            await ctx.send("No poll with the provided id")
        if self.current_poll is not None:
            self.current_poll.active = False
        poll.active = True
        self.s.commit()
        self.logger.info(f"Enabled poll {poll.name}")
        await ctx.send(f"Enabled poll {poll.name}")
        self.current_poll = poll

    @commands.has_permissions(manage_channels=True)
    @poll.command()
    async def close(self, ctx):
        """Closes a poll"""
        if self.current_poll is None:
            return await ctx.send("No ongoing poll")
        self.current_poll.active = False
        self.s.commit()
        self.current_poll = None

    @commands.has_permissions(manage_nicknames=True)
    @commands.command()
    async def tally(self, ctx):
        if self.current_poll is None:
            return await ctx.send("No ongoing poll")
        result = self.count_votes(self.current_poll)
        embed = discord.Embed()
        msg = ""
        for x in result.keys():
            msg += f"{x}: {result[x]}   "
        embed.add_field(name="Votes", value=msg, inline=False)
        await ctx.send(embed=embed)

    @commands.has_permissions(manage_channels=True)
    @poll.command()
    async def list(self, ctx):
        polls = self.s.query(Poll).all()
        if polls:
            embed = discord.Embed(title="Poll List")
            for poll in polls:
                msg = f"id={poll.id}\n" \
                      f"link={poll.link}\n" \
                      f"option={poll.options}\n" \
                      f"active={poll.active}\n" \
                      f"votes={len(poll.votes)}\n"
                embed.add_field(name=poll.name, value=msg)
            await ctx.send(embed=embed)
        else:
            await ctx.send("No polls to show!")

    @commands.has_permissions(manage_guild=True)
    @poll.command()
    async def delete(self, ctx, poll_id: int):
        """Deletes a poll"""
        poll = self.s.query(Poll).get(poll_id)
        if not poll:
            await ctx.send("No poll associated with provided ID")
        else:
            if poll == self.current_poll:
                self.current_poll = None
            self.s.delete(poll)
            self.s.commit()
            await ctx.send("Poll deleted successfully")

    @commands.has_permissions(manage_nicknames=True)
    @poll.command()
    async def info(self, ctx, poll_id: int = None):
        """Shows info about current poll or provided poll id"""
        if poll_id is None:
            if self.current_poll is None:
                await ctx.send_help(ctx.command)
                return
            else:
                poll_id = self.current_poll.id
        poll = self.s.query(Poll).get(poll_id)
        embed = discord.Embed(title=poll.name, color=discord.Color.blurple())
        embed.add_field(name="ID", value=poll.id, inline=False)
        embed.add_field(name="Link", value=poll.link, inline=False)
        embed.add_field(name="Options", value=" ".join(self.parse_options(poll.options)), inline=False)
        result = self.count_votes(poll)
        msg = ""
        for x in result.keys():
            msg += f"{x}: {result[x]}   "
        embed.add_field(name="Votes", value=msg, inline=False)
        await ctx.send(embed=embed)

    @commands.group()
    async def blacklist(self, ctx):
        """Commands for the blacklist"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @blacklist.command(name="add")
    async def blacklist_add(self, ctx, member: discord.Member):
        """Adds member to blacklist"""
        if self.s.query(BlackList).get(member.id):
            await ctx.send("User is already blacklisted")
            return
        self.add_blacklisted(member)
        await ctx.send(f"Blacklisted {member.mention}!")

    @blacklist.command(name="remove")
    async def blacklist_remove(self, ctx, member: discord.Member):
        """Removes member from blacklist."""
        user = self.s.query(BlackList).get(member.id)
        if not user:
            await ctx.send("User is not blacklisted")
            return
        self.remove_blacklisted(member)
        await ctx.send(f"Removed {member} from blacklist!")

    async def cog_command_error(self, ctx, exc):
        self.logger.debug(f"{ctx.command}: {type(exc).__name__}: {exc}")


def setup(bot):
    bot.add_cog(Voting(bot))
