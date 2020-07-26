import discord
from discord.ext import commands
import subprocess
import aiohttp


class General(commands.Cog):
    """General commands for general use."""

    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.get_logger(self)

    @commands.command()
    async def about(self, ctx):
        """About Mayushii"""
        embed = discord.Embed(
            title="Mayushii", url="https://github.com/FrozenChen/Mayushii"
        )
        embed.description = "A bot for Nintendo Homebrew artistic channel."
        embed.set_thumbnail(url="https://files.frozenchen.me/vD7vM.png")
        await ctx.send(embed=embed)

    @commands.has_permissions(manage_channels=True)
    @commands.command()
    async def pull(self, ctx):
        """Pull changes from repo"""
        await ctx.send("Pulling changes")
        subprocess.run(["git", "pull"])
        await self.bot.close()

    @commands.has_permissions(manage_channels=True)
    @commands.command()
    async def load(self, ctx, cog: str):
        """Load a cog"""
        try:
            self.bot.load_extension(f"cogs.{cog}")
            await ctx.send(f"Loaded `{cog}``!")
        except commands.ExtensionNotFound:
            await ctx.send(f"Extension {cog} not found")
        except commands.ExtensionFailed:
            await ctx.send(f"Error occurred when loading {cog}")

    @commands.has_permissions(manage_channels=True)
    @commands.command()
    async def unload(self, ctx, cog: str):
        """Unloads a cog"""
        try:
            self.bot.unload_extension(f"cogs.{cog}")
            await ctx.send(f"Unloaded {cog}!")
        except Exception as exc:
            await ctx.send(
                f"Failed to unload cog!```\n{type(exc).__name__}: {exc}\n```"
            )

    @commands.has_permissions(manage_channels=True)
    @commands.command()
    async def quit(self, ctx):
        """This kills the bot"""
        await ctx.send("See you later!")
        await self.bot.close()

    @commands.has_permissions(manage_guild=True)
    @commands.command()
    async def changepfp(self, ctx, url: str = ""):
        """Change bot profile picture"""
        if not url:
            if ctx.message.attachments:
                url = ctx.message.attachments[0].url
            else:
                await ctx.send("No image provided")
                return
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                if r.status != 200:
                    return await ctx.send("Failed to retrieve image!")
                data = await r.read()
                await self.bot.user.edit(avatar=data)
                await ctx.send("Profile picture changed successfully.")

    async def cog_command_error(self, ctx, exc):
        self.logger.debug(f"{ctx.command}: {type(exc).__name__}: {exc}")


def setup(bot):
    bot.add_cog(General(bot))
