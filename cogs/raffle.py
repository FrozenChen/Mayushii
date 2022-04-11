import asyncio
import discord
import random

from discord import app_commands
from discord.ext import commands
from utils.checks import not_new, not_blacklisted
from utils.database import Giveaway, Entry, GiveawayRole, Guild
from utils.managers import RaffleManager
from utils.exceptions import NoOnGoingRaffle
from utils.utilities import ConfirmationButtons
from typing import List


class Raffle(commands.Cog, app_commands.Group):
    """Raffle related commands"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        self.bot.raffle_manager = RaffleManager(bot)
        self.queue = asyncio.Queue()

    @staticmethod
    def is_enabled(interaction):
        dbguild = interaction.client.s.query(Guild).get(interaction.guild.id)
        return dbguild.flags & 0b100

    # checks
    def ongoing_raffle(interaction):
        raffle = interaction.client.raffle_manager.get_raffle(interaction)
        if raffle and raffle.ongoing:
            return True
        raise NoOnGoingRaffle("There is no ongoing raffle.")

    async def queue_empty(self):
        while not self.queue.empty():
            pass

    async def process_entry(self):
        interaction = await self.queue.get()
        raffle = self.bot.raffle_manager.get_raffle(interaction)
        if raffle.roles:
            for role in raffle.roles:
                if not any(discord.utils.get(interaction.author.roles, id=role.id)):
                    return await interaction.send(
                        "You are not allowed to participate!", ephemeral=True
                    )
        user_id = interaction.author.id
        entry = self.bot.s.query(Entry).get((user_id, raffle.id))
        if entry:
            return await interaction.send(
                "You are already participating!", ephemeral=True
            )
        self.bot.s.add(Entry(id=user_id, giveaway=raffle.id))
        self.bot.s.commit()
        await interaction.send(
            f"{interaction.author.mention} now you are participating in the raffle!",
            ephemeral=True,
        )
        self.queue.task_done()

    def create_raffle(self, name: str, winners: int, guild: int, roles: List[int]):
        raffle = Giveaway(name=name, win_count=winners, guild=guild)
        self.bot.s.add(raffle)
        self.bot.s.commit()
        if roles:
            self.bot.s.add_all(
                [GiveawayRole(id=role_id, giveaway=raffle.id) for role_id in roles]
            )
            self.bot.s.commit()
        return raffle

    def get_winner(self, interaction):
        raffle = interaction.application_command.cog.raffles[interaction.guild.id]
        while len(raffle.entries) >= 1:
            entry = random.choice(raffle.entries)
            if (winner := interaction.guild.get_member(entry.id)) is not None:
                entry.winner = True
                self.bot.s.commit()
                return winner
            self.bot.s.delete(entry)
        return None

    @app_commands.check(not_blacklisted)
    @app_commands.check(not_new)
    @app_commands.check(ongoing_raffle)
    @app_commands.command()
    async def join(self, interaction):
        """Joins the ongoing raffle if there is one"""
        await self.queue.put(interaction)
        await self.process_entry()

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        name="Name of the new raffle",
        winners="Number of winners",
        allowed_role="Roles allowed to participate",
    )
    @app_commands.command()
    async def create(
        self,
        interaction,
        name: str,
        winners: int = 1,
        allowed_role: discord.Role = None,
    ):
        """Creates a giveaway"""
        if self.bot.raffle_manager.get_raffle(interaction):
            return await interaction.send("There is an already ongoing giveaway!")
        embed = discord.Embed(title="Proposed Giveaway", color=discord.Color.purple())
        embed.add_field(name="Name", value=name, inline=False)
        embed.add_field(name="Number of winners", value=str(winners), inline=False)
        if allowed_role:
            embed.add_field(
                name="Roles accepted",
                value=allowed_role.name,
                inline=False,
            )
        view = ConfirmationButtons()
        await interaction.send("Is this giveaway correct?", embed=embed, view=view)
        if view.value:
            self.bot.raffle_manager[interaction.guild.id] = self.create_raffle(
                name=name,
                winners=winners,
                roles=[allowed_role.name] if allowed_role else [],
                guild=interaction.guild.id,
            )
            await interaction.send(
                f"Started giveaway {name} with {winners} possible winners! Use `/raffle join`to join"
            )
        else:
            await interaction.send("Alright then.")

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.check(ongoing_raffle)
    @commands.guild_only()
    @app_commands.command()
    async def info(self, interaction):
        """Shows information about current giveaway"""
        raffle = self.bot.raffle_manager[interaction.guild.id]
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
        await interaction.send(embed=embed)

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.check(ongoing_raffle)
    @app_commands.command()
    async def cancel(self, interaction):
        """Cancels current giveaway"""
        view = ConfirmationButtons()
        await interaction.send(
            "Are you sure you want to cancel current giveaway?", view=view
        )
        if view.value:
            self.bot.raffle_manager.raffles[interaction.guild.id].ongoing = False
            self.bot.raffle_manager.raffles[interaction.guild.id] = None
            self.bot.s.commit()
            return await interaction.send("Giveaway cancelled.")
        await interaction.send("And the raffle continues.")

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.check(ongoing_raffle)
    @app_commands.command()
    async def finish(self, interaction):
        """Finishes the current raffle"""
        raffle = self.bot.raffle_manager.raffles[interaction.guild.id]
        raffle.ongoing = False
        self.bot.s.commit()
        await asyncio.wait_for(self.queue_empty(), timeout=None)
        winners = []
        for i in range(0, raffle.win_count):
            winners.append(self.get_winner(interaction))
        winners = list(filter(lambda a: a is not None, winners))
        if len(winners) < raffle.win_count:
            await interaction.send("Not enough participants for giveaway!")
            if not winners:
                await interaction.send("No users to choose...")
                raffle.ongoing = True
                return
        await interaction.send("And the winner is....!!")
        async with interaction.channel.typing():
            await asyncio.sleep(5)
            for user in winners:
                await interaction.send(f"{user.mention}")
            await interaction.send("Congratulations")
        for user in winners:
            try:
                await user.send(f"You're the {raffle.name} raffle winner!!")
            except (discord.HTTPException, discord.Forbidden):
                await interaction.send(
                    f"Failed to send message to winner {user.mention}!"
                )
        self.bot.s.commit()
        await interaction.send(
            f"Giveaway finished with {len(raffle.entries)} participants."
        )
        self.bot.raffle_manager.raffles[interaction.guild.id] = None

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
        await interaction.sendd(f"Updated number of winners to {new_value}")

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(new_role="Role to allow in the raffle")
    @modify.command()
    async def add_allowed_role(
        self,
        interaction,
        new_role: discord.Role,
    ):
        """Add a role to raffle"""
        raffle = self.bot.raffle_manager.get_raffle(interaction)
        self.bot.s.add(GiveawayRole(id=new_role.id, giveaway=raffle.id))
        self.bot.s.commit()
        await interaction.sendd(f"Added role {new_role.name} to the raffle")


async def setup(bot):
    await bot.add_cog(Raffle(bot))
