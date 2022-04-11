import discord
import datetime

from discord.ext import commands, tasks
from discord import app_commands
from utils.database import Poll, Guild
from utils.utilities import ConfirmationButtons, TimeTransformer, DateTransformer
from utils.views import VoteView, LinkButton
from utils.managers import VoteManager


class Voting(commands.Cog, app_commands.Group, name="poll"):
    """Commands for managing a poll."""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        self.bot.poll_manager = VoteManager(self.bot)

    async def cog_load(self):
        for guild, poll in self.bot.poll_manager.polls.items():
            self.bot.add_view(
                VoteView(
                    options=poll.parsed_options,
                    custom_id=poll.custom_id,
                    guild_id=poll.guild_id,
                    poll_manager=self.bot.poll_manager,
                    channel_id=poll.channel_id,
                )
            )
        self.check_views.start()

    @tasks.loop(seconds=60.0)
    async def check_views(self):
        now = datetime.datetime.utcnow()
        for poll in self.bot.poll_manager.polls.values():
            if poll.end and poll.end < now:
                view = discord.utils.get(
                    self.bot.persistent_views, custom_id=poll.custom_id
                )
                await self.bot.poll_manager.end_poll(poll, view)

    @staticmethod
    def is_enabled(interaction):
        dbguild = interaction.client.s.query(Guild).get(interaction.guild.id)
        return dbguild.flags & 0b1000

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.command()
    @app_commands.describe(
        name="Name of the new poll",
        description="Link to the relevant image to the poll",
        options="Options for the poll. Example A|B|C",
        target_channel="Channel to post the poll",
        end_date="End date of poll. dd/mm/yy hh:mm:ss format. Time is optional",
        lasts="How long the poll lasts. #d#h#m#s format.",
    )
    async def create(
        self,
        interaction: discord.Interaction,
        name: str,
        description: str,
        message: str,
        options: str,
        target_channel: discord.TextChannel,
        end_date: app_commands.Transform[datetime.datetime, DateTransformer] = None,
        lasts: app_commands.Transform[int, TimeTransformer] = None,
        url: str = None,
    ):
        """Creates a poll"""
        if self.bot.poll_manager.get_ongoing_poll(interaction.guild_id):
            return await interaction.response.send(
                "There is an ongoing poll!", ephemeral=True
            )
        if lasts and end_date:
            return await interaction.response.send_message(
                "end_date and lasts parameters are mutually exclusive"
            )
        if lasts and lasts < 600:
            return await interaction.response.send_message(
                "A poll has to last longer than 10 minutes"
            )
        parsed_options = self.bot.poll_manager.parse_options(options)
        embed = discord.Embed(title="Proposed Poll", color=discord.Color.green())
        embed.add_field(name="Name", value=name, inline=False)
        embed.add_field(name="Description", value=description, inline=False)
        embed.add_field(name="Options", value=" ".join(parsed_options), inline=False)
        conf_view = ConfirmationButtons()
        await interaction.response.send_message(
            "Is this poll correct?", view=conf_view, embed=embed, ephemeral=True
        )
        await conf_view.wait()
        if conf_view.value:
            start = datetime.datetime.utcnow()
            if lasts or end_date:
                if lasts:
                    diff = datetime.timedelta(seconds=lasts)
                    end_date = start + diff
                if end_date < start or (end_date - start).total_seconds() < 600:
                    return await interaction.edit_original_message(
                        content="A poll has to last longer than 10 minutes",
                        view=None,
                        embed=None,
                    )
            vote_view = VoteView(
                options=parsed_options,
                custom_id=interaction.id,
                guild_id=interaction.guild_id,
                poll_manager=self.bot.poll_manager,
                channel_id=target_channel.id,
            )
            if url:
                vote_view.add_item(LinkButton(label="Gallery", url=url))
            msg = await target_channel.send("Loading", view=vote_view)
            poll = self.bot.poll_manager.create_poll(
                name=name,
                options=options,
                guild_id=interaction.guild_id,
                message_id=msg.id,
                url=url,
                author_id=interaction.user.id,
                custom_id=interaction.id,
                description=description,
                start=start,
                end=end_date,
                channel_id=msg.channel.id,
            )
            await msg.edit(
                content=None,
                embed=self.bot.poll_manager.create_embed(poll, description=message),
            )
            poll.active = True
            self.bot.s.commit()
            self.logger.info(f"Enabled poll {poll.name}")
            self.bot.poll_manager.polls[interaction.guild.id] = poll
            await interaction.edit_original_message(
                content="Poll Created!", view=None, embed=None
            )
        else:
            await interaction.edit_original_message(
                content="Alright then.", view=None, embed=None
            )

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.command()
    async def close(self, interaction: discord.Interaction):
        """Closes a poll"""
        if (
            poll := self.bot.poll_manager.get_ongoing_poll(interaction.guild_id)
        ) is None:
            return await interaction.response.send_message("No ongoing poll")

        view = discord.utils.get(self.bot.persistent_views, custom_id=poll.custom_id)
        await self.bot.poll_manager.end_poll(poll, view)
        await interaction.response.send_message("Poll closed successfully")

    @app_commands.checks.has_permissions(manage_nicknames=True)
    @app_commands.command()
    async def tally(self, interaction: discord.Interaction):
        """Show the current state of the poll"""
        if poll := self.bot.poll_manager.get_ongoing_poll(interaction.guild_id) is None:
            return await interaction.response.send_message("There is no ongoing poll")
        result = self.bot.poll_manager.count_votes(poll)
        embed = discord.Embed()
        msg = ""
        for x in result.keys():
            msg += f"{x}: {result[x]}   "
        embed.add_field(name="Votes", value=msg, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.command()
    async def list(self, interaction: discord.Interaction):
        """Shows a list with current and past polls"""
        polls = (
            self.bot.s.query(Poll).filter(Poll.guild_id == interaction.guild.id).all()
        )
        if polls:
            embed = discord.Embed(title="Poll List")
            for poll in polls:
                msg = (
                    f"id={poll.id}\n"
                    f"link={poll.description}\n"
                    f"option={poll.options}\n"
                    f"active={poll.active}\n"
                    f"votes={len(poll.voters)}\n"
                )
                embed.add_field(name=poll.name, value=msg)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("No polls to show!")

    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.command()
    async def delete(self, interaction: discord.Interaction, poll_id: int):
        """Deletes a poll"""
        poll = (
            self.bot.s.query(Poll)
            .filter(Poll.id == poll_id, Poll.guild_id == interaction.guild.id)
            .first()
        )
        if not poll:
            await interaction.response.send_message(
                "No poll associated with provided ID"
            )
        else:
            if poll == self.bot.poll_manager.get_ongoing_poll(interaction.guild_id):
                del self.bot.poll_manager.polls[interaction.guild.id]
            self.bot.s.delete(poll)
            self.bot.s.commit()
            await interaction.response.send_message("Poll deleted successfully")

    @app_commands.checks.has_permissions(manage_nicknames=True)
    @app_commands.command()
    async def info(self, interaction: discord.Interaction, poll_id: int = None):
        """Shows info about current poll or provided poll id"""
        if poll_id is None:
            if self.bot.poll_manager.get_ongoing_poll(interaction.guild_id) is None:
                await interaction.response.send_message(
                    "There is no ongoing poll", ephemeral=True
                )
                return
            else:
                poll_id = self.bot.poll_manager.get_ongoing_poll(
                    interaction.guild_id
                ).id
        poll = self.bot.poll_manager.get_poll(poll_id, interaction.guild_id)
        embed = discord.Embed(title=poll.name, color=discord.Color.blurple())
        embed.add_field(name="ID", value=poll.id, inline=False)
        if poll.url:
            embed.add_field(name="Link", value=poll.url, inline=False)
        embed.add_field(
            name="Options",
            value=" ".join(self.bot.poll_manager.parse_options(poll.options)),
            inline=False,
        )
        if poll.end:
            embed.add_field(
                name="End date", value=discord.utils.format_dt(poll.end, "F")
            )
        result = self.bot.poll_manager.count_votes(poll)
        msg = ""
        for x in result.keys():
            msg += f"{x}: {result[x]}   "
        embed.add_field(name="Votes", value=msg, inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Voting(bot))
