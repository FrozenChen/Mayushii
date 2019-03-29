import discord
from discord.ext import commands
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from utils.database import Art, Artist, BlackList, Base


class Gallery(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.get_logger(self)
        engine = create_engine('sqlite:///gallery.db')
        session = sessionmaker(bind=engine)
        self.s = session()
        Base.metadata.create_all(engine, tables=[Art.__table__, Artist.__table__, BlackList.__table__])
        self.s.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.attachments and message.attachments[0].height:
            self.add_art(message.author, message.attachments[0].url)

    def add_artist(self, artist):
        self.s.add(Artist(userid=artist.id))
        self.logger.debug(f'Added artist artist.id')

    def add_art(self, author, url):
        if self.s.query(BlackList).filter(BlackList.userid == author.id).scalar():
            return
        if not self.s.query(Artist).filter(Artist.userid == author.id).all():
            self.add_artist(author.id)
        self.s.add(Art(artist=author.id, link=url))
        self.logger.debug(f'Added art with link {url}')
        self.s.commit()

    def delete_art(self, art_id):
        self.s.query(Art).filter(Art.id == art_id).delete()
        self.logger.debug(f'Added art with id {art_id}')
        self.s.commit()

    @commands.command()
    async def delart(self, ctx, art_id: int):
        """Removes image from user gallery"""
        art = self.s.query(Art).get(art_id)
        if art is None:
            await ctx.send("Art ID not found")
            return
        elif not ctx.author.id == art.artist or not ctx.author.permissions_in(ctx.channel).manage_nicknames:
            await ctx.send("You cant delete other people art scum!")
            return
        await self.s.delete(art)
        await ctx.send("Art deleted succesfully!")

    @commands.command()
    async def gallery(self, ctx, member: discord.Member = None):
        """Show user gallery in DMs"""
        await ctx.message.delete()
        if not member:
            member = ctx.author
        artist = self.s.query(Artist).get(member.id)
        if artist is not None:
            for idx, art in enumerate(artist.gallery):
                embed = discord.Embed(color=discord.Color.dark_red())
                embed.set_author(name=f"{member.display_name}'s Gallery Image {idx + 1}", icon_url=member.avatar_url)
                embed.set_image(url=art.link)
                embed.set_footer(text=f"Image id: {art.id}")
                await ctx.author.send(embed=embed)
        else:
            await ctx.author.send("This user doesnt have a gallery")

    @commands.guild_only()
    @commands.command()
    async def delartist(self, ctx, member: discord.Member):
        """Deletes artist along with gallery"""
        artist = self.s.query(Artist).get(member.id)
        if artist is None:
            await ctx.send(f"{member} doesnt have a gallery")
            return
        self.s.delete(artist)
        self.s.commit()
        await ctx.send("Artist deleted")

    @commands.has_permissions(manage_nicknames=True)
    @commands.guild_only()
    @commands.command()
    async def blackart(self, ctx, member: discord.Member):
        """Blacklist user"""
        if self.s.query(BlackList).get(member.id):
            await ctx.send(f"{member} is already in the blacklist")
            return
        self.s.add(BlackList(userid=member.id))
        self.s.commit()
        await ctx.send(f"Added {member} to the blacklist")

    @commands.has_permissions(manage_nicknames=True)
    @commands.guild_only()
    @commands.command()
    async def whiteart(self, ctx, member: discord.Member):
        """Blacklist user"""
        user = self.s.query(BlackList).get(member.id)
        if user is None:
            await ctx.send(f"{member} is not in the blacklist")
        self.s.delete(user)
        await ctx.send(f"Removed {member} from the blacklist")

    async def cog_command_error(self, ctx, exc):
        self.logger.debug(f"{ctx.command}: {exc}")

def setup(bot):
    bot.add_cog(Gallery(bot))
