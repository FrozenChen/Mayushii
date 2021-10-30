import disnake

from disnake.ext import commands
from disnake.ext.commands import Param
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

    @commands.slash_command()
    async def communityrole(self, inter):
        pass

    @commands.cooldown(rate=1, per=20.0, type=commands.BucketType.member)
    @communityrole.sub_command()
    async def giveme(
        self, inter, role_name: str = Param(description="Name of the community role")
    ):
        """Gives a community role to yourself."""
        if not (
            entry := self.bot.s.query(CommunityRole)
            .filter(
                CommunityRole.alias == role_name, CommunityRole.guild == inter.guild.id
            )
            .one_or_none()
        ):
            inter.application_command.reset_cooldown(inter)
            return await inter.response.send_message(
                f"Check the community roles with `/community_roles list`",
                ephemeral=True,
            )
        role = inter.guild.get_role(entry.id)
        if role in inter.author.roles:
            return await inter.response.send_message(
                "You already have this role.", ephemeral=True
            )
        try:
            await inter.author.add_roles(role)
        except disnake.errors.Forbidden:
            return await inter.response.send_message(
                "I can't add the role.", ephemeral=True
            )
        await inter.response.send_message(
            f"You now have the {role.name} role!", ephemeral=True
        )

    @commands.cooldown(rate=1, per=20.0, type=commands.BucketType.member)
    @communityrole.sub_command()
    async def takeme(
        self, inter, role_name: str = Param(description="Name of the community role")
    ):
        """Removes a community role from yourself"""
        if not (
            entry := self.bot.s.query(CommunityRole)
            .filter(
                CommunityRole.alias == role_name, CommunityRole.guild == inter.guild.id
            )
            .one_or_none()
        ):
            inter.application_command.reset_cooldown(inter)
            return await inter.response.send_message(
                f"Check the community roles with {self.bot.command_prefix}cr list",
                ephemeral=True,
            )
        role = disnake.utils.get(inter.author.roles, id=entry.id)
        if not role:
            return await inter.response.send_message("You don't have this role")
        try:
            await inter.author.remove_roles(role)
        except disnake.errors.Forbidden:
            return await inter.response.send_message(
                "I can't remove the role.", ephemeral=True
            )
        await inter.response.send_message(
            f"{inter.author.mention} The role has been removed!", ephemeral=True
        )

    @commands.has_guild_permissions(manage_channels=True)
    @communityrole.sub_command()
    async def create(
        self,
        inter,
        alias: str = Param(description="Alias for the new community role"),
        role: disnake.Role = Param(description="Role which will be a community role"),
        description: str = Param(description="Description for the role"),
    ):
        """Makes a server role as a community role"""
        if (
            self.bot.s.query(CommunityRole)
            .filter(CommunityRole.alias == alias, CommunityRole.guild == inter.guild.id)
            .one_or_none()
        ):
            await inter.response.send_message("This alias is already in use.")
        elif self.bot.s.query(CommunityRole).get((role.id, inter.guild.id)):
            return await inter.response.send_message(
                "This role is a community role already."
            )
        self.bot.s.add(
            CommunityRole(
                id=role.id,
                guild=inter.guild.id,
                name=role.name,
                alias=alias,
                description=description,
            )
        )
        self.bot.s.commit()
        self.load_roles()
        await inter.response.send_message("Added community role succesfully.")

    @commands.has_guild_permissions(manage_channels=True)
    @communityrole.sub_command()
    async def delete(
        self,
        inter,
        role: disnake.Role = Param(
            description="Server role to delete as a community role"
        ),
    ):
        """Deletes a server role from the community roles"""
        if not (
            entry := self.bot.s.query(CommunityRole).get((role.id, inter.guild.id))
        ):
            return await inter.response.send_message(
                "This role is not a community role."
            )
        self.bot.s.delete(entry)
        self.bot.s.commit()
        self.load_roles()
        await inter.response.send_message("Role removed succesfully.")

    @communityrole.sub_command()
    async def list(self, inter):
        """List the community roles"""
        if not self.roles[inter.guild.id]:
            return await inter.response.send_message("There is no community roles.")
        embed = disnake.Embed(
            title="Community roles", colour=gen_color(inter.author.id)
        )
        for role in self.roles[inter.guild.id]:
            embed.add_field(name=role.alias, value=role.description)
        await inter.response.send_message(embed=embed)


def setup(bot):
    bot.add_cog(Community(bot))
