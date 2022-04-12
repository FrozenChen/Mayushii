import aiohttp
import asyncio
import discord

from discord import ButtonStyle, app_commands
from discord.ext import commands
from sqlalchemy.orm import contains_eager
from utils.database import Art, Artist, BlackList, Guild


class GalleryView(discord.ui.View):
    def __init__(
        self, interaction: discord.Interaction, artist: Artist, member: discord.Member
    ):
        super().__init__(timeout=20)
        self.inter = interaction
        self.artist = artist
        self.artist_user = member
        self.current = 0
        self.message = None
        if len(artist.gallery) == 1:
            self.clear_items()
            self.stop()

    async def on_timeout(self):
        if self.message:
            await self.message.edit(view=None)

    def create_embed(self):
        embed = discord.Embed(color=discord.Color.dark_red())
        art = self.artist.gallery[self.current]
        embed.set_author(
            name=f"{self.artist_user.display_name}'s Gallery {self.current + 1}",
            icon_url=self.artist_user.avatar.url,
        )
        footer = f"Art id: {art.id}"
        if art.link.lower().endswith((".gif", ".png", ".jpeg", "jpg")):
            embed.set_image(url=art.link)
            if art.description:
                footer += f"\n{art.description}"
        else:
            embed.description = f"{art.description}\n{art.link}"
        footer += f"\n{self.current + 1}/{len(self.artist.gallery)}"
        embed.set_footer(text=footer)
        return embed

    @discord.ui.button(label="Previous", style=ButtonStyle.primary)
    async def previous_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current = (self.current - 1) % len(self.artist.gallery)
        await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Next", style=ButtonStyle.primary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current = (self.current + 1) % len(self.artist.gallery)
        await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="First", style=ButtonStyle.primary)
    async def first_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current = 0
        await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Latest", style=ButtonStyle.primary)
    async def latest_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current = len(self.artist.gallery) - 1
        await interaction.response.edit_message(embed=self.create_embed())


class Gallery(commands.Cog):
    """Commands for managing a user gallery."""

    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        self.cleanup = False
        self.bot.art_channels = {
            guild.id: guild.art_channel for guild in self.bot.s.query(Guild).all()
        }

    def is_enabled(self, guild):
        dbguild = self.bot.s.query(Guild).get(guild.id)
        return dbguild.flags & 0b10

    async def no_cleanup(self):
        while self.cleanup:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            isinstance(message.channel, discord.abc.PrivateChannel)
            or message.author == message.guild.me
        ):
            return
        art_channel_id = self.bot.art_channels.get(message.guild.id)
        if not self.is_enabled(message.guild) or art_channel_id is None:
            return
        if message.channel.id == art_channel_id:
            count = 0
            added = []
            for attachment in message.attachments:
                if attachment.height and not message.content.startswith("."):
                    art_id = self.add_art(
                        message.author, attachment.url, message.content
                    )
                    added.append(art_id)
                    count += 1
            if count:
                await message.channel.send(
                    f"Added {count} image(s) to {message.author}'s gallery with id(s) {', '.join(map(str, added))}!"
                )

    def add_artist(self, member: discord.Member):
        artist = Artist(userid=member.id, guild=member.guild.id)
        self.bot.s.add(artist)
        self.logger.debug(f"Added artist {member.id} in guild {member.guild.id}")
        return artist

    async def add_art(self, member: discord.Member, url, description=""):
        await asyncio.wait_for(self.no_cleanup(), timeout=None)
        if self.bot.s.query(BlackList).get((member.id, member.guild.id)):
            return
        if not (artist := self.get_artist(member)):
            artist = self.add_artist(member)
            self.bot.s.commit()
            self.bot.s.refresh(artist)

        art = Art(artist_id=artist.id, link=url, description=description)
        self.bot.s.add(art)
        self.bot.s.commit()
        self.bot.s.refresh(art)
        self.logger.debug(f"Added art with id {art.id} in guild {art.artist.guild}")
        return art.id

    def get_artist(self, member: discord.Member):
        return (
            self.bot.s.query(Artist)
            .filter(Artist.userid == member.id, Artist.guild == member.guild.id)
            .one_or_none()
        )

    def delete_art(self, art_id):
        self.bot.s.query(Art).filter_by(id=art_id).delete()
        self.logger.debug(f"Deleted art with id {art_id}")
        self.bot.s.commit()

    art = app_commands.Group(name="art", description="Commands for managing art")

    @app_commands.describe(link="Link to the art", description="Description of the art")
    @art.command()
    async def add(self, interaction, link: str, description: str):
        """Adds link to user gallery"""
        if interaction.channel.id != self.bot.art_channels.get(interaction.guild_id):
            return await interaction.response.send_message(
                "This command can only be used in the art channel."
            )
        if (
            not link.lower().endswith((".gif", ".png", ".jpeg", "jpg"))
            and description == ""
        ):
            await interaction.response.send_message(
                "Add a description for non image entries!", ephemeral=True
            )
        else:
            id = await self.add_art(interaction.user, link, description)
            await interaction.response.send_message(f"Added art with id {id}!")

    @app_commands.describe(art_id="ID of the art to delete")
    @art.command(name="delete")
    async def art_delete(self, interaction, art_id: int):
        """Removes image from user gallery"""
        deleted = []
        art = (
            self.bot.s.query(Art)
            .join(Artist)
            .filter(
                Art.id == art_id,
                Art.artist_id == Artist.id,
                Artist.guild == interaction.guild.id,
            )
            .one_or_none()
        )
        if art is None:
            await interaction.response.send_message(f"ID {art_id} not found")
            return
        elif (
            interaction.user.id != art.artist.userid
            and not interaction.channel.permissions_for(
                interaction.user
            ).manage_nicknames
        ):
            await interaction.response.send_message("You cant delete other people art!")
            return
        self.delete_art(art_id)
        deleted.append(str(art_id))
        if deleted:
            await interaction.response.send_message(
                f"Deleted with ID {', '.join(deleted)} successfully!"
            )

    @app_commands.checks.has_permissions(manage_guild=True)
    @art.command()
    async def cleanup(self, interaction):
        """Cleans up the galleries of invalid links"""
        todelete = []
        self.cleanup = True
        await interaction.response.send_message(
            "Starting gallery cleanup (This might take a while)!"
        )
        await self.bot.change_presence(status=discord.Status.dnd)
        arts: list[Art] = (
            self.bot.s.query(Art)
            .join(Art.artist)
            .filter(Artist.guild == interaction.guild.id)
            .options(contains_eager("artist"))
            .all()
        )
        tasks = []

        async def head(url: str, s: aiohttp.ClientSession):
            try:
                async with s.head(url) as r:
                    return r.status != 400
            except aiohttp.InvalidURL:
                return False
            except Exception as e:
                self.logger.error(f"Unknown exception in clean up: {type(e)}:{e}")
                return True

        for art in arts:
            task = asyncio.ensure_future(head(art.link, self.bot.session))
            tasks.append(task)
        responses = await asyncio.gather(*tasks)

        for n, ok in enumerate(responses):
            if not ok:
                todelete.append(arts[n])

        if todelete:
            for art in todelete:
                self.bot.s.delete(art)
            self.bot.s.commit()
            await interaction.edit_original_message(
                content=f"Deleted {len(todelete)} invalid images!"
            )
        else:
            await interaction.edit_original_message(content="No invalid images found!")
        self.cleanup = False
        await self.bot.change_presence(status=discord.Status.online)

    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(channel="Text channel to set as the art channel")
    @art.command()
    async def setchannel(self, interaction, channel: discord.TextChannel):
        """Sets a Text channel as the art channel"""
        dbguild = self.bot.s.query(Guild).get(interaction.guild.id)
        dbguild.art_channel = channel.id
        self.bot.art_channel[interaction.guild.id] = channel.id
        self.bot.s.commit()
        await interaction.response.send_message(f"Set art channel to {channel.mention}")

    @app_commands.describe(member="Member to check the gallery of")
    @art.command()
    async def gallery(self, interaction, member: discord.Member):
        """Show a user gallery"""
        artist = self.get_artist(member)
        if artist and artist.gallery:
            view = GalleryView(interaction, artist, member)
            view.message = await interaction.response.send_message(
                embed=view.create_embed(), view=view, ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "This user doesnt have a gallery", ephemeral=True
            )

    artist = app_commands.Group(
        name="artist", description="Commands for managing artists"
    )

    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="Member to delete the gallery of")
    @artist.command(name="delete")
    async def artist_delete(self, interaction, member: discord.Member):
        """Deletes artist along with gallery"""
        artist = self.get_artist(member)
        if artist is None:
            await interaction.response.send_message(f"{member} doesnt have a gallery")
            return
        self.bot.s.delete(artist)
        self.bot.s.commit()
        await interaction.response.send_message("Artist deleted")


async def setup(bot):
    await bot.add_cog(Gallery(bot))
