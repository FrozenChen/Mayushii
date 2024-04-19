from __future__ import annotations

import discord
import subprocess
import platform

from discord import app_commands
from discord.ext import commands
from typing import TYPE_CHECKING
from utils.database import Guild, BlackList
from utils.exceptions import BotOwnerOnly

if TYPE_CHECKING:
    from main import Mayushii


def bot_owner_only(interaction):
    if interaction.user.id != interaction.client.owner_id:
        raise BotOwnerOnly("Only the bot owner can use this command.")
    return True


class General(commands.Cog):
    """General commands for general use."""

    def __init__(self, bot: Mayushii):
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        self.cogs = {
            "community": 0b1,
            "gallery": 0b10,
            "raffle": 0b100,
            "voting": 0b1000,
        }

        self.getpfp_menu = app_commands.ContextMenu(
            name="Get pfp",
            callback=self.getpfp_menu_callback,
        )
        self.bot.tree.add_command(self.getpfp_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.getpfp_menu.name, type=self.getpfp_menu.type)

    @commands.has_guild_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.command()
    async def sync(self, ctx):
        await ctx.bot.tree.sync()
        await ctx.send("App commands synced.")

    @app_commands.command()
    async def about(self, interaction):
        """About Mayushii"""
        embed = discord.Embed(
            title="Mayushii", url="https://github.com/FrozenChen/Mayushii"
        )
        embed.description = "A bot for Nintendo Homebrew artistic channel."
        embed.set_thumbnail(url="https://files.frozenchen.me/vD7vM.png")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    group_bot = app_commands.Group(
        name="bot",
        description="Bot commands",
        default_permissions=discord.Permissions(administrator=True),
        guild_only=True,
    )

    @app_commands.check(bot_owner_only)
    @group_bot.command()
    async def pull(self, interaction):
        """Pull changes from repo"""
        await interaction.response.send_message("Pulling changes")
        subprocess.run(["git", "pull"])
        await self.bot.close()

    @app_commands.check(bot_owner_only)
    @app_commands.describe(cog="Cog to load")
    @group_bot.command()
    async def load(self, interaction, cog: str):
        """Load a cog"""
        try:
            await self.bot.load_extension(f"cogs.{cog}")
            await interaction.response.send_message(f"Loaded `{cog}`!")
        except commands.ExtensionNotFound:
            await interaction.response.send_message(f"Extension {cog} not found")
        except commands.ExtensionAlreadyLoaded:
            await interaction.response.send_message(
                f"Extension {cog} is already loaded"
            )
        except commands.ExtensionFailed as exc:
            await interaction.response.send_message(
                f"Failed to load cog!```\n{type(exc).__name__}: {exc}\n```",
                ephemeral=True,
            )

    @app_commands.check(bot_owner_only)
    @app_commands.describe(cog="Cog to reload")
    @group_bot.command()
    async def reload(self, interaction, cog: str):
        """Reloads a cog"""
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
        except commands.ExtensionNotFound:
            await interaction.response.send_message(f"Extension {cog} not found")
        except commands.ExtensionNotLoaded:
            await interaction.response.send_message(f"Extension {cog} is not loaded")
        except commands.ExtensionFailed as exc:
            await interaction.response.send_message(
                f"Failed to reload cog!```\n{type(exc).__name__}: {exc}\n```",
                ephemeral=True,
            )

    @app_commands.check(bot_owner_only)
    @app_commands.describe(cog="Cog to unload")
    @group_bot.command()
    async def unload(self, interaction, cog: str):
        """Unloads a cog"""
        try:
            await self.bot.unload_extension(f"cogs.{cog}")
            await interaction.response.send_message(f"Unloaded {cog}!")
        except commands.ExtensionNotFound:
            await interaction.response.send_message(f"Extension {cog} not found")
        except commands.ExtensionNotLoaded:
            await interaction.response.send_message(f"Extension {cog} is not loaded")
        except commands.ExtensionFailed as exc:
            await interaction.response.send_message(
                f"Failed to unload cog!```\n{type(exc).__name__}: {exc}\n```",
                ephemeral=True,
            )

    @app_commands.check(bot_owner_only)
    @group_bot.command()
    async def quit(self, interaction):
        """This kills the bot"""
        await interaction.response.send_message("See you later!")
        await self.bot.close()

    @app_commands.check(bot_owner_only)
    @app_commands.describe(image="Image to set as the new pfp")
    @group_bot.command()
    async def changepfp(self, interaction, image: discord.Attachment):
        """Change bot profile picture"""

        if not image.content_type or image.content_type not in (
            "image/jpeg",
            "image/png",
            "image/gif",
        ):
            return await interaction.response.send_message(
                "This is not a valid image.", ephemeral=True
            )

        image_bytes = await image.read()
        await self.bot.user.edit(avatar=image_bytes)
        await interaction.response.send_message(
            "Profile picture changed successfully.", ephemeral=True
        )

    @app_commands.check(bot_owner_only)
    @app_commands.describe(channel="Text channel to set as the error channel")
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
            name="Python Version",
            value=platform.python_version(),
            inline=False,
        )
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
    @app_commands.describe(cog="Name of the cog to toggle")
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
        name="blacklist",
        description="Commands for the blacklist",
        default_permissions=discord.Permissions(administrator=True),
        guild_only=True,
    )

    @app_commands.check(bot_owner_only)
    @app_commands.describe(member="Member to add to the blacklist")
    @blacklist.command(name="add")
    async def blacklist_add(self, interaction, member: discord.Member):
        """Adds member to blacklist"""
        if self.bot.s.query(BlackList).get((member.id, interaction.guild.id)):
            await interaction.response.send_message("User is already blacklisted")
            return
        self.bot.s.add(BlackList(userid=member.id, guild=interaction.guild.id))
        self.bot.s.commit()
        await interaction.response.send_message(f"Blacklisted {member.mention}!")

    @app_commands.check(bot_owner_only)
    @app_commands.describe(member="Member to remove from the blacklist")
    @blacklist.command(name="remove")
    async def blacklist_remove(self, interaction, member: discord.Member):
        """Removes member from blacklist."""
        user = self.bot.s.query(BlackList).get((member.id, interaction.guild.id))
        if not user:
            await interaction.response.send_message("User is not blacklisted")
            return
        self.bot.s.delete(user)
        self.bot.s.commit()
        await interaction.response.send_message(
            f"Removed {member.mention} from blacklist!"
        )

    async def getpfp_menu_callback(self, interaction, member: discord.Member):
        """Gets the user's pfp"""
        embed = discord.Embed(title=f"{member}'s pfp")
        embed.set_image(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(General(bot))
