import discord

from utils.checks import not_new, not_blacklisted
from utils.managers import VoteManager


class VoteButton(discord.ui.Button["VoteView"]):
    def __init__(
        self,
        custom_id: str,
        label: str,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
    ):
        super().__init__(style=style, label=label, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        await self.view.poll_manager.process_vote(interaction, option=self.label)


class LinkButton(discord.ui.Button):
    def __init__(self, label: str, url: str):
        super().__init__(label=label, url=url, style=discord.ButtonStyle.link)


class VoteView(discord.ui.View):
    def __init__(
        self,
        options: list[str],
        custom_id: int,
        guild_id: int,
        channel_id: int,
        poll_manager: VoteManager,
    ):
        super().__init__(timeout=None)
        self.custom_id = custom_id
        self.message_id = None
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.poll_manager = poll_manager
        for n, option in enumerate(options):
            self.add_item(VoteButton(label=option, custom_id=f"{custom_id}_{n}"))

    async def interaction_check(self, interaction: discord.Interaction):
        return (
            not_new(interaction)
            and not_blacklisted(interaction)
            and self.poll_manager.ongoing_poll(self.guild_id)
        )

    async def stop_vote(self):
        if self.message_id:
            if guild := self.poll_manager.bot.get_guild(self.guild_id):
                channel = guild.get_channel(self.channel_id)
                if channel:
                    msg = await channel.fetch_message(self.message_id)
                    await msg.edit(view=None)
        self.stop()
