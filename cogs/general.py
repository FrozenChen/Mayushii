import discord
from discord.ext import commands
import subprocess
from urllib import request


class General(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.get_logger(self)

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

    @commands.has_permissions(manage_channels=True)
    @commands.command()
    async def quit(self, ctx):
        await ctx.send("See you later!")
        await self.bot.close()

    @commands.has_permissions(manage_guild=True)
    @commands.command()
    async def changepfp(self, ctx, url: str = ""):
        if not url:
            if ctx.message.attachments:
                url = ctx.message.attachments[0].url
            else:
                await ctx.send("No image provided")
                return
        req = request.Request(url, headers={"user-agent": "Mayushii"})
        data = request.urlopen(req).read()
        await self.bot.user.edit(avatar=data)
        await ctx.send("Profile picture changed successfully.")

    async def cog_command_error(self, ctx, exc):
        self.logger.debug(f"{ctx.command}: {type(exc).__name__}: {exc}")

def setup(bot):
    bot.add_cog(General(bot))
