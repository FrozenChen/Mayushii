import aiohttp
import asyncio
import discord

from discord.ext import commands
from utils.database import Art, Artist, BlackList, Guild
from utils.exceptions import DisabledCog


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
            message.channel, discord.abc.PrivateChannel
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

    def add_artist(self, member: discord.Member):
        artist = Artist(userid=member.id, guild=member.guild.id)
        self.bot.s.add(artist)
        self.logger.debug(f"Added artist {member.id} in guild {member.guild.id}")
        return artist

    def add_art(self, member: discord.Member, url, description=""):
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
    async def gallery(self, ctx, member: discord.Member = None):
        """Show user gallery in DMs"""
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        if not member:
            member = ctx.author
        artist = self.get_artist(member)
        if artist and artist.gallery:
            idx = 0
            total = len(artist.gallery)
            message = None
            while True:
                art = artist.gallery[idx]
                embed = discord.Embed(color=discord.Color.dark_red())
                embed.set_author(
                    name=f"{member.display_name}'s Gallery {idx + 1}",
                    icon_url=member.avatar_url,
                )
                footer = f"Art id: {art.id}"
                if art.link.lower().endswith((".gif", ".png", ".jpeg", "jpg")):
                    embed.set_image(url=art.link)
                    if art.description:
                        footer += f"\n{art.description}"

                else:
                    embed.description = f"{art.description}\n{art.link}"
                footer += f"\n{idx + 1}/{total}"
                embed.set_footer(text=footer)
                if not message:
                    message = await ctx.author.send(embed=embed)
                else:
                    await message.edit(embed=embed)
                if total > 1:
                    await message.add_reaction("👈")
                    await message.add_reaction("👉")
                    try:
                        react, user = await ctx.bot.wait_for(
                            "reaction_add",
                            check=lambda reaction, user: reaction.message == message
                            and str(reaction.emoji) in ["👈", "👉"]
                            and user != self.bot.user,
                            timeout=20.0,
                        )
                        if str(react) == "👈":
                            idx = (idx - 1) % total
                        else:
                            idx = (idx + 1) % total
                    except asyncio.TimeoutError:
                        return
                else:
                    return
        else:
            try:
                await ctx.author.send("This user doesnt have a gallery")
            except discord.Forbidden:
                pass

    @commands.has_guild_permissions(kick_members=True)
    @commands.guild_only()
    @commands.command()
    async def delartist(self, ctx, member: discord.Member):
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
        await self.bot.change_presence(status=discord.Status.dnd)
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
        await self.bot.change_presence(status=discord.Status.online)

    @commands.has_guild_permissions(manage_guild=True)
    @commands.command()
    async def setartchannel(self, ctx, channel: discord.TextChannel):
        dbguild = self.bot.s.query(Guild).get(ctx.guild.id)
        dbguild.art_channel = channel.id
        self.art_channel[ctx.guild.id] = channel.id
        self.bot.s.commit()
        await ctx.send(f"Set art channel to {channel.mention}")

    async def cog_command_error(self, ctx, exc):
        self.logger.debug(f"{ctx.command}: {exc}")


def setup(bot):
    bot.add_cog(Gallery(bot))
