from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Mapped

Base = declarative_base()


class Artist(Base):
    __tablename__ = "artist"
    id = Column(Integer, primary_key=True)
    userid = Column(Integer)
    guild = Column(Integer)
    gallery: Mapped[list["Art"]] = relationship(
        back_populates="artist",
        cascade="all, delete, delete-orphan",
    )

    def __repr__(self):
        return f"<Artist userid='{self.id}'>"


class Art(Base):
    __tablename__ = "gallery"
    id = Column(Integer, primary_key=True)
    artist_id = Column(Integer, ForeignKey("artist.id"))
    link = Column(String)
    description = Column(String)
    artist: Mapped["Artist"] = relationship(
        back_populates="gallery",
    )

    def __repr__(self):
        return f"<Art id={self.id}, artist={self.artist_id}, link='{self.link}'>"


class BlackList(Base):
    __tablename__ = "blacklist"
    userid = Column(Integer, primary_key=True)
    guild = Column(Integer, ForeignKey("guilds.id"), primary_key=True)

    def __repr__(self):
        return f"<Blacklist userid={self.userid} in guild {self.guild}'>"


class Guild(Base):
    __tablename__ = "guilds"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    error_channel = Column(Integer, default=None)
    art_channel = Column(Integer, default=None)
    min_days = Column(Integer, default=7)
    flags = Column(Integer, default=0)


class Poll(Base):
    __tablename__ = "polls"
    id = Column(Integer, primary_key=True)

    name = Column(String)
    description = Column(String)
    options = Column(String)
    url = Column(String)

    custom_id = Column(Integer)
    author_id = Column(Integer)

    # Needed to fetch the view message, ugh
    guild_id = Column(Integer, ForeignKey("guilds.id"))
    channel_id = Column(Integer)
    message_id = Column(Integer)

    active = Column(Boolean, default=False)
    start = Column(TIMESTAMP)
    end = Column(TIMESTAMP)

    voters: Mapped[list["Voter"]] = relationship(
        back_populates="poll", cascade="all, delete, delete-orphan"
    )

    def __repr__(self):
        return f"<Poll id={self.id}, name={self.name}, description={self.description}, options={self.options}, active={self.active}'>"

    @property
    def parsed_options(self):
        return self.options.split("|")


class Voter(Base):
    __tablename__ = "voters"
    userid = Column(Integer, primary_key=True)
    poll_id = Column(Integer, ForeignKey("polls.id"), primary_key=True)
    option = Column(String, default=None)

    poll: Mapped["Poll"] = relationship(back_populates="voters")

    def __repr__(self):
        return f"<Voter userid={self.userid}'>"


class Giveaway(Base):
    __tablename__ = "giveaway"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    url = Column(String)

    author_id = Column(Integer)
    custom_id = Column(Integer)

    # Needed to fetch the view message, ugh
    guild_id = Column(Integer, ForeignKey("guilds.id"))
    channel_id = Column(Integer)
    message_id = Column(Integer)

    ongoing = Column(Boolean, default=False)
    start_date = Column(TIMESTAMP)
    end_date = Column(TIMESTAMP)
    max_participants = Column(Integer)
    win_count = Column(Integer)

    entries: Mapped[list["GiveawayEntry"]] = relationship(
        back_populates="giveaway", cascade="all, delete, delete-orphan"
    )

    roles: Mapped[list["GiveawayRole"]] = relationship(
        back_populates="giveaway",
        cascade="all, delete, delete-orphan",
    )

    def __repr__(self):
        return f"<Giveaway id={self.id}, name={self.name}, win_count={self.win_count}, ongoing={self.ongoing}>"


class GiveawayRole(Base):
    __tablename__ = "giveawayroles"
    id = Column(Integer, primary_key=True)
    giveaway_id = Column(Integer, ForeignKey("giveaway.id"), primary_key=True)

    giveaway: Mapped["Giveaway"] = relationship(back_populates="roles")

    def __repr__(self):
        return f"<GiveawayRole id={self.id}, giveaway={self.giveaway_id}>"


class GiveawayEntry(Base):
    __tablename__ = "giveawayentries"
    user_id = Column(Integer, primary_key=True)
    giveaway_id = Column(Integer, ForeignKey("giveaway.id"), primary_key=True)

    winner = Column(Boolean, default=False)

    giveaway: Mapped["Giveaway"] = relationship(back_populates="entries")

    def __repr__(self):
        return f"<GiveawayEntry giveaway={self.giveaway_id}, winner={self.winner}>"


class CommunityRole(Base):
    __tablename__ = "community_roles"
    id = Column(Integer, primary_key=True)
    guild = Column(Integer, ForeignKey("guilds.id"), primary_key=True)
    name = Column(String)
    alias = Column(String)
    description = Column(String)
