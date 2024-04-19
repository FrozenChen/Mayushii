import discord

from discord.ext import commands
from discord import app_commands
from utils.database import CommunityRole, Guild
from utils.utilities import gen_color


@app_commands.guild_only
class Community(commands.GroupCog, name="communityrole"):
    """General commands for members."""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        self.roles = {}
        self.load_roles()

    @staticmethod
    def is_enabled(interaction):
        dbguild = interaction.client.s.query(Guild).get(interaction.guild.id)
        return dbguild.flags & 0b1

    def load_roles(self):
        self.roles = {}
        self.roles = {guild.id: [] for guild in self.bot.s.query(Guild).all()}
        for role in self.bot.s.query(CommunityRole).all():
            self.roles[role.guild].append(role)

    @commands.cooldown(rate=1, per=20.0, type=commands.BucketType.member)
    @app_commands.describe(role_name="Name of the community role")
    @app_commands.command()
    async def giveme(self, interaction, role_name: str):
        """Gives a community role to yourself."""
        if not (
            entry := self.bot.s.query(CommunityRole)
            .filter(
                CommunityRole.alias == role_name,
                CommunityRole.guild == interaction.guild.id,
            )
            .one_or_none()
        ):
            return await interaction.response.send_message(
                "Check the community roles with `/community_roles list`",
                ephemeral=True,
            )
        role = interaction.guild.get_role(entry.id)
        if role in interaction.user.roles:
            return await interaction.response.send_message(
                "You already have this role.", ephemeral=True
            )
        try:
            await interaction.user.add_roles(role)
        except discord.errors.Forbidden:
            return await interaction.response.send_message(
                "I can't add the role.", ephemeral=True
            )
        await interaction.response.send_message(
            f"You now have the {role.name} role!", ephemeral=True
        )

    @commands.cooldown(rate=1, per=20.0, type=commands.BucketType.member)
    @app_commands.describe(role_name="Name of the community role")
    @app_commands.command()
    async def takeme(self, interaction, role_name: str):
        """Removes a community role from yourself"""
        if not (
            entry := self.bot.s.query(CommunityRole)
            .filter(
                CommunityRole.alias == role_name,
                CommunityRole.guild == interaction.guild.id,
            )
            .one_or_none()
        ):

            return await interaction.response.send_message(
                f"Check the community roles with {self.bot.command_prefix}cr list",
                ephemeral=True,
            )
        role = discord.utils.get(interaction.user.roles, id=entry.id)
        if not role:
            return await interaction.response.send_message("You don't have this role", ephemeral=True)
        try:
            await interaction.user.remove_roles(role)
        except discord.errors.Forbidden:
            return await interaction.response.send_message(
                "I can't remove the role.", ephemeral=True
            )
        await interaction.response.send_message(
            "The role has been removed!", ephemeral=True
        )

    @staticmethod
    def can_be_community_role(role: discord.Role, top_role_pos: int):
        permissions = role.permissions
        return not (
            permissions.administrator
            or permissions.ban_members
            or permissions.kick_members
            or permissions.manage_channels
            or permissions.manage_guild
            or permissions.manage_messages
            or permissions.manage_roles
            or permissions.manage_webhooks
            or permissions.view_audit_log
            or permissions.mention_everyone
            or permissions.manage_nicknames
            or role.position >= top_role_pos
        )

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        alias="Alias for the new community role",
        role="Role which will be a community role",
        description="Description for the role",
    )
    @app_commands.command()
    async def create(
        self,
        interaction: discord.Interaction,
        alias: str,
        role: discord.Role,
        description: str,
    ):
        """Makes a server role as a community role"""

        if interaction.guild is None:
            return await interaction.response.send_message(
                "This command can't be used in DMs!"
            )

        top_role = interaction.guild.me.top_role
        if (
            self.bot.s.query(CommunityRole)
            .filter(
                CommunityRole.alias == alias,
                CommunityRole.guild == interaction.guild.id,
            )
            .one_or_none()
        ):
            await interaction.response.send_message("This alias is already in use.")
        elif self.bot.s.query(CommunityRole).get((role.id, interaction.guild.id)):
            return await interaction.response.send_message(
                "This role is a community role already."
            )
        elif not self.can_be_community_role(role, top_role.position):
            return await interaction.response.send_message(
                "Roles with moderation permissions or higher than the bot highest role can't be community roles."
            )
        self.bot.s.add(
            CommunityRole(
                id=role.id,
                guild=interaction.guild.id,
                name=role.name,
                alias=alias,
                description=description,
            )
        )
        self.bot.s.commit()
        self.load_roles()
        await interaction.response.send_message("Added community role succesfully.")

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(role="Server role to delete as a community role")
    @app_commands.command()
    async def delete(self, interaction, role: discord.Role):
        """Deletes a server role from the community roles"""
        if not (
            entry := self.bot.s.query(CommunityRole).get(
                (role.id, interaction.guild.id)
            )
        ):
            return await interaction.response.send_message(
                "This role is not a community role."
            )
        self.bot.s.delete(entry)
        self.bot.s.commit()
        self.load_roles()
        await interaction.response.send_message("Role removed succesfully.")

    @app_commands.command()
    async def list(self, interaction):
        """List the community roles"""
        if not self.roles[interaction.guild.id]:
            return await interaction.response.send_message(
                "There is no community roles."
            )
        embed = discord.Embed(
            title="Community roles", colour=gen_color(interaction.user.id)
        )
        for role in self.roles[interaction.guild.id]:
            embed.add_field(name=role.alias, value=role.description)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Community(bot))
