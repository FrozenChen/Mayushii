import random
from discord.ext import commands
import os
import json
import discord
from utils.checks import not_new
import asyncio
from utils.exceptions import NoOnGoingRaffle
from datetime import datetime


class Giveaway(commands.Cog):
    """Giveaway commands for giveaway use"""
    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        self.raffle = None
        self.end = False
        self.queue = asyncio.Queue()
        if os.path.exists("giveaway.json"):
            with open("giveaway.json", 'r') as f:
                self.raffle = json.load(f)

    def write_raffle(self):
        with open("giveaway.json", 'w') as f:
            json.dump(self.raffle, f)

    def ongoing_raffle(ctx):
        if ctx.cog.raffle and not ctx.cog.end:
            return True
        raise NoOnGoingRaffle("There is no ongoing raffle.")

    async def process_entry(self):
        ctx = await self.queue.get()
        userid = ctx.author.id
        if userid in self.raffle['users']:
            return await ctx.send("You are already participating!")
        self.raffle['users'].append(ctx.author.id)
        self.write_raffle()
        await ctx.send(f"{ctx.author.mention} now you are participating in the raffle!")
        self.queue.task_done()

    @commands.check(not_new)
    @commands.check(ongoing_raffle)
    @commands.guild_only()
    @commands.command()
    async def join(self, ctx):
        await self.queue.put((ctx))
        await self.process_entry()

    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    @commands.command()
    async def start(self, ctx, winners:int =1):
        if self.raffle:
            return await ctx.send("There is an already ongoing giveaway!")
        self.raffle = {'users': [], 'winners':winners}
        self.write_raffle()
        await ctx.send(f"Started giveaway with {winners} possible winners! Use `{self.bot.command_prefix}join`to join")

    async def queue_empty(self):
        while not self.queue.empty():
            pass

    def get_winner(self):
        while len(self.raffle['users']) >= 1:
            winnerid = random.choice(self.raffle['users'])
            if (winner := self.bot.guild.get_member(winnerid)) is not None:
                return winner
            self.raffle['users'].remove(winnerid)
        return None

    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    @commands.check(ongoing_raffle)
    @commands.command()
    async def finish(self, ctx):
        self.end = True
        await asyncio.wait_for(self.queue_empty(), timeout=None)
        winners = []
        for i in range(0, self.raffle['winners']):
            winners.append(self.get_winner())
        winners = list(filter(lambda a: a is not None, winners))
        if len(winners) < self.raffle['winners']:
            await ctx.send("Not enough participants for giveaway!")
            if not winners:
                await ctx.send("No users to choose...")
                self.end = False
                return
        await ctx.send("And the winner is....!!")
        async with ctx.channel.typing():
            await asyncio.sleep(5)
            for user in winners:
                await ctx.send(f"{user.mention}")
            await ctx.send("Congratulations")
        for user in winners:
            try:
                await user.send("you're the winner")
            except (discord.HTTPException, discord.Forbidden):
                await ctx.send(f"Failed to send message to winner {user.mention}!")
        await ctx.send(f"Giveaway finished with {len(self.raffle['users'])} participants.")
        self.end = False
        os.rename('giveaway.json', f'giveaway.json.old-{datetime.now().strftime("%d-%b-%Y-%H-%M-%S)")}')

    @commands.guild_only()
    @commands.group()
    async def modify(self,ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("No parameter selected.")

    @commands.has_permissions(manage_channels=True)
    @commands.check(ongoing_raffle)
    @commands.guild_only()
    @modify.command()
    async def winners(self,ctx, value: int):
        """Modify a parameter of the raffle"""
        self.raffle['winners'] = value
        self.write_raffle()
        await ctx.send(f"Updated number of winners to {value}")


def setup(bot):
    bot.add_cog(Giveaway(bot))





