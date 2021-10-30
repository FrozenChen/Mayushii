import disnake

from disnake.ext import commands
from utils.database import CommunityRole, Guild
from utils.exceptions import DisabledCog
from utils.utilities import gen_color


class Community(commands.Cog):
    """General commands for members."""

    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        self.roles = {}
        self.load_roles()

    @staticmethod
    def is_enabled(ctx):
        dbguild = ctx.bot.s.query(Guild).get(ctx.guild.id)
        return dbguild.flags & 0b1

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if not self.is_enabled(ctx):
            raise DisabledCog()
        return True

    def load_roles(self):
        self.roles = {}
        self.roles = {guild.id: [] for guild in self.bot.s.query(Guild).all()}
        for role in self.bot.s.query(CommunityRole).all():
            self.roles[role.guild].append(role)

    @commands.command()
    @commands.cooldown(rate=1, per=20.0, type=commands.BucketType.member)
    async def giveme(self, ctx, *, role_name=""):
        """Gives a community role to yourself."""
        if not (
            entry := self.bot.s.query(CommunityRole)
            .filter(
                CommunityRole.alias == role_name, CommunityRole.guild == ctx.guild.id
            )
            .one_or_none()
        ):
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"Check the community roles with {self.bot.command_prefix}cr list"
            )
        role = ctx.guild.get_role(entry.id)
        if role in ctx.author.roles:
            return await ctx.send("You already have this role.")
        try:
            await ctx.author.add_roles(role)
        except disnake.errors.Forbidden:
            return await ctx.send("💢 I don't have permission to do this.")
        await ctx.send(f"You now have the {role.name} role!")

    @commands.command()
    @commands.cooldown(rate=1, per=20.0, type=commands.BucketType.member)
    async def takeme(self, ctx, *, role_name=""):
        """Removes a community role from yourself"""
        if not (
            entry := self.bot.s.query(CommunityRole)
            .filter(
                CommunityRole.alias == role_name, CommunityRole.guild == ctx.guild.id
            )
            .one_or_none()
        ):
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"Check the community roles with {self.bot.command_prefix}cr list"
            )
        role = disnake.utils.get(ctx.author.roles, id=entry.id)
        if not role:
            return await ctx.send("You don't have this role")
        try:
            await ctx.author.remove_roles(role)
        except disnake.errors.Forbidden:
            return await ctx.send("💢 I don't have permission to do this.")
        await ctx.send(f"{ctx.author.mention} The role has been removed!")

    @commands.group(aliases=["cr"])
    async def communityrole(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @commands.has_guild_permissions(manage_channels=True)
    @communityrole.command()
    async def add(self, ctx, alias: str, role: disnake.Role, *, description: str):
        """Adds a server role as a community role"""
        if (
            self.bot.s.query(CommunityRole)
            .filter(CommunityRole.alias == alias, CommunityRole.guild == ctx.guild.id)
            .one_or_none()
        ):
            await ctx.send("This alias is already in use.")
        elif self.bot.s.query(CommunityRole).get((role.id, ctx.guild.id)):
            return await ctx.send("This role is a community role already.")
        self.bot.s.add(
            CommunityRole(
                id=role.id,
                guild=ctx.guild.id,
                name=role.name,
                alias=alias,
                description=description,
            )
        )
        self.bot.s.commit()
        self.load_roles()
        await ctx.send("Added community role succesfully")

    @commands.has_guild_permissions(manage_channels=True)
    @communityrole.command(aliases=["delete"])
    async def remove(self, ctx, role: disnake.Role):
        """Removes a server role from the community roles"""
        if not (entry := self.bot.s.query(CommunityRole).get((role.id, ctx.guild.id))):
            return await ctx.send("This role is not a community role.")
        self.bot.s.delete(entry)
        self.bot.s.commit()
        self.load_roles()
        await ctx.send("Role removed succesfully")

    @communityrole.command()
    async def list(self, ctx):
        """List the community roles"""
        if not self.roles[ctx.guild.id]:
            return await ctx.send("There is no community roles.")
        embed = disnake.Embed(title="Community roles", colour=gen_color(ctx.author.id))
        for role in self.roles[ctx.guild.id]:
            embed.add_field(name=role.alias, value=role.description)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Community(bot))
