import discord
from discord.ext import commands
import subprocess


class General(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def about(self, ctx):
        embed = discord.Embed(title="Mayushii", url="https://github.com/FrozenChen/Mayushii")
        embed.description = "A bot for Nintendo Homebrew artistic channel."
        embed.set_thumbnail(url="https://files.frozenchen.me/vD7vM.png")
        await ctx.send(embed=embed)

    @commands.has_permissions(manage_channels=True)
    @commands.command()
    async def pull(self, ctx):
        await ctx.send("Pulling changes")
        subprocess.run(["git", "pull"])
        await self.bot.close()


def setup(bot):
    bot.add_cog(General(bot))
