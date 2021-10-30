import aiohttp
import disnake

from disnake import ButtonStyle
from disnake.ext import commands
from utils.database import Art, Artist, BlackList, Guild
from utils.exceptions import DisabledCog


class GalleryView(disnake.ui.View):
    def __init__(self, ctx, artist: Artist):
        super().__init__(timeout=20)
        self.ctx = ctx
        self.artist = artist
        self.current = 0
        self.message = None

    async def on_timeout(self):
        if self.message:
            await self.message.edit(view=None)

    def create_embed(self):
        embed = disnake.Embed(color=disnake.Color.dark_red())
        art = self.artist.gallery[self.current]
        embed.set_author(
            name=f"{self.ctx.author.display_name}'s Gallery {self.current + 1}",
            icon_url=self.ctx.author.avatar.url,
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

    @commands.command()
    async def addart(self, ctx, link, *, description=""):
        """Adds link to user gallery"""
        if (
            not link.lower().endswith((".gif", ".png", ".jpeg", "jpg"))
            and description == ""
        ):
            await ctx.send("Add a description for non image entries!")
        else:
            id = self.add_art(ctx.author, link, description)
            await ctx.send(f"Added art with id {id}!")

    @commands.command()
    async def delart(self, ctx, art_ids: commands.Greedy[int]):
        """Removes image from user gallery"""
        deleted = []
        for art_id in art_ids:
            art = (
                self.bot.s.query(Art)
                .join(Artist)
                .filter(
                    Art.id == art_id,
                    Art.artist_id == Artist.id,
                    Artist.guild == ctx.guild.id,
                )
                .one_or_none()
            )
            if art is None:
                await ctx.send(f"ID {art_id} not found")
                continue
            elif (
                ctx.author.id != art.artist.userid
                and not ctx.author.permissions_in(ctx.channel).manage_nicknames
            ):
                await ctx.send("You cant delete other people art!")
                return
            self.delete_art(art_id)
            deleted.append(str(art_id))
        if deleted:
            await ctx.send(f"Deleted with ID {', '.join(deleted)} successfully!")

    @commands.command()
    async def gallery(self, ctx, member: disnake.Member = None):
        """Show user gallery in DMs"""
        try:
            await ctx.message.delete()
        except disnake.Forbidden:
            pass
        if not member:
            member = ctx.author
        artist = self.get_artist(member)
        if artist and artist.gallery:
            view = GalleryView(ctx, artist)
            view.message = await ctx.author.send(embed=view.create_embed(), view=view)
        else:
            try:
                await ctx.author.send("This user doesnt have a gallery")
            except disnake.Forbidden:
                pass

    @commands.has_guild_permissions(kick_members=True)
    @commands.guild_only()
    @commands.command()
    async def delartist(self, ctx, member: disnake.Member):
        """Deletes artist along with gallery"""
        artist = self.get_artist(member)
        if artist is None:
            await ctx.send(f"{member} doesnt have a gallery")
            return
        self.bot.s.delete(artist)
        self.bot.s.commit()
        await ctx.send("Artist deleted")

    @commands.has_guild_permissions(manage_guild=True)
    @commands.command()
    async def cleanup(self, ctx):
        todelete = []
        self.cleanup = True
        await ctx.send("Starting gallery cleanup (This might take a while)!")
        await self.bot.change_presence(status=disnake.Status.dnd)
        for art in self.bot.s.query(Art).filter(Art.artist.guild == ctx.guild.id).all():
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.head(art.link) as resp:
                        if resp.status == 403:
                            todelete.append(art)
                except aiohttp.InvalidURL:
                    todelete.append(art)
        if todelete:
            for art in todelete:
                self.bot.s.delete(art)
            self.bot.s.commit()
            await ctx.send(f"Deleted {len(todelete)} invalid images!")
        else:
            await ctx.send("No invalid images found!")
        self.cleanup = False
        await self.bot.change_presence(status=disnake.Status.online)

    @commands.has_guild_permissions(manage_guild=True)
    @commands.command()
    async def setartchannel(self, ctx, channel: disnake.TextChannel):
        dbguild = self.bot.s.query(Guild).get(ctx.guild.id)
        dbguild.art_channel = channel.id
        self.art_channel[ctx.guild.id] = channel.id
        self.bot.s.commit()
        await ctx.send(f"Set art channel to {channel.mention}")

    async def cog_command_error(self, ctx, exc):
        self.logger.debug(f"{ctx.command}: {exc}")


def setup(bot):
    bot.add_cog(Gallery(bot))
