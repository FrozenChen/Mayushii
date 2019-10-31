import discord
from discord.ext import commands


class Roles(commands.Cog):
    """Cog for managing roles."""

    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        self.roles = {
            '3d-general': None,
            '2d-general': None,
            '3d-kinky': None,
            '2d-kinky': None,
            'hardcore': None,
            'lesbian': None,
            'gay': None,
            'furry': None
        }
        self.init_roles()

    def init_roles(self):
        for role in self.roles.keys():
            self.roles[role] = discord.utils.get(self.bot.guild.roles, name=role)
            if not self.roles[role]:
                self.logger.error(f'Failed to find role `{role}`')

    @commands.command(aliases=["tr"])
    async def toggleroles(self, ctx, *, channels=""):
        """Toggle roles for user."""
        await ctx.message.delete()
        if not channels:
            return await ctx.send(f"Options: {', '.join([x for x in self.roles.keys()])}.")
        roles = [self.roles.get(x) for x in channels.split(" ") if self.roles.get(x) is not None]
        for role in roles:
            if role in ctx.author.roles:
                await ctx.author.remove_roles(role)
            else:
                await ctx.author.add_roles(role)
        await ctx.author.send("Updated roles successfully!.")

    @commands.has_permissions(Manage_Roles=True)
    @commands.command("rr")
    async def reloadroles(self, ctx):
        self.init_roles()
        await ctx.send("Reloaded roles!")


def setup(bot):
    bot.add_cog(Roles(bot))
