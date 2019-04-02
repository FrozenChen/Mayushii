
import asyncio
import discord
from discord.ext import commands
from sqlalchemy import create_engine, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from utils.database import Poll, Voter, Vote, BlackList
from datetime import datetime

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

    def ongoing_poll(ctx):
        return ctx.cog.current_poll is not None

    def not_new(ctx):
        print(datetime.now() - ctx.author.joined_at)
        return datetime.now() - ctx.author.joined_at


    def add_vote(self, user, option):
        voter = self.s.query(Voter).get(user.id)
        if voter is None:
            voter = Voter(userid=user.id)
            self.s.add(voter)
        vote = self.s.query(Vote).get((voter.id, self.current_poll.id))
        if vote is None:
            self.logger.debug(f"Added vote")
            self.s.add(Vote(voter_id=voter.userid), poll_id=self.current_poll.id, option=option)
        else:
            self.logger.debug(f"Modified vote")
            vote.option = option
        self.s.commit()

    def delete_vote(self, user):
        vote = self.s.query(Vote).get((user.id, self.current_poll.id))
        if vote is not None:
            self.s.delete(vote)
            self.s.commit()

    def create_poll(self, name, link, options: str):
        self.s.add(Poll(name=name, link=link, options=options))
        self.s.commit()

    @staticmethod
    def parse_options(options: str):
        return options.split(" | ")

    async def process_vote(self):
        ctx, option = await self.queue.get()
        self.s.add(Vote(voter_id=ctx.author.id, poll_id=self.current_poll.id, option=option))
        self.s.commit()
        self.queue.task_done()

    def count_votes(self, poll: Poll)-> dict:
        result = {}
        for option in self.parse_options(poll.options):
            c = self.s.query(Vote).filter(and_(Vote.poll_id == Poll.id, Vote.option == option)).count()
            result[option] = c
        return result

    @commands.check(not_new)
    @commands.check(ongoing_poll)
    @commands.command()
    async def vote(self, ctx, option: str):
        """Votes for a option in the current poll."""
        if option not in self.parse_options(self.current_poll.options):
            await ctx.send("Invalid option")
            return
        vote = self.s.query(Vote).filter(and_(Vote.voter_id == ctx.author.id, Vote.poll_id == self.current_poll.id)).scalar()
        if vote is not None:
            vote.option = option
            self.s.commit()
            await ctx.send("Vote modified successfully")
            return
        await self.queue.put((ctx, option))
        await self.process_vote()
        await ctx.send("Vote added successfully")

    @commands.group()
    async def poll(self, ctx):
        """Poll related commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @commands.has_permissions(manage_channels=True)
    @poll.command()
    async def create(self, ctx, name, link, *, options):
        """Creates a poll"""
        await ctx.send("The following poll will be created:\n"
                       f"Name={name}\n"
                       f"link={link}\n"
                       f"options={' '.join(self.parse_options(options))}\n"
                       "Say `yes` to confirm or `no` to deny")
        try:
            msg = await self.bot.wait_for('message', timeout=15, check=lambda message: message.author == ctx.author
                                          and 'yes' in message.content or 'no' in message.content)
        except asyncio.TimeoutError:
            await ctx.send("You took too long 🐢")
            return
        if "yes" in msg.content:
            self.create_poll(name, link, options)
            await ctx.send("Poll created successfully")
        else:
            await ctx.send("Alright then")

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

    @poll.command()
    async def list(self, ctx):
        embed = discord.Embed(title="Poll List")
        for poll in self.s.query(Poll).all():
            msg = f"id={poll.id}\nlink={poll.link}\noption={poll.options}\nactive={poll.active}\nvotes={len(poll.votes)}\n\n\n"
            embed.add_field(name=poll.name, value=msg)
        await ctx.send(embed=embed)

    @commands.has_permissions(manager_guild=True)
    @poll.command()
    async def delete(self, ctx, poll_id: int):
        """Deletes a poll"""
        poll = self.s.query(Poll).get(poll_id)
        if not poll:
            await ctx.send("No poll associated with provided ID")
        else:
            self.s.delete(poll)
            self.s.commit()
            await ctx.send("Poll deleted successfully")

    @commands.has_permissions(change_nicknames=True)
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

    @vote.error
    async def on_error(self, ctx ,exc):
        if isinstance(exc, commands.CheckFailure):
            await ctx.send("There is no ongoing poll")
            return True

    async def cog_command_error(self, ctx, exc):
        self.logger.debug(f"{ctx.command}: {type(exc).__name__}: {exc}")

def setup(bot):
    bot.add_cog(Voting(bot))
