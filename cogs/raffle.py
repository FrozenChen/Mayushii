import asyncio
import discord
import random

from discord.ext import commands
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from utils.checks import not_new, not_blacklisted
from utils.database import Giveaway, Entry, GiveawayRole, BlackList
from utils.exceptions import NoOnGoingRaffle

Base = declarative_base()


class Raffle(commands.Cog):
    """Giveaway commands for giveaway use"""

    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        engine = create_engine("sqlite:///giveaway.db")
        session = sessionmaker(bind=engine)
        self.s = session()
        Base.metadata.create_all(
            engine,
            tables=[
                Giveaway.__table__,
                Entry.__table__,
                GiveawayRole.__table__,
                BlackList.__table__,
            ],
        )
        self.s.commit()
        self.raffle = self.s.query(Giveaway).filter_by(ongoing=True).scalar()
        self.queue = asyncio.Queue()

    def ongoing_raffle(ctx: commands.Context):
        if ctx.cog.raffle and ctx.cog.raffle.ongoing:
            return True
        raise NoOnGoingRaffle("There is no ongoing raffle.")

    async def process_entry(self):
        ctx = await self.queue.get()
        if self.raffle.roles:
            if not any(
                self.s.query(GiveawayRole).get((role.id, self.raffle.id))
                for role in ctx.author.roles
            ):
                return await ctx.send("You are not allowed to participate!")
        user_id = ctx.author.id
        entry = self.s.query(Entry).get((user_id, self.raffle.id))
        if entry:
            return await ctx.send("You are already participating!")
        self.s.add(Entry(id=user_id, giveaway=self.raffle.id))
        self.s.commit()
        await ctx.send(f"{ctx.author.mention} now you are participating in the raffle!")
        self.queue.task_done()

    @commands.check(not_blacklisted)
    @commands.check(not_new)
    @commands.check(ongoing_raffle)
    @commands.guild_only()
    @commands.command()
    async def join(self, ctx):
        await self.queue.put(ctx)
        await self.process_entry()

    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    @commands.command()
    async def start(
        self,
        ctx,
        name: str,
        winners: int = 1,
        roles: commands.Greedy[discord.Role] = None,
    ):
        if self.raffle:
            return await ctx.send("There is an already ongoing giveaway!")
        self.raffle = Giveaway(name=name, win_count=winners)
        self.s.add(self.raffle)
        self.s.commit()
        if roles:
            self.s.add_all(
                [GiveawayRole(id=role.id, giveaway=self.raffle.id) for role in roles]
            )
            self.s.add_all(
                [
                    GiveawayRole(id=role_id, giveaway=self.raffle.id)
                    for role_id in self.bot.config["default_roles"]
                ]
            )
        self.s.commit()
        await ctx.send(
            f"Started giveaway with {winners} possible winners! Use `{self.bot.command_prefix}join`to join"
        )

    async def queue_empty(self):
        while not self.queue.empty():
            pass

    def get_winner(self):
        while len(self.raffle.entries) >= 1:
            entry = random.choice(self.raffle.entries)
            if (winner := self.bot.guild.get_member(entry.id)) is not None:
                entry.winner = True
                self.s.commit()
                return winner
            self.s.delete(entry)
        return None

    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    @commands.check(ongoing_raffle)
    @commands.command()
    async def finish(self, ctx):
        self.raffle.ongoing = False
        self.s.commit()
        await asyncio.wait_for(self.queue_empty(), timeout=None)
        winners = []
        for i in range(0, self.raffle.win_count):
            winners.append(self.get_winner())
        winners = list(filter(lambda a: a is not None, winners))
        if len(winners) < self.raffle.win_count:
            await ctx.send("Not enough participants for giveaway!")
            if not winners:
                await ctx.send("No users to choose...")
                self.raffle.ongoing = True
                return
        await ctx.send("And the winner is....!!")
        async with ctx.channel.typing():
            await asyncio.sleep(5)
            for user in winners:
                await ctx.send(f"{user.mention}")
            await ctx.send("Congratulations")
        for user in winners:
            try:
                await user.send(f"You're the {self.raffle.name} raffle winner!!")
            except (discord.HTTPException, discord.Forbidden):
                await ctx.send(f"Failed to send message to winner {user.mention}!")
        self.s.commit()
        await ctx.send(
            f"Giveaway finished with {len(self.raffle.entries)} participants."
        )
        self.raffle = None

    @commands.has_permissions(manage_nicknames=True)
    @commands.guild_only()
    @commands.command()
    async def denygiveaway(self, ctx, member: discord.Member):
        """Blacklist user"""
        if self.s.query(BlackList).get(member.id):
            await ctx.send(f"{member} is already in the blacklist")
            return
        self.s.add(BlackList(userid=member.id))
        self.s.commit()
        await ctx.send(f"Added {member} to the blacklist")

    @commands.has_permissions(manage_nicknames=True)
    @commands.guild_only()
    @commands.command()
    async def allowgiveaway(self, ctx, member: discord.Member):
        """Removes user from Blacklist"""
        if not (entry := self.s.query(BlackList).get(member.id)):
            await ctx.send(f"{member} is not in the blacklist.")
            return
        self.s.remove(entry)
        self.s.commit()
        await ctx.send(f"Removed {member} from the blacklist")

    @commands.guild_only()
    @commands.group()
    async def modify(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("No parameter selected.")

    @commands.has_permissions(manage_channels=True)
    @commands.check(ongoing_raffle)
    @commands.guild_only()
    @modify.command()
    async def winner_count(self, ctx, value: int):
        """Modify a parameter of the raffle"""
        self.raffle.win_count = value
        self.s.commit()
        await ctx.send(f"Updated number of winners to {value}")


def setup(bot):
    bot.add_cog(Raffle(bot))
