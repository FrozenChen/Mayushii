import asyncio
import disnake
import random

from disnake.ext import commands
from disnake.ext.commands import Param
from utils.checks import not_new, not_blacklisted
from utils.database import Giveaway, Entry, GiveawayRole, Guild
from utils.exceptions import NoOnGoingRaffle, DisabledCog
from utils.utilities import ConfirmationButtons
from typing import List


class Raffle(commands.Cog):
    """Giveaway commands for giveaway use"""

    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        self.raffles = {
            raffle.guild: raffle
            for raffle in self.bot.s.query(Giveaway).filter_by(ongoing=True).all()
        }
        self.queue = asyncio.Queue()

    @staticmethod
    def is_enabled(inter):
        dbguild = inter.application_command.cog.bot.s.query(Guild).get(inter.guild.id)
        return dbguild.flags & 0b100

    async def cog_check(self, inter):
        if inter.guild is None:
            raise commands.NoPrivateMessage()
        if not self.is_enabled(inter):
            raise DisabledCog()
        return True

    # checks
    def ongoing_raffle(inter):
        raffle = inter.application_command.cog.get_raffle(inter)
        if raffle and raffle.ongoing:
            return True
        raise NoOnGoingRaffle("There is no ongoing raffle.")

    # internal functions
    @staticmethod
    def get_raffle(inter):
        return inter.application_command.cog.raffles.get(inter.guild.id)

    async def queue_empty(self):
        while not self.queue.empty():
            pass

    async def process_entry(self):
        inter = await self.queue.get()
        raffle = self.get_raffle(inter)
        if raffle.roles:
            for role in raffle.roles:
                if not any(disnake.utils.get(inter.author.roles, id=role.id)):
                    return await inter.response.send_message(
                        "You are not allowed to participate!", ephemeral=True
                    )
        user_id = inter.author.id
        entry = self.bot.s.query(Entry).get((user_id, raffle.id))
        if entry:
            return await inter.response.send_message(
                "You are already participating!", ephemeral=True
            )
        self.bot.s.add(Entry(id=user_id, giveaway=raffle.id))
        self.bot.s.commit()
        await inter.response.send_message(
            f"{inter.author.mention} now you are participating in the raffle!",
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

    def get_winner(self, inter):
        raffle = inter.application_command.cog.raffles[inter.guild.id]
        while len(raffle.entries) >= 1:
            entry = random.choice(raffle.entries)
            if (winner := inter.guild.get_member(entry.id)) is not None:
                entry.winner = True
                self.bot.s.commit()
                return winner
            self.bot.s.delete(entry)
        return None

    @commands.slash_command()
    async def raffle(self, inter):
        """Raffle related commands"""
        pass

    @commands.check(not_blacklisted)
    @commands.check(not_new)
    @commands.check(ongoing_raffle)
    @commands.guild_only()
    @raffle.sub_command()
    async def join(self, inter):
        """Joins the ongoing raffle if there is one"""
        await self.queue.put(inter)
        await self.process_entry()

    @commands.has_guild_permissions(manage_channels=True)
    @commands.guild_only()
    @raffle.sub_command()
    async def create(
        self,
        inter,
        name: str = Param(description="Name of the new raffle"),
        winners: int = Param(default=1, description="Number of winners"),
        allowed_role: disnake.Role = Param(
            default=None, description="Roles allowed to participate"
        ),
    ):
        """Creates a giveaway"""
        if self.get_raffle(inter):
            return await inter.response.send_message(
                "There is an already ongoing giveaway!"
            )
        embed = disnake.Embed(title="Proposed Giveaway", color=disnake.Color.purple())
        embed.add_field(name="Name", value=name, inline=False)
        embed.add_field(name="Number of winners", value=str(winners), inline=False)
        if allowed_role:
            embed.add_field(
                name="Roles accepted",
                value=allowed_role.name,
                inline=False,
            )
        view = ConfirmationButtons()
        await inter.response.send_message(
            "Is this giveaway correct?", embed=embed, view=view
        )
        if view.value:
            self.raffles[inter.guild.id] = self.create_raffle(
                name=name,
                winners=winners,
                roles=[allowed_role.name] if allowed_role else [],
                guild=inter.guild.id,
            )
            await inter.response.send_message(
                f"Started giveaway {name} with {winners} possible winners! Use `/raffle join`to join"
            )
        else:
            await inter.response.send_message("Alright then.")

    @commands.has_guild_permissions(manage_channels=True)
    @commands.check(ongoing_raffle)
    @commands.guild_only()
    @raffle.sub_command()
    async def info(self, inter):
        """Shows information about current giveaway"""
        raffle = self.raffles[inter.guild.id]
        embed = disnake.Embed()
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
        await inter.response.send_message(embed=embed)

    @commands.has_guild_permissions(manage_channels=True)
    @commands.check(ongoing_raffle)
    @commands.guild_only()
    @raffle.sub_command()
    async def cancel(self, inter):
        """Cancels current giveaway"""
        view = ConfirmationButtons()
        await inter.response.send_message(
            "Are you sure you want to cancel current giveaway?", view=view
        )
        if view.value:
            self.raffles[inter.guild.id].ongoing = False
            self.raffles[inter.guild.id] = None
            self.bot.s.commit()
            return await inter.response.send_message("Giveaway cancelled.")
        await inter.response.send_message("And the raffle continues.")

    @commands.has_guild_permissions(manage_channels=True)
    @commands.check(ongoing_raffle)
    @commands.guild_only()
    @raffle.sub_command()
    async def finish(self, inter):
        """Finishes the current raffle"""
        raffle = self.raffles[inter.guild.id]
        raffle.ongoing = False
        self.bot.s.commit()
        await asyncio.wait_for(self.queue_empty(), timeout=None)
        winners = []
        for i in range(0, raffle.win_count):
            winners.append(self.get_winner(inter))
        winners = list(filter(lambda a: a is not None, winners))
        if len(winners) < raffle.win_count:
            await inter.response.send_message("Not enough participants for giveaway!")
            if not winners:
                await inter.response.send_message("No users to choose...")
                raffle.ongoing = True
                return
        await inter.response.send_message("And the winner is....!!")
        async with inter.channel.typing():
            await asyncio.sleep(5)
            for user in winners:
                await inter.response.send_message(f"{user.mention}")
            await inter.response.send_message("Congratulations")
        for user in winners:
            try:
                await user.send(f"You're the {raffle.name} raffle winner!!")
            except (disnake.HTTPException, disnake.Forbidden):
                await inter.response.send_message(
                    f"Failed to send message to winner {user.mention}!"
                )
        self.bot.s.commit()
        await inter.response.send_message(
            f"Giveaway finished with {len(raffle.entries)} participants."
        )
        self.raffles[inter.guild.id] = None

    @commands.check(ongoing_raffle)
    @commands.guild_only()
    @raffle.sub_command_group()
    async def modify(self, inter):
        pass

    @commands.has_guild_permissions(manage_channels=True)
    @modify.sub_command()
    async def winner_count(
        self, inter, new_value: int = Param(description="New amount of winners")
    ):
        """Modify number of winners for the ongoing raffle"""
        self.raffles[inter.guild.id].win_count = new_value
        self.bot.s.commit()
        await inter.response.send_messaged(f"Updated number of winners to {new_value}")

    @commands.has_guild_permissions(manage_channels=True)
    @modify.sub_command()
    async def add_allowed_role(
        self,
        inter,
        new_role: disnake.Role = Param(description="Role to allow in the raffle"),
    ):
        """Add a role to raffle"""
        raffle = self.get_raffle(inter)
        self.bot.s.add(GiveawayRole(id=new_role.id, giveaway=raffle.id))
        self.bot.s.commit()
        await inter.response.send_messaged(f"Added role {new_role.name} to the raffle")


def setup(bot):
    bot.add_cog(Raffle(bot))
