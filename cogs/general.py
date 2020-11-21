import discord
import subprocess
import aiohttp

from discord.ext import commands
from utils.database import Guild, BlackList
from utils.exceptions import BotOwnerOnly


class General(commands.Cog):
    """General commands for general use."""

    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        self.cogs = {
            "community": 0b1,
            "gallery": 0b10,
            "raffle": 0b100,
            "voting": 0b1000,
        }

    def bot_owner_only(ctx):
        if ctx.author.id != ctx.bot.owner_id:
            raise BotOwnerOnly()
        return True

    @commands.check(bot_owner_only)
    @commands.command()
    async def about(self, ctx):
        """About Mayushii"""
        embed = discord.Embed(
            title="Mayushii", url="https://github.com/FrozenChen/Mayushii"
        )
        embed.description = "A bot for Nintendo Homebrew artistic channel."
        embed.set_thumbnail(url="https://files.frozenchen.me/vD7vM.png")
        await ctx.send(embed=embed)

    @commands.check(bot_owner_only)
    @commands.command()
    async def pull(self, ctx):
        """Pull changes from repo"""
        await ctx.send("Pulling changes")
        subprocess.run(["git", "pull"])
        await self.bot.close()

    @commands.check(bot_owner_only)
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

    @commands.check(bot_owner_only)
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

    @commands.check(bot_owner_only)
    @commands.command()
    async def quit(self, ctx):
        """This kills the bot"""
        await ctx.send("See you later!")
        await self.bot.close()

    @commands.check(bot_owner_only)
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

    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @commands.command()
    async def seterrchannel(self, ctx, channel: discord.TextChannel):
        """Set the channel to output errors"""
        dbguild = self.bot.s.query(Guild).get(ctx.guild.id)
        dbguild.error_channel = channel.id
        self.bot.s.commit()
        await ctx.send(f"Error Channel set to {channel.mention}")

    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @commands.command()
    async def status(self, ctx):
        dbguild = self.bot.s.query(Guild).get(ctx.guild.id)
        embed = discord.Embed()
        embed.add_field(name="Guild", value=f"{ctx.guild.name}", inline=False)
        embed.add_field(
            name="Cogs",
            value="\n".join(
                f'{cog}: {"enabled" if value & dbguild.flags else "disabled"}'
                for cog, value in self.cogs.items()
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @commands.command()
    async def togglecog(self, ctx, cog: str):
        if cog in self.cogs:
            dbguild = self.bot.s.query(Guild).get(ctx.guild.id)
            dbguild.flags ^= self.cogs[cog]
            self.bot.s.commit()
            return await ctx.send("Cog toggled.")
        await ctx.send("Cog not found.")

    @commands.guild_only()
    @commands.group()
    async def blacklist(self, ctx):
        """Commands for the blacklist"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @blacklist.command(name="add")
    async def blacklist_add(self, ctx, member: discord.Member):
        """Adds member to blacklist"""
        if self.bot.s.query(BlackList).get((member.id, ctx.guild.id)):
            await ctx.send("User is already blacklisted")
            return
        self.bot.s.add(BlackList(userid=member.id, guild=ctx.guild.id))
        await ctx.send(f"Blacklisted {member.mention}!")

    @blacklist.command(name="remove")
    async def blacklist_remove(self, ctx, member: discord.Member):
        """Removes member from blacklist."""
        user = self.bot.s.query(BlackList).get((member.id, ctx.guild.id))
        if not user:
            await ctx.send("User is not blacklisted")
            return
        self.bot.s.delete(user)
        await ctx.send(f"Removed {member.mention} from blacklist!")

    async def cog_command_error(self, ctx, exc):
        self.logger.debug(f"{ctx.command}: {type(exc).__name__}: {exc}")


def setup(bot):
    bot.add_cog(General(bot))
