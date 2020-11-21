import asyncio
import discord
import random

from discord.ext import commands
from utils.checks import not_new, not_blacklisted
from utils.database import Giveaway, Entry, GiveawayRole, Guild
from utils.exceptions import NoOnGoingRaffle, DisabledCog
from utils.utilities import wait_for_answer
from typing import List


class Raffle(commands.Cog):
    """Giveaway commands for giveaway use"""

    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        self.raffles = {
            raffle.guild: raffle
            for raffle in self.bot.s.query(Giveaway).filter_by(ongoing=True).all()
        }
        self.queue = asyncio.Queue()

    @staticmethod
    def is_enabled(ctx):
        dbguild = ctx.bot.s.query(Guild).get(ctx.guild.id)
        return dbguild.flags & 0b100

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if not self.is_enabled(ctx):
            raise DisabledCog()
        return True

    # checks
    def ongoing_raffle(ctx: commands.Context):
        raffle = ctx.cog.get_raffle(ctx)
        if raffle and raffle.ongoing:
            return True
        raise NoOnGoingRaffle("There is no ongoing raffle.")

    # internal functions
    @staticmethod
    def get_raffle(ctx):
        return ctx.cog.raffles.get(ctx.guild.id)

    async def queue_empty(self):
        while not self.queue.empty():
            pass

    async def process_entry(self):
        ctx = await self.queue.get()
        raffle = self.get_raffle(ctx)
        if raffle.roles:
            for role in raffle.roles:
                if not any(discord.utils.get(ctx.author.roles, id=role.id)):
                    return await ctx.send("You are not allowed to participate!")
        user_id = ctx.author.id
        entry = self.bot.s.query(Entry).get((user_id, raffle.id))
        if entry:
            return await ctx.send("You are already participating!")
        self.bot.s.add(Entry(id=user_id, giveaway=raffle.id))
        self.bot.s.commit()
        await ctx.send(f"{ctx.author.mention} now you are participating in the raffle!")
        self.queue.task_done()

    def create_raffle(self, name: str, winners: int, guild: int, roles: List[int]):
        raffle = Giveaway(name=name, win_count=winners, guild=guild)
        self.bot.s.add(raffle)
        self.bot.s.commit()
        if roles:
            self.bot.s.add_all(
                [GiveawayRole(id=role_id, giveaway=raffle.id) for role_id in roles]
            )
            self.bot.s.commit()
        return raffle

    def get_winner(self, ctx):
        raffle = ctx.cog.raffles[ctx.guild.id]
        while len(raffle.entries) >= 1:
            entry = random.choice(raffle.entries)
            if (winner := ctx.guild.get_member(entry.id)) is not None:
                entry.winner = True
                self.bot.s.commit()
                return winner
            self.bot.s.delete(entry)
        return None

    @commands.check(not_blacklisted)
    @commands.check(not_new)
    @commands.check(ongoing_raffle)
    @commands.guild_only()
    @commands.command()
    async def join(self, ctx):
        await self.queue.put(ctx)
        await self.process_entry()

    @commands.guild_only()
    @commands.group(aliases=["raffle"])
    async def giveaway(self, ctx):
        """Giveaway related commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @commands.has_guild_permissions(manage_channels=True)
    @commands.guild_only()
    @giveaway.command()
    async def create(
        self,
        ctx,
        name: str,
        winners: int = 1,
        roles: commands.Greedy[discord.Role] = None,
    ):
        """Creates a giveaway"""
        if self.get_raffle(ctx):
            return await ctx.send("There is an already ongoing giveaway!")
        embed = discord.Embed(title="Proposed Giveaway", color=discord.Color.purple())
        embed.add_field(name="Name", value=name, inline=False)
        embed.add_field(name="Number of winners", value=str(winners), inline=False)
        if roles:
            embed.add_field(
                name="Roles accepted",
                value=" ".join(role.name for role in roles),
                inline=False,
            )
        await ctx.send(
            "Say `yes` to confirm giveaway creation, `no` to cancel", embed=embed
        )
        if await wait_for_answer(ctx):
            self.raffles[ctx.guild.id] = self.create_raffle(
                name=name,
                winners=winners,
                roles=[role.id for role in roles] if roles else [],
                guild=ctx.guild.id,
            )
            await ctx.send(
                f"Started giveaway {name} with {winners} possible winners! Use `{self.bot.command_prefix}join`to join"
            )
        else:
            await ctx.send("Alright then.")

    @commands.has_guild_permissions(manage_channels=True)
    @commands.check(ongoing_raffle)
    @commands.guild_only()
    @giveaway.command()
    async def info(self, ctx):
        """Shows information about current giveaway"""
        raffle = self.raffles[ctx.guild.id]
        embed = discord.Embed()
        embed.add_field(name="ID", value=raffle.id, inline=False)
        embed.add_field(name="Name", value=raffle.name, inline=False)
        if raffle.roles:
            embed.add_field(
                name="Allowed Roles",
                value="\n".join(role.id for role in raffle.roles),
                inline=False,
            )
        embed.add_field(
            name="Number of entries", value=str(len(raffle.entries)), inline=False
        )
        await ctx.send(embed=embed)

    @commands.has_guild_permissions(manage_channels=True)
    @commands.check(ongoing_raffle)
    @commands.guild_only()
    @giveaway.command()
    async def cancel(self, ctx):
        """Cancels current giveaway"""
        await ctx.send("Are you sure you want to cancel current giveaway?")
        if await wait_for_answer(ctx):
            self.raffles[ctx.guild.id].ongoing = False
            self.raffles[ctx.guild.id] = None
            self.bot.s.commit()
            return await ctx.send("Giveaway cancelled.")
        await ctx.send("And the raffle continues.")

    @commands.has_guild_permissions(manage_channels=True)
    @commands.check(ongoing_raffle)
    @commands.guild_only()
    @giveaway.command()
    async def finish(self, ctx):
        raffle = self.raffles[ctx.guild.id]
        raffle.ongoing = False
        self.bot.s.commit()
        await asyncio.wait_for(self.queue_empty(), timeout=None)
        winners = []
        for i in range(0, raffle.win_count):
            winners.append(self.get_winner(ctx))
        winners = list(filter(lambda a: a is not None, winners))
        if len(winners) < raffle.win_count:
            await ctx.send("Not enough participants for giveaway!")
            if not winners:
                await ctx.send("No users to choose...")
                raffle.ongoing = True
                return
        await ctx.send("And the winner is....!!")
        async with ctx.channel.typing():
            await asyncio.sleep(5)
            for user in winners:
                await ctx.send(f"{user.mention}")
            await ctx.send("Congratulations")
        for user in winners:
            try:
                await user.send(f"You're the {raffle.name} raffle winner!!")
            except (discord.HTTPException, discord.Forbidden):
                await ctx.send(f"Failed to send message to winner {user.mention}!")
        self.bot.s.commit()
        await ctx.send(f"Giveaway finished with {len(raffle.entries)} participants.")
        self.raffles[ctx.guild.id] = None

    @commands.check(ongoing_raffle)
    @commands.guild_only()
    @giveaway.group()
    async def modify(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @commands.has_guild_permissions(manage_channels=True)
    @modify.command()
    async def winner_count(self, ctx, value: int):
        """Modify a parameter of the raffle"""
        self.raffles[ctx.guild.id].win_count = value
        self.bot.s.commit()
        await ctx.send(f"Updated number of winners to {value}")


def setup(bot):
    bot.add_cog(Raffle(bot))
