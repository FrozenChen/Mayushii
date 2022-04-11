import aiohttp
import discord
import subprocess

from discord import app_commands
from discord.ext import commands

from main import Mayushii
from utils.database import Guild, BlackList
from utils.exceptions import BotOwnerOnly


def bot_owner_only(interaction):
    if interaction.user.id != interaction.client.owner_id:
        raise BotOwnerOnly()
    return True


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

    @app_commands.command()
    async def about(self, interaction):
        """About Mayushii"""
        embed = discord.Embed(
            title="Mayushii", url="https://github.com/FrozenChen/Mayushii"
        )
        embed.description = "A bot for Nintendo Homebrew artistic channel."
        embed.set_thumbnail(url="https://files.frozenchen.me/vD7vM.png")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    group_bot = app_commands.Group(name="bot", description="Bot commands")

    @app_commands.check(bot_owner_only)
    @group_bot.command()
    async def pull(self, interaction):
        """Pull changes from repo"""
        await interaction.response.send_message("Pulling changes")
        subprocess.run(["git", "pull"])
        await self.bot.close()

    @app_commands.check(bot_owner_only)
    @group_bot.command()
    async def load(self, interaction, cog: str):
        """Load a cog"""
        try:
            await self.bot.load_extension(f"cogs.{cog}")
            await interaction.response.send_message(f"Loaded `{cog}`!")
        except commands.ExtensionNotFound:
            await interaction.response.send_message(f"Extension {cog} not found")
        except commands.ExtensionFailed as exc:
            await interaction.response.send_message(
                f"Failed to load cog!```\n{type(exc).__name__}: {exc}\n```"
            )

    @app_commands.check(bot_owner_only)
    @group_bot.command()
    async def unload(self, interaction, cog: str):
        """Unloads a cog"""
        try:
            await self.bot.unload_extension(f"cogs.{cog}")
            await interaction.response.send_message(f"Unloaded {cog}!")
        except Exception as exc:
            await interaction.response.send_message(
                f"Failed to unload cog!```\n{type(exc).__name__}: {exc}\n```"
            )

    @app_commands.check(bot_owner_only)
    @group_bot.command()
    async def quit(self, interaction):
        """This kills the bot"""
        await interaction.response.send_message("See you later!")
        await self.bot.close()

    @app_commands.check(bot_owner_only)
    @group_bot.command()
    async def changepfp(self, interaction, url: str):
        """Change bot profile picture"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                if r.status != 200:
                    return await interaction.response.send_message(
                        "Failed to retrieve image!"
                    )
                data = await r.read()
                await self.bot.user.edit(avatar=data)
                await interaction.response.send_message.send(
                    "Profile picture changed successfully."
                )

    @app_commands.check(bot_owner_only)
    @group_bot.command()
    async def seterrchannel(self, interaction, channel: discord.TextChannel):
        """Set the channel to output errors"""
        dbguild = self.bot.s.query(Guild).get(interaction.guild.id)
        dbguild.error_channel = channel.id
        self.bot.s.commit()
        await interaction.response.send_message(
            f"Error Channel set to {channel.mention}"
        )

    @app_commands.check(bot_owner_only)
    @group_bot.command()
    async def status(self, interaction):
        """Shows the bot current guild status"""
        dbguild = self.bot.s.query(Guild).get(interaction.guild.id)
        embed = discord.Embed()
        embed.add_field(name="Guild", value=f"{interaction.guild.name}", inline=False)
        embed.add_field(
            name="Cogs",
            value="\n".join(
                f'{cog}: {"enabled" if value & dbguild.flags else "disabled"}'
                for cog, value in self.cogs.items()
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.check(bot_owner_only)
    @group_bot.command()
    async def togglecog(self, interaction, cog: str):
        """Enables or disables a cog"""
        if cog in self.cogs:
            dbguild = self.bot.s.query(Guild).get(interaction.guild.id)
            dbguild.flags ^= self.cogs[cog]
            self.bot.s.commit()
            return await interaction.response.send_message("Cog toggled.")
        await interaction.response.send_message("Cog not found.")

    blacklist = app_commands.Group(
        name="blacklist", description="Commands for the blacklist"
    )

    @app_commands.check(bot_owner_only)
    @blacklist.command(name="add")
    async def blacklist_add(self, interaction, member: discord.Member):
        """Adds member to blacklist"""
        if self.bot.s.query(BlackList).get((member.id, interaction.guild.id)):
            await interaction.response.send_message("User is already blacklisted")
            return
        self.bot.s.add(BlackList(userid=member.id, guild=interaction.guild.id))
        await interaction.response.send_message(f"Blacklisted {member.mention}!")

    @app_commands.check(bot_owner_only)
    @blacklist.command(name="remove")
    async def blacklist_remove(self, interaction, member: discord.Member):
        """Removes member from blacklist."""
        user = self.bot.s.query(BlackList).get((member.id, interaction.guild.id))
        if not user:
            await interaction.response.send_message("User is not blacklisted")
            return
        self.bot.s.delete(user)
        await interaction.response.send_message(
            f"Removed {member.mention} from blacklist!"
        )

    async def cog_command_error(self, ctx, exc):
        self.logger.debug(f"{ctx.command}: {type(exc).__name__}: {exc}")


async def setup(bot: Mayushii):
    await bot.add_cog(General(bot))
