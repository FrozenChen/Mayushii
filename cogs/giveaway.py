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
        self.queue = asyncio.Queue()
        if os.path.exists("giveaway.json"):
            with open("giveaway.json", 'r') as f:
                self.raffle = json.load(f)

    def write_raffle(self):
        with open("giveaway.json", 'w') as f:
            json.dump(self.raffle, f)

    def ongoing_raffle(ctx):
        if ctx.cog.raffle:
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
    async def start(self, ctx):
        if self.raffle:
            return await ctx.send("There is an already ongoing giveaway!")
        self.raffle = {'users': []}
        self.write_raffle()
        await ctx.send(f"Started giveaway! Use `{self.bot.command_prefix}join`to join")

    async def queue_empty(self):
        while not self.queue.empty():
            pass

    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    @commands.check(ongoing_raffle)
    @commands.command()
    async def finish(self, ctx):
        await asyncio.wait_for(self.queue_empty(), timeout=None)
        winnerid = random.choice(self.raffle['users'])
        if (winner := ctx.guild.get_member(winnerid)) is None:
            self.raffle['users'].remove(winnerid)
            self.write_raffle()
            return await ctx.send("Winner is no longer in the server, run `finish` command again to select a different winner")
        await ctx.send("And the winner is....!!")
        async with ctx.channel.typing():
            await asyncio.sleep(5)
            await ctx.send(f"{winner.mention}!\nCongratulations!")
        try:
            await winner.send("you're the winner")
        except (discord.HTTPException, discord.Forbidden):
            await ctx.send("Failed to send message to winner!")
        await ctx.send(f"Giveaway finished with {len(self.raffle['users'])} participants.")
        self.raffle = None
        os.rename('giveaway.json', f'giveaway.json.old-{datetime.now().strftime("%d-%b-%Y-%H-%M-%S)")}')


def setup(bot):
    bot.add_cog(Giveaway(bot))





