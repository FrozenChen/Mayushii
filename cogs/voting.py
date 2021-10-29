import asyncio
import discord

from discord.ext import commands
from utils.database import Poll, Voter, Guild
from utils.exceptions import NoOnGoingPoll, DisabledCog
from utils.checks import not_new, not_blacklisted
from utils.utilities import wait_for_answer


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
    def ongoing_poll(ctx: commands.context):
        if ctx.cog.polls.get(ctx.guild.id) is None:
            raise NoOnGoingPoll(f"There is no ongoing poll")
        return True

    # Internal functions
    def get_voter(self, member: discord.Member):
        return self.bot.s.query(Voter).get((member.id, self.polls[member.guild.id].id))

    @staticmethod
    def get_current_poll(ctx):
        return ctx.cog.polls.get(ctx.guild.id)

    @staticmethod
    def get_poll(ctx, poll_id: str):
        return (
            ctx.bot.s.query(Poll)
            .filter(Poll.id == poll_id, Poll.guild == ctx.guild.id)
            .one_or_none()
        )

    def delete_vote(self, member: discord.Member):
        voter = self.get_voter(member)
        if voter is not None:
            self.bot.s.delete(voter)
            self.bot.s.commit()

    async def process_vote(self):
        ctx, option = await self.queue.get()
        voter = self.get_voter(ctx.author)
        poll = self.get_current_poll(ctx)
        if voter is None:
            voter = Voter(userid=ctx.author.id, poll_id=poll.id, option=option)
            self.bot.s.add(voter)
            await ctx.send("Vote added successfully!", delete_after=10)
        else:
            voter.option = option
            await ctx.send("Vote modified successfully!", delete_after=10)

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

    @commands.check(not_new)
    @commands.check(not_blacklisted)
    @commands.check(ongoing_poll)
    @commands.guild_only()
    @commands.command()
    async def vote(self, ctx, option: str):
        """Votes for a option in the current poll."""
        await ctx.message.delete()
        if option not in self.parse_options(self.get_current_poll(ctx).options):
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

    @commands.has_guild_permissions(manage_channels=True)
    @poll.command()
    async def create(self, ctx, name, link, *, options):
        """Creates a poll"""
        embed = discord.Embed(title="Proposed Poll", color=discord.Color.green())
        embed.add_field(name="Name", value=name, inline=False)
        embed.add_field(name="Link", value=link, inline=False)
        embed.add_field(
            name="Options", value=" ".join(self.parse_options(options)), inline=False
        )
        await ctx.send(
            "Say `yes` to confirm poll creation, `no` to cancel", embed=embed
        )
        current_poll = self.get_current_poll(ctx)
        if await wait_for_answer(ctx):
            poll = self.create_poll(name, ctx.guild.id, link, options)
            await ctx.send(
                f"Poll created successfully with id {poll.id}\nDo you want to activate it now?"
            )
            if await wait_for_answer(ctx):
                if current_poll:
                    current_poll.active = False
                poll.active = True
                self.bot.s.commit()
                self.logger.info(f"Enabled poll {poll.name}")
                self.polls[ctx.guild.id] = poll
                await ctx.send("Poll activated!")
        else:
            await ctx.send("Alright then.")

    @commands.has_guild_permissions(manage_channels=True)
    @poll.command()
    async def activate(self, ctx, poll_id: int):
        """Activates a poll"""
        poll = (
            self.bot.s.query(Poll)
            .filter(Poll.guild == ctx.guild.id, Poll.id == poll_id)
            .one_or_none()
        )
        if poll is None:
            await ctx.send("No poll with the provided id")
        current_poll = self.get_current_poll(ctx)
        if self.get_current_poll(ctx) is not None:
            current_poll.active = False
        poll.active = True
        self.bot.s.commit()
        self.logger.info(f"Enabled poll {poll.name}")
        await ctx.send(f"Enabled poll {poll.name}")
        self.polls[ctx.guild.id] = poll

    @commands.has_guild_permissions(manage_channels=True)
    @poll.command()
    async def close(self, ctx):
        """Closes a poll"""
        if (poll := self.get_current_poll(ctx)) is None:
            return await ctx.send("No ongoing poll")
        poll.active = False
        self.bot.s.commit()
        del self.polls[ctx.guild.id]

    @commands.has_guild_permissions(manage_nicknames=True)
    @commands.command()
    async def tally(self, ctx):
        if self.get_current_poll(ctx) is None:
            return await ctx.send("No ongoing poll")
        result = self.count_votes(self.get_current_poll(ctx))
        embed = discord.Embed()
        msg = ""
        for x in result.keys():
            msg += f"{x}: {result[x]}   "
        embed.add_field(name="Votes", value=msg, inline=False)
        await ctx.send(embed=embed)

    @commands.has_guild_permissions(manage_channels=True)
    @poll.command()
    async def list(self, ctx):
        polls = self.bot.s.query(Poll).filter(Poll.guild == ctx.guild.id).all()
        if polls:
            embed = discord.Embed(title="Poll List")
            for poll in polls:
                msg = (
                    f"id={poll.id}\n"
                    f"link={poll.link}\n"
                    f"option={poll.options}\n"
                    f"active={poll.active}\n"
                    f"votes={len(poll.voters)}\n"
                )
                embed.add_field(name=poll.name, value=msg)
            await ctx.send(embed=embed)
        else:
            await ctx.send("No polls to show!")

    @commands.has_guild_permissions(manage_guild=True)
    @poll.command()
    async def delete(self, ctx, poll_id: int):
        """Deletes a poll"""
        poll = self.bot.s.query(Poll).filter(
            Poll.id == poll_id, Poll.guild == ctx.guild.id
        ).first()
        if not poll:
            await ctx.send("No poll associated with provided ID")
        else:
            if poll == self.get_current_poll(ctx):
                del self.polls[ctx.guild.id]
            self.bot.s.delete(poll)
            self.bot.s.commit()
            await ctx.send("Poll deleted successfully")

    @commands.has_guild_permissions(manage_nicknames=True)
    @poll.command()
    async def info(self, ctx, poll_id: int = None):
        """Shows info about current poll or provided poll id"""
        if poll_id is None:
            if self.get_current_poll(ctx) is None:
                await ctx.send_help(ctx.command)
                return
            else:
                poll_id = self.get_current_poll(ctx).id
        poll = self.get_poll(ctx, poll_id)
        embed = discord.Embed(title=poll.name, color=discord.Color.blurple())
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
        await ctx.send(embed=embed)

    async def cog_command_error(self, ctx, exc):
        self.logger.debug(f"{ctx.command}: {type(exc).__name__}: {exc}")


def setup(bot):
    bot.add_cog(Voting(bot))
