from discord.ext import commands
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from utils.database import CommunityRole, Base
from utils.utilities import gen_color
import discord


class Community(commands.Cog):
    """General commands for members."""

    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        engine = create_engine("sqlite:///community.db")
        session = sessionmaker(bind=engine)
        self.s = session()
        Base.metadata.create_all(engine, tables=[CommunityRole.__table__])
        self.s.commit()
        self.roles = self.s.query(CommunityRole).all()

    @commands.command()
    @commands.cooldown(rate=1, per=20.0, type=commands.BucketType.member)
    async def giveme(self, ctx, *, role_name=""):
        """Gives a community role to yourself."""
        if not (
            entry := self.s.query(CommunityRole)
            .filter(CommunityRole.alias == role_name)
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
        except discord.errors.Forbidden:
            return await ctx.send("💢 I don't have permission to do this.")
        await ctx.send(f"You now have the {role.name} role!")

    @commands.command()
    @commands.cooldown(rate=1, per=20.0, type=commands.BucketType.member)
    async def takeme(self, ctx, *, role_name=""):
        """Removes a community role from yourself"""
        if not (
            entry := self.s.query(CommunityRole)
            .filter(CommunityRole.alias == role_name)
            .one_or_none()
        ):
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"Check the community roles with {self.bot.command_prefix}cr list"
            )
        role = discord.utils.get(ctx.author.roles, id=entry.id)
        if not role:
            return await ctx.send("You don't have this role")
        try:
            await ctx.author.remove_roles(role)
        except discord.errors.Forbidden:
            return await ctx.send("💢 I don't have permission to do this.")
        await ctx.send(f"{ctx.author.mention} The role has been removed!")

    @commands.group(aliases=["cr"])
    async def communityrole(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @commands.has_permissions(manage_channels=True)
    @communityrole.command()
    async def add(self, ctx, alias: str, role: discord.Role, *, description: str):
        """Adds a server role as a community role"""
        if (
            self.s.query(CommunityRole)
            .filter(CommunityRole.alias == alias)
            .one_or_none()
        ):
            await ctx.send("This alias is already in use.")
        elif self.s.query(CommunityRole).get(role.id):
            return await ctx.send("This role is a community role already.")
        self.s.add(
            CommunityRole(
                id=role.id, name=role.name, alias=alias, description=description
            )
        )
        self.s.commit()
        self.roles = self.s.query(CommunityRole).all()
        await ctx.send("Added community role succesfully")

    @commands.has_permissions(manage_channels=True)
    @communityrole.command(aliases=["delete"])
    async def remove(self, ctx, role: discord.Role):
        """Removes a server role from the community roles"""
        if not (entry := self.s.query(CommunityRole).get(role.id)):
            return await ctx.send("This role is not a community role.")
        entry.delete()
        self.s.commit()
        self.roles = self.s.query(CommunityRole).all()
        await ctx.send("Role removed succesfully")

    @communityrole.command()
    async def list(self, ctx):
        """List the community roles"""
        if not self.roles:
            return await ctx.send("There is no community roles.")
        embed = discord.Embed(title="Community roles", colour=gen_color(ctx.author.id))
        for role in self.roles:
            embed.add_field(name=role.alias, value=role.description)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Community(bot))
