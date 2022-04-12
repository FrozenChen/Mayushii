import asyncio
import datetime
import discord

from discord import app_commands
from discord.ext import commands, tasks
from utils.database import GiveawayRole, Guild
from utils.managers import RaffleManager
from utils.exceptions import NoOnGoingRaffle
from utils.utilities import (
    ConfirmationButtons,
    DateTransformer,
    TimeTransformer,
    GreedyRoleTransformer,
)
from utils.views import RaffleView, LinkButton


class Raffle(commands.Cog, app_commands.Group):
    """Raffle related commands"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        self.bot.raffle_manager = RaffleManager(bot)
        self.queue = asyncio.Queue()

    async def cog_load(self):
        for guild_id, raffle in self.bot.raffle_manager.raffles.items():
            view = RaffleView(
                custom_id=raffle.custom_id,
                guild_id=raffle.guild_id,
                message_id=raffle.message_id,
                raffle_manager=self.bot.raffle_manager,
                channel_id=raffle.channel_id,
            )
            self.bot.add_view(view)
        self.check_views.start()

    @tasks.loop(seconds=60.0)
    async def check_views(self):
        now = datetime.datetime.utcnow()
        for raffle in self.bot.raffle_manager.raffles.values():
            if raffle.end_date and raffle.end_date < now:
                view = discord.utils.get(
                    self.bot.persistent_views, custom_id=raffle.custom_id
                )
                await self.bot.raffle_manager.end_raffle(raffle, view)

    @staticmethod
    def is_enabled(interaction):
        dbguild = interaction.client.s.query(Guild).get(interaction.guild.id)
        return dbguild.flags & 0b100

    # checks
    def ongoing_raffle(interaction):
        raffle = interaction.client.raffle_manager.get_raffle(interaction.guild_id)
        if raffle and raffle.ongoing:
            return True
        raise NoOnGoingRaffle("There is no ongoing raffle.")

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        name="Name of the new raffle",
        winners="Number of winners",
        allowed_roles="Roles allowed to participate",
    )
    @app_commands.command()
    async def create(
        self,
        interaction: discord.Interaction,
        name: str,
        description: str,
        target_channel: discord.TextChannel,
        url: str = None,
        winners: int = 1,
        max_participants: int = None,
        end_date: app_commands.Transform[datetime.datetime, DateTransformer] = None,
        lasts: app_commands.Transform[int, TimeTransformer] = None,
        allowed_roles: app_commands.Transform[
            list[discord.Role], GreedyRoleTransformer
        ] = None,
    ):
        """Creates a giveaway"""
        if self.bot.raffle_manager.get_raffle(interaction.guild.id):
            return await interaction.response.send_message(
                "There is an already ongoing giveaway!", ephemeral=True
            )

        if lasts and end_date:
            return await interaction.response.send_message(
                "end_date and lasts parameters are mutually exclusive", ephemeral=True
            )
        if lasts and lasts < 600:
            return await interaction.response.send_message(
                "A poll has to last longer than 10 minutes", ephemeral=True
            )

        embed = discord.Embed(title="Proposed Giveaway", color=discord.Color.purple())
        embed.add_field(name="Name", value=name, inline=False)
        embed.add_field(name="Description", value=description, inline=False)
        embed.add_field(name="Number of winners", value=str(winners), inline=False)
        if allowed_roles:
            embed.add_field(
                name="Roles accepted",
                value=" ".join(role.name for role in allowed_roles),
                inline=False,
            )
        view = ConfirmationButtons()
        await interaction.response.send_message(
            "Is this giveaway correct?", embed=embed, view=view, ephemeral=True
        )
        await view.wait()
        if view.value:
            start = datetime.datetime.utcnow()
            if lasts or end_date:
                if lasts:
                    diff = datetime.timedelta(seconds=lasts)
                    end_date = start + diff
                if end_date < start or (end_date - start).total_seconds() < 600:
                    return await interaction.edit_original_message(
                        content="A raffle has to last longer than 10 minutes",
                        view=None,
                        embed=None,
                    )
            raffle_view = RaffleView(
                custom_id=interaction.id,
                guild_id=interaction.guild_id,
                channel_id=target_channel.id,
                raffle_manager=self.bot.raffle_manager,
            )
            if url:
                raffle_view.add_item(LinkButton(label="link", url=url))
            msg = await target_channel.send("Loading", view=raffle_view)

            raffle_view.message_id = msg.id
            raffle = self.bot.raffle_manager.create_raffle(
                name=name,
                description=description,
                url=url,
                win_count=winners,
                max_participants=max_participants,
                roles=allowed_roles,
                guild_id=interaction.guild_id,
                channel_id=target_channel.id,
                message_id=msg.id,
                author_id=interaction.user.id,
                custom_id=interaction.id,
                start_date=start,
                end_date=end_date,
            )
            self.bot.raffle_manager.raffles[interaction.guild.id] = raffle
            await msg.edit(
                content="",
                embed=self.bot.raffle_manager.create_embed(
                    raffle, description=description
                ),
            )
            await interaction.edit_original_message(
                content=f"Started giveaway {name} with {winners} possible winners! Use `/raffle join`to join",
                embed=None,
                view=None,
            )
        else:
            await interaction.edit_original_message(content="Alright then.")

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.check(ongoing_raffle)
    @commands.guild_only()
    @app_commands.command()
    async def info(self, interaction):
        """Shows information about current giveaway"""
        raffle = self.bot.raffle_manager.raffles[interaction.guild.id]
        embed = discord.Embed()
        embed.add_field(name="ID", value=raffle.id, inline=False)
        embed.add_field(name="Name", value=raffle.name, inline=False)
        if raffle.roles:
            embed.add_field(
                name="Allowed Roles",
                value="\n".join(role.id for role in raffle.roles),
                inline=False,
            )
        embed.add_field(
            name="Number of entries", value=str(len(raffle.entries)), inline=False
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.check(ongoing_raffle)
    @app_commands.command()
    async def cancel(self, interaction: discord.Interaction):
        """Cancels current giveaway"""
        view = ConfirmationButtons()
        await interaction.response.send_message(
            "Are you sure you want to cancel current giveaway?", view=view
        )
        if view.value:
            self.bot.raffle_manager.raffles[interaction.guild.id].ongoing = False
            del self.bot.raffle_manager.raffles[interaction.guild.id]
            await self.bot.raffle_manager.views[interaction.guild.id].stop()
            del self.bot.raffle_manager.views[interaction.guild.id]
            self.bot.s.commit()
            return await interaction.edit_original_message(
                content="Giveaway cancelled.", view=None
            )
        await interaction.edit_original_message(
            content="And the raffle continues.", view=None
        )

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.check(ongoing_raffle)
    @app_commands.command()
    async def finish(self, interaction: discord.Interaction):
        """Finishes the current raffle"""
        await self.bot.raffle_manager.stop_raffle(interaction.guild_id)
        await interaction.response.send_message("Raffle finished!")

    modify = app_commands.Group(
        name="modify", description="Commands to modify a raffle"
    )

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(new_value="New amount of winners")
    @modify.command()
    async def winner_count(self, interaction, new_value: int):
        """Modify number of winners for the ongoing raffle"""
        self.bot.raffle_manager.raffles[interaction.guild.id].win_count = new_value
        self.bot.s.commit()
        await interaction.response.send_message(
            f"Updated number of winners to {new_value}"
        )

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(new_role="Role to allow in the raffle")
    @modify.command()
    async def add_allowed_role(
        self,
        interaction: discord.Interaction,
        new_role: discord.Role,
    ):
        """Add a role to raffle"""
        raffle = self.bot.raffle_manager.get_raffle(interaction.guild_id)
        self.bot.s.add(GiveawayRole(id=new_role.id, giveaway=raffle.id))
        self.bot.s.commit()
        await interaction.response.send_message(
            f"Added role {new_role.name} to the raffle"
        )


async def setup(bot):
    await bot.add_cog(Raffle(bot))
