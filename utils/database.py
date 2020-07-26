from sqlalchemy import Column, String, Integer, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Artist(Base):
    __tablename__ = "artist"
    userid = Column(Integer, primary_key=True)
    gallery = relationship(
        "Art", back_populates="user", cascade="all, delete, delete-orphan"
    )

    def __repr__(self):
        return f"<Artist userid='{self.userid}'>"


class Art(Base):
    __tablename__ = "gallery"
    id = Column(Integer, primary_key=True)
    artist = Column(Integer, ForeignKey("artist.userid"))
    link = Column(String)
    description = Column(String)
    user = relationship("Artist", back_populates="gallery")

    def __repr__(self):
        return f"<Art id={self.id}, artist={self.artist}, link='{self.link}'>"


class BlackList(Base):
    __tablename__ = "blacklist"
    userid = Column(Integer, primary_key=True)

    def __repr__(self):
        return f"<Blacklist userid={self.userid}'>"


class Voter(Base):
    __tablename__ = "voters"
    userid = Column(Integer, primary_key=True)
    votes = relationship(
        "Vote", back_populates="user", cascade="all, delete, delete-orphan"
    )

    def __repr__(self):
        return f"<Voter userid={self.userid}'>"


class Vote(Base):
    __tablename__ = "votes"
    id = Column(Integer, primary_key=True)
    voter_id = Column(Integer, ForeignKey("voters.userid"))
    poll_id = Column(Integer, ForeignKey("polls.id"))
    option = Column(String)
    user = relationship("Voter", back_populates="votes")
    poll = relationship("Poll", back_populates="votes")

    def __repr__(self):
        return f"<Vote id={self.id}, voter_id={self.voter_id}, poll_id={self.poll_id}, option={self.option}'>"


class Poll(Base):
    __tablename__ = "polls"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    link = Column(String)
    options = Column(String)
    active = Column(Boolean, default=0)
    votes = relationship(
        "Vote", back_populates="poll", cascade="all, delete, delete-orphan"
    )

    def __repr__(self):
        return f"<Poll id={self.id}, name={self.name}, link={self.link}, options={self.options}, active={self.active}'>"


class Giveaway(Base):
    __tablename__ = "giveaway"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    win_count = Column(Integer)
    ongoing = Column(Boolean, default=True)
    entries = relationship(
        "Entry", back_populates="giveaway_ref", cascade="all, delete, delete-orphan"
    )
    roles = relationship(
        "GiveawayRole",
        back_populates="giveaway_ref",
        cascade="all, delete, delete-orphan",
    )

    def __repr__(self):
        return f"<Giveaway id={self.id}, name={self.name}, win_count={self.win_count}, ongoing={self.ongoing}>"


class GiveawayRole(Base):
    __tablename__ = "giveaway_roles"
    id = Column(Integer, primary_key=True)
    giveaway = Column(Integer, ForeignKey("giveaway.id"), primary_key=True)
    giveaway_ref = relationship("Giveaway", back_populates="roles")

    def __repr__(self):
        return f"<GiveawayRole id={self.id}, giveaway={self.giveaway}>"


class Entry(Base):
    __tablename__ = "entries"
    id = Column(Integer, primary_key=True)
    giveaway = Column(Integer, ForeignKey("giveaway.id"), primary_key=True)
    winner = Column(Boolean, default=False)
    giveaway_ref = relationship("Giveaway", back_populates="entries")

    def __repr__(self):
        return f"<GiveawayEntry id={self.id}, giveaway={self.giveaway}, winner={self.winner}>"
