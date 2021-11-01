import aiohttp
import asyncio
import disnake

from disnake import ButtonStyle
from disnake.ext import commands
from disnake.ext.commands import Param
from sqlalchemy.orm import contains_eager
from utils.database import Art, Artist, BlackList, Guild
from utils.exceptions import DisabledCog


class GalleryView(disnake.ui.View):
    def __init__(self, inter, artist: Artist):
        super().__init__(timeout=20)
        self.inter = inter
        self.artist = artist
        self.artist_user = inter.filled_options["member"]
        self.current = 0
        self.message = None

    async def on_timeout(self):
        if self.message:
            await self.message.edit(view=None)

    def create_embed(self):
        embed = disnake.Embed(color=disnake.Color.dark_red())
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

    @disnake.ui.button(label="Previous", style=ButtonStyle.primary)
    async def previous_button(
        self, button: disnake.ui.Button, interaction: disnake.Interaction
    ):
        self.current = (self.current - 1) % len(self.artist.gallery)
        await interaction.response.edit_message(embed=self.create_embed())

    @disnake.ui.button(label="Next", style=ButtonStyle.primary)
    async def next_button(
        self, button: disnake.ui.Button, interaction: disnake.Interaction
    ):
        self.current = (self.current + 1) % len(self.artist.gallery)
        await interaction.response.edit_message(embed=self.create_embed())

    @disnake.ui.button(label="First", style=ButtonStyle.primary)
    async def first_button(
        self, button: disnake.ui.Button, interaction: disnake.Interaction
    ):
        self.current = 0
        await interaction.response.edit_message(embed=self.create_embed())

    @disnake.ui.button(label="Latest", style=ButtonStyle.primary)
    async def latest_button(
        self, button: disnake.ui.Button, interaction: disnake.Interaction
    ):
        self.current = len(self.artist.gallery) - 1
        await interaction.response.edit_message(embed=self.create_embed())


class Gallery(commands.Cog):
    """Commands for managing a user gallery."""

    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        self.cleanup = False
        self.art_channel = {
            guild.id: guild.art_channel for guild in self.bot.s.query(Guild).all()
        }

    def is_enabled(self, guild):
        dbguild = self.bot.s.query(Guild).get(guild.id)
        return dbguild.flags & 0b10

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if not self.is_enabled(ctx.guild):
            raise DisabledCog()
        return True

    @commands.Cog.listener()
    async def on_message(self, message):
        if isinstance(
            message.channel, disnake.abc.PrivateChannel
        ) or not self.is_enabled(message.guild):
            return
        if message.channel.id == self.art_channel[message.guild.id]:
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

    def add_artist(self, member: disnake.Member):
        artist = Artist(userid=member.id, guild=member.guild.id)
        self.bot.s.add(artist)
        self.logger.debug(f"Added artist {member.id} in guild {member.guild.id}")
        return artist

    def add_art(self, member: disnake.Member, url, description=""):
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

    def get_artist(self, member: disnake.Member):
        return (
            self.bot.s.query(Artist)
            .filter(Artist.userid == member.id, Artist.guild == member.guild.id)
            .one_or_none()
        )

    def delete_art(self, art_id):
        self.bot.s.query(Art).filter_by(id=art_id).delete()
        self.logger.debug(f"Deleted art with id {art_id}")
        self.bot.s.commit()

    @commands.slash_command()
    async def art(self, inter):
        pass

    @art.sub_command()
    async def add(
        self,
        inter,
        link: str = Param(description="Link to the art"),
        description: str = Param(description="Description of the art"),
    ):
        """Adds link to user gallery"""
        if (
            not link.lower().endswith((".gif", ".png", ".jpeg", "jpg"))
            and description == ""
        ):
            await inter.response.send_message(
                "Add a description for non image entries!"
            )
        else:
            id = self.add_art(inter.author, link, description)
            await inter.response.send_message(f"Added art with id {id}!")

    @art.sub_command()
    async def delete(
        self, inter, art_id: int = Param(description="ID of the art to delete")
    ):
        """Removes image from user gallery"""
        deleted = []
        art = (
            self.bot.s.query(Art)
            .join(Artist)
            .filter(
                Art.id == art_id,
                Art.artist_id == Artist.id,
                Artist.guild == inter.guild.id,
            )
            .one_or_none()
        )
        if art is None:
            await inter.response.send_message(f"ID {art_id} not found")
            return
        elif (
            inter.author.id != art.artist.userid
            and not inter.author.permissions_in(inter.channel).manage_nicknames
        ):
            await inter.response.send_message("You cant delete other people art!")
            return
        self.delete_art(art_id)
        deleted.append(str(art_id))
        if deleted:
            await inter.response.send_message(
                f"Deleted with ID {', '.join(deleted)} successfully!"
            )

    @commands.has_guild_permissions(manage_guild=True)
    @art.sub_command()
    async def cleanup(self, inter):
        """Cleans up the galleries of invalid links"""
        todelete = []
        self.cleanup = True
        await inter.response.send_message(
            "Starting gallery cleanup (This might take a while)!"
        )
        await self.bot.change_presence(status=disnake.Status.dnd)
        arts = (
            self.bot.s.query(Art)
            .join(Art.artist)
            .filter(Artist.guild == inter.guild.id)
            .options(contains_eager("artist"))
            .all()
        )
        tasks = []

        async def head(url, s):
            async with s.head(url) as r:
                return r

        async with aiohttp.ClientSession() as session:
            for art in arts:
                task = asyncio.ensure_future(head(art.link, session))
                tasks.append(task)
            responses = await asyncio.gather(*tasks)

        for resp in responses:
            if resp.status == 403:
                todelete.append(art)

        if todelete:
            for art in todelete:
                self.bot.s.delete(art)
            self.bot.s.commit()
            await inter.edit_original_message(
                content=f"Deleted {len(todelete)} invalid images!"
            )
        else:
            await inter.edit_original_message(content="No invalid images found!")
        self.cleanup = False
        await self.bot.change_presence(status=disnake.Status.online)

    @commands.has_guild_permissions(manage_guild=True)
    @art.sub_command()
    async def setchannel(
        self,
        inter,
        channel: disnake.TextChannel = Param(
            description="Text channel to set as the art channel"
        ),
    ):
        """Sets a Text channel as the art channel"""
        dbguild = self.bot.s.query(Guild).get(inter.guild.id)
        dbguild.art_channel = channel.id
        self.art_channel[inter.guild.id] = channel.id
        self.bot.s.commit()
        await inter.response.send_message(f"Set art channel to {channel.mention}")

    @art.sub_command()
    async def gallery(
        self,
        inter,
        member: disnake.Member = Param(description="Member to check the gallery of"),
    ):
        """Show a user gallery"""
        artist = self.get_artist(member)
        if artist and artist.gallery:
            view = GalleryView(inter, artist)
            view.message = await inter.response.send_message(
                embed=view.create_embed(), view=view, ephemeral=True
            )
        else:
            await inter.response.send_message(
                "This user doesnt have a gallery", ephemeral=True
            )

    @commands.slash_command()
    async def artist(self, inter):
        pass

    @commands.has_guild_permissions(kick_members=True)
    @commands.guild_only()
    @artist.sub_command()
    async def delete(
        self,
        inter,
        member: disnake.Member = Param(description="Member to delete the gallery of"),
    ):
        """Deletes artist along with gallery"""
        artist = self.get_artist(member)
        if artist is None:
            await inter.response.send_message(f"{member} doesnt have a gallery")
            return
        self.bot.s.delete(artist)
        self.bot.s.commit()
        await inter.response.send_message("Artist deleted")

    async def cog_command_error(self, ctx, exc):
        self.logger.debug(f"{ctx.command}: {exc}")


def setup(bot):
    bot.add_cog(Gallery(bot))
