import discord

from typing import Optional
from utils.checks import not_new, not_blacklisted
from utils.managers import VoteManager, RaffleManager


class VoteButton(discord.ui.Button["VoteView"]):
    label: str

    def __init__(
        self,
        custom_id: str,
        label: str,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
    ):
        super().__init__(style=style, label=label, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        await self.view.manager.process_vote(interaction, option=self.label)


class LinkButton(discord.ui.Button):
    def __init__(self, label: str, url: str):
        super().__init__(label=label, url=url, style=discord.ButtonStyle.link)


class BasePersistentView(discord.ui.View):
    def __init__(
        self,
        custom_id: int,
        channel_id: int,
        manager,
        message_id: Optional[int] = None,
    ):

        super().__init__(timeout=None)
        self.custom_id = custom_id
        self.message_id = message_id
        self.channel_id = channel_id
        self.manager = manager
        self.messageable: discord.PartialMessageable = (
            self.manager.bot.get_partial_messageable(id=self.channel_id)
        )

    async def stop(self):
        if self.message_id:
            try:
                msg = await self.messageable.fetch_message(self.message_id)
                await msg.edit(view=None)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        super().stop()


class VoteView(BasePersistentView):
    def __init__(
        self,
        custom_id: int,
        channel_id: int,
        poll_manager: VoteManager,
        message_id: Optional[int] = None,
        *,
        options: list[str],
    ):
        super().__init__(
            custom_id=custom_id,
            channel_id=channel_id,
            manager=poll_manager,
            message_id=message_id,
        )
        for n, option in enumerate(options):
            self.add_item(VoteButton(label=option, custom_id=f"{custom_id}_{n}"))

    async def interaction_check(self, interaction: discord.Interaction):
        assert interaction.guild is not None
        return (
            not_new(interaction)
            and not_blacklisted(interaction)
            and self.manager.ongoing_poll(interaction.guild.id)
        )


class RaffleButton(discord.ui.Button["RaffleView"]):
    def __init__(
        self,
        custom_id: str,
        label: str,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
    ):
        super().__init__(style=style, label=label, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        await self.view.manager.process_entry(interaction)


class RaffleView(BasePersistentView):
    def __init__(
        self,
        custom_id: int,
        channel_id: int,
        raffle_manager: RaffleManager,
        message_id: Optional[int] = None,
    ):
        super().__init__(
            custom_id=custom_id,
            channel_id=channel_id,
            manager=raffle_manager,
            message_id=message_id,
        )
        self.add_item(RaffleButton(label="Join", custom_id=f"{custom_id}_join"))

    async def interaction_check(self, interaction: discord.Interaction):
        assert interaction.guild is not None
        if not_new(interaction) and not_blacklisted(interaction):
            if not self.manager.get_raffle(interaction.guild.id):
                await interaction.response.send_message(
                    "There is no ongoing raffle", ephemeral=True
                )
                return False
        return True
