import aiohttp
import disnake
import subprocess

from disnake.ext import commands
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

    def bot_owner_only(inter):
        if inter.author.id != inter.bot.owner_id:
            raise BotOwnerOnly()
        return True

    @commands.slash_command()
    async def about(self, inter):
        """About Mayushii"""
        embed = disnake.Embed(
            title="Mayushii", url="https://github.com/FrozenChen/Mayushii"
        )
        embed.description = "A bot for Nintendo Homebrew artistic channel."
        embed.set_thumbnail(url="https://files.frozenchen.me/vD7vM.png")
        await inter.response.send_message(embed=embed, ephemeral=True)

    @commands.check(bot_owner_only)
    @commands.slash_command()
    async def pull(self, inter):
        """Pull changes from repo"""
        await inter.response.send_message("Pulling changes")
        subprocess.run(["git", "pull"])
        await self.bot.close()

    @commands.check(bot_owner_only)
    @commands.slash_command()
    async def load(self, inter, cog: str):
        """Load a cog"""
        try:
            self.bot.load_extension(f"cogs.{cog}")
            await inter.response.send_message(f"Loaded `{cog}``!")
        except commands.ExtensionNotFound:
            await inter.response.send_message(f"Extension {cog} not found")
        except commands.ExtensionFailed:
            await inter.response.send_message(f"Error occurred when loading {cog}")

    @commands.check(bot_owner_only)
    @commands.slash_command()
    async def unload(self, inter, cog: str):
        """Unloads a cog"""
        try:
            self.bot.unload_extension(f"cogs.{cog}")
            await inter.response.send_message(f"Unloaded {cog}!")
        except Exception as exc:
            await inter.response.send_message(
                f"Failed to unload cog!```\n{type(exc).__name__}: {exc}\n```"
            )

    @commands.check(bot_owner_only)
    @commands.slash_command()
    async def quit(self, inter):
        """This kills the bot"""
        await inter.response.send_message("See you later!")
        await self.bot.close()

    @commands.check(bot_owner_only)
    @commands.slash_command()
    async def changepfp(self, inter, url: str):
        """Change bot profile picture"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                if r.status != 200:
                    return await inter.response.send_message(
                        "Failed to retrieve image!"
                    )
                data = await r.read()
                await self.bot.user.edit(avatar=data)
                await inter.response.send_message.send(
                    "Profile picture changed successfully."
                )

    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @commands.slash_command()
    async def seterrchannel(self, inter, channel: disnake.TextChannel):
        """Set the channel to output errors"""
        dbguild = self.bot.s.query(Guild).get(inter.guild.id)
        dbguild.error_channel = channel.id
        self.bot.s.commit()
        await inter.response.send_message(f"Error Channel set to {channel.mention}")

    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @commands.slash_command()
    async def status(self, inter):
        """Shows the bot current guild status"""
        dbguild = self.bot.s.query(Guild).get(inter.guild.id)
        embed = disnake.Embed()
        embed.add_field(name="Guild", value=f"{inter.guild.name}", inline=False)
        embed.add_field(
            name="Cogs",
            value="\n".join(
                f'{cog}: {"enabled" if value & dbguild.flags else "disabled"}'
                for cog, value in self.cogs.items()
            ),
            inline=False,
        )
        await inter.response.send_message(embed=embed)

    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @commands.slash_command()
    async def togglecog(self, inter, cog: str):
        """Enables or disables a cog"""
        if cog in self.cogs:
            dbguild = self.bot.s.query(Guild).get(inter.guild.id)
            dbguild.flags ^= self.cogs[cog]
            self.bot.s.commit()
            return await inter.response.send_message("Cog toggled.")
        await inter.response.send_message("Cog not found.")

    @commands.guild_only()
    @commands.check(bot_owner_only)
    @commands.slash_command()
    async def blacklist(self, inter):
        """Commands for the blacklist"""
        pass

    @blacklist.sub_command(name="add")
    async def blacklist_add(self, inter, member: disnake.Member):
        """Adds member to blacklist"""
        if self.bot.s.query(BlackList).get((member.id, inter.guild.id)):
            await inter.response.send_message("User is already blacklisted")
            return
        self.bot.s.add(BlackList(userid=member.id, guild=inter.guild.id))
        await inter.response.send_message(f"Blacklisted {member.mention}!")

    @blacklist.sub_command(name="remove")
    async def blacklist_remove(self, inter, member: disnake.Member):
        """Removes member from blacklist."""
        user = self.bot.s.query(BlackList).get((member.id, inter.guild.id))
        if not user:
            await inter.response.send_message("User is not blacklisted")
            return
        self.bot.s.delete(user)
        await inter.response.send_message(f"Removed {member.mention} from blacklist!")

    @commands.user_command(name="Get pfp")
    async def get_user_pfp(self, inter):
        """Gets the user's pfp"""
        embed = disnake.Embed(title=f"{inter.target}'s pfp")
        embed.set_image(url=inter.target.display_avatar.url)
        await inter.response.send_message(embed=embed, ephemeral=True)

    async def cog_command_error(self, ctx, exc):
        self.logger.debug(f"{ctx.command}: {type(exc).__name__}: {exc}")


def setup(bot):
    bot.add_cog(General(bot))
